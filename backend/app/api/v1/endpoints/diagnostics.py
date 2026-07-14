"""Developer diagnostics endpoints.

Everything under `/diagnostics` (except `/diagnostics/status`, whose only
job is to answer "should the frontend even show diagnostics UI") returns a
plain 404 when diagnostics are disabled — see `app.diagnostics.gating`.
That's deliberate: a 404 is indistinguishable from a route that doesn't
exist at all, so production never leaks that this feature exists, let
alone any data through it.

Read-only and entirely separate from the registration flow itself — this
router only ever reads from `app.diagnostics.diagnostics_store`, which
`app/api/v1/endpoints/registration.py` writes to as a side effect. Nothing
here can affect registration, attendance, or authentication.
"""
from __future__ import annotations

import json

from fastapi import APIRouter, HTTPException, Query, Response, status
from fastapi.responses import FileResponse

from app.diagnostics import diagnostics_store, is_diagnostics_enabled
from app.diagnostics.images import resolve_stage_image_path
from app.diagnostics.schemas import RegistrationAttempt, RegistrationAttemptSummary

router = APIRouter()

_VALID_STAGES = {"original", "preprocessed", "barcode_region", "prn_region", "enhanced_prn", "final_ocr_input"}


def _require_enabled() -> None:
    if not is_diagnostics_enabled():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not Found")


@router.get("/status")
def diagnostics_status() -> dict[str, bool]:
    """Always reachable (even when disabled) — its only job is telling the
    frontend whether to render any diagnostics UI at all. Returns no data,
    just a boolean, so it's safe to expose unconditionally."""
    return {"enabled": is_diagnostics_enabled()}


@router.get("/attempts", response_model=list[RegistrationAttemptSummary])
def list_attempts(
    search: str | None = Query(default=None),
    barcode_success: bool | None = Query(default=None),
    ocr_success: bool | None = Query(default=None),
    manual_entry: bool | None = Query(default=None),
    quality_failed: bool | None = Query(default=None),
    glare: bool | None = Query(default=None),
    blur: bool | None = Query(default=None),
) -> list[RegistrationAttemptSummary]:
    _require_enabled()
    return diagnostics_store.list(
        search=search,
        barcode_success=barcode_success,
        ocr_success=ocr_success,
        manual_entry=manual_entry,
        quality_failed=quality_failed,
        glare=glare,
        blur=blur,
    )


@router.get("/attempts/{attempt_id}", response_model=RegistrationAttempt)
def get_attempt(attempt_id: str) -> RegistrationAttempt:
    _require_enabled()
    attempt = diagnostics_store.get(attempt_id)
    if attempt is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Attempt not found.")
    return attempt


@router.get("/attempts/{attempt_id}/export")
def export_attempt(attempt_id: str) -> Response:
    """Download one attempt's full diagnostic record as a JSON file."""
    _require_enabled()
    attempt = diagnostics_store.get(attempt_id)
    if attempt is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Attempt not found.")

    payload = json.dumps(attempt.model_dump(mode="json"), indent=2)
    return Response(
        content=payload,
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="attempt-{attempt.attempt_number}.json"'},
    )


@router.get("/attempts/{attempt_id}/images/{stage}")
def get_attempt_image(attempt_id: str, stage: str) -> FileResponse:
    """Serve one pipeline-stage debug image for tappable thumbnail / full-
    screen viewing. 404 if diagnostics is disabled, the attempt doesn't
    exist, the stage name is unrecognized, or that stage was never
    generated for this attempt (e.g. SNAPATTEND_AI_DEBUG was off, or the
    barcode-supplied path skipped OCR-region cropping entirely)."""
    _require_enabled()
    if stage not in _VALID_STAGES:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unknown stage.")

    attempt = diagnostics_store.get(attempt_id)
    if attempt is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Attempt not found.")

    path = resolve_stage_image_path(attempt, stage)
    if path is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not Generated")

    return FileResponse(path, media_type="image/jpeg")
