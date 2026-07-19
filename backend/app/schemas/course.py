"""Course request/response schemas (Milestone 8A — Course Normalization).

`CourseRead` is the shared, minimal shape used everywhere a course needs to
be listed or referenced — a teacher's "assigned courses" list when
starting a session, a session's own course, and the admin Manage Courses
screen all read the exact same shape. Kept in its own file (not
`app/schemas/admin.py`) because it's read outside the admin surface too,
following the precedent of `app/schemas/attendance.py` holding shapes
shared by students, teachers, and admins alike rather than being split per
role.
"""
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class CourseRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    course_code: str | None
    course_name: str
    created_at: datetime
    is_archived: bool = Field(
        default=False, description="Milestone 8B — Course Management. Archived courses stay assigned/historical but drop out of pickers."
    )


class CourseCreateRequest(BaseModel):
    course_code: str = Field(..., min_length=1, max_length=50)
    course_name: str = Field(..., min_length=1, max_length=150)


class CourseUpdateRequest(BaseModel):
    """All fields optional — an edit only ever changes what the admin
    actually touched, matching TeacherUpdateRequest/StudentUpdateRequest's
    existing pattern. `is_archived` is set here too (not a separate
    endpoint) — same "PUT is the one mutation path" shape every other
    admin resource in this codebase already uses."""

    course_code: str | None = Field(default=None, min_length=1, max_length=50)
    course_name: str | None = Field(default=None, min_length=1, max_length=150)
    is_archived: bool | None = Field(default=None, description="Milestone 8B — Archive/unarchive this course.")


class TeacherCourseAssignRequest(BaseModel):
    """Body for POST /admin/teachers/{teacher_id}/courses — assign one
    existing course to one existing teacher."""

    course_id: int


class TeacherCourseRead(CourseRead):
    """A course as it appears in a teacher's own "assigned courses" list —
    identical shape to CourseRead, named separately so the teacher-facing
    endpoint's response model documents its intent (see
    GET /teachers/me/courses)."""
