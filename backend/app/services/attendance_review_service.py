"""Teacher review of a session's attendance: the full roster (present +
absent), the evidence behind every present record, manual Present/Absent
overrides, and access to the original captured photo.

Deliberately a separate service from `AttendanceVerificationService` —
that one turns a freshly captured *scene* into a pass/fail decision via the
AI pipeline; this one has no AI pipeline involvement at all. It only reads
and updates rows that already exist (or creates a bare manual-override row
when a teacher marks an absent student present), scoped to a teacher's own
session. Keeping them separate means neither module's docstring has to
explain the other's concern, and the AI-verification decision logic in
`attendance_verification_service.py` — the part of this milestone under
the most scrutiny — stays exactly as focused as before.

Non-destructive by design, per this milestone's explicit requirement: a
Present/Absent override never deletes an existing row's AI evidence
(photo reference, detected character, confidence, evidence tier) — it only
flips `status` and stamps the `overridden_*` audit columns. A student who
never attempted (or never succeeded) gets a fresh row on their first
override, since "absent, no attempt" and "no row at all" are otherwise
indistinguishable to a teacher scanning the review page.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.sorting import roll_number_sort_key
from app.models.attendance import Attendance
from app.models.attendance_session import AttendanceSession
from app.models.student import Student
from app.models.teacher import Teacher
from app.schemas.attendance import SessionReviewResponse, StudentAttendanceReviewItem


class AttendanceReviewService:
    def __init__(self, db: Session) -> None:
        self.db = db

    # --- Ownership -----------------------------------------------------------
    def get_session_for_teacher(self, session_id: int, teacher: Teacher) -> AttendanceSession:
        """Look up a session, raising LookupError (translated to a 404 by
        the endpoint) unless it belongs to the requesting teacher — the
        same ownership check `get_session_records` already applies, reused
        here so a teacher can never review or override another teacher's
        session by guessing an id."""
        session = self.db.get(AttendanceSession, session_id)
        if session is None or session.teacher_id != teacher.id:
            raise LookupError("Attendance session not found")
        return session

    def get_session_for_admin(self, session_id: int) -> AttendanceSession:
        """Milestone 7A — Administrator System: the same lookup as
        `get_session_for_teacher`, but deliberately with no ownership
        check at all — an Administrator has unrestricted access and is not
        scoped to any one teacher's sessions. Kept as its own method
        (rather than making the check in `get_session_for_teacher`
        conditional) so that method's existing behavior and call sites
        stay completely untouched; this is purely additive, used only by
        `app/services/admin_session_service.py` and the `/admin/sessions/*`
        endpoints — the teacher-facing review page still goes through
        `get_session_for_teacher` exactly as before."""
        session = self.db.get(AttendanceSession, session_id)
        if session is None:
            raise LookupError("Attendance session not found")
        return session

    # --- Roster ----------------------------------------------------------------
    def build_session_review(self, session: AttendanceSession) -> SessionReviewResponse:
        """Every registered student, exactly once — present ones carry the
        full evidence trail behind their record; absent ones (including
        students who were never verified at all) carry defaults.

        Ordering (spec Part 11 — Student Ordering): by Roll Number
        ascending, numeric-aware, matching the official classroom
        attendance register — this applies regardless of present/absent
        status or arrival order. This supersedes this page's earlier
        "arrival order, then name" behavior (Milestone 6B) now that the
        spec explicitly requires roll-number ordering for "session
        details" and "live attendance monitoring" — a teacher scanning
        this list during a live session should see the same order as a
        physical roll-call sheet, not whoever happened to check in first.
        """
        # Roster scoped to the session's panel, per the spec's "Attendance
        # valid only for students belonging to that panel" — a session with
        # no panel (predates this migration) falls back to every student,
        # preserving historical review pages exactly as they were.
        roster_stmt = select(Student)
        if session.panel_id is not None:
            roster_stmt = roster_stmt.where(Student.panel_id == session.panel_id)
        students = list(self.db.scalars(roster_stmt))
        students.sort(key=lambda s: roll_number_sort_key(s.roll_number))

        attendance_rows = list(self.db.scalars(select(Attendance).where(Attendance.session_id == session.id)))
        by_student_id = {row.student_id: row for row in attendance_rows}

        items: list[StudentAttendanceReviewItem] = []
        present_count = 0
        for student in students:
            row = by_student_id.get(student.id)
            if row is None:
                items.append(
                    StudentAttendanceReviewItem(
                        student_id=student.id,
                        prn=student.prn,
                        full_name=student.full_name,
                        roll_number=student.roll_number,
                        status="absent",
                    )
                )
                continue

            if row.status == "present":
                present_count += 1

            items.append(
                StudentAttendanceReviewItem(
                    student_id=student.id,
                    prn=student.prn,
                    full_name=student.full_name,
                    roll_number=student.roll_number,
                    status=row.status,  # type: ignore[arg-type]
                    verification_source=row.verification_source,  # type: ignore[arg-type]
                    marked_at=row.marked_at,
                    marker_detected_character=row.marker_detected_character,
                    marker_confidence=row.marker_confidence,
                    display_detected=row.display_detected,
                    display_confidence=row.display_confidence,
                    marker_verification_mode=row.marker_verification_mode,  # type: ignore[arg-type]
                    is_teacher_override=row.is_teacher_override,
                    overridden_at=row.overridden_at,
                    has_photo=row.image_reference is not None,
                )
            )

        # Same computation as _to_active_session_info (app/api/v1/endpoints/attendance.py)
        # for the presentation screen's countdown — duplicated rather than
        # imported/shared since that helper is endpoint-local, not a
        # service method; kept here so this response is self-contained for
        # the live countdown on the review page.
        remaining_seconds = max(0, int((session.expires_at - datetime.now(timezone.utc)).total_seconds()))

        return SessionReviewResponse(
            session_id=session.id,
            marker=session.marker,
            course=session.course.course_name if session.course else None,
            panel=session.panel.name if session.panel else None,
            is_active=session.is_active,
            remaining_seconds=remaining_seconds,
            present_count=present_count,
            absent_count=len(students) - present_count,
            students=items,
        )

    # --- Override ----------------------------------------------------------------
    def set_status(
        self, *, session: AttendanceSession, student_id: int, status: str, teacher: Teacher
    ) -> StudentAttendanceReviewItem:
        """Teacher override: set a student's effective status for this
        session, immediately. Updates the existing row in place if one
        exists (preserving any AI evidence it already carries — see this
        module's docstring); creates a bare manual row otherwise."""
        student = self.db.get(Student, student_id)
        if student is None:
            raise LookupError("Student not found")

        row = self.db.scalar(
            select(Attendance).where(Attendance.student_id == student_id, Attendance.session_id == session.id)
        )

        now = datetime.now(timezone.utc)
        if row is not None:
            row.status = status
            row.is_teacher_override = True
            row.overridden_by_teacher_id = teacher.id
            row.overridden_at = now
        else:
            row = Attendance(
                student_id=student_id,
                session_id=session.id,
                verification_source="teacher_override",
                marker=session.marker,
                status=status,
                marker_verification_mode="teacher_override",
                is_teacher_override=True,
                overridden_by_teacher_id=teacher.id,
                overridden_at=now,
            )
            self.db.add(row)

        try:
            self.db.commit()
        except IntegrityError:
            # A concurrent request already created the row between the
            # SELECT above and this commit — reload and retry once as an
            # update instead of an insert, same race-safety pattern as
            # AttendanceVerificationService.verify_and_record.
            self.db.rollback()
            row = self.db.scalar(
                select(Attendance).where(Attendance.student_id == student_id, Attendance.session_id == session.id)
            )
            if row is None:
                raise
            row.status = status
            row.is_teacher_override = True
            row.overridden_by_teacher_id = teacher.id
            row.overridden_at = now
            self.db.commit()

        self.db.refresh(row)

        return StudentAttendanceReviewItem(
            student_id=student.id,
            prn=student.prn,
            full_name=student.full_name,
            roll_number=student.roll_number,
            status=row.status,  # type: ignore[arg-type]
            verification_source=row.verification_source,  # type: ignore[arg-type]
            marked_at=row.marked_at,
            marker_detected_character=row.marker_detected_character,
            marker_confidence=row.marker_confidence,
            display_detected=row.display_detected,
            display_confidence=row.display_confidence,
            marker_verification_mode=row.marker_verification_mode,  # type: ignore[arg-type]
            is_teacher_override=row.is_teacher_override,
            overridden_at=row.overridden_at,
            has_photo=row.image_reference is not None,
        )

    def set_status_as_admin(self, *, session: AttendanceSession, student_id: int, status: str) -> StudentAttendanceReviewItem:
        """Administrator override (Milestone 7A): identical semantics to
        `set_status` above, except `overridden_by_teacher_id` is left NULL
        rather than attributed to a teacher — an Administrator is not a
        `Teacher` row, so there is no id to store there, and the column is
        nullable with `ondelete="SET NULL"` precisely to allow that. A new,
        parallel method rather than widening `set_status`'s signature to
        accept `Teacher | None`, so that method's existing behavior, tests,
        and call sites (the teacher review endpoint) are completely
        unaffected by this milestone. See `set_status`'s docstring for the
        non-destructive-override rationale, which applies identically here."""
        student = self.db.get(Student, student_id)
        if student is None:
            raise LookupError("Student not found")

        row = self.db.scalar(
            select(Attendance).where(Attendance.student_id == student_id, Attendance.session_id == session.id)
        )

        now = datetime.now(timezone.utc)
        if row is not None:
            row.status = status
            row.is_teacher_override = True
            row.overridden_by_teacher_id = None
            row.overridden_at = now
        else:
            row = Attendance(
                student_id=student_id,
                session_id=session.id,
                verification_source="teacher_override",
                marker=session.marker,
                status=status,
                marker_verification_mode="teacher_override",
                is_teacher_override=True,
                overridden_by_teacher_id=None,
                overridden_at=now,
            )
            self.db.add(row)

        try:
            self.db.commit()
        except IntegrityError:
            self.db.rollback()
            row = self.db.scalar(
                select(Attendance).where(Attendance.student_id == student_id, Attendance.session_id == session.id)
            )
            if row is None:
                raise
            row.status = status
            row.is_teacher_override = True
            row.overridden_by_teacher_id = None
            row.overridden_at = now
            self.db.commit()

        self.db.refresh(row)

        return StudentAttendanceReviewItem(
            student_id=student.id,
            prn=student.prn,
            full_name=student.full_name,
            roll_number=student.roll_number,
            status=row.status,  # type: ignore[arg-type]
            verification_source=row.verification_source,  # type: ignore[arg-type]
            marked_at=row.marked_at,
            marker_detected_character=row.marker_detected_character,
            marker_confidence=row.marker_confidence,
            display_detected=row.display_detected,
            display_confidence=row.display_confidence,
            marker_verification_mode=row.marker_verification_mode,  # type: ignore[arg-type]
            is_teacher_override=row.is_teacher_override,
            overridden_at=row.overridden_at,
            has_photo=row.image_reference is not None,
        )

    # --- Photo access --------------------------------------------------------
    def get_photo_path(self, *, session: AttendanceSession, student_id: int) -> Path:
        """Resolve the on-disk photo for one student's attendance row in
        this session. Scoped through `session` (already ownership-checked
        by `get_session_for_teacher`), so a teacher can only ever reach
        photos belonging to their own sessions — never an arbitrary
        image_reference. Raises LookupError (404) if there's no row, no
        photo on that row (e.g. a teacher-override row with no AI attempt
        behind it), or the file is missing from disk."""
        row = self.db.scalar(
            select(Attendance).where(Attendance.student_id == student_id, Attendance.session_id == session.id)
        )
        if row is None or not row.image_reference:
            raise LookupError("No photo available for this attendance record")

        path = Path(settings.UPLOAD_DIR) / f"{row.image_reference}.jpg"
        if not path.is_file():
            raise LookupError("Stored photo could not be found")
        return path
