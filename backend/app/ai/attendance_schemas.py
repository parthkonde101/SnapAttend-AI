"""Pydantic schemas for the Attendance Verification Engine (V1).

Kept separate from `app/ai/schemas.py` (the registration pipeline's
contract, not touched by this milestone) for the same reason that file is
separate from `app/schemas`: a clean boundary between what each pipeline
returns. `app.ai.attendance_pipeline` and `app.ai.display` import shared
primitives (`OcrField`, `BarcodeResult`, `QualityCheckResult`,
`DetectionResult`) from `app/ai/schemas.py` — reusing those types, not
redefining them — but every attendance-specific shape lives here.
"""
from __future__ import annotations

from pydantic import BaseModel, Field


class DisplayRegionCandidate(BaseModel):
    """One dark, blob-shaped connected component `app.ai.display` considered
    as a candidate "display panel" (projector/monitor showing the marker)
    within a search region — evaluated by pure geometry (area, how filled/
    rectangular the blob is, aspect ratio) before any OCR runs. Recorded
    whether accepted or rejected, so a developer can see exactly why a
    scene did or didn't resolve to a display region.
    """

    rect: tuple[int, int, int, int] = Field(description="(left, top, width, height) in full-scene coordinates.")
    area: int = Field(description="Actual dark-pixel count in the component, not just its bounding-box area.")
    fill_ratio: float = Field(description="area / (bbox width * height) — how rectangular/filled the blob is.")
    mean_brightness: float = Field(description="Mean grayscale value (0-255) inside the bounding box.")
    accepted: bool = Field(default=False, description="True if this candidate passed every geometric filter.")
    rejection_reason: str | None = Field(default=None, description="Why this candidate was rejected, if it was.")


class GlyphCandidate(BaseModel):
    """One *merged group* of bright connected components found inside an
    accepted display region — a candidate for the actual marker glyph.

    Real captures showed a single displayed character is frequently split
    into several disconnected bright components by sensor noise/JPEG
    compression (confirmed against real attendance captures, not assumed),
    so a candidate here is never a single raw component in isolation: every
    nearby raw component is merged into one group first (by proximity —
    see `app.ai.attendance_config.MARKER_GLYPH_MERGE_GAP_RATIO`), and this
    object describes that merged group's union bounding box. `rect`/`area`
    are the union box and summed pixel area across every member component;
    `member_count` says how many raw fragments were merged into it (1 if a
    component had no close neighbors — a clean, unfragmented glyph).
    Geometric filters (height relative to the display region, aspect
    ratio, absolute area) are evaluated against the *merged* group, which
    is what actually rejects tiny OCR noise before OCR ever runs — a group
    that's still too small/oddly-shaped even after merging cannot
    physically be the displayed marker.
    """

    rect: tuple[int, int, int, int] = Field(description="Union bounding box (left, top, width, height) in full-scene coordinates.")
    area: int = Field(description="Summed bright-pixel count across every merged component.")
    aspect_ratio: float = Field(description="bbox width / bbox height.")
    height_ratio: float = Field(description="bbox height / the display region's own height.")
    fill_ratio: float = Field(
        description="area / (bbox width * height) — how densely the union bbox is filled. Recorded for "
        "inspection only, not used as an accept/reject filter: real glyphs (hollow letterforms, thin "
        "strokes) and noise-bridged chains were found to occupy an overlapping range in practice."
    )
    edge_density: float = Field(description="Fraction of the bbox that is a strong gradient edge — near 0 for flat noise blobs.")
    member_count: int = Field(default=1, description="How many raw connected components were merged into this group.")
    accepted: bool = Field(default=False, description="True if this candidate passed every geometric filter.")
    rejection_reason: str | None = Field(default=None, description="Why this candidate was rejected, if it was.")
    selected: bool = Field(default=False, description="True for the single candidate actually normalized and sent to OCR.")


class MarkerScanAttempt(BaseModel):
    """One full geometry-then-OCR pass over one search region (the primary
    region, then a wider fallback region if the primary search resolves to
    nothing) — the complete evidence trail for that pass: the search crop,
    every display-region candidate considered, the accepted display crop
    (if any), every merged glyph-group candidate considered inside it, the
    final normalized glyph image actually handed to OCR (if any), and the
    raw OCR outcome.
    """

    tier: str = Field(description="'primary' or 'fallback' — which search region this pass covered.")
    fractional_box: tuple[float, float, float, float] = Field(description="(left, top, right, bottom) as fractions of the full scene.")
    pixel_box: tuple[int, int, int, int] = Field(description="Same region in absolute pixel coordinates of the full scene.")
    search_stage_image_key: str | None = Field(default=None, description="Key for this pass's full search-region crop.")
    display_regions: list[DisplayRegionCandidate] = Field(default_factory=list)
    display_stage_image_key: str | None = Field(default=None, description="Key for the accepted display-region crop, if one was found.")
    glyph_candidates: list[GlyphCandidate] = Field(default_factory=list)
    glyph_stage_image_key: str | None = Field(default=None, description="Key for the tight (un-normalized) merged glyph crop, if any.")
    glyph_normalized_stage_image_key: str | None = Field(
        default=None, description="Key for the final normalized glyph image actually sent to OCR, if any."
    )
    ocr_text: str | None = Field(default=None, description="Raw text Tesseract returned for the normalized glyph, before whitelist/validation.")
    ocr_confidence: float | None = Field(default=None, description="Tesseract's own confidence for ocr_text, 0-1.")
    outcome: str = Field(description="Human-readable summary of what happened in this pass, e.g. why it did or didn't produce a marker.")


