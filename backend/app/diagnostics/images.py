"""Resolves a diagnostics stage image to the file saved on disk by
`app.ai.pipeline`'s debug capture (`app/ai/config.DEBUG_OUTPUT_DIR`).

Kept separate from the recorder/store so the API endpoint that serves
image bytes doesn't need to know anything about how stage names map to
filenames — it just asks this module for a path.
"""
from __future__ import annotations

from pathlib import Path

from app.ai.config import DEBUG_OUTPUT_DIR
from app.diagnostics.schemas import RegistrationAttempt


def resolve_stage_image_path(attempt: RegistrationAttempt, stage: str) -> Path | None:
    """Return the on-disk path for `stage` on `attempt`, or None if that
    stage wasn't generated for this attempt (debug mode off, or that
    branch of the pipeline never ran)."""
    slot = next((s for s in attempt.stage_images if s.stage == stage), None)
    if slot is None or not slot.available or not slot.filename:
        return None

    path = Path(DEBUG_OUTPUT_DIR) / attempt.id / f"{slot.filename}.jpg"
    return path if path.is_file() else None
