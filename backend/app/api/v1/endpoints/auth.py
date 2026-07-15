"""Authentication endpoints: student registration/login, teacher login, and
the no-email/no-OTP student password reset flow (forgot-password/verify +
forgot-password/reset below — see their docstrings)."""
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.pipeline import analyze_registration_photo
from app.api.deps import get_password_reset_student
from app.core.config import settings
from app.core.database import get_db
from app.core.security import create_access_token, hash_password, verify_password
from app.models.admin import Admin
from app.models.student import Student
from app.models.teacher import Teacher
from app.schemas.admin import AdminLogin
from app.schemas.auth import PasswordResetCompleteRequest, PasswordResetVerifyResponse, Token
from app.schemas.student import StudentLogin, StudentRegister
from app.schemas.teacher import TeacherLogin

router = APIRouter()

# Same allowlist/size cap as POST /registration/analyze (app/api/v1/endpoints/registration.py) —
# the forgot-password verify step below runs the identical photo through
# the identical pipeline, so it's held to the identical input constraints.
_ALLOWED_ID_PHOTO_CONTENT_TYPES = {
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}
_MAX_ID_PHOTO_UPLOAD_BYTES = 10 * 1024 * 1024  # 10 MB

# Deliberately short — this token is only ever meant to bridge "just proved
# identity via ID card" to "now set a new password", a single short
# interaction, not a standing session.
_PASSWORD_RESET_TOKEN_EXPIRE_MINUTES = 10


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


@router.post("/admin/login", response_model=Token)
def login_admin(payload: AdminLogin, db: Session = Depends(get_db)) -> Token:
    """Authenticate an administrator by login id and password (Milestone
    7A — Administrator System).

    Deliberately a separate endpoint/flow from `/teacher/login` even
    though the shape is identical — an Administrator is not a Teacher (see
    `app.models.admin.Admin`), and issuing a token with `role="admin"`
    here (never `"teacher"`) is what lets `get_current_admin` and
    `get_current_teacher` stay mutually exclusive: an admin token can
    never be used against a teacher-only route, and a teacher token can
    never reach an admin-only one.
    """
    admin = db.scalar(select(Admin).where(Admin.login_id == payload.login_id))
    if admin is None or not verify_password(payload.password, admin.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid login ID or password")

    access_token = create_access_token(subject=str(admin.id), role="admin")
    return Token(access_token=access_token)


# --- Forgot password (no email, no OTP) ----------------------------------------
# Flow: enter PRN -> capture ID card -> verify PRN matches the extracted
# PRN -> create new password -> success. The ID card itself is the identity
# proof, exactly like registration — deliberately reuses
# `app.ai.pipeline.analyze_registration_photo` (the same registration
# verification engine, not a second one) to extract a PRN from the photo.


@router.post("/student/forgot-password/verify", response_model=PasswordResetVerifyResponse)
async def verify_forgot_password(
    prn: str = Form(..., min_length=1, max_length=50),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> PasswordResetVerifyResponse:
    """Step 2-3 of the reset flow: confirm an account exists for `prn`,
    then confirm the freshly captured ID photo's own extracted PRN matches
    it. On success, issues a short-lived, single-purpose reset token (see
    `app.core.security.TokenRole` and `get_password_reset_student`) — never
    a normal session token, since a photo alone should never grant full
    account access the way a correct password would.
    """
    student = db.scalar(select(Student).where(Student.prn == prn.strip()))
    if student is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No account found for this PRN.")

    content_type = (file.content_type or "").lower()
    if content_type not in _ALLOWED_ID_PHOTO_CONTENT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Unsupported image type. Please upload a JPEG, PNG, or WEBP photo.",
        )

    contents = await file.read()
    if not contents:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Uploaded file is empty.")
    if len(contents) > _MAX_ID_PHOTO_UPLOAD_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Photo is too large. Maximum size is 10 MB.",
        )

    # Same pipeline registration uses, same storage directory — this is not
    # a second identity-verification system, it's the existing one run
    # again against a new photo. No diagnostics recorder is attached here:
    # this endpoint is unauthenticated by design (that's the whole point —
    # the ID card is the proof), and diagnostics attempts are otherwise
    # always tied to a student/session context that doesn't exist yet here.
    result = analyze_registration_photo(contents, storage_dir=Path(settings.REGISTRATION_UPLOAD_DIR))

    if not result.quality_passed:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="; ".join(result.quality_messages) or "Photo quality too low. Please retry.",
        )

    extracted_prn = (result.prn or "").strip()
    if not extracted_prn or extracted_prn.upper() != prn.strip().upper():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="The ID card does not match the PRN entered. Please retake the photo or check your PRN.",
        )

    reset_token = create_access_token(
        subject=str(student.id), role="password_reset", expires_minutes=_PASSWORD_RESET_TOKEN_EXPIRE_MINUTES
    )
    return PasswordResetVerifyResponse(reset_token=reset_token)


@router.post("/student/forgot-password/reset", response_model=Token)
def complete_forgot_password(
    payload: PasswordResetCompleteRequest,
    current_student: Student = Depends(get_password_reset_student),
    db: Session = Depends(get_db),
) -> Token:
    """Step 4-5: set the new password (authorized by the reset token from
    the verify step, not by any field in this body), then immediately log
    the student in — the same "confirm identity once, land on your
    dashboard" experience registration already gives, rather than making
    them log in again right after resetting."""
    current_student.password_hash = hash_password(payload.new_password)
    db.add(current_student)
    db.commit()

    access_token = create_access_token(subject=str(current_student.id), role="student")
    return Token(access_token=access_token)
