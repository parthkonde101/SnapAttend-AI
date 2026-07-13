"""Attendance ORM model.

Records that a given student was marked present for a given attendance
session. Creation of these records (the actual "marking" logic, including
any future OCR / AI verification) is intentionally not implemented yet.
"""
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Attendance(Base):
    __tablename__ = "attendance"
    __table_args__ = (
        UniqueConstraint("student_id", "session_id", name="uq_attendance_student_session"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id", ondelete="CASCADE"), nullable=False)
    session_id: Mapped[int] = mapped_column(
        ForeignKey("attendance_sessions.id", ondelete="CASCADE"), nullable=False
    )
    marked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    student: Mapped["Student"] = relationship(back_populates="attendance_records")
    session: Mapped["AttendanceSession"] = relationship(back_populates="attendance_records")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Attendance id={self.id} student_id={self.student_id} session_id={self.session_id}>"
