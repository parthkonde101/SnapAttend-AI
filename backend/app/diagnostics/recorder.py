"""Diagnostics recorder — an observer that `app.ai.pipeline` optionally
reports to.

Design goal: `app.ai.pipeline` must never depend on this module (it
doesn't import it — see `app/ai/pipeline.py`'s `recorder` parameter, typed
generically and called defensively). This class exists purely to receive
simple, factual method calls ("here's the quality result", "here's a
candidate we considered") and turn them into a `RegistrationAttempt` for
display. It never returns anything the pipeline reacts to, so it cannot
change pipeline behaviour, by construction.

Usage (from `app/api/v1/endpoints/registration.py`):
    recorder = DiagnosticsRecorder() if is_diagnostics_enabled() else None
    analysis = analyze_registration_photo(contents, storage_dir, recorder=recorder)
    if recorder is not None:
        attempt = recorder.finalize(analysis, image_id=analysis.image_reference, attempt_number=...)
        diagnostics_store.add(attempt)
"""
from __future__ import annotations

import time
from datetime import datetime, timezone

from app.ai.config import PRN_MAX_LENGTH, PRN_MIN_LENGTH
from app.ai.schemas import BarcodeResult, OcrField, QualityCheckResult, RegistrationAnalysis
from app.diagnostics.schemas import (
    BarcodeDiagnostics,
    FinalResultDiagnostics,
    OcrCandidateDiagnostics,
    OcrDiagnostics,
    PipelineLogEntry,
    QualityDiagnostics,
    RegistrationAttempt,
    StageImageInfo,
)

# Static stage-image slots map 1:1 to a fixed debug filename pipeline.py
# always uses (when it uses one at all). Kept here, not in app.ai, since
# naming/labeling for display is purely a diagnostics concern.
_STATIC_STAGE_SLOTS: tuple[tuple[str, str, str], ...] = (
    ("original", "Original Image", "00_original"),
    ("preprocessed", "Perspective Corrected", "01_preprocessed"),
    ("barcode_region", "Barcode Region", "02_barcode_region"),
)


def _score_breakdown(value: str | None) -> tuple[float | None, float | None]:
    """Best-effort digit/pattern score breakdown for display purposes,
    recomputed from the candidate string alone rather than reaching into
    `app.ai.ocr`'s private combined-score internals."""
    if not value:
        return None, None
    digit_score = sum(ch.isdigit() for ch in value) / len(value)
    pattern_score = 1.0 if PRN_MIN_LENGTH <= len(value) <= PRN_MAX_LENGTH else 0.0
    return round(digit_score, 3), round(pattern_score, 3)


