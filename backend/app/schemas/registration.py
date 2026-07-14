"""API-facing schemas for the registration intelligence endpoints.

`RegistrationAnalysis` (the pipeline's output) lives in `app.ai.schemas`
and is re-exported here so callers can import everything registration-
related from one place; it is not redefined.
"""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.ai.schemas import RegistrationAnalysis

__all__ = ["RegistrationAnalysis", "RegistrationVerifyRequest", "RegistrationVerifyResponse"]


class RegistrationVerifyRequest(BaseModel):
    """Submitted once the student has reviewed/edited the extracted values."""

    prn: str = Field(..., min_length=1, max_length=50)
    student_name: str = Field(..., min_length=1, max_length=150)
    image_reference: str | None = Field(
        default=None, description="image_reference returned by POST /registration/analyze, if any."
    )


class RegistrationVerifyResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    verified_prn: str
    verified_name: str
    id_image_path: str | None
    verified_at: datetime
