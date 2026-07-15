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

    # --- Roster ----------------------------------------------------------------
    def build_session_review(self, session: AttendanceSession) -> SessionReviewResponse:
        """Every registered student, exactly once — present ones carry the
        full evidence trail behind their record; absent ones (including
        students who were never verified at all) carry defaults.

        Ordering (Milestone 6B — this is also the *live* view while the
        session is active, polled repeatedly as attendance arrives): a
        student who has an attendance row at all — present or overridden
        to absent — is sorted by that row's `marked_at`, ascending. A row's
        `marked_at` never changes after it's created (a status override
        only touches `status`/`overridden_*`, see `set_status` below), so
        this ordering is permanently stable for every row once it exists —
        new arrivals only ever get appended after the current last arrival,
        never inserted earlier or reshuffled. Students with no row at all
        sit in a second, separately-stable block after every arrival,
        ordered by name — they only ever leave that block by gaining a row
        (moving to the arrival-ordered block above), never by reordering
        within it.
        """
        students = list(self.db.scalars(select(Student).order_by(Student.full_name.asc())))

        attendance_rows = list(self.db.scalars(select(Attendance).where(Attendance.session_id == session.id)))
        by_student_id = {row.student_id: row for row in attendance_rows}

        def sort_key(student: Student) -> tuple[int, object]:
            row = by_student_id.get(student.id)
            if row is not None:
                return (0, row.marked_at)
            return (1, student.full_name)

        ordered_students = sorted(students, key=sort_key)

        items: list[StudentAttendanceReviewItem] = []
        present_count = 0
        for student in ordered_students:
            row = by_student_id.get(student.id)
            if row is None:
                items.append(
                    StudentAttendanceReviewItem(
                        student_id=student.id,
                        prn=student.prn,
                        full_name=student.full_name,
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
