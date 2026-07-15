"""Administrator management of attendance sessions (Milestone 7A) —
system-wide, not scoped to any one teacher.

The list/review/export/photo/override surfaces all reuse the *existing*
attendance review machinery (`AttendanceReviewService`,
`build_attendance_export`) exactly as teachers already do — see
`get_session_for_admin` / `set_status_as_admin`, the two small additive
methods on `AttendanceReviewService`. This module adds exactly one new
capability that has no teacher-facing equivalent at all: permanently
deleting a session and everything that belongs to it.
"""
from __future__ import annotations

from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.diagnostics.attendance_store import attendance_diagnostics_store
from app.models.attendance import Attendance
from app.models.attendance_session import AttendanceSession
from app.models.teacher import Teacher
from app.services.attendance_session_service import AttendanceSessionService
from app.schemas.admin import AdminSessionDeleteConfirmation, AdminSessionListItem


class InvalidDeleteConfirmationError(Exception):
    """Raised when the admin-typed confirmation text isn't exactly "DELETE"."""


class AdminSessionService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self._session_service = AttendanceSessionService(db)

    def list_sessions(self) -> list[AdminSessionListItem]:
        """Every attendance session system-wide, most recent first —
        unlike `GET /attendance/session-history`, which is scoped to the
        requesting teacher, an Administrator sees every teacher's
        sessions."""
        self._session_service.expire_stale_sessions()

        rows = list(
            self.db.execute(
                select(AttendanceSession, Teacher)
                .join(Teacher, AttendanceSession.teacher_id == Teacher.id)
                .order_by(AttendanceSession.created_at.desc())
            )
        )

        return [
            AdminSessionListItem(
                session_id=session.id,
                course=teacher.course,
                teacher_id=teacher.id,
                teacher_name=teacher.full_name,
                date=session.created_at,
                duration_seconds=session.duration_seconds,
                present_count=self._session_service.get_present_count(session.id),
                status="active" if session.is_active else "ended",
            )
            for session, teacher in rows
        ]

    def _get_session_and_teacher(self, session_id: int) -> tuple[AttendanceSession, Teacher]:
        session = self.db.get(AttendanceSession, session_id)
        if session is None:
            raise LookupError("Attendance session not found")
        teacher = self.db.get(Teacher, session.teacher_id)
        if teacher is None:
            # Should be unreachable (Teacher.attendance_sessions cascades
            # its own delete-orphan, and AdminTeacherService blocks
            # deleting a teacher with sessions) — guarded anyway rather
            # than letting a None propagate into the response schema.
            raise LookupError("Attendance session's teacher not found")
        return session, teacher

    def get_delete_confirmation(self, session_id: int) -> AdminSessionDeleteConfirmation:
        """Exactly the facts the milestone requires be shown before
        permanent deletion: course, teacher, date, present count, photo
        count, attendance record count."""
        session, teacher = self._get_session_and_teacher(session_id)

        attendance_rows = list(self.db.scalars(select(Attendance).where(Attendance.session_id == session_id)))
        present_count = sum(1 for row in attendance_rows if row.status == "present")
        photo_count = sum(1 for row in attendance_rows if row.image_reference)

        return AdminSessionDeleteConfirmation(
            session_id=session.id,
            course=teacher.course,
            teacher_name=teacher.full_name,
            date=session.created_at,
            present_count=present_count,
            photo_count=photo_count,
            attendance_record_count=len(attendance_rows),
        )

    def delete_session(self, session_id: int, *, confirmation: str) -> None:
        """Permanently removes the session and every child record:
        attendance records, teacher/admin overrides, verification
        metadata, attendance photos, device locks, and diagnostics.

        Requires the literal text "DELETE" — enforced here, not just in
        the frontend, so the backend itself refuses to run the destructive
        transaction without it.

        The actual row deletion is a single `DELETE FROM attendance_sessions
        WHERE id = ...` wrapped in one transaction: `Attendance.session_id`
        and `AttendanceDeviceLock.session_id` both carry
        `ondelete="CASCADE"` (see their models — neither touched by this
        milestone), so the database itself atomically removes every
        `Attendance` row (which is where teacher overrides and AI
        verification metadata both live — there's no separate table for
        either) and every `AttendanceDeviceLock` row for this session as
        part of that same statement. If anything raises, `db.rollback()`
        below undoes the entire transaction — the session row, and
        therefore every dependent row the database would otherwise have
        cascaded, all survive untouched. Photo files on disk and the
        in-memory diagnostics entries are cleaned up only *after* that
        transaction commits successfully, for the same reason documented
        in `AdminStudentService.delete_student`.
        """
        if confirmation != "DELETE":
            raise InvalidDeleteConfirmationError(confirmation)

        session = self.db.get(AttendanceSession, session_id)
        if session is None:
            raise LookupError("Attendance session not found")

        photo_refs = list(
            self.db.scalars(
                select(Attendance.image_reference).where(
                    Attendance.session_id == session_id, Attendance.image_reference.is_not(None)
                )
            )
        )

        try:
            self.db.delete(session)
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

        upload_dir = Path(settings.UPLOAD_DIR)
        for ref in photo_refs:
            (upload_dir / f"{ref}.jpg").unlink(missing_ok=True)

        attendance_diagnostics_store.purge(session_id=session_id)
