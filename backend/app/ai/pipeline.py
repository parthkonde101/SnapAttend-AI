"""Orchestrates the registration intelligence pipeline.

quality gate -> preprocessing -> ID detection -> barcode decode -> PRN
extraction (barcode first, ROI-cropped digit-priority OCR as fallback) ->
name extraction -> assembled into a single `RegistrationAnalysis`. Each
stage lives in its own module and is independently testable; this file
only wires them together and decides what happens when a stage fails or
is unavailable.

PRN priority order (highest confidence first):
  1. Barcode payload, if decoded and it validates as a plausible PRN
     (`app/ai/ocr.is_plausible_prn`) — cheap and precise when the card has
     a barcode, so it's tried before any OCR at all.
  2. Digit-priority OCR over a small, enhanced crop of the region most
     likely to contain the PRN (`app/ai/roi.locate_prn_candidates` — first
     anchored to the barcode's own location if one was found, then a set
     of generic, configurable fallback bands).
  3. Digit-priority OCR over the whole preprocessed image, as a last
     resort before falling back to the general-purpose OCR pass already
     used for the student's name.

Reliability note: no single stage may take the whole registration flow
down. Barcode decoding (`decode_barcode`) never raises by construction —
and the call site here wraps it again anyway, so registration survives
even a defect in that guarantee. Every other new stage introduced here
(card-bbox estimation, ROI cropping, region preprocessing, digit OCR) is
wrapped so a failure just means "try the next fallback," never an
exception bubbling out of this function. If the OCR engine isn't
installed, fails to load, or throws mid-extraction, this pipeline still
returns a valid `RegistrationAnalysis` with empty PRN/name fields and a
warning telling the student to enter them manually.

Diagnostics hook: the optional `recorder` parameter lets a developer
diagnostics observer (`app/diagnostics/recorder.py`) watch what this
function does, for tuning purposes. This module never imports
`app.diagnostics` and the parameter is duck-typed (called defensively,
guarded by `if recorder:`), so `app.ai` stays fully self-contained and a
missing/None recorder is a complete no-op — zero behavioural or
performance difference from before this hook existed.
"""
from __future__ import annotations

import io
import secrets
import time
from pathlib import Path
from typing import Any

from PIL import Image

from app.ai import config
from app.ai.barcode import decode_barcode
from app.ai.detector import detect_id_card, estimate_card_bbox
from app.ai.ocr import OcrEngine, get_ocr_engine, is_plausible_prn
from app.ai.preprocess import preprocess_for_ocr, preprocess_prn_region
from app.ai.quality import check_image_quality
from app.ai.roi import crop_region, locate_prn_candidates
from app.ai.schemas import BarcodeResult, OcrField, OcrResult, RegistrationAnalysis


