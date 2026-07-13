"""AttendanceSession ORM model.

Represents a single attendance-taking window opened by a teacher. Students
check in against the `session_code` while it is active and not expired.
Actual check-in verification logic (OCR / AI) is intentionally not
implemented yet and will be layered on top of this model later.
"""
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class AttendanceSession(Base):
    __tablename__ = "attendance_sessions"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    session_code: Mapped[str] = mapped_column(String(20), unique=True, index=True, nullable=False)
    teacher_id: Mapped[int] = mapped_column(ForeignKey("teachers.id", ondelete="CASCADE"), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    teacher: Mapped["Teacher"] = relationship(back_populates="attendance_sessions")
    attendance_records: Mapped[list["Attendance"]] = relationship(
        back_populates="session", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<AttendanceSession id={self.id} session_code={self.session_code!r}>"
