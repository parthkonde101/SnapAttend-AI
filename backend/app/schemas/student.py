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