def analyze_registration_photo(
    image_bytes: bytes,
    storage_dir: Path,
    *,
    recorder: Any = None,
) -> RegistrationAnalysis:
    """Run the full pipeline against a freshly captured registration photo.

    `storage_dir` is where the image is persisted — and only when quality
    passes. Poor quality captures are never written to disk.

    `recorder`, if given, must duck-type the (undeclared, intentionally
    loose) interface implemented by `app.diagnostics.recorder.DiagnosticsRecorder`:
    `log`, `record_quality`, `record_barcode`, `record_engine`,
    `record_roi_count`, `record_candidate`, `record_chosen`,
    `record_ocr_timing`, `record_available_images`, `set_image_id`. Every
    call site below is guarded so a caller that passes `None` (the
    default) skips all of this work entirely.
    """
    image_id = secrets.token_hex(16)
    if recorder:
        recorder.set_image_id(image_id)
        recorder.log("Capture Started")

    quality_start = time.monotonic()
    quality = check_image_quality(image_bytes)
    if recorder:
        recorder.record_quality(quality, elapsed_ms=(time.monotonic() - quality_start) * 1000)

    debug_stages: dict[str, Image.Image] = {}
    if config.DEBUG_SAVE_INTERMEDIATES:
        try:
            debug_stages["00_original"] = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        except Exception:
            pass

    if not quality.passed:
        if recorder:
            recorder.log("Quality Check Failed", ", ".join(quality.messages) or None)
            recorder.record_available_images(debug_stages.keys())
        if config.DEBUG_SAVE_INTERMEDIATES:
            _save_debug_artifacts(image_id, debug_stages)
        return RegistrationAnalysis(
            quality_passed=False,
            quality_messages=quality.messages,
            id_detected=False,
            warnings=[],
        )

    if recorder:
        recorder.log("Quality Check Passed")

    warnings: list[str] = []

    try:
        image = preprocess_for_ocr(image_bytes)
    except Exception:
        warnings.append("Could not preprocess the image; using the original capture.")
        image = Image.open(io.BytesIO(image_bytes)).convert("RGB")

    if config.DEBUG_SAVE_INTERMEDIATES:
        # "Perspective corrected" stage — currently an identity transform
        # (see preprocess.correct_perspective), but the pipeline shape and
        # this debug hook already match what a real implementation needs.
        debug_stages["01_preprocessed"] = image

    detection = detect_id_card(image)
    if not detection.id_detected:
        warnings.append("Could not clearly detect an ID card in the frame.")

    try:
        card_bbox = estimate_card_bbox(image)
    except Exception:
        card_bbox = None

    # --- Barcode decode, BEFORE any OCR ------------------------------------
    # `decode_barcode` already guarantees it never raises; this try/except
    # is defense-in-depth so a defect in that guarantee still can't take
    # registration down — barcode decoding must never be a hard dependency.
    if recorder:
        recorder.log("Barcode Detection")
    barcode_start = time.monotonic()
    try:
        barcode_result = decode_barcode(image)
    except Exception as exc:
        barcode_result = BarcodeResult(
            decoded=False, attempted=True, status="failed", failure_reason=f"Unexpected barcode error ({exc})."
        )
    barcode_elapsed_ms = (time.monotonic() - barcode_start) * 1000

    if config.DEBUG_SAVE_INTERMEDIATES and barcode_result.rect is not None:
        try:
            left, top, bar_w, bar_h = barcode_result.rect
            debug_stages["02_barcode_region"] = crop_region(image, (left, top, left + bar_w, top + bar_h))
        except Exception:
            pass

    engine: OcrEngine = get_ocr_engine()

    prn_field = OcrField()
    used_barcode_for_prn = False
    if barcode_result.decoded and barcode_result.data and is_plausible_prn(barcode_result.data):
        prn_field = OcrField(value=barcode_result.data.strip(), confidence=0.95)
        used_barcode_for_prn = True

    if recorder:
        recorder.record_barcode(barcode_result, used_as_prn=used_barcode_for_prn, elapsed_ms=barcode_elapsed_ms)
        recorder.log(
            "Barcode Success" if barcode_result.decoded else ("Barcode Failed" if barcode_result.attempted else "Barcode Not Attempted"),
            barcode_result.failure_reason,
        )
        recorder.record_engine(type(engine).__name__)

    ocr_start = time.monotonic()

    # --- Whole-card OCR pass: always run, drives name + raw_text, and is
    # the final PRN fallback if barcode + ROI extraction both come up empty.
    if recorder:
        recorder.log("OCR")
    try:
        ocr_result = engine.extract(image)
    except Exception:
        warnings.append("OCR engine is unavailable — enter your PRN and name manually.")
        ocr_result = OcrResult()

    if recorder and ocr_result.prn.value:
        recorder.record_candidate(source="whole_image", region_index=None, field=ocr_result.prn, near_label=None)

    # --- ROI-based, digit-priority PRN extraction (only if barcode didn't
    # already give us a trustworthy identifier). Registration must never
    # fail here — every stage is wrapped and simply moves to the next
    # fallback on error.
    chosen_source: str | None = "barcode" if used_barcode_for_prn else None

    if not used_barcode_for_prn:
        try:
            candidates = locate_prn_candidates(image, barcode_rect=barcode_result.rect, card_bbox=card_bbox)
        except Exception:
            candidates = []

        if recorder:
            recorder.log("ROI Detection", f"{len(candidates)} candidate region(s)")
            recorder.record_roi_count(len(candidates))

        # Collect a candidate pool rather than taking the first non-empty
        # result: an ROI crop with no label context can still yield *a*
        # digit run (e.g. part of a validity date), so it must compete on
        # score against the whole-card OCR pass, which already has label
        # context and may well be the better answer.
        prn_candidates: list[OcrField] = []
        candidate_sources: list[str] = []
        if ocr_result.prn.value:
            prn_candidates.append(ocr_result.prn)
            candidate_sources.append("whole_image")

        for idx, box in enumerate(candidates):
            # Zero-padded to match the debug_stages filenames below
            # (f"roi_{idx:02d}_crop"/"_enhanced") exactly — recorder.py's
            # `_resolve_stage_images` derives the winning candidate's debug
            # filenames straight from this source string, so any mismatch
            # here means "PRN Region"/"Enhanced PRN"/"Final OCR Input" never
            # resolve even when an ROI candidate wins and its images were
            # genuinely saved to disk.
            source = f"roi_{idx:02d}"
            try:
                crop = crop_region(image, box)
                enhanced = preprocess_prn_region(crop, upscale_factor=config.PRN_UPSCALE_FACTOR)
                if config.DEBUG_SAVE_INTERMEDIATES:
                    debug_stages[f"roi_{idx:02d}_crop"] = crop
                    debug_stages[f"roi_{idx:02d}_enhanced"] = enhanced
                field = engine.extract_digits(enhanced)
            except Exception:
                continue
            if recorder and field.value:
                recorder.record_candidate(source=source, region_index=idx, field=field)
            if field.value:
                prn_candidates.append(field)
                candidate_sources.append(source)

        if prn_candidates:
            best_idx = max(range(len(prn_candidates)), key=lambda i: prn_candidates[i].confidence or 0.0)
            prn_field = prn_candidates[best_idx]
            chosen_source = candidate_sources[best_idx]

        if prn_field.value is None:
            # Last resort before giving up entirely: a digit-priority pass
            # over the whole preprocessed image.
            if recorder:
                recorder.log("Candidate Scoring", "No ROI/whole-image candidate found — trying whole-image digit pass.")
            try:
                prn_field = engine.extract_digits(image)
                if prn_field.value:
                    chosen_source = "whole_image_digits"
                    if recorder:
                        recorder.record_candidate(source=chosen_source, region_index=None, field=prn_field)
            except Exception:
                prn_field = OcrField()
        elif recorder:
            recorder.log("Candidate Scoring", f"Chosen: {chosen_source}")

    if recorder:
        recorder.record_chosen(chosen_source)
        recorder.record_ocr_timing((time.monotonic() - ocr_start) * 1000)

    if prn_field.value is None:
        warnings.append("Could not read a PRN automatically. Please enter it manually.")
    if ocr_result.student_name.value is None:
        warnings.append("Could not read your name automatically. Please enter it manually.")

    image_reference = _persist_image(image, storage_dir, image_id)

    if config.DEBUG_SAVE_INTERMEDIATES:
        _save_debug_artifacts(image_id, debug_stages)
    if recorder:
        recorder.record_available_images(debug_stages.keys())
        recorder.log("Registration Complete")

    return RegistrationAnalysis(
        quality_passed=True,
        quality_messages=quality.messages,
        id_detected=detection.id_detected,
        barcode=barcode_result.data,
        barcode_type=barcode_result.symbology,
        barcode_status=barcode_result.status,
        barcode_failure_reason=barcode_result.failure_reason,
        prn=prn_field.value,
        student_name=ocr_result.student_name.value,
        warnings=warnings,
        raw_text=ocr_result.raw_text,
        image_reference=image_reference,
    )


def _persist_image(image: Image.Image, storage_dir: Path, image_id: str) -> str:
    """Save the (already quality-approved) capture and return an opaque id."""
    storage_dir.mkdir(parents=True, exist_ok=True)
    image.convert("RGB").save(storage_dir / f"{image_id}.jpg", format="JPEG", quality=90)
    return image_id


def _save_debug_artifacts(image_id: str, stages: dict[str, Image.Image]) -> None:
    """Development-only: dump every intermediate stage to a per-capture
    debug folder for tuning the pipeline against real ID cards.

    Only called when `SNAPATTEND_AI_DEBUG` is explicitly enabled
    (`app/ai/config.DEBUG_SAVE_INTERMEDIATES`) — never required in
    production, and a failure here must never affect the actual
    registration result, hence the blanket try/except.
    """
    if not stages:
        return
    debug_dir = Path(config.DEBUG_OUTPUT_DIR) / image_id
    try:
        debug_dir.mkdir(parents=True, exist_ok=True)
        for name, stage_image in stages.items():
            stage_image.convert("RGB").save(debug_dir / f"{name}.jpg", format="JPEG", quality=90)
    except Exception:
        pass
