"""Student request/response schemas."""
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class StudentRegister(BaseModel):
    prn: str = Field(..., min_length=1, max_length=50, description="Unique permanent registration number")
    full_name: str = Field(..., min_length=1, max_length=150)
    password: str = Field(..., min_length=8, max_length=128)


class StudentLogin(BaseModel):
    prn: str = Field(..., min_length=1, max_length=50)
    password: str = Field(..., min_length=1, max_length=128)


class StudentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    prn: str
    full_name: str
    created_at: datetime
    password_changed: bool = Field(
        default=True,
        description="False forces the mandatory change-password screen — see POST /students/me/change-password.",
    )


# --- Student Password Reset (self-service) --------------------------------


class StudentChangePasswordRequest(BaseModel):
    """Body for POST /students/me/change-password. Requires the student's
    *current* password (whether that's the administrator-issued default or
    one they already chose) — this is a self-service change, not an admin
    reset, so proving knowledge of the current password is the identity
    check, exactly like every other authenticated password-change flow."""

    current_password: str = Field(..., min_length=1, max_length=128)
    new_password: str = Field(..., min_length=8, max_length=128)


# --- Student Import System (Excel roster upload) ---------------------------


class ImportRowError(BaseModel):
    row_number: int = Field(..., description="1-indexed spreadsheet row, including the header row.")
    message: str


class ExcelImportSummary(BaseModel):
    """Response for POST /admin/panels/{panel_id}/import — the exact four
    counts the spec requires: Imported / Updated / Skipped / Errors."""

    imported: int
    updated: int
    skipped: int
    errors: list[ImportRowError] = Field(default_factory=list)
