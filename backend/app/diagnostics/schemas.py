"""Pydantic schemas for the developer diagnostics layer.

Describes how a *past pipeline run* is displayed to a developer — this is
a display/reporting concern, deliberately kept separate from
`app.ai.schemas` (which describes the pipeline's actual production
contract). Nothing in `app.ai` depends on anything defined here.
"""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

PrnSource = Literal["barcode", "ocr", "manual", "none"]
BarcodeStatusLiteral = Literal["not_attempted", "decoded", "not_found", "failed"]


class PipelineLogEntry(BaseModel):
    """One line of Section 6 ("Pipeline Log")."""

    step: str
    message: str | None = None
    timestamp: datetime
    elapsed_ms: float


class QualityDiagnostics(BaseModel):
    """Section 1 ("Image Quality")."""

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


class BarcodeDiagnostics(BaseModel):
    """Section 2 ("Barcode")."""

    attempted: bool = False
    status: BarcodeStatusLiteral = "not_attempted"
    decoded: bool = False
    barcode_type: str | None = None
    decoded_value: str | None = None
    failure_reason: str | None = None
    used_as_prn: bool = False
    processing_time_ms: float | None = None


class OcrCandidateDiagnostics(BaseModel):
    """One entry in Section 3's candidate list (whole-image pass, or one
    ROI region's digit-priority pass)."""

    source: str
    region_index: int | None = None
    value: str | None = None
    confidence: float | None = None
    digit_score: float | None = None
    pattern_score: float | None = None
    near_label: bool | None = None
    chosen: bool = False


class OcrDiagnostics(BaseModel):
    """Section 3 ("OCR")."""

    engine: str | None = None
    roi_detected: bool = False
    roi_count: int = 0
    candidates: list[OcrCandidateDiagnostics] = Field(default_factory=list)
    chosen_candidate: OcrCandidateDiagnostics | None = None
    final_prn: str | None = None
    processing_time_ms: float | None = None


class FinalResultDiagnostics(BaseModel):
    """Section 4 ("Final Result")."""

    verified_name: str | None = None
    verified_prn: str | None = None
    prn_source: PrnSource = "none"
    registration_completed: bool = False
    warnings: list[str] = Field(default_factory=list)


class StageImageInfo(BaseModel):
    """One entry in Section 5 ("Pipeline Images")."""

    stage: str
    label: str
    filename: str | None = Field(default=None, description="Debug filename (no extension), internal use.")
    available: bool = False


class RegistrationAttempt(BaseModel):
    """Full diagnostic record of one `/registration/analyze` pipeline run
    (plus whatever `/registration/verify` later confirms, if anything)."""

    id: str
    attempt_number: int
    created_at: datetime

    quality: QualityDiagnostics = Field(default_factory=QualityDiagnostics)
    barcode: BarcodeDiagnostics = Field(default_factory=BarcodeDiagnostics)
    ocr: OcrDiagnostics = Field(default_factory=OcrDiagnostics)
    final: FinalResultDiagnostics = Field(default_factory=FinalResultDiagnostics)
    log: list[PipelineLogEntry] = Field(default_factory=list)
    stage_images: list[StageImageInfo] = Field(default_factory=list)

    id_detected: bool = False


class RegistrationAttemptSummary(BaseModel):
    """Row shown in the Developer Diagnostics history list."""

    id: str
    attempt_number: int
    created_at: datetime
    student_name: str | None = None
    prn: str | None = None
    prn_source: PrnSource = "none"
    barcode_success: bool = False
    quality_passed: bool = False
    registration_completed: bool = False
