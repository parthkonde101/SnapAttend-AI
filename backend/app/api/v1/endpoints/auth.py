"""Authentication endpoints: student registration/login and teacher login."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import create_access_token, hash_password, verify_password
from app.models.student import Student
from app.models.teacher import Teacher
from app.schemas.auth import Token
from app.schemas.student import StudentLogin, StudentRegister
from app.schemas.teacher import TeacherLogin

router = APIRouter()


@router.post("/student/register", response_model=Token, status_code=status.HTTP_201_CREATED)
def register_student(payload: StudentRegister, db: Session = Depends(get_db)) -> Token:
    """Create a new student account and return an access token."""
    existing = db.scalar(select(Student).where(Student.prn == payload.prn))
    if existing is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="A student with this PRN already exists")

    student = Student(
        prn=payload.prn,
        full_name=payload.full_name,
        password_hash=hash_password(payload.password),
    )
    db.add(student)
    db.commit()
    db.refresh(student)

    access_token = create_access_token(subject=str(student.id), role="student")
    return Token(access_token=access_token)


@router.post("/student/login", response_model=Token)
def login_student(payload: StudentLogin, db: Session = Depends(get_db)) -> Token:
    """Authenticate a student by PRN and password."""
    student = db.scalar(select(Student).where(Student.prn == payload.prn))
    if student is None or not verify_password(payload.password, student.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid PRN or password")

    access_token = create_access_token(subject=str(student.id), role="student")
    return Token(access_token=access_token)


@router.post("/teacher/login", response_model=Token)
def login_teacher(payload: TeacherLogin, db: Session = Depends(get_db)) -> Token:
    """Authenticate a teacher by teacher ID and password."""
    teacher = db.scalar(select(Teacher).where(Teacher.teacher_id == payload.teacher_id))
    if teacher is None or not verify_password(payload.password, teacher.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid teacher ID or password")

    access_token = create_access_token(subject=str(teacher.id), role="teacher")
    return Token(access_token=access_token)
