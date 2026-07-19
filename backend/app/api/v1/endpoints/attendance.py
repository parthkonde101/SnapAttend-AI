"""Attendance endpoints.

Session lifecycle (`/start-session`, `/active-session`, `/end-session`,
`/session-history`) delegates to `AttendanceSessionService`. Student
check-in (`/mark`) delegates to `AttendanceVerificationService`, which in
turn calls the Attendance Verification Engine's AI pipeline
(`app.ai.attendance_pipeline`). Business logic lives in
`app/services/*` — this module stays a thin request/response translator,
per the Attendance Verification Engine V1 spec.

`/sessions`, `/sessions/{id}` (generic session CRUD) and `/upload-photo`
(dumb file drop) below the "Legacy" markers predate this milestone and are
untouched — nothing here reads or writes them.
"""
import secrets
import string
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_actor, get_current_student, get_current_teacher
from app.core.config import settings
from app.core.database import get_db
from app.core.sorting import roll_number_sort_key
from app.diagnostics.attendance_recorder import AttendanceDiagnosticsRecorder
from app.diagnostics.gating import is_diagnostics_enabled
from app.models.attendance import Attendance
from app.models.attendance_session import AttendanceSession
from app.models.student import Student
from app.models.teacher import Teacher
from app.schemas.attendance import (
    ActiveSessionInfo,
    ActiveSessionResponse,
    AttendanceOverrideRequest,
    AttendanceRecordDetail,
    AttendanceSessionCreate,
    AttendanceSessionRead,
    AttendanceSessionStartRequest,
    MarkAttendanceResponse,
    PhotoUploadResponse,
    SessionHistoryItem,
    SessionRecordsResponse,
    SessionReviewResponse,
    StudentAttendanceReviewItem,
)
from app.services.attendance_export_service import build_attendance_export
from app.services.attendance_review_service import AttendanceReviewService
from app.services.attendance_session_service import AttendanceSessionService
from app.services.attendance_verification_service import AttendanceVerificationService
from app.services.device_lock_service import DEVICE_ALREADY_USED_MESSAGE, DeviceLockService

router = APIRouter()

_CODE_ALPHABET = string.ascii_uppercase + string.digits


def _generate_session_code(length: int = 6) -> str:
    return "".join(secrets.choice(_CODE_ALPHABET) for _ in range(length))


# --- Attendance Session Engine -------------------------------------------------
# Powers /start-session, /active-session, /end-session, /session-history,
# and /session-records. Lifecycle logic itself lives in
# app/services/attendance_session_service.py.


def _to_active_session_info(
    service: AttendanceSessionService, session: AttendanceSession, *, include_marker: bool
) -> ActiveSessionInfo:
    now = datetime.now(timezone.utc)
    remaining = max(0, int((session.expires_at - now).total_seconds()))
    return ActiveSessionInfo(
        session_id=session.id,
        session_code=session.session_code,
        marker=session.marker if include_marker else None,
        course=session.course.course_name if session.course else None,
        panel=session.panel.name if session.panel else None,
        created_at=session.created_at,
        expires_at=session.expires_at,
        duration_seconds=session.duration_seconds,
        remaining_seconds=remaining,
        present_count=service.get_present_count(session.id),
    )


