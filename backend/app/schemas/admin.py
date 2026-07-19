"""Administrator request/response schemas (Milestone 7A — Administrator
System).

Kept entirely separate from `app/schemas/teacher.py` / `app/schemas/student.py`
/ `app/schemas/attendance.py` even where the shape overlaps (e.g.
`TeacherAdminRead` vs `TeacherRead`) — the admin surface is intentionally
additive and independently evolvable, so nothing here changes the meaning
of an existing response a teacher- or student-facing client already
depends on.
"""
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.attendance import ActiveSessionInfo
from app.schemas.course import CourseRead
from app.schemas.panel import PanelRead

# --- Shared -----------------------------------------------------------------


class SimpleSuccessResponse(BaseModel):
    """Minimal body for admin actions that don't return a resource (reset
    password, delete) — mirrors the existing `PhotoUploadResponse`'s
    `{"success": bool}` minimalism elsewhere in this codebase."""

    success: bool = True


# --- Auth ----------------------------------------------------------------


class AdminLogin(BaseModel):
    login_id: str = Field(..., min_length=1, max_length=50)
    password: str = Field(..., min_length=1, max_length=128)


class AdminRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    login_id: str
    full_name: str
    created_at: datetime


# --- Dashboard -------------------------------------------------------------


class RecentActivityItem(BaseModel):
    """One row in the dashboard's "Recent Activity" feed — the most recent
    attendance check-ins system-wide, newest first. Deliberately minimal
    (no AI/verification evidence): this is an at-a-glance overview, not a
    review surface — an admin who wants the full evidence trail for a
    session already has "Review" on the Attendance Sessions page."""

    student_name: str
    student_prn: str
    course: str | None
    panel: str | None = None
    teacher_name: str
    status: Literal["present", "absent"]
    marked_at: datetime


class DashboardStats(BaseModel):
    """Response for GET /admin/dashboard/stats."""

    total_students: int
    total_teachers: int
    total_sessions: int
    active_session: ActiveSessionInfo | None = Field(
        default=None, description="The single system-wide active session, if any. Reuses the existing schema."
    )
    today_present_count: int = Field(..., description="Attendance rows with status='present' marked today (server-local date, UTC).")
    recent_activity: list[RecentActivityItem]


# --- Teacher management ----------------------------------------------------


class TeacherAdminRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    teacher_id: str
    full_name: str
    course: str | None = Field(default=None, description="Deprecated free-text field. See `courses` below.")
    courses: list[CourseRead] = Field(
        default_factory=list, description="Courses assigned via TeacherCourse — the source of truth going forward."
    )
    created_at: datetime
    session_count: int = Field(..., description="How many attendance sessions this teacher has ever started.")


class TeacherCreateRequest(BaseModel):
    full_name: str = Field(..., min_length=1, max_length=150)
    teacher_id: str = Field(..., min_length=1, max_length=50, description="Login ID.")
    course: str | None = Field(default=None, max_length=150, description="Deprecated. Use course_ids.")
    course_ids: list[int] = Field(default_factory=list, description="Courses to assign on creation.")
    password: str = Field(..., min_length=8, max_length=128)


class TeacherUpdateRequest(BaseModel):
    """All fields optional — an edit only ever changes what the admin
    actually touched. Password is deliberately excluded; that's the
    separate Reset Password action below, matching the milestone's
    distinct "Edit" vs "Reset Password" row actions. `course_ids`, when
    provided, replaces the teacher's entire assigned-course set in one call
    (not a partial add/remove) — matching how every other admin edit form
    in this codebase submits its full current state."""

    full_name: str | None = Field(default=None, min_length=1, max_length=150)
    teacher_id: str | None = Field(default=None, min_length=1, max_length=50)
    course: str | None = Field(default=None, max_length=150)
    course_ids: list[int] | None = Field(default=None, description="If provided, replaces assigned courses.")


class AdminPasswordResetRequest(BaseModel):
    """Shared body for the admin-initiated "Reset Password" action on
    either a teacher or a student — same validation rule as every other
    password field in this system (StudentRegister, PasswordResetCompleteRequest)."""

    new_password: str = Field(..., min_length=8, max_length=128)


