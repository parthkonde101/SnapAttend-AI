"""Pydantic schemas shared across the AI package.

Kept separate from `app/schemas` so the AI package has no dependency on
the rest of the application. The API layer imports *from* here; nothing
in here imports from the API layer.
"""
from __future__ import annotations

from pydantic import BaseModel, Field


class QualityCheckResult(BaseModel):
    """Output of the pre-OCR image quality gate."""

    passed: bool
    messages: list[str] = Field(default_factory=list)
    resolution_ok: bool
    blur_ok: bool
    brightness_ok: bool
    glare_ok: bool
    coverage_ok: bool = True

    # --- Raw metric values (development use) ---------------------------------
    # None of these participate in `passed` — that's still decided purely
    # by the *_ok booleans above and the thresholds in quality.py. They're
    # surfaced only so developer diagnostics can show real numbers instead
    # of just pass/fail.
    width: int | None = Field(default=None, description="Development use.")
    height: int | None = Field(default=None, description="Development use.")
    blur_score: float | None = Field(default=None, description="Laplacian variance. Development use.")
    brightness: float | None = Field(default=None, description="Mean grayscale value (0-255). Development use.")
    contrast: float | None = Field(default=None, description="Grayscale standard deviation. Development use.")
    glare_ratio: float | None = Field(default=None, description="Fraction of blown-out (>=250) pixels. Development use.")


class DetectionResult(BaseModel):
    """Output of the (heuristic) ID-card presence detector."""

    id_detected: bool
    confidence: float = Field(ge=0.0, le=1.0)


class OcrField(BaseModel):
    """A single extracted field with an approximate confidence, if known."""

    value: str | None = None
    confidence: float | None = None


class OcrResult(BaseModel):
    """Output of the OCR engine. Only PRN and student name are extracted."""

    prn: OcrField = Field(default_factory=OcrField)
    student_name: OcrField = Field(default_factory=OcrField)
    raw_text: list[str] = Field(default_factory=list)


class BarcodeResult(BaseModel):
    """Output of barcode/QR decoding. Optional — never blocks registration."""

    decoded: bool
    data: str | None = None
    symbology: str | None = None
    attempted: bool = True
    status: str = Field(
        default="not_attempted",
        description="One of: not_attempted, decoded, not_found, failed. Set explicitly by decode_barcode, not re-derived downstream.",
    )
    failure_reason: str | None = None
    rect: tuple[int, int, int, int] | None = Field(
        default=None,
        description="Barcode bounding box (left, top, width, height) in the analyzed image, used internally to anchor PRN ROI search. Not part of the public API contract.",
    )


class RegistrationAnalysis(BaseModel):
    """Structured result of the full registration intelligence pipeline.

    This is the only shape the rest of the application ever sees — no
    stage of the pipeline returns a bare dict.
    """

    quality_passed: bool
    quality_messages: list[str] = Field(default_factory=list)
    id_detected: bool
    barcode: str | None = None
    prn: str | None = None
    student_name: str | None = None
    warnings: list[str] = Field(default_factory=list)
    raw_text: list[str] = Field(default_factory=list)
    image_reference: str | None = Field(
        default=None,
        description="Opaque id of the stored capture, only set when quality_passed is true.",
    )

    # --- Barcode debug info (development use) -------------------------------
    # Surfaced so the barcode step can be tuned/verified independently of
    # OCR. `barcode` above remains the single "did we get an identifier"
    # value the rest of the app cares about; these three exist purely to
    # make barcode decoding observable during development.
    barcode_type: str | None = Field(default=None, description="Decoded barcode symbology (e.g. CODE128, QRCODE). Development use.")
    barcode_status: str = Field(
        default="not_attempted",
        description="One of: not_attempted, decoded, not_found, failed. Development use.",
    )
    barcode_failure_reason: str | None = Field(
        default=None, description="Human-readable reason decoding didn't produce a usable value, if any. Development use."
    )

    # Generic, opaque passthrough — `app.ai` never sets this itself (it
    # stays None here always). The registration endpoint sets it after
    # recording a developer diagnostics attempt, purely so the frontend
    # has something to hand back to `/diagnostics/attempts/{id}`. Kept as
    # a plain optional string (not a diagnostics-specific type) so this
    # schema still has zero dependency on `app.diagnostics`.
    diagnostics_attempt_id: str | None = Field(default=None, description="Development use.")