@router.post("/start-session", response_model=ActiveSessionInfo, status_code=status.HTTP_201_CREATED)
def start_session(
    payload: AttendanceSessionStartRequest,
    db: Session = Depends(get_db),
    current_teacher: Teacher = Depends(get_current_teacher),
) -> ActiveSessionInfo:
    """Start a new attendance session against a Course and Panel the
    teacher selected (default duration 2 minutes; teacher may choose
    1/2/3/5 minutes via `payload.duration_seconds`).

    Only one session may be active system-wide. Any currently active
    session (regardless of which teacher opened it) is terminated first.
    """
    service = AttendanceSessionService(db)
    try:
        session = service.start_session(
            current_teacher,
            course_id=payload.course_id,
            panel_id=payload.panel_id,
            duration_seconds=payload.duration_seconds,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc

    return _to_active_session_info(service, session, include_marker=True)


@router.get("/active-session", response_model=ActiveSessionResponse)
def get_active_session(
    db: Session = Depends(get_db),
    current_actor: tuple[str, int] = Depends(get_current_actor),
) -> ActiveSessionResponse:
    """Return the single system-wide active session, if any.

    Shared by both students and teachers: students poll this to know when
    to show the "Mark Attendance" prompt, and the teacher presentation
    screen polls it to keep the countdown, marker, and present count in
    sync across page refreshes. `marker` is only ever populated for the
    teacher role — see `ActiveSessionInfo`.
    """
    service = AttendanceSessionService(db)
    service.expire_stale_sessions()

    session = service.get_active_session()
    if session is None:
        return ActiveSessionResponse(active=False, session=None)

    role, _ = current_actor
    return ActiveSessionResponse(active=True, session=_to_active_session_info(service, session, include_marker=role == "teacher"))


@router.post("/end-session", response_model=ActiveSessionInfo)
def end_session(
    db: Session = Depends(get_db),
    current_teacher: Teacher = Depends(get_current_teacher),
) -> ActiveSessionInfo:
    """Immediately end the current teacher's active session."""
    service = AttendanceSessionService(db)
    try:
        session = service.end_session(current_teacher)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    return _to_active_session_info(service, session, include_marker=True)


@router.get("/session-history", response_model=list[SessionHistoryItem])
def get_session_history(
    db: Session = Depends(get_db),
    current_teacher: Teacher = Depends(get_current_teacher),
) -> list[SessionHistoryItem]:
    """List past attendance sessions started by the current teacher, most recent first."""
    service = AttendanceSessionService(db)
    service.expire_stale_sessions()

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
            marker=s.marker,
            course=s.course.course_name if s.course else None,
            panel=s.panel.name if s.panel else None,
            created_at=s.created_at,
            expires_at=s.expires_at,
            duration_seconds=s.duration_seconds,
            status="active" if s.is_active else "ended",
            present_count=service.get_present_count(s.id),
        )
        for s in sessions
    ]


@router.get("/session-records/{session_id}", response_model=SessionRecordsResponse)
def get_session_records(
    session_id: int,
    db: Session = Depends(get_db),
    current_teacher: Teacher = Depends(get_current_teacher),
) -> SessionRecordsResponse:
    """Live attendance list for one of the current teacher's sessions —
    powers the teacher dashboard's present/remaining counts and roster."""
    session = db.get(AttendanceSession, session_id)
    if session is None or session.teacher_id != current_teacher.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Attendance session not found")

    service = AttendanceSessionService(db)
    total_students = service.get_total_registered_students()

    # Filtered to status='present' — see AttendanceSessionService.get_present_count
    # for why a row's mere existence no longer implies "currently present"
    # since teacher overrides were added. Ordered by Roll Number ascending
    # (spec Part 11 — Student Ordering, "Live attendance monitoring"),
    # numeric-aware — not arrival order.
    stmt = (
        select(Attendance, Student)
        .join(Student, Attendance.student_id == Student.id)
        .where(Attendance.session_id == session_id, Attendance.status == "present")
    )
    rows = list(db.execute(stmt).all())
    rows.sort(key=lambda pair: roll_number_sort_key(pair[1].roll_number))

    records = [
        AttendanceRecordDetail(
            student_id=student.id,
            prn=student.prn,
            full_name=student.full_name,
            roll_number=student.roll_number,
            marked_at=attendance.marked_at,
            verification_source=attendance.verification_source,  # type: ignore[arg-type]
        )
        for attendance, student in rows
    ]

    return SessionRecordsResponse(
        session_id=session.id,
        marker=session.marker,
        present_count=len(records),
        remaining_count=max(0, total_students - len(records)),
        records=records,
    )


# --- Teacher review + verification-philosophy refinement ----------------------
# Powers the per-session review page: every registered student (present and
# absent), the evidence behind every present record, a Present/Absent
# override teachers can flip at any time, and one-click access to the
# original photo behind a record. Business logic lives in
# app/services/attendance_review_service.py.


