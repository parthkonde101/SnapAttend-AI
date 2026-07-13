"""Student resource endpoints."""
from fastapi import APIRouter, Depends

from app.api.deps import get_current_student
from app.models.student import Student
from app.schemas.student import StudentRead

router = APIRouter()


@router.get("/me", response_model=StudentRead)
def read_current_student(current_student: Student = Depends(get_current_student)) -> Student:
    """Return the profile of the currently authenticated student."""
    return current_student
