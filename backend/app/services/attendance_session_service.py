"""Attendance session lifecycle: starting, ending, and querying sessions.

Relocated here from `app/api/v1/endpoints/attendance.py` (which previously
had this logic inline) so the endpoint stays a thin request/response
translator, per the spec's "avoid placing business logic directly inside
API routes." Behavior for the pre-existing session engine
(`/start-session`, `/active-session`, `/end-session`, `/session-history`)
is preserved exactly — only the marker and teacher-selectable duration are
new.

Raises plain Python exceptions (`ValueError`, `LookupError`, `RuntimeError`)
rather than `HTTPException` — this layer has no FastAPI/HTTP dependency;
the endpoint translates these into the right status codes.
"""
from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.ai.attendance_config import MARKER_ALPHABET
from app.models.attendance import Attendance
from app.models.attendance_session import DEFAULT_SESSION_DURATION_SECONDS, AttendanceSession
from app.models.panel_course import PanelCourse
from app.models.student import Student
from app.models.teacher import Teacher
from app.models.teacher_course import TeacherCourse
from app.services.device_lock_service import DeviceLockService

# Characters chosen to avoid visual ambiguity on a projected classroom
# display (e.g. no 0/O, 1/I/L) — unchanged from the pre-existing session
# engine. `session_code` itself is legacy (predates the marker) and is not
# read by the new verification flow, but is kept for backward compatibility.
_SESSION_CODE_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ234679"
_SESSION_CODE_LENGTH = 3
_SESSION_CODE_MAX_ATTEMPTS = 25

# Teacher-selectable durations, per the Attendance Verification Engine V1
# spec: 1 / 2 / 3 / 5 minutes, default 2.
ALLOWED_SESSION_DURATIONS_SECONDS: frozenset[int] = frozenset({60, 120, 180, 300})