class DiagnosticsRecorder:
    def __init__(self) -> None:
        self._start = time.monotonic()
        self._log: list[PipelineLogEntry] = []
        self._quality: QualityDiagnostics | None = None
        self._barcode: BarcodeDiagnostics | None = None
        self._engine_name: str | None = None
        self._roi_count = 0
        self._candidates: list[OcrCandidateDiagnostics] = []
        self._chosen_source: str | None = None
        self._available_images: set[str] = set()
        self._ocr_elapsed_ms: float | None = None
        self._image_id: str | None = None

    def set_image_id(self, image_id: str) -> None:
        self._image_id = image_id

    def record_ocr_timing(self, elapsed_ms: float) -> None:
        self._ocr_elapsed_ms = round(elapsed_ms, 2)

    # --- Section 6: pipeline log ------------------------------------------
    def log(self, step: str, message: str | None = None) -> None:
        self._log.append(
            PipelineLogEntry(
                step=step,
                message=message,
                timestamp=datetime.now(timezone.utc),
                elapsed_ms=round((time.monotonic() - self._start) * 1000, 2),
            )
        )

    # --- Section 1: image quality -------------------------------------------
    def record_quality(
        self,
        quality: QualityCheckResult,
        *,
        elapsed_ms: float,
    ) -> None:
        self._quality = QualityDiagnostics(
            width=quality.width,
            height=quality.height,
            resolution_ok=quality.resolution_ok,
            blur_score=quality.blur_score,
            blur_ok=quality.blur_ok,
            brightness=quality.brightness,
            brightness_ok=quality.brightness_ok,
            contrast=quality.contrast,
            glare_ratio=quality.glare_ratio,
            glare_ok=quality.glare_ok,
            coverage_ok=quality.coverage_ok,
            passed=quality.passed,
            messages=list(quality.messages),
            processing_time_ms=round(elapsed_ms, 2),
        )

    # --- Section 2: barcode -------------------------------------------------
    def record_barcode(self, barcode: BarcodeResult, *, used_as_prn: bool, elapsed_ms: float) -> None:
        self._barcode = BarcodeDiagnostics(
            attempted=barcode.attempted,
            status=barcode.status,
            decoded=barcode.decoded,
            barcode_type=barcode.symbology,
            decoded_value=barcode.data,
            failure_reason=barcode.failure_reason,
            used_as_prn=used_as_prn,
            processing_time_ms=round(elapsed_ms, 2),
        )

    # --- Section 3: OCR -------------------------------------------------------
    def record_engine(self, name: str) -> None:
        self._engine_name = name

    def record_roi_count(self, count: int) -> None:
        self._roi_count = count

    def record_candidate(
        self,
        *,
        source: str,
        region_index: int | None,
        field: OcrField,
        near_label: bool | None = None,
    ) -> None:
        digit_score, pattern_score = _score_breakdown(field.value)
        self._candidates.append(
            OcrCandidateDiagnostics(
                source=source,
                region_index=region_index,
                value=field.value,
                confidence=field.confidence,
                digit_score=digit_score,
                pattern_score=pattern_score,
                near_label=near_label,
                chosen=False,
            )
        )

    def record_chosen(self, source: str | None) -> None:
        self._chosen_source = source
        for candidate in self._candidates:
            candidate.chosen = source is not None and candidate.source == source

    # --- Section 5: pipeline images ------------------------------------------
    def record_available_images(self, names) -> None:
        """`names` is whatever keys `pipeline.py`'s `debug_stages` dict
        ended up with — only populated at all when `SNAPATTEND_AI_DEBUG=1`."""
        self._available_images = set(names)

    # --- assembly --------------------------------------------------------------
    def finalize(self, analysis: RegistrationAnalysis, *, attempt_number: int) -> RegistrationAttempt:
        chosen = next((c for c in self._candidates if c.chosen), None)
        image_id = self._image_id or f"attempt-{attempt_number}"

        if self._barcode is not None and self._barcode.used_as_prn:
            prn_source: str = "barcode"
        elif analysis.prn:
            prn_source = "ocr"
        else:
            prn_source = "none"

        ocr = OcrDiagnostics(
            engine=self._engine_name,
            roi_detected=self._roi_count > 0,
            roi_count=self._roi_count,
            candidates=self._candidates,
            chosen_candidate=chosen,
            final_prn=analysis.prn,
            processing_time_ms=self._ocr_elapsed_ms,
        )

        final = FinalResultDiagnostics(
            verified_name=analysis.student_name,
            verified_prn=analysis.prn,
            prn_source=prn_source,
            registration_completed=False,
            warnings=list(analysis.warnings),
        )

        return RegistrationAttempt(
            id=image_id,
            attempt_number=attempt_number,
            created_at=datetime.now(timezone.utc),
            quality=self._quality or QualityDiagnostics(),
            barcode=self._barcode or BarcodeDiagnostics(),
            ocr=ocr,
            final=final,
            log=self._log,
            stage_images=self._resolve_stage_images(),
            id_detected=analysis.id_detected,
        )

    def _resolve_stage_images(self) -> list[StageImageInfo]:
        images = [
            StageImageInfo(stage=stage, label=label, filename=filename, available=filename in self._available_images)
            for stage, label, filename in _STATIC_STAGE_SLOTS
        ]

        crop_filename = enhanced_filename = None
        if self._chosen_source and self._chosen_source.startswith("roi_"):
            idx = self._chosen_source.split("_", 1)[1]
            candidate_crop = f"roi_{idx}_crop"
            candidate_enhanced = f"roi_{idx}_enhanced"
            if candidate_crop in self._available_images:
                crop_filename = candidate_crop
            if candidate_enhanced in self._available_images:
                enhanced_filename = candidate_enhanced

        images.append(StageImageInfo(stage="prn_region", label="PRN Region", filename=crop_filename, available=crop_filename is not None))
        images.append(
            StageImageInfo(stage="enhanced_prn", label="Enhanced PRN", filename=enhanced_filename, available=enhanced_filename is not None)
        )
        images.append(
            StageImageInfo(
                stage="final_ocr_input", label="Final OCR Input", filename=enhanced_filename, available=enhanced_filename is not None
            )
        )
        return images
