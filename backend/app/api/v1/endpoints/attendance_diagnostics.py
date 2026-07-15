"""Developer diagnostics endpoints — attendance.

Parallel to `app/api/v1/endpoints/diagnostics.py` (the registration
diagnostics router, not touched by this milestone): same gating
discipline (a plain 404 when diagnostics are disabled — see
`app.diagnostics.gating`, imported directly, not through the registration
diagnostics package's `__init__.py`), same read-only relationship to the
store it serves (`app.diagnostics.attendance_store`, which
`app/services/attendance_verification_service.py` writes to as a side
effect). Nothing here can affect attendance verification, sessions, or
authentication.

Kept as an entirely separate router/prefix (`/attendance-diagnostics`)
rather than added to the registration diagnostics router, so this can be
built, extended, and reasoned about without touching that file at all.
"""
from __future__ import annotations

import json

from fastapi import APIRouter, HTTPException, Query, Response, status
from fastapi.responses import FileResponse

from app.diagnostics.attendance_images import resolve_attendance_stage_image_path
from app.diagnostics.attendance_schemas import AttendanceAttempt, AttendanceAttemptSummary
from app.diagnostics.attendance_store import attendance_diagnostics_store
from app.diagnostics.gating import is_diagnostics_enabled

router = APIRouter()


def _require_enabled() -> None:
    if not is_diagnostics_enabled():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not Found")


@router.get("/status")
def attendance_diagnostics_status() -> dict[str, bool]:
    """Always reachable (even when disabled) — its only job is telling the
    frontend whether to render any diagnostics UI at all. Same semantics as
    the registration diagnostics router's `/status`."""
    return {"enabled": is_diagnostics_enabled()}


@router.get("/attempts", response_model=list[AttendanceAttemptSummary])
def list_attendance_attempts(
    session_id: int | None = Query(default=None),
    student_id: int | None = Query(default=None),
) -> list[AttendanceAttemptSummary]:
    _require_enabled()
    return attendance_diagnostics_store.list(session_id=session_id, student_id=student_id)


@router.get("/attempts/{attempt_id}", response_model=AttendanceAttempt)
def get_attendance_attempt(attempt_id: str) -> AttendanceAttempt:
    _require_enabled()
    attempt = attendance_diagnostics_store.get(attempt_id)
    if attempt is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Attempt not found.")
    return attempt


@router.get("/attempts/{attempt_id}/export")
def export_attendance_attempt(attempt_id: str) -> Response:
    """Download one attempt's full diagnostic record as a JSON file — the
    complete marker evidence trail (every region scanned, every candidate
    found) included, for offline inspection."""
    _require_enabled()
    attempt = attendance_diagnostics_store.get(attempt_id)
    if attempt is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Attempt not found.")

    payload = json.dumps(attempt.model_dump(mode="json"), indent=2)
    return Response(
        content=payload,
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="attendance-attempt-{attempt.attempt_number}.json"'},
    )


@router.get("/attempts/{attempt_id}/images/{stage}")
def get_attendance_attempt_image(attempt_id: str, stage: str) -> FileResponse:
    """Serve one debug image for tappable thumbnail / full-screen viewing —
    the exact crop handed to the marker detector (or the identity stage's
    card-region crop), by stage key. 404 if diagnostics is disabled, the
    attempt doesn't exist, or that stage was never generated for this
    attempt (e.g. SNAPATTEND_AI_DEBUG was off, or that region/PSM tier
    never ran because an earlier one already found the marker).

    Unlike registration's fixed six-slot set, attendance's stage keys are
    dynamic (however many marker scans actually ran), so validity is
    checked against this specific attempt's own recorded stages rather
    than a fixed global set.
    """
    _require_enabled()
    attempt = attendance_diagnostics_store.get(attempt_id)
    if attempt is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Attempt not found.")

    valid_stages = {s.stage for s in attempt.stage_images}
    if stage not in valid_stages:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unknown stage.")

    path = resolve_attendance_stage_image_path(attempt, stage)
    if path is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not Generated")

    return FileResponse(path, media_type="image/jpeg")
