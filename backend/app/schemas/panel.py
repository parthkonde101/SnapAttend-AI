"""Panel request/response schemas ("Extending the attendance system" spec,
Parts 2/7 — Academic Panels + Panel Management admin interface).

`PanelRead` is shared across the teacher "Start Attendance" flow (panel
selection), the student dashboard, and the admin Manage Panels screen —
same rationale as `app/schemas/course.py`'s `CourseRead` for living outside
`app/schemas/admin.py`.
"""
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.course import CourseRead


class PanelRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    academic_year: str | None = Field(default=None, description='Optional, e.g. "2025-26". Free text.')
    created_at: datetime


class PanelCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    academic_year: str | None = Field(default=None, max_length=20)


class PanelUpdateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    academic_year: str | None = Field(default=None, max_length=20)


# --- Panel Management ----------------------------------------------------


class PanelCourseAssignRequest(BaseModel):
    """Body for POST /admin/panels/{panel_id}/courses — assign one
    existing course to one existing panel. Mirrors
    `TeacherCourseAssignRequest` (`app/schemas/course.py`)."""

    course_id: int


class PanelOverview(BaseModel):
    """Response for GET /admin/panels/{panel_id} — everything the admin
    Panel detail page's Overview tab needs in one call: the panel itself,
    its assigned courses, and a headline roster count (the full roster
    itself is a separate call — see `StudentAdminRead`/
    `GET /admin/panels/{panel_id}/students`)."""

    panel: PanelRead
    courses: list[CourseRead]
    student_count: int