class DisplayMarkerResult(BaseModel):
    """Output of `app.ai.display.detect_attendance_marker`.

    Optional and best-effort like `BarcodeResult` in the registration
    pipeline: if no marker is found, the caller gets `detected=False` and
    the attendance verification simply fails with a clear reason — nothing
    downstream ever crashes because of this.

    `scans` is the full evidence trail: every search region tried, the
    geometric display/glyph reasoning within each one, and the crop that
    was (or wasn't) finally handed to OCR — see
    `app.diagnostics.attendance_recorder` for how this gets surfaced in the
    diagnostics UI.
    """

    detected: bool
    character: str | None = None
    confidence: float | None = None
    attempted: bool = True
    failure_reason: str | None = None
    rect: tuple[int, int, int, int] | None = Field(
        default=None, description="Marker bounding box (left, top, width, height) in the analyzed scene. Development use."
    )
    display_detected: bool = Field(
        default=False,
        description=(
            "True if a glyph-shaped bright region was geometrically isolated inside a plausible display "
            "panel in *any* scanned tier — independent of whether OCR then managed to read a character "
            "from it. This is the 'was a classroom display actually photographed' signal the verification "
            "service weighs on its own; see app.ai.attendance_config's display-confidence-tier block."
        ),
    )
    display_confidence: float = Field(
        default=0.0,
        description=(
            "0.0/0.3/0.6/1.0 — which geometric evidence tier the strongest scan across all tiers reached "
            "(none / display-panel-only / glyph-isolated / OCR-read-a-character). See "
            "app.ai.attendance_config.MARKER_DISPLAY_CONFIDENCE_*."
        ),
    )
    scans: list[MarkerScanAttempt] = Field(default_factory=list, description="Development use.")


class IdentityExtraction(BaseModel):
    """Result of extracting a PRN from the ID card region of the captured
    scene. Pure extraction — no opinion about whether it belongs to the
    student making the request. `app.ai` never imports `app.models` (same
    isolation rule the registration pipeline follows), so it has no way to
    look a PRN up against the `students` table at all; that comparison —
    including the important anti-fraud check that the extracted PRN
    belongs to the *authenticated* student, not just *some* registered
    student — happens in `app.services.attendance_verification_service`,
    which has both this extraction result and the authenticated student
    record available.
    """

    extracted_prn: str | None = None
    source: str | None = Field(default=None, description="'barcode' or 'ocr', whichever produced extracted_prn.")
    failure_reason: str | None = None


class AttendanceEvidence(BaseModel):
    """Structured output of the Attendance Verification Engine's extraction
    pipeline (`app.ai.attendance_pipeline.extract_attendance_evidence`).

    Deliberately *evidence only* — this schema has no `verified` field and
    no knowledge of a specific student or session, matching the isolation
    rule that keeps `app.ai` free of any dependency on `app.models`/`app.api`.
    `app.services.attendance_verification_service` turns this evidence
    (plus the authenticated student + active session, both DB-aware
    concerns) into an actual pass/fail decision. This mirrors
    `RegistrationAnalysis`'s role in the registration pipeline: the only
    shape any stage of this pipeline returns, never a bare dict.
    """

    quality_passed: bool
    quality_messages: list[str] = Field(default_factory=list)
    id_detected: bool

    identity: IdentityExtraction = Field(default_factory=IdentityExtraction)
    marker: DisplayMarkerResult = Field(default_factory=lambda: DisplayMarkerResult(detected=False, attempted=False))

    warnings: list[str] = Field(default_factory=list)
    image_reference: str | None = Field(
        default=None, description="Opaque id of the stored capture, only set when quality_passed is true."
    )
    processing_time_ms: float | None = None

    # Generic, opaque passthrough for developer diagnostics — mirrors
    # `RegistrationAnalysis.diagnostics_attempt_id`. `app.ai` never sets
    # this itself; the attendance endpoint sets it after recording an
    # attempt via `app.diagnostics.attendance_recorder`.
    diagnostics_attempt_id: str | None = Field(default=None, description="Development use.")
