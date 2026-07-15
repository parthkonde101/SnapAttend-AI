"""Administrator dashboard overview (Milestone 7A): the six summary cards
on `/admin/dashboard` — total students, total teachers, total sessions,
the current active session (if any), today's attendance, and a recent
activity feed.

Read-only and side-effect-free; every number here is a plain aggregate
query, nothing this module touches is written to.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.attendance import Attendance
from app.models.attendance_session import AttendanceSession
from app.models.student import Student
from app.models.teacher import Teacher
from app.schemas.attendance import ActiveSessionInfo
from app.schemas.admin import DashboardStats, RecentActivityItem
from app.services.attendance_session_service import AttendanceSessionService

_RECENT_ACTIVITY_LIMIT = 10


class AdminDashboardService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_stats(self) -> DashboardStats:
        session_service = AttendanceSessionService(self.db)
        session_service.expire_stale_sessions()

        total_students = int(self.db.scalar(select(func.count(Student.id))) or 0)
        total_teachers = int(self.db.scalar(select(func.count(Teacher.id))) or 0)
        total_sessions = int(self.db.scalar(select(func.count(AttendanceSession.id))) or 0)

        active = session_service.get_active_session()
        active_session: ActiveSessionInfo | None = None
        if active is not None:
            # Same computation as attendance.py's `_to_active_session_info`
            # (teacher view, marker included) — duplicated rather than
            # imported, matching the precedent already set in
            # AttendanceReviewService for this exact value (see that
            # module's `build_session_review` docstring): that helper is
            # endpoint-local, not a shared service method.
            now = datetime.now(timezone.utc)
            remaining = max(0, int((active.expires_at - now).total_seconds()))
            active_session = ActiveSessionInfo(
                session_id=active.id,
                session_code=active.session_code,
                marker=active.marker,
                created_at=active.created_at,
                expires_at=active.expires_at,
                duration_seconds=active.duration_seconds,
                remaining_seconds=remaining,
                present_count=session_service.get_present_count(active.id),
            )

        today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        today_present_count = int(
            self.db.scalar(
                select(func.count(Attendance.id)).where(
                    Attendance.status == "present", Attendance.marked_at >= today_start
                )
            )
            or 0
        )

        recent_rows = list(
            self.db.execute(
                select(Attendance, Student, AttendanceSession, Teacher)
                .join(Student, Attendance.student_id == Student.id)
                .join(AttendanceSession, Attendance.session_id == AttendanceSession.id)
                .join(Teacher, AttendanceSession.teacher_id == Teacher.id)
                .order_by(Attendance.marked_at.desc())
                .limit(_RECENT_ACTIVITY_LIMIT)
            )
        )
        recent_activity = [
            RecentActivityItem(
                student_name=student.full_name,
                student_prn=student.prn,
                course=teacher.course,
                teacher_name=teacher.full_name,
                status=attendance.status,  # type: ignore[arg-type]
                marked_at=attendance.marked_at,
            )
            for attendance, student, _session, teacher in recent_rows
        ]

        return DashboardStats(
            total_students=total_students,
            total_teachers=total_teachers,
            total_sessions=total_sessions,
            active_session=active_session,
            today_present_count=today_present_count,
            recent_activity=recent_activity,
        )
