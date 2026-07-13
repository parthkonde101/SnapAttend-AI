"""Attendance session / record request response schemas.

These schemas define the professional REST contract for attendance
sessions. The endpoints that consume them intentionally stop short of
implementing check-in verification logic (see app/api/v1/endpoints/attendance.py).
"""
from datetime import datetime

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
