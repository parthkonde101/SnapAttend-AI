"""Teacher request/response schemas."""
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class TeacherLogin(BaseModel):
    teacher_id: str = Field(..., min_length=1, max_length=50)
    password: str = Field(..., min_length=1, max_length=128)


class TeacherRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    teacher_id: str
    full_name: str
    created_at: datetime
