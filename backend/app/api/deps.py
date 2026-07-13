"""Reusable FastAPI dependencies: DB session access and JWT-based auth guards."""
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import decode_access_token
from app.models.student import Student
from app.models.teacher import Teacher

student_oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/v1/auth/student/login", auto_error=False)
teacher_oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/v1/auth/teacher/login", auto_error=False)

CREDENTIALS_EXCEPTION = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Could not validate credentials",
    headers={"WWW-Authenticate": "Bearer"},
)


def get_current_student(
    token: str | None = Depends(student_oauth2_scheme),
    db: Session = Depends(get_db),
) -> Student:
    """Resolve the currently authenticated student from a bearer token."""
    if token is None:
        raise CREDENTIALS_EXCEPTION

    payload = decode_access_token(token)
    if payload is None or payload.get("role") != "student":
        raise CREDENTIALS_EXCEPTION

    student = db.get(Student, int(payload["sub"]))
    if student is None:
        raise CREDENTIALS_EXCEPTION

    return student


def get_current_teacher(
    token: str | None = Depends(teacher_oauth2_scheme),
    db: Session = Depends(get_db),
) -> Teacher:
    """Resolve the currently authenticated teacher from a bearer token."""
    if token is None:
        raise CREDENTIALS_EXCEPTION

    payload = decode_access_token(token)
    if payload is None or payload.get("role") != "teacher":
        raise CREDENTIALS_EXCEPTION

    teacher = db.get(Teacher, int(payload["sub"]))
    if teacher is None:
        raise CREDENTIALS_EXCEPTION

    return teacher
