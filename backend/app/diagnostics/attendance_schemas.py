"""Pydantic schemas for the developer diagnostics layer — attendance.

Parallel to `app/diagnostics/schemas.py` (the registration diagnostics
contract, not touched by this milestone). Reuses that file's fully generic
building blocks (`QualityDiagnostics`, `BarcodeDiagnostics`,
`PipelineLogEntry`) by import — genuine reuse of the diagnostics framework,
per the spec — while every attendance-specific shape (identity match,
marker match, final verification decision) lives here, so nothing in the
registration diagnostics module needs to change to support a second,
unrelated pipeline.
"""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.diagnostics.schemas import BarcodeDiagnostics, PipelineLogEntry, QualityDiagnostics, StageImageInfo

VerificationSource = Literal["barcode", "ocr", "none"]


class AttendanceIdentityDiagnostics(BaseModel):
    """Section: ID verification — what the pipeline extracted from the
    card, and (once the service layer has compared it) whether it matched
    the authenticated student."""

    extracted_prn: str | None = None
    source: str | None = None
    matched_student_id: int | None = None
    identity_verified: bool = False
    failure_reason: str | None = None
    ocr_fallback_time_ms: float | None = Field(
        default=None, description="Time spent in the ROI/digit-priority OCR fallback path, when barcode decoding didn't apply."
    )


class DisplayRegionCandidateDiagnostics(BaseModel):
    """One dark connected-component candidate the detector considered as
    the display panel — geometry only, no OCR. Mirrors
    `app.ai.attendance_schemas.DisplayRegionCandidate` field-for-field."""

    rect: tuple[int, int, int, int]
    area: int
    fill_ratio: float
    mean_brightness: float
    accepted: bool = False
    rejection_reason: str | None = None


class GlyphCandidateDiagnostics(BaseModel):
    """One *merged group* of bright connected components the detector
    considered as the marker glyph, inside an accepted display region —
    geometry only, no OCR. Mirrors `app.ai.attendance_schemas.GlyphCandidate`
    field-for-field. `member_count` is how many raw connected components
    were merged into this group (real captures frequently split one
    displayed character into several disconnected fragments via sensor
    noise/JPEG compression — merging fixes the "isolating only a fragment"
    failure mode). `rejection_reason` is exactly why a too-small/
    wrong-shaped candidate was thrown out before OCR ever saw it."""

    rect: tuple[int, int, int, int]
    area: int
    aspect_ratio: float
    height_ratio: float
    fill_ratio: float
    edge_density: float
    member_count: int = 1
    accepted: bool = False
    rejection_reason: str | None = None
    selected: bool = False


class MarkerScanAttemptDiagnostics(BaseModel):
    """One full geometry-then-OCR pass over one search region (primary,
    then a wider fallback if the primary search resolved to nothing) — the
    complete evidence trail for that pass: the search crop, every
    display-region candidate considered, the accepted display crop (if
    any), every glyph candidate considered inside it, the final glyph crop
    actually sent to OCR (if any), and the raw OCR outcome. Mirrors
    `app.ai.attendance_schemas.MarkerScanAttempt` field-for-field."""

    tier: str
    fractional_box: tuple[float, float, float, float]
    pixel_box: tuple[int, int, int, int]
    search_stage_image_key: str | None = None
    display_regions: list[DisplayRegionCandidateDiagnostics] = Field(default_factory=list)
    display_stage_image_key: str | None = None
    glyph_candidates: list[GlyphCandidateDiagnostics] = Field(default_factory=list)
    glyph_stage_image_key: str | None = None
    glyph_normalized_stage_image_key: str | None = None
    ocr_text: str | None = None
    ocr_confidence: float | None = None
    outcome: str


class AttendanceMarkerDiagnostics(BaseModel):
    """Section: attendance display marker.

    `scans` is the full evidence trail — every search region the detector
    tried, its geometric display-panel and glyph reasoning (accepted and
    rejected candidates alike, with the reason), and the exact crop handed
    to OCR at the end of each pass — added specifically to diagnose
    "marker matching keeps failing" reports without guessing.
    `comparison_note` is a plain-English sentence explaining exactly why
    the final comparison passed or failed (e.g. "Detected 'Q' does not
    match expected 'G'." or "No marker character was detected in any
    scanned region."), computed once by
    `app.services.attendance_verification_service` (which is the only
    place that knows both the detected character and the session's actual
    marker) and handed to the recorder — never guessed at by this schema.
    """

    expected_marker: str | None = None
    detected_character: str | None = None
    confidence: float | None = None
    marker_verified: bool = False
    failure_reason: str | None = None
    processing_time_ms: float | None = None
    comparison_note: str | None = None
    scans: list[MarkerScanAttemptDiagnostics] = Field(default_factory=list)


class AttendanceFinalDiagnostics(BaseModel):
    """Section: final verification decision."""

    verified: bool = False
    reason: str | None = None
    verification_source: VerificationSource = "none"
    already_recorded: bool = False
    warnings: list[str] = Field(default_factory=list)


class AttendanceAttempt(BaseModel):
    """Full diagnostic record of one `/attendance/mark` pipeline run."""

    id: str
    attempt_number: int
    created_at: datetime
    student_id: int | None = None
    session_id: int | None = None

    quality: QualityDiagnostics = Field(default_factory=QualityDiagnostics)
    barcode: BarcodeDiagnostics = Field(default_factory=BarcodeDiagnostics)
    identity: AttendanceIdentityDiagnostics = Field(default_factory=AttendanceIdentityDiagnostics)
    marker: AttendanceMarkerDiagnostics = Field(default_factory=AttendanceMarkerDiagnostics)
    final: AttendanceFinalDiagnostics = Field(default_factory=AttendanceFinalDiagnostics)
    log: list[PipelineLogEntry] = Field(default_factory=list)
    stage_images: list[StageImageInfo] = Field(default_factory=list)

    id_detected: bool = False
    processing_time_ms: float | None = None


class AttendanceAttemptSummary(BaseModel):
    """Row shown in a future Developer Diagnostics history list for
    attendance — kept minimal for V1 (no dedicated history UI yet, but the
    store/endpoint contract is stable for one to attach to later)."""

    id: str
    attempt_number: int
    created_at: datetime
    student_id: int | None = None
    session_id: int | None = None
    extracted_prn: str | None = None
    detected_marker: str | None = None
    verified: bool = False
    verification_source: VerificationSource = "none"