class TeacherDeleteBlockedResponse(BaseModel):
    """Body of the 409 response when a teacher can't be deleted because
    they own historical attendance sessions — see this milestone's
    explicit "Do NOT allow deleting a teacher who owns historical
    attendance sessions" rule."""

    detail: str
    session_count: int


# --- Student management -----------------------------------------------------


class StudentAdminRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    prn: str
    full_name: str
    division: str | None
    created_at: datetime
    attendance_percentage: float = Field(..., ge=0, le=100)
    panel: PanelRead | None = None
    roll_number: str | None = None
    batch: str | None = None
    is_active: bool = True
    password_changed: bool = Field(
        default=True, description="False means this account is still on the administrator-issued default password."
    )


class StudentUpdateRequest(BaseModel):
    full_name: str | None = Field(default=None, min_length=1, max_length=150)
    prn: str | None = Field(default=None, min_length=1, max_length=50)
    division: str | None = Field(default=None, max_length=50)
    panel_id: int | None = Field(default=None, description="Reassign this student to a different panel.")
    roll_number: str | None = Field(default=None, max_length=50)
    batch: str | None = Field(default=None, max_length=50)


class StudentCourseAttendance(BaseModel):
    """One course's slice of a student's attendance history. "Course" here
    is the teacher's course (see Teacher.course) — this system has no
    separate per-course enrollment table, so a course's total is every
    session any teacher of that course ever started, and "present" is
    counted against that total. See AdminStudentService for the exact
    computation and its documented assumption."""

    course: str
    present_count: int
    total_sessions: int
    percentage: float = Field(..., ge=0, le=100)


class StudentAttendanceHistoryItem(BaseModel):
    session_id: int
    course: str | None
    teacher_name: str
    date: datetime
    status: Literal["present", "absent"]
    marked_at: datetime | None
    verification_source: str


class StudentProfile(BaseModel):
    """Response for GET /admin/students/{id} — everything the Student
    Profile screen needs in one call."""

    student: StudentAdminRead
    verified_prn: str | None
    verified_name: str | None
    verified_at: datetime | None
    has_registration_photo: bool
    course_wise: list[StudentCourseAttendance]
    history: list[StudentAttendanceHistoryItem]


# --- Attendance session management ------------------------------------------


class AdminSessionListItem(BaseModel):
    """One row on the Attendance Session Management page — every session
    system-wide, not scoped to any one teacher (that scoping is exactly
    what distinguishes this from GET /attendance/session-history)."""

    session_id: int
    course: str | None
    panel: str | None = None
    teacher_id: int
    teacher_name: str
    date: datetime
    duration_seconds: int
    present_count: int
    status: Literal["active", "ended"]


class AdminSessionDeleteConfirmation(BaseModel):
    """Response for GET /admin/sessions/{id} — the exact facts the
    milestone requires be shown before permanent deletion is allowed:
    course, teacher, date, present count, photo count, attendance record
    count."""

    session_id: int
    course: str | None
    teacher_name: str
    date: datetime
    present_count: int
    photo_count: int
    attendance_record_count: int


class AdminSessionDeleteRequest(BaseModel):
    """Body for DELETE /admin/sessions/{id}. The milestone requires the
    admin to type the literal word DELETE before permanent deletion — kept
    as a request body field (not just a frontend-only gate) so the backend
    itself refuses to run the transaction without it, not just the UI."""

    confirmation: str = Field(..., description='Must be exactly "DELETE".')


# --- Attendance Filtering (spec Part 6) -------------------------------------


class AttendanceReportItem(BaseModel):
    """One row in the cross-session attendance report — GET
    /admin/attendance/report, filterable by course/panel/teacher/date/
    student. Every session permanently stores its teacher/course/panel, so
    this is a plain filtered join, not a recomputation."""

    session_id: int
    date: datetime
    course: str | None
    panel: str | None
    teacher_name: str
    student_id: int
    student_prn: str
    student_name: str
    student_roll_number: str | None = None
    status: Literal["present", "absent"]
    marked_at: datetime | None