class AttendanceSessionService:
    def __init__(self, db: Session) -> None:
        self.db = db

    # --- Queries -----------------------------------------------------------
    def expire_stale_sessions(self) -> None:
        """Flip any active session whose expiry has passed to inactive.

        There is no background scheduler in this milestone, so expiry is
        applied lazily whenever a session-engine method runs. Combined with
        client-side polling this keeps state accurate without a
        long-running worker process. Unchanged from the pre-existing
        session engine.

        Milestone 6C addition: a session going inactive — by any path,
        including this lazy natural-expiry one, not just an explicit
        "End Session" click — is exactly when its temporary device locks
        (see `app/services/device_lock_service.py`) must disappear. Nothing
        about a device/student pairing should ever outlive the session it
        was created in.
        """
        now = datetime.now(timezone.utc)
        stmt = select(AttendanceSession).where(
            AttendanceSession.is_active.is_(True), AttendanceSession.expires_at <= now
        )
        stale_sessions = list(self.db.scalars(stmt))
        for stale_session in stale_sessions:
            stale_session.is_active = False
        self.db.commit()

        device_lock_service = DeviceLockService(self.db)
        for stale_session in stale_sessions:
            device_lock_service.clear_locks_for_session(session_id=stale_session.id)

    def get_active_session(self) -> AttendanceSession | None:
        return self.db.scalar(select(AttendanceSession).where(AttendanceSession.is_active.is_(True)))

    def get_present_count(self, session_id: int) -> int:
        # Filtered to status='present' since the teacher-review milestone:
        # a row can now exist for a student who was later overridden to
        # 'absent' (see app/services/attendance_review_service.py) without
        # being deleted, so "a row exists" is no longer the same claim as
        # "currently present." A count of every row regardless of status
        # would over-count anyone a teacher has overridden to absent.
        stmt = select(func.count(Attendance.id)).where(
            Attendance.session_id == session_id, Attendance.status == "present"
        )
        return int(self.db.scalar(stmt) or 0)

    def get_total_registered_students(self) -> int:
        return int(self.db.scalar(select(func.count(Student.id))) or 0)

    def get_total_panel_students(self, panel_id: int) -> int:
        return int(self.db.scalar(select(func.count(Student.id)).where(Student.panel_id == panel_id)) or 0)

    # --- Session Creation Workflow (Course -> Panel -> Session) -------------
    def _assert_teacher_owns_course(self, teacher: Teacher, course_id: int) -> None:
        link = self.db.scalar(
            select(TeacherCourse).where(TeacherCourse.teacher_id == teacher.id, TeacherCourse.course_id == course_id)
        )
        if link is None:
            raise ValueError("You are not assigned to this course. Select one of your assigned courses.")

    def _assert_panel_assigned_to_course(self, panel_id: int, course_id: int) -> None:
        link = self.db.scalar(
            select(PanelCourse).where(PanelCourse.panel_id == panel_id, PanelCourse.course_id == course_id)
        )
        if link is None:
            raise ValueError("This panel is not assigned to the selected course.")

    # --- Lifecycle ---------------------------------------------------------
    def start_session(
        self,
        teacher: Teacher,
        *,
        course_id: int,
        panel_id: int,
        duration_seconds: int | None = None,
    ) -> AttendanceSession:
        """Start a new attendance session, terminating any currently active
        one first (only one may be active system-wide). Generates both the
        legacy `session_code` and the new verification `marker`.

        `course_id`/`panel_id` are mandatory per the "Extending the
        attendance system" spec's Session Creation Workflow: Step 1 select
        a Course the teacher is actually assigned to (`TeacherCourse`),
        Step 2 select a Panel assigned to that course (`PanelCourse`) — both
        validated here, not just filtered client-side, so a teacher can
        never start a session for a course/panel combination they weren't
        actually offered. The session then permanently stores both, which
        is what makes attendance restriction (see
        `AttendanceVerificationService.verify_and_record`) and cross-session
        reporting (see `AttendanceReportService`) possible.
        """
        self.expire_stale_sessions()

        self._assert_teacher_owns_course(teacher, course_id)
        self._assert_panel_assigned_to_course(panel_id, course_id)

        previous = self.get_active_session()
        previous_id = previous.id if previous is not None else None
        if previous is not None:
            previous.is_active = False
            self.db.flush()

        duration = duration_seconds if duration_seconds is not None else DEFAULT_SESSION_DURATION_SECONDS
        if duration not in ALLOWED_SESSION_DURATIONS_SECONDS:
            allowed = ", ".join(str(s) for s in sorted(ALLOWED_SESSION_DURATIONS_SECONDS))
            raise ValueError(f"Invalid session duration. Choose one of: {allowed} seconds.")

        code = self._generate_unique_session_code()
        marker = secrets.choice(MARKER_ALPHABET)

        now = datetime.now(timezone.utc)
        session = AttendanceSession(
            session_code=code,
            marker=marker,
            teacher_id=teacher.id,
            course_id=course_id,
            panel_id=panel_id,
            duration_seconds=duration,
            expires_at=now + timedelta(seconds=duration),
            is_active=True,
        )
        self.db.add(session)
        self.db.commit()
        self.db.refresh(session)

        # The previous session (if any) was just superseded — that's an
        # "end" for its temporary device locks too, per the same
        # Milestone 6C rule as an explicit End Session / natural expiry.
        if previous_id is not None:
            DeviceLockService(self.db).clear_locks_for_session(session_id=previous_id)

        return session

    def end_session(self, teacher: Teacher) -> AttendanceSession:
        self.expire_stale_sessions()

        session = self.get_active_session()
        if session is None or session.teacher_id != teacher.id:
            raise LookupError("No active attendance session found")

        session.is_active = False
        self.db.commit()
        self.db.refresh(session)

        # Milestone 6C: "When the teacher ends the attendance session,
        # remove every temporary device lock for that session." — the next
        # session always starts with zero locked devices.
        DeviceLockService(self.db).clear_locks_for_session(session_id=session.id)

        return session

    def _generate_unique_session_code(self) -> str:
        for _ in range(_SESSION_CODE_MAX_ATTEMPTS):
            candidate = "".join(secrets.choice(_SESSION_CODE_ALPHABET) for _ in range(_SESSION_CODE_LENGTH))
            clash = self.db.scalar(
                select(AttendanceSession).where(
                    AttendanceSession.session_code == candidate, AttendanceSession.is_active.is_(True)
                )
            )
            if clash is None:
                return candidate
        # pragma: no cover - astronomically unlikely with 27^3 combinations
        raise RuntimeError("Could not generate a unique session code. Please try again.")
