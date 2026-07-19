"""Public panel listing (Milestone 8A — Panel System, extended in
Milestone 8B — Teacher Session course->panel filtering).

Deliberately unauthenticated — a panel's name carries no sensitive
information, so exposing the list without auth is safe — creating,
editing, or deleting one still requires an Administrator (see
`app/api/v1/endpoints/admin.py`).

There is no more student registration flow (a student never picks their
own panel — it's always admin/Excel-import supplied, see
`app/services/excel_import_service.py`), so this endpoint's consumer is
the teacher "Start Attendance" flow's panel picker. `course_id` is an
optional filter for exactly that: "Only compatible panels appear" once a
course is selected, via the `PanelCourse` join. Omitting `course_id`
returns every panel unfiltered, preserving this endpoint's original
behavior for any other caller.
"""
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.panel import Panel
from app.models.panel_course import PanelCourse
from app.schemas.panel import PanelRead

router = APIRouter()


@router.get("", response_model=list[PanelRead])
def list_panels(course_id: int | None = None, db: Session = Depends(get_db)) -> list[Panel]:
    """Every panel, alphabetical by name — or, if `course_id` is given,
    only the panels assigned that course (see `PanelCourse`). Powers the
    teacher "Start Attendance" panel picker, filtered to just the panels
    compatible with the course already selected."""
    stmt = select(Panel).order_by(Panel.name.asc())
    if course_id is not None:
        stmt = stmt.join(PanelCourse, PanelCourse.panel_id == Panel.id).where(PanelCourse.course_id == course_id)
    return list(db.scalars(stmt))
