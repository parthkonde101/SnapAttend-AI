"""Teacher ORM model."""
from datetime import datetime

from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Teacher(Base):
    __tablename__ = "teachers"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    teacher_id: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    full_name: Mapped[str] = mapped_column(String(150), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # --- Administrator System (Milestone 7A) ---------------------------------
    # Nullable/additive: existing teacher rows predate this concept and
    # simply have no course on file until an administrator sets one. A
    # teacher is assumed to teach exactly one course in this system (no
    # separate course/enrollment table exists), so this single column is
    # both "the course shown in Teacher Management" and the value
    # `AdminSessionService` reads for a session's "Course" column (via
    # `session.teacher.course` — a session has no course field of its own).
    course: Mapped[str | None] = mapped_column(String(150), nullable=True)

    attendance_sessions: Mapped[list["AttendanceSession"]] = relationship(
        back_populates="teacher", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Teacher id={self.id} teacher_id={self.teacher_id!r}>"
