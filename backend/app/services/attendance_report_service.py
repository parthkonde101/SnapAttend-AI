"""Cross-session attendance reporting ("Extending the attendance system"
spec, Part 6 — Attendance Filtering).

Every attendance session permanently stores its teacher, course, and panel
(see `app/models/attendance_session.py`), so a filterable report across
every session is a single joined query, not a recomputation — this service
is intentionally thin.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.sorting import roll_number_sort_key
from app.models.attendance import Attendance
from app.models.attendance_session import AttendanceSession
from app.models.student import Student
from app.models.teacher import Teacher
from app.schemas.admin import AttendanceReportItem


class AttendanceReportService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def build_report(
        self,
        *,
        course_id: int | None = None,
        panel_id: int | None = None,
        teacher_id: int | None = None,
        student_id: int | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> list[AttendanceReportItem]:
        stmt = (
            select(Attendance, AttendanceSession, Student, Teacher)
            .join(AttendanceSession, Attendance.session_id == AttendanceSession.id)
            .join(Student, Attendance.student_id == Student.id)
            .join(Teacher, AttendanceSession.teacher_id == Teacher.id)
        )

        if course_id is not None:
            stmt = stmt.where(AttendanceSession.course_id == course_id)
        if panel_id is not None:
            stmt = stmt.where(AttendanceSession.panel_id == panel_id)
        if teacher_id is not None:
            stmt = stmt.where(AttendanceSession.teacher_id == teacher_id)
        if student_id is not None:
            stmt = stmt.where(Attendance.student_id == student_id)
        if date_from is not None:
            stmt = stmt.where(AttendanceSession.created_at >= date_from)
        if date_to is not None:
            stmt = stmt.where(AttendanceSession.created_at <= date_to)

        rows = list(self.db.execute(stmt))

        # Ordered by Roll Number ascending (spec Part 11 — Student
        # Ordering, "Attendance reports"), numeric-aware; session date
        # descending is the secondary key so a single student's multiple
        # records still read newest-first within their own block.
        rows.sort(key=lambda r: (roll_number_sort_key(r[2].roll_number), -r[1].created_at.timestamp()))

        return [
            AttendanceReportItem(
                session_id=session.id,
                date=session.created_at,
                course=session.course.course_name if session.course else teacher.course,
                panel=session.panel.name if session.panel else None,
                teacher_name=teacher.full_name,
                student_id=student.id,
                student_prn=student.prn,
                student_name=student.full_name,
                student_roll_number=student.roll_number,
                status=attendance.status,  # type: ignore[arg-type]
                marked_at=attendance.marked_at,
            )
            for attendance, session, student, teacher in rows
        ]
