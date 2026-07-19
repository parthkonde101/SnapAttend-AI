"""Administrator management of Student accounts (Milestone 7A; extended by
"Extending the attendance system" spec Parts 3/4 — Student Import System +
Student Password Reset).

Search, profile (registration details + attendance summary + course-wise
breakdown + full history), edit, password reset, and a genuinely complete
delete — everything a row's deletion touches, including files on disk and
the in-memory diagnostics ring buffer, not just database rows.

`Attendance.student_id` and `AttendanceDeviceLock.student_id` both already
carry `ondelete="CASCADE"` (see `app/models/attendance.py`,
`app/models/attendance_device_lock.py` — neither touched by this
milestone), so a plain `db.delete(student)` already cascades those rows at
the database level with no code here needed for that part. What the
database *can't* clean up on its own — files on disk, and the ephemeral
diagnostics store — is handled explicitly below.
"""
from __future__ import annotations

from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import hash_password
from app.core.sorting import roll_number_sort_key
from app.diagnostics.attendance_store import attendance_diagnostics_store
from app.models.attendance import Attendance
from app.models.attendance_session import AttendanceSession
from app.models.course import Course
from app.models.student import Student
from app.models.teacher import Teacher
from app.schemas.admin import (
    StudentAdminRead,
    StudentAttendanceHistoryItem,
    StudentCourseAttendance,
    StudentProfile,
    StudentUpdateRequest,
)
from app.services.excel_import_service import DEFAULT_STUDENT_PASSWORD


class StudentPrnTakenError(Exception):
    """Raised when an edit would collide with another student's PRN."""


