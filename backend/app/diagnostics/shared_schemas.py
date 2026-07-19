"""Shared diagnostics building blocks.

These models used to live in the registration-diagnostics-only
`app/diagnostics/schemas.py`, removed along with the registration flow
itself. They're pulled out here because the *attendance* diagnostics
subsystem (`app/diagnostics/attendance_schemas.py`,
`app/diagnostics/attendance_recorder.py`) also depends on them — quality
gate and pipeline-log reporting are generic, pipeline-agnostic concerns.

Milestone (marker-only attendance capture): `BarcodeDiagnostics` used to
live here too, shared between the registration pipeline and the attendance
identity-extraction stage. Both are gone, and nothing else ever used it, so
it was deleted along with them rather than kept around unused.
"""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class PipelineLogEntry(BaseModel):
    """One line of a pipeline's step-by-step diagnostic log."""

    step: str
    message: str | None = None
    timestamp: datetime
    elapsed_ms: float


class QualityDiagnostics(BaseModel):
    """Pre-OCR image quality gate diagnostics."""

    width: int | None = None
    height: int | None = None
    resolution_ok: bool = False
    blur_score: float | None = None
    blur_ok: bool = False
    brightness: float | None = None
    brightness_ok: bool = False
    contrast: float | None = None
    glare_ratio: float | None = None
    glare_ok: bool = False
    coverage_ok: bool = False
    passed: bool = False
    messages: list[str] = Field(default_factory=list)
    processing_time_ms: float | None = None


class StageImageInfo(BaseModel):
    """One entry in a pipeline's "stage images" debug list."""

    stage: str
    label: str
    filename: str | None = Field(default=None, description="Debug filename (no extension), internal use.")
    available: bool = False
