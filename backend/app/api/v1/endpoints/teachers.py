"""Teacher resource endpoints."""
from fastapi import APIRouter, Depends

from app.api.deps import get_current_teacher
from app.models.teacher import Teacher
from app.schemas.teacher import TeacherRead

router = APIRouter()


@router.get("/me", response_model=TeacherRead)
def read_current_teacher(current_teacher: Teacher = Depends(get_current_teacher)) -> Teacher:
    """Return the profile of the currently authenticated teacher."""
    return current_teacher
