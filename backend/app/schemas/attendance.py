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
    """Live view of the single system-wide active session."""

    session_id: int
    session_code: str
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
    created_at: datetime
    expires_at: datetime
    duration_seconds: int
    status: Literal["active", "ended"]
    present_count: int = Field(..., ge=0)
