"""TeacherCourse ORM model (Milestone 8A — Course Normalization).

Many-to-many join between `Teacher` and `Course`. A row here means "this
teacher is assigned to teach this course" — assignment/removal is an
Administrator-only action (see `app/services/admin_course_service.py`), the
same way `AdminTeacherService`/`AdminStudentService` are the only writers
of the accounts they manage.

`UniqueConstraint(teacher_id, course_id)` is the hard backstop against a
duplicate assignment, mirroring the exact pattern
`AttendanceDeviceLock` already uses for its own composite uniqueness.
"""
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class TeacherCourse(Base):
    __tablename__ = "teacher_courses"
    __table_args__ = (UniqueConstraint("teacher_id", "course_id", name="uq_teacher_course"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    teacher_id: Mapped[int] = mapped_column(ForeignKey("teachers.id", ondelete="CASCADE"), nullable=False, index=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id", ondelete="CASCADE"), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<TeacherCourse teacher_id={self.teacher_id} course_id={self.course_id}>"