@router.get("/session-review/{session_id}", response_model=SessionReviewResponse)
def get_session_review(
    session_id: int,
    db: Session = Depends(get_db),
    current_teacher: Teacher = Depends(get_current_teacher),
) -> SessionReviewResponse:
    """Full roster for one of the current teacher's sessions — every
    registered student, whether or not they have an attendance record."""
    review_service = AttendanceReviewService(db)
    try:
        session = review_service.get_session_for_teacher(session_id, current_teacher)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    return review_service.build_session_review(session)


@router.post("/session-review/{session_id}/override", response_model=StudentAttendanceReviewItem)
def override_attendance_status(
    session_id: int,
    payload: AttendanceOverrideRequest,
    db: Session = Depends(get_db),
    current_teacher: Teacher = Depends(get_current_teacher),
) -> StudentAttendanceReviewItem:
    """Teacher override: immediately set a student's Present/Absent status
    for this session. Never deletes an existing record's AI evidence — see
    `AttendanceReviewService.set_status`."""
    review_service = AttendanceReviewService(db)
    try:
        session = review_service.get_session_for_teacher(session_id, current_teacher)
        return review_service.set_status(
            session=session, student_id=payload.student_id, status=payload.status, teacher=current_teacher
        )
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get("/session-review/{session_id}/photo/{student_id}")
def get_attendance_photo(
    session_id: int,
    student_id: int,
    db: Session = Depends(get_db),
    current_teacher: Teacher = Depends(get_current_teacher),
) -> FileResponse:
    """Serve the original captured photo behind one student's attendance
    record in this session, so a teacher can visually verify a submission
    before overriding it. Scoped to the current teacher's own session —
    see `AttendanceReviewService.get_photo_path`."""
    review_service = AttendanceReviewService(db)
    try:
        session = review_service.get_session_for_teacher(session_id, current_teacher)
        path = review_service.get_photo_path(session=session, student_id=student_id)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    return FileResponse(path, media_type="image/jpeg")


@router.get("/session-review/{session_id}/export")
def export_attendance(
    session_id: int,
    db: Session = Depends(get_db),
    current_teacher: Teacher = Depends(get_current_teacher),
) -> Response:
    """Download the final attendance list for one of the current teacher's
    *ended* sessions as a formatted .xlsx workbook (see
    `app/services/attendance_export_service.py`). Only ever reflects each
    student's final effective status — including any Present/Absent
    override — never raw AI evidence.

    Available only after the session has ended: exporting a still-active
    session would produce a file that goes stale the moment another student
    checks in or the teacher makes another override, undermining the whole
    point of an export being a fixed, final record.
    """
    review_service = AttendanceReviewService(db)
    try:
        session = review_service.get_session_for_teacher(session_id, current_teacher)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    if session.is_active:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This session is still active. End it before exporting the final attendance list.",
        )

    export = build_attendance_export(db, session)
    return Response(
        content=export.content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{export.filename}"'},
    )


# --- Attendance Verification Engine (V1) --------------------------------------
# Powers the student check-in flow: capture a scene (ID card + classroom
# display), verify it, and record attendance on the first success.

_ALLOWED_MARK_CONTENT_TYPES = {
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}
_MAX_MARK_UPLOAD_BYTES = 10 * 1024 * 1024  # 10 MB


