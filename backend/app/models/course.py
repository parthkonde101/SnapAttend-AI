"""Course ORM model (Milestone 8A — Course Normalization).

Replaces the old assumption that "a teacher teaches exactly one course"
(`Teacher.course`, a free-text string) with a real `Course` entity plus a
many-to-many `TeacherCourse` join table (see `app/models/teacher_course.py`)
— a teacher may now be assigned any number of courses, and a course may
have any number of teachers.

`Teacher.course` itself is left in place (deprecated, not dropped) — see
migration 0008_courses's module docstring for exactly how existing values
are backfilled into `Course` rows before this table is treated as the
source of truth.
"""
from datetime import datetime

from sqlalchemy import Boolean, DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Course(Base):
    __tablename__ = "courses"

    # No `index=True` here — the primary key constraint already provides
    # Postgres's own implicit unique index (see migration 0006/0007's
    # documented lesson on redundant/duplicate indexes).
    id: Mapped[int] = mapped_column(primary_key=True)
    course_code: Mapped[str | None] = mapped_column(
        String(50),
        unique=True,
        nullable=True,
        doc="Nullable: legacy courses backfilled from Teacher.course get an "
        "auto-generated placeholder code (see 0008_courses); an admin can "
        "correct it later. Every newly-created course requires a real one "
        "at the API layer (CourseCreateRequest).",
    )
    course_name: Mapped[str] = mapped_column(String(150), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # --- Course Management refinement (Milestone 8B) ------------------------
    # "Archive Course" per the milestone spec: a soft-delete flag, not a row
    # deletion — an archived course keeps every TeacherCourse/PanelCourse
    # assignment and every historical AttendanceSession.course_id reference
    # intact, it simply drops out of the *pickers* a teacher/admin sees when
    # assigning something new (see AdminCourseService.list_courses' `
    # include_archived` parameter). This is additive and defaults to
    # `False`, so every course created before this migration keeps behaving
    # exactly as it always has.
    is_archived: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")

    # Both read-only — see Teacher.courses' docstring for why. All writes go
    # through explicit TeacherCourse/PanelCourse row creation.
    teachers: Mapped[list["Teacher"]] = relationship(
        secondary="teacher_courses", back_populates="courses", viewonly=True
    )
    panels: Mapped[list["Panel"]] = relationship(secondary="panel_courses", back_populates="courses", viewonly=True)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Course id={self.id} course_code={self.course_code!r} course_name={self.course_name!r} is_archived={self.is_archived!r}>"
