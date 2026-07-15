"""Temporary, session-scoped device lock (Milestone 6C — Production Security).

Goal: stop one phone from marking attendance for multiple student accounts
during the *same* attendance session, without ever permanently binding a
device to a student.

A row here means "this device already successfully marked attendance for
this student, in this session." It is created only once a student's
attendance has actually been recorded (see
`app/services/device_lock_service.py` and its call site in
`app/api/v1/endpoints/attendance.py`'s `/mark`) — never merely because a
student logged in or opened the camera. The unique constraint on
`(session_id, device_id)` is the hard backstop: a second row for the same
device in the same session is impossible, so "does a lock exist, and does
it belong to someone else" is a single indexed lookup.

Deliberately keyed by `session_id`, not permanent: every row for a session
is deleted the moment that session ends (naturally, via a teacher's
"End Session", or by being superseded when a new session starts) — see
`AttendanceSessionService`'s cleanup calls. The next session always begins
with zero locked devices. There is no table, column, or relationship
anywhere that remembers "this device belongs to this student" beyond a
single active session's lifetime.
"""
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class AttendanceDeviceLock(Base):
    __tablename__ = "attendance_device_locks"
    __table_args__ = (
        UniqueConstraint("session_id", "device_id", name="uq_device_lock_session_device"),
    )

    # Deliberately no `index=True` here: a primary key already carries its
    # own implicit unique index in Postgres, so `index=True` on `id` would
    # be redundant and — worse — would make a future `alembic revision
    # --autogenerate` reproduce the exact duplicate-index bug fixed in
    # migration 0006 (see that file's module docstring for the full
    # mechanics of why `create_table` + a same-named `create_index` for a
    # PK column collide).
    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(
        ForeignKey("attendance_sessions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    device_id: Mapped[str] = mapped_column(
        String(128), nullable=False, doc="Client-generated UUID, stored locally on the device. Never chosen by the server."
    )
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id", ondelete="CASCADE"), nullable=False)
    locked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<AttendanceDeviceLock session_id={self.session_id} device_id={self.device_id!r} student_id={self.student_id}>"
