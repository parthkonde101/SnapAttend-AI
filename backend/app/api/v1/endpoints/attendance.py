"""Attendance endpoints.

Session lifecycle (create / list / retrieve) is implemented so the teacher
dashboard has something real to build against. The actual check-in flow
(a student marking themselves present, including any future OCR / AI
photo verification) is intentionally left unimplemented for now and is
represented by a stub endpoint that returns HTTP 501.
"""
import secrets
import string
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_student, get_current_teacher
from app.core.database import get_db
from app.models.attendance_session import AttendanceSession
from app.models.teacher import Teacher
from app.schemas.attendance import AttendanceSessionCreate, AttendanceSessionRead

router = APIRouter()

_CODE_ALPHABET = string.ascii_uppercase + string.digits


def _generate_session_code(length: int = 6) -> str:
    return "".join(secrets.choice(_CODE_ALPHABET) for _ in range(length))


@router.post("/sessions", response_model=AttendanceSessionRead, status_code=status.HTTP_201_CREATED)
def create_session(
    payload: AttendanceSessionCreate,
    db: Session = Depends(get_db),
    current_teacher: Teacher = Depends(get_current_teacher),
) -> AttendanceSession:
    """Open a new attendance session for the current teacher."""
    session = AttendanceSession(
        session_code=_generate_session_code(),
        teacher_id=current_teacher.id,
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=payload.duration_minutes),
        is_active=True,
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


@router.get("/sessions", response_model=list[AttendanceSessionRead])
def list_sessions(
    db: Session = Depends(get_db),
    current_teacher: Teacher = Depends(get_current_teacher),
) -> list[AttendanceSession]:
    """List attendance sessions created by the current teacher, most recent first."""
    stmt = (
        select(AttendanceSession)
        .where(AttendanceSession.teacher_id == current_teacher.id)
        .order_by(AttendanceSession.created_at.desc())
    )
    return list(db.scalars(stmt))


@router.get("/sessions/{session_id}", response_model=AttendanceSessionRead)
def get_session(
    session_id: int,
    db: Session = Depends(get_db),
    current_teacher: Teacher = Depends(get_current_teacher),
) -> AttendanceSession:
    """Retrieve a single attendance session owned by the current teacher."""
    session = db.get(AttendanceSession, session_id)
    if session is None or session.teacher_id != current_teacher.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Attendance session not found")
    return session


@router.post("/mark", status_code=status.HTTP_501_NOT_IMPLEMENTED)
def mark_attendance(current_student=Depends(get_current_student)) -> None:
    """Placeholder for the student check-in flow.

    Marking attendance (including photo capture, OCR, and AI-based
    verification) is out of scope for this milestone. The route is
    defined now so the frontend and API contract are stable once the
    feature is implemented.
    """
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Attendance marking is not implemented yet.",
    )
