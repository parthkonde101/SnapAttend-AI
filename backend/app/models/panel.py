"""Panel ORM model (Milestone 8A — Panel System).

A Panel is a named cohort a student belongs to (e.g. "Panel A") and a
teacher targets when opening an attendance session — students only ever
see attendance sessions for their own panel (see
`AttendanceSessionService.get_active_session_for_student` and
`app/api/v1/endpoints/attendance.py`'s `/active-session`).

Deliberately a standalone table (not an enum/string column) so it gets the
same Admin CRUD treatment (Add/Edit/Delete Panel) as `Course` — see
`app/services/admin_panel_service.py`.
"""
from datetime import datetime

from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Panel(Base):
    __tablename__ = "panels"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    # Optional per the Academic Panels spec ("Academic year (if needed)") —
    # free-text (e.g. "2025-26") rather than a constrained type, since
    # institutions format this differently and nothing in this system
    # parses or compares it programmatically.
    academic_year: Mapped[str | None] = mapped_column(String(20), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Read-only — see Teacher.courses' docstring for the same rationale.
    courses: Mapped[list["Course"]] = relationship(secondary="panel_courses", back_populates="panels", viewonly=True)
    students: Mapped[list["Student"]] = relationship(back_populates="panel")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Panel id={self.id} name={self.name!r}>"
