"""AttendanceSession ORM model.

Represents a single attendance-taking window opened by a teacher. Students
check in against the `session_code` while it is active and not expired.

`marker` (added for the Attendance Verification Engine, V1) is the single
A-Z0-9 character shown large on the teacher's projected session screen
(see `app/api/v1/endpoints/attendance.py`'s `/start-session` and
`/active-session`). It is what a student's capture is actually verified
against — never sent to students over the API (they must read it
optically off the projected display), only to the teacher who is
presenting it. `session_code` is unrelated and kept as-is; it predates the
marker and nothing in the new verification flow reads it.

Only one session may be active system-wide at any time. This is enforced
at the database level with a partial unique index on `is_active`
(see alembic revision 0002_attendance_session_engine) in addition to the
application-level termination logic in the `/attendance/start-session`
endpoint.
"""
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

# 2 minutes, per the Attendance Verification Engine V1 spec. Teachers may
# override with any of `app.services.attendance_session_service.ALLOWED_SESSION_DURATIONS_SECONDS`.
DEFAULT_SESSION_DURATION_SECONDS = 120


class AttendanceSession(Base):
    __tablename__ = "attendance_sessions"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    session_code: Mapped[str] = mapped_column(String(20), index=True, nullable=False)
    marker: Mapped[str] = mapped_column(
        String(1), nullable=False, server_default="A", doc="Single A-Z0-9 character shown on the projected display."
    )
    teacher_id: Mapped[int] = mapped_column(ForeignKey("teachers.id", ondelete="CASCADE"), nullable=False)
    duration_seconds: Mapped[int] = mapped_column(
        Integer, nullable=False, default=DEFAULT_SESSION_DURATION_SECONDS, server_default="90"
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    teacher: Mapped["Teacher"] = relationship(back_populates="attendance_sessions")
    attendance_records: Mapped[list["Attendance"]] = relationship(
        back_populates="session", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<AttendanceSession id={self.id} session_code={self.session_code!r}>"
