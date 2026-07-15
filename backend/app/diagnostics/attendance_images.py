"""Resolves an attendance diagnostics stage image to the file saved on disk
by `app.ai.attendance_pipeline`'s debug capture
(`app/ai/attendance_config.ATTENDANCE_DEBUG_OUTPUT_DIR`).

Parallel to `app/diagnostics/images.py` (the registration resolver, not
touched by this milestone). Simpler than that one: attendance's stage set
is dynamic (however many marker region/PSM scans actually ran), so
`AttendanceDiagnosticsRecorder._resolve_stage_images` already sets each
slot's `filename` equal to its own `stage` key — no fixed stage-to-filename
mapping table is needed here, just a lookup by stage name.
"""
from __future__ import annotations

from pathlib import Path

from app.ai.attendance_config import ATTENDANCE_DEBUG_OUTPUT_DIR
from app.diagnostics.attendance_schemas import AttendanceAttempt


def resolve_attendance_stage_image_path(attempt: AttendanceAttempt, stage: str) -> Path | None:
    """Return the on-disk path for `stage` on `attempt`, or None if that
    stage wasn't generated for this attempt (debug mode off, or that
    scan/tier never ran for this particular capture)."""
    slot = next((s for s in attempt.stage_images if s.stage == stage), None)
    if slot is None or not slot.available or not slot.filename:
        return None

    path = Path(ATTENDANCE_DEBUG_OUTPUT_DIR) / attempt.id / f"{slot.filename}.jpg"
    return path if path.is_file() else None
