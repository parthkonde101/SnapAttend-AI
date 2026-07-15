"""Attendance session / record request response schemas.

These schemas define the professional REST contract for attendance
sessions. The endpoints that consume them intentionally stop short of
implementing check-in verification logic (see app/api/v1/endpoints/attendance.py).
"""
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class AttendanceSessionCreate(BaseModel):
    duration_minutes: int = Field(15, ge=1, le=240, description="How long the session stays open for")


class AttendanceSessionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    session_code: str
    teacher_id: int
    expires_at: datetime
    is_active: bool
    created_at: datetime


class AttendanceRecordRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    student_id: int
    session_id: int
    marked_at: datetime


# --- Attendance Session Engine -------------------------------------------------
# Schemas backing the /start-session, /active-session, /end-session and
# /session-history endpoints. Kept separate from the schemas above so the
# original generic session CRUD contract is left untouched.


class ActiveSessionInfo(BaseModel):
    """Live view of the single system-wide active session.

    `marker` is deliberately `None` unless the caller is a teacher — see
    `app/api/v1/endpoints/attendance.py`'s `get_active_session`. Students
    must read the marker optically off the projected display; sending it
    to them over the API would let them mark attendance from anywhere,
    defeating the whole point of the marker-matching verification step.
    """

    session_id: int
    session_code: str
    marker: str | None = Field(default=None, description="Teacher-only. Never sent to students.")
    created_at: datetime
    expires_at: datetime
    duration_seconds: int
    remaining_seconds: int = Field(..., ge=0)
    present_count: int = Field(..., ge=0)


class ActiveSessionResponse(BaseModel):
    """Response for GET /attendance/active-session, shared by students and teachers."""

    active: bool
    session: ActiveSessionInfo | None = None


class SessionHistoryItem(BaseModel):
    model_config = ConfigDict(from_attributes=False)

    session_id: int
    session_code: str
    marker: str
    created_at: datetime
    expires_at: datetime
    duration_seconds: int
    status: Literal["active", "ended"]
    present_count: int = Field(..., ge=0)


# --- Smart Camera Capture -------------------------------------------------
# Response for POST /attendance/upload-photo. Field names intentionally
# match the exact contract requested for this milestone (camelCase
# `imageId`) rather than the snake_case used elsewhere in this file.


class PhotoUploadResponse(BaseModel):
    success: bool
    imageId: str


# --- Attendance Verification Engine (V1) --------------------------------------
# Schemas backing /start-session's new duration selection, marker
# visibility, /mark, and /session-records. Kept in this same file (not a
# new module) since these are still attendance-session/record concerns —
# just extending the existing contract, not replacing it.


class AttendanceSessionStartRequest(BaseModel):
    """Body for POST /attendance/start-session. Optional — omitting
    `duration_seconds` keeps the previous "just start a default session"
    behavior working unchanged."""

    duration_seconds: int | None = Field(
        default=None, description="One of 60, 120, 180, 300. Defaults to 120 (2 minutes) if omitted."
    )


class MarkAttendanceResponse(BaseModel):
    """Response for POST /attendance/mark."""

    success: bool = Field(..., description="True only for a brand-new, successful verification.")
    already_recorded: bool = Field(default=False, description="True if this student had already been marked present.")
    reason: str | None = Field(default=None, description="Human-readable explanation when success is False.")
    verification_source: Literal["barcode", "ocr", "teacher_override", "none"] = "none"
    marker_detected: str | None = None
    warnings: list[str] = Field(default_factory=list)
    diagnostics_attempt_id: str | None = Field(default=None, description="Development use.")


class AttendanceRecordDetail(BaseModel):
    """One row in the teacher's live attendance list."""

    student_id: int
    prn: str
    full_name: str
    marked_at: datetime
    verification_source: Literal["barcode", "ocr", "teacher_override", "none"] = "none"


class SessionRecordsResponse(BaseModel):
    """Response for GET /attendance/session-records/{session_id}."""

    session_id: int
    marker: str
    present_count: int
    remaining_count: int
    records: list[AttendanceRecordDetail]


# --- Teacher review + verification-philosophy refinement ----------------------
# Backs GET /attendance/session-review/{id} (full roster, present + absent,
# with the evidence behind every present record) and POST
# /attendance/session-review/{id}/override (the Present/Absent toggle). See
# app/services/attendance_review_service.py.


class StudentAttendanceReviewItem(BaseModel):
    """One student's row in the teacher review page — every registered
    student appears exactly once, whether or not they have an attendance
    record for this session."""

    student_id: int
    prn: str
    full_name: str
    status: Literal["present", "absent"]
    verification_source: Literal["barcode", "ocr", "teacher_override", "none"] = "none"
    marked_at: datetime | None = Field(default=None, description="When the underlying row was created, if any.")
    marker_detected_character: str | None = None
    marker_confidence: float | None = None
    display_detected: bool = False
    display_confidence: float = 0.0
    marker_verification_mode: Literal["exact_match", "display_evidence", "teacher_override"] | None = None
    is_teacher_override: bool = False
    overridden_at: datetime | None = None
    has_photo: bool = Field(default=False, description="Whether GET .../photo/{student_id} will return an image.")


class SessionReviewResponse(BaseModel):
    """Response for GET /attendance/session-review/{session_id}."""

    session_id: int
    marker: str
    is_active: bool = Field(
        default=False,
        description="Whether the session is still open. The Excel export (see attendance_export_service.py) is "
        "only available once this is false — the frontend uses this to gate the Export button without a "
        "second request.",
    )
    remaining_seconds: int = Field(
        default=0, description="Live session countdown, mirrors ActiveSessionInfo.remaining_seconds. 0 once ended."
    )
    present_count: int
    absent_count: int
    students: list[StudentAttendanceReviewItem]


class AttendanceOverrideRequest(BaseModel):
    """Body for POST /attendance/session-review/{session_id}/override."""

    student_id: int
    status: Literal["present", "absent"]
