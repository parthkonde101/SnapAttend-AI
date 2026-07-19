"""PanelCourse ORM model (Milestone 8B — Panel Management).

Many-to-many join between `Panel` and `Course` — "each panel contains
Assigned Courses," per the milestone spec's Part 4. A row here means "this
panel's students study this course," which drives two things:

  1. The panel's "Courses" tab in the admin Panel detail page.
  2. Which panels a teacher sees after selecting a course when starting an
     attendance session (`AttendanceSessionService.start_session`'s new
     panel-compatibility check, and the panels-filtered-by-course listing
     in `GET /panels?course_id=`) — "Only compatible panels appear."

Same shape as `TeacherCourse` (see that model's docstring): a plain join
table with a `UniqueConstraint` backstop against duplicate assignment,
managed exclusively by an Administrator via `AdminPanelService`.
"""
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class PanelCourse(Base):
    __tablename__ = "panel_courses"
    __table_args__ = (UniqueConstraint("panel_id", "course_id", name="uq_panel_course"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    panel_id: Mapped[int] = mapped_column(ForeignKey("panels.id", ondelete="CASCADE"), nullable=False, index=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id", ondelete="CASCADE"), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<PanelCourse panel_id={self.panel_id} course_id={self.course_id}>"
