"""Registration intelligence endpoints.

Two-step flow used by the student registration wizard:

1. `POST /registration/analyze` — unauthenticated (the account doesn't
   exist yet). Runs the AI pipeline (`app.ai.pipeline`) against a freshly
   captured ID photo and returns a `RegistrationAnalysis` with suggested
   PRN / name values for the student to review and edit.
2. `POST /registration/verify` — student-authenticated. Called right
   after the student confirms their (possibly edited) values and the
   account has been created via the existing, untouched
   `POST /auth/student/register`. Persists the verified snapshot onto
   their own student row.

Neither endpoint touches authentication, attendance sessions, or the
existing attendance camera/upload flow.

Developer diagnostics (`app.diagnostics`) hook into both endpoints as a
pure side effect: when enabled, `/analyze` records what the pipeline did
and `/verify` updates that same record with the student's final confirmed
values. Neither endpoint's request/response contract changes because of
this — see `app/diagnostics/recorder.py` for why a recorder can't
influence pipeline behaviour, only observe it.
"""
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.ai.pipeline import analyze_registration_photo
from app.ai.schemas import RegistrationAnalysis
from app.api.deps import get_current_student
from app.core.config import settings
from app.core.database import get_db
from app.diagnostics import DiagnosticsRecorder, diagnostics_store, is_diagnostics_enabled
from app.models.student import Student
from app.schemas.registration import RegistrationVerifyRequest, RegistrationVerifyResponse

router = APIRouter()

_ALLOWED_CONTENT_TYPES = {
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}
_MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10 MB


@router.post("/analyze", response_model=RegistrationAnalysis)
async def analyze_registration_id(file: UploadFile = File(...)) -> RegistrationAnalysis:
    """Run the registration intelligence pipeline against a captured ID photo.

    No authentication — this runs before the student account exists. Does
    not create or modify any student record; purely analysis.
    """
    content_type = (file.content_type or "").lower()
    if content_type not in _ALLOWED_CONTENT_TYPES:
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

    # Diagnostics recording is a pure side effect: when disabled (the
    # production default), `recorder` stays None and `analyze_registration_photo`
    # runs exactly as it did before this hook existed — no extra work, no
    # behavioural difference.
    recorder = DiagnosticsRecorder() if is_diagnostics_enabled() else None
    result = analyze_registration_photo(contents, storage_dir=Path(settings.REGISTRATION_UPLOAD_DIR), recorder=recorder)

    if recorder is not None:
        attempt = recorder.finalize(result, attempt_number=diagnostics_store.next_attempt_number())
        diagnostics_store.add(attempt)
        result = result.model_copy(update={"diagnostics_attempt_id": attempt.id})

    return result


@router.post("/verify", response_model=RegistrationVerifyResponse)
def verify_registration(
    payload: RegistrationVerifyRequest,
    db: Session = Depends(get_db),
    current_student: Student = Depends(get_current_student),
) -> Student:
    """Persist the AI-verified PRN/name snapshot onto the current student.

    Called after the account already exists (via the unchanged
    `POST /auth/student/register`). Does not create accounts and does not
    touch `students.prn` / `students.full_name` — those remain whatever
    was submitted at registration.
    """
    id_image_path: str | None = None
    if payload.image_reference:
        candidate = Path(settings.REGISTRATION_UPLOAD_DIR) / f"{payload.image_reference}.jpg"
        if candidate.is_file():
            id_image_path = str(candidate)

    current_student.verified_prn = payload.prn
    current_student.verified_name = payload.student_name
    current_student.id_image_path = id_image_path
    current_student.verified_at = datetime.now(timezone.utc)

    db.add(current_student)
    db.commit()
    db.refresh(current_student)

    _record_verification_diagnostics(payload)

    return current_student


def _record_verification_diagnostics(payload: RegistrationVerifyRequest) -> None:
    """Side-effect only: update the matching diagnostics attempt (if
    diagnostics is enabled and one exists) with the student's final
    confirmed values, so "Registration Successful" / "PRN Source" in the
    diagnostics UI reflect what actually happened, not just what the
    pipeline suggested at `/analyze` time. Never raises, never affects the
    actual verify response — the account is already committed by the time
    this runs.
    """
    if not is_diagnostics_enabled() or not payload.image_reference:
        return
    try:
        attempt = diagnostics_store.get(payload.image_reference)
        if attempt is None:
            return

        suggested_prn = (attempt.final.verified_prn or "").strip()
        is_manual = payload.prn.strip() != suggested_prn
        prn_source = "manual" if is_manual else attempt.final.prn_source

        updated_final = attempt.final.model_copy(
            update={
                "verified_prn": payload.prn,
                "verified_name": payload.student_name,
                "prn_source": prn_source,
                "registration_completed": True,
            }
        )
        diagnostics_store.update(attempt.id, final=updated_final)
    except Exception:
        pass