@router.post("/mark", response_model=MarkAttendanceResponse)
async def mark_attendance(
    file: UploadFile = File(...),
    device_id: str | None = Form(default=None),
    db: Session = Depends(get_db),
    current_student: Student = Depends(get_current_student),
) -> MarkAttendanceResponse:
    """Verify a captured attendance scene and record attendance on the
    first successful attempt for the active session.

    Students may retry unlimited times while the session remains active —
    a failed attempt never writes a row, so it never consumes an
    opportunity to attend (see `AttendanceVerificationService`).

    `device_id` (Milestone 6C, Part 1 — Temporary Device Lock): a random
    UUID the frontend generates once and stores locally, sent with every
    attendance attempt. Optional/nullable purely for backward
    compatibility with any client that doesn't send it yet — when absent,
    the device-lock check below is simply skipped for that request (no
    lock check, no lock recorded), rather than blocking a legitimate
    student on a technicality. See `app/services/device_lock_service.py`
    for the actual same-device/different-student rule.
    """
    content_type = (file.content_type or "").lower()
    if content_type not in _ALLOWED_MARK_CONTENT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Unsupported image type. Please upload a JPEG, PNG, or WEBP photo.",
        )

    contents = await file.read()
    if not contents:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Uploaded file is empty.")
    if len(contents) > _MAX_MARK_UPLOAD_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Photo is too large. Maximum size is 10 MB.",
        )

    session_service = AttendanceSessionService(db)
    session_service.expire_stale_sessions()
    session = session_service.get_active_session()
    if session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No active attendance session.")

    # Device lock (Milestone 6C, Part 1): cheap request-level gate, same
    # spirit as AttendanceVerificationService.already_marked's early exit —
    # no point running the AI pipeline against a photo whose outcome is
    # already determined. Same device + same student is always allowed
    # (covers accidental logout, app restart, browser refresh, logging back
    # in); only a *different* student on an already-locked device is
    # rejected, with a friendly explanation, before any verification runs.
    device_lock_service = DeviceLockService(db)
    if device_id and device_lock_service.is_blocked(
        session_id=session.id, device_id=device_id, student_id=current_student.id
    ):
        return MarkAttendanceResponse(success=False, reason=DEVICE_ALREADY_USED_MESSAGE)

    # Diagnostics recording is a pure side effect: when disabled (the
    # production default), `recorder` stays None and verification runs
    # exactly as it would without this hook — no extra work, no
    # behavioural difference. Mirrors app/api/v1/endpoints/registration.py.
    recorder = AttendanceDiagnosticsRecorder() if is_diagnostics_enabled() else None

    verification_service = AttendanceVerificationService(db)
    result = verification_service.verify_and_record(
        student=current_student,
        session=session,
        image_bytes=contents,
        storage_dir=Path(settings.UPLOAD_DIR),
        recorder=recorder,
    )

    # Only a brand-new, successful verification creates the lock — never a
    # failed attempt, and never "already_recorded" (that student's device
    # relationship for this session was already established on their
    # original success).
    if result.success and device_id:
        device_lock_service.record_lock(session_id=session.id, device_id=device_id, student_id=current_student.id)

    return result


# --- Legacy: generic session CRUD ----------------------------------------------
# Predates the session engine above (initial project foundation milestone).
# Not used by the current frontend or the verification engine — left
# entirely untouched.


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


# --- Legacy: dumb photo upload -------------------------------------------------
# Predates the verification engine above. Not used by the current frontend
# (which now calls /mark directly) or by the verification engine — left
# entirely untouched.

_ALLOWED_UPLOAD_CONTENT_TYPES = {
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}
_MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10 MB


@router.post("/upload-photo", response_model=PhotoUploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_attendance_photo(
    file: UploadFile = File(...),
    current_student: Student = Depends(get_current_student),
) -> PhotoUploadResponse:
    """Accept an attendance ID-card photo and store it on local disk.

    Does not process, verify, or link the photo to a session — superseded
    by /mark for the actual check-in flow, kept only for backward
    compatibility.
    """
    content_type = (file.content_type or "").lower()
    extension = _ALLOWED_UPLOAD_CONTENT_TYPES.get(content_type)
    if extension is None:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Unsupported image type. Please upload a JPEG, PNG, or WEBP photo.",
        )

    contents = await file.read()
    if not contents:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Uploaded file is empty.")
    if len(contents) > _MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Photo is too large. Maximum size is 10 MB.",
        )

    image_id = uuid.uuid4().hex
    upload_dir = Path(settings.UPLOAD_DIR)
    upload_dir.mkdir(parents=True, exist_ok=True)
    (upload_dir / f"{image_id}{extension}").write_bytes(contents)

    return PhotoUploadResponse(success=True, imageId=image_id)
