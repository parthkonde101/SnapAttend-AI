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
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_actor, get_current_student, get_current_teacher
from app.core.database import get_db
from app.models.attendance import Attendance
from app.models.attendance_session import DEFAULT_SESSION_DURATION_SECONDS, AttendanceSession
from app.models.teacher import Teacher
from app.schemas.attendance import (
    ActiveSessionInfo,
    ActiveSessionResponse,
    AttendanceSessionCreate,
    AttendanceSessionRead,
    SessionHistoryItem,
)

router = APIRouter()

_CODE_ALPHABET = string.ascii_uppercase + string.digits


def _generate_session_code(length: int = 6) -> str:
    return "".join(secrets.choice(_CODE_ALPHABET) for _ in range(length))


# --- Attendance Session Engine -------------------------------------------------
# Powers /start-session, /active-session, /end-session and /session-history.
# Session capture (camera / OCR / AI verification) is explicitly out of
# scope for this milestone — see the `/mark` stub below.

# Characters chosen to avoid visual ambiguity on a projected classroom
# display (e.g. no 0/O, 1/I/L).
_SESSION_CODE_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ234679"
_SESSION_CODE_LENGTH = 3
_SESSION_CODE_MAX_ATTEMPTS = 25


def _generate_engine_session_code() -> str:
    return "".join(secrets.choice(_SESSION_CODE_ALPHABET) for _ in range(_SESSION_CODE_LENGTH))


def _expire_stale_sessions(db: Session) -> None:
    """Flip any active session whose expiry has passed to inactive.

    There is no background scheduler in this milestone, so expiry is
    applied lazily whenever a session-engine endpoint is hit. Combined
    with client-side polling every few seconds this keeps state accurate
    without needing a long-running worker process.
    """
    now = datetime.now(timezone.utc)
    stmt = select(AttendanceSession).where(
        AttendanceSession.is_active.is_(True), AttendanceSession.expires_at <= now
    )
    for stale_session in db.scalars(stmt):
        stale_session.is_active = False
    db.commit()


def _get_present_count(db: Session, session_id: int) -> int:
    stmt = select(func.count(Attendance.id)).where(Attendance.session_id == session_id)
    return int(db.scalar(stmt) or 0)


def _to_active_session_info(db: Session, session: AttendanceSession) -> ActiveSessionInfo:
    now = datetime.now(timezone.utc)
    remaining = max(0, int((session.expires_at - now).total_seconds()))
    return ActiveSessionInfo(
        session_id=session.id,
        session_code=session.session_code,
        created_at=session.created_at,
        expires_at=session.expires_at,
        duration_seconds=session.duration_seconds,
        remaining_seconds=remaining,
        present_count=_get_present_count(db, session.id),
    )


def _get_active_session(db: Session) -> AttendanceSession | None:
    stmt = select(AttendanceSession).where(AttendanceSession.is_active.is_(True))
    return db.scalar(stmt)


@router.post("/start-session", response_model=ActiveSessionInfo, status_code=status.HTTP_201_CREATED)
def start_session(
    db: Session = Depends(get_db),
    current_teacher: Teacher = Depends(get_current_teacher),
) -> ActiveSessionInfo:
    """Start a new 90 second attendance session.

    Only one session may be active system-wide. Any currently active
    session (regardless of which teacher opened it) is terminated first.
    """
    _expire_stale_sessions(db)

    previous = _get_active_session(db)
    if previous is not None:
        previous.is_active = False
        db.flush()

    code = None
    for _ in range(_SESSION_CODE_MAX_ATTEMPTS):
        candidate = _generate_engine_session_code()
        clash = db.scalar(
            select(AttendanceSession).where(
                AttendanceSession.session_code == candidate, AttendanceSession.is_active.is_(True)
            )
        )
        if clash is None:
            code = candidate
            break
    if code is None:  # pragma: no cover - astronomically unlikely with 27^3 combinations
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Could not generate a unique session code. Please try again.",
        )

    now = datetime.now(timezone.utc)
    session = AttendanceSession(
        session_code=code,
        teacher_id=current_teacher.id,
        duration_seconds=DEFAULT_SESSION_DURATION_SECONDS,
        expires_at=now + timedelta(seconds=DEFAULT_SESSION_DURATION_SECONDS),
        is_active=True,
    )
    db.add(session)
    db.commit()
    db.refresh(session)

    return _to_active_session_info(db, session)


@router.get("/active-session", response_model=ActiveSessionResponse)
def get_active_session(
    db: Session = Depends(get_db),
    current_actor: tuple[str, int] = Depends(get_current_actor),
) -> ActiveSessionResponse:
    """Return the single system-wide active session, if any.

    Shared by both students and teachers: students poll this to know
    when to show the "Mark Attendance" prompt, and the teacher
    presentation screen polls it to keep the countdown and present count
    in sync across page refreshes.
    """
    _expire_stale_sessions(db)

    session = _get_active_session(db)
    if session is None:
        return ActiveSessionResponse(active=False, session=None)

    return ActiveSessionResponse(active=True, session=_to_active_session_info(db, session))


@router.post("/end-session", response_model=ActiveSessionInfo)
def end_session(
    db: Session = Depends(get_db),
    current_teacher: Teacher = Depends(get_current_teacher),
) -> ActiveSessionInfo:
    """Immediately end the current teacher's active session."""
    _expire_stale_sessions(db)

    session = _get_active_session(db)
    if session is None or session.teacher_id != current_teacher.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No active attendance session found")

    session.is_active = False
    db.commit()
    db.refresh(session)

    return _to_active_session_info(db, session)


@router.get("/session-history", response_model=list[SessionHistoryItem])
def get_session_history(
    db: Session = Depends(get_db),
    current_teacher: Teacher = Depends(get_current_teacher),
) -> list[SessionHistoryItem]:
    """List past attendance sessions started by the current teacher, most recent first."""
    _expire_stale_sessions(db)

    stmt = (
        select(AttendanceSession)
        .where(AttendanceSession.teacher_id == current_teacher.id)
        .order_by(AttendanceSession.created_at.desc())
    )
    sessions = list(db.scalars(stmt))

    return [
        SessionHistoryItem(
            session_id=s.id,
            session_code=s.session_code,
            created_at=s.created_at,
            expires_at=s.expires_at,
            duration_seconds=s.duration_seconds,
            status="active" if s.is_active else "ended",
            present_count=_get_present_count(db, s.id),
        )
        for s in sessions
    ]


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