class AdminStudentService:
    def __init__(self, db: Session) -> None:
        self.db = db

    # --- Shared computations --------------------------------------------------
    def _total_session_count(self) -> int:
        return int(self.db.scalar(select(func.count(AttendanceSession.id))) or 0)

    def _present_count(self, student_id: int) -> int:
        return int(
            self.db.scalar(
                select(func.count(Attendance.id)).where(
                    Attendance.student_id == student_id, Attendance.status == "present"
                )
            )
            or 0
        )

    def _attendance_percentage(self, student_id: int, total_sessions: int) -> float:
        if total_sessions == 0:
            return 0.0
        return round(100.0 * self._present_count(student_id) / total_sessions, 1)

    def _to_read(self, student: Student, total_sessions: int) -> StudentAdminRead:
        return StudentAdminRead(
            id=student.id,
            prn=student.prn,
            full_name=student.full_name,
            division=student.division,
            created_at=student.created_at,
            attendance_percentage=self._attendance_percentage(student.id, total_sessions),
            panel=student.panel,  # type: ignore[arg-type]
            roll_number=student.roll_number,
            batch=student.batch,
            is_active=student.is_active,
            password_changed=student.password_changed,
        )

    # --- List / search -----------------------------------------------------
    def search_students(self, query: str | None = None, *, panel_id: int | None = None) -> list[StudentAdminRead]:
        """Search by PRN, name, roll number, or division — a single `query`
        string matched against all four (case-insensitive substring),
        extending the milestone's original "Search by: PRN, Name,
        Division" now that roll numbers exist. `panel_id` narrows the list
        to one panel — used by the panel detail page's Students tab.

        Ordered by Roll Number ascending (spec Part 11 — Student Ordering),
        numeric-aware via `roll_number_sort_key` — not a plain DB-level
        `ORDER BY`, since Postgres would sort the string column
        lexicographically ("10" before "2"). Student rosters are small
        enough that sorting in Python after the fetch is simplest and
        correct; this is the one place every "list of students" screen in
        the admin surface (Student Management, and Panel student lists via
        `panel_id`) ultimately goes through.
        """
        stmt = select(Student)
        if query:
            like = f"%{query.strip()}%"
            stmt = stmt.where(
                Student.prn.ilike(like)
                | Student.full_name.ilike(like)
                | Student.division.ilike(like)
                | Student.roll_number.ilike(like)
            )
        if panel_id is not None:
            stmt = stmt.where(Student.panel_id == panel_id)
        students = list(self.db.scalars(stmt))
        students.sort(key=lambda s: roll_number_sort_key(s.roll_number))
        total_sessions = self._total_session_count()
        return [self._to_read(s, total_sessions) for s in students]

    def get_student(self, student_id: int) -> Student:
        student = self.db.get(Student, student_id)
        if student is None:
            raise LookupError("Student not found")
        return student

    # --- Profile -------------------------------------------------------------
    def get_profile(self, student_id: int) -> StudentProfile:
        student = self.get_student(student_id)
        total_sessions = self._total_session_count()

        rows = list(
            self.db.execute(
                select(Attendance, AttendanceSession, Teacher)
                .join(AttendanceSession, Attendance.session_id == AttendanceSession.id)
                .join(Teacher, AttendanceSession.teacher_id == Teacher.id)
                .where(Attendance.student_id == student_id)
                .order_by(AttendanceSession.created_at.desc())
            )
        )

        history = [
            StudentAttendanceHistoryItem(
                session_id=session.id,
                course=session.course.course_name if session.course else teacher.course,
                teacher_name=teacher.full_name,
                date=session.created_at,
                status=attendance.status,  # type: ignore[arg-type]
                marked_at=attendance.marked_at,
                verification_source=attendance.verification_source,
            )
            for attendance, session, teacher in rows
        ]

        # Course-wise breakdown: prefers each session's own `course_id`
        # (Course entity) now that sessions carry one; falls back to the
        # teacher's deprecated free-text `course` for historical sessions
        # that predate this migration. A course's total is every session
        # system-wide that resolved to that course name, not just ones this
        # student attended — matching how overall attendance % is computed
        # above.
        course_id_to_name = {c.id: c.course_name for c in self.db.scalars(select(Course))}
        all_session_rows = list(
            self.db.execute(
                select(AttendanceSession.course_id, Teacher.course)
                .select_from(AttendanceSession)
                .join(Teacher, AttendanceSession.teacher_id == Teacher.id)
            )
        )
        course_totals: dict[str, int] = {}
        for course_id, legacy_course in all_session_rows:
            resolved = course_id_to_name.get(course_id) if course_id else legacy_course
            if resolved:
                course_totals[resolved] = course_totals.get(resolved, 0) + 1

        course_present: dict[str, int] = {}
        for item in history:
            if item.course and item.status == "present":
                course_present[item.course] = course_present.get(item.course, 0) + 1

        course_wise = [
            StudentCourseAttendance(
                course=course,
                present_count=course_present.get(course, 0),
                total_sessions=total,
                percentage=round(100.0 * course_present.get(course, 0) / total, 1) if total else 0.0,
            )
            for course, total in sorted(course_totals.items())
        ]

        return StudentProfile(
            student=self._to_read(student, total_sessions),
            verified_prn=student.verified_prn,
            verified_name=student.verified_name,
            verified_at=student.verified_at,
            has_registration_photo=bool(student.id_image_path),
            course_wise=course_wise,
            history=history,
        )

    def get_registration_photo_path(self, student_id: int) -> Path:
        student = self.get_student(student_id)
        if not student.id_image_path:
            raise LookupError("No registration photo available for this student")
        path = Path(student.id_image_path)
        if not path.is_file():
            raise LookupError("Stored registration photo could not be found")
        return path

    # --- Edit ------------------------------------------------------------------
    def update_student(self, student_id: int, payload: StudentUpdateRequest) -> StudentAdminRead:
        student = self.get_student(student_id)

        if payload.prn is not None and payload.prn != student.prn:
            clash = self.db.scalar(select(Student).where(Student.prn == payload.prn))
            if clash is not None:
                raise StudentPrnTakenError(payload.prn)
            student.prn = payload.prn

        if payload.full_name is not None:
            student.full_name = payload.full_name
        if payload.division is not None:
            student.division = payload.division
        if payload.panel_id is not None:
            student.panel_id = payload.panel_id
        if payload.roll_number is not None:
            student.roll_number = payload.roll_number
        if payload.batch is not None:
            student.batch = payload.batch

        self.db.add(student)
        self.db.commit()
        self.db.refresh(student)
        return self._to_read(student, self._total_session_count())

    def reset_to_default_password(self, student_id: int) -> None:
        """Admin "Reset Password" action (spec Part 4): resets to the
        administrator-issued default (`Test@123`, the same one Excel import
        uses) and re-arms the forced change-password flow — the student
        sees the mandatory Change Password screen again on next login. This
        is deliberately the *only* way a student's password gets reset:
        there is no way to choose an arbitrary password from the admin UI,
        and the password itself is never exposed anywhere — see this
        module's spec-derived rationale in the endpoint docstring."""
        student = self.get_student(student_id)
        student.password_hash = hash_password(DEFAULT_STUDENT_PASSWORD)
        student.password_changed = False
        self.db.add(student)
        self.db.commit()

    # --- Delete ------------------------------------------------------------------
    def delete_student(self, student_id: int) -> None:
        """Deletes the student and every dependent record.

        Order matters: gather every file path this student's row and
        attendance rows reference *before* the DB delete (once the rows
        are gone, `image_reference` values are gone with them), commit the
        DB transaction (letting the existing `ondelete="CASCADE"` foreign
        keys remove `Attendance` / `AttendanceDeviceLock` rows), then clean
        up files on disk and the in-memory diagnostics store. File/store
        cleanup is intentionally best-effort *after* a successful commit —
        those aren't part of the SQL transaction and can't be rolled back
        with it either way, so failing loudly on a missing/already-gone
        file would only turn a successful account deletion into a
        confusing partial error.
        """
        student = self.get_student(student_id)

        registration_photo = Path(student.id_image_path) if student.id_image_path else None
        attendance_photo_refs = list(
            self.db.scalars(
                select(Attendance.image_reference).where(
                    Attendance.student_id == student_id, Attendance.image_reference.is_not(None)
                )
            )
        )

        self.db.delete(student)
        self.db.commit()

        if registration_photo is not None:
            registration_photo.unlink(missing_ok=True)

        upload_dir = Path(settings.UPLOAD_DIR)
        for ref in attendance_photo_refs:
            (upload_dir / f"{ref}.jpg").unlink(missing_ok=True)

        attendance_diagnostics_store.purge(student_id=student_id)
