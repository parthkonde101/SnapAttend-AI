"""Orchestrates the Attendance Verification Engine's extraction pipeline.

quality gate -> preprocessing -> ID detection -> card-region isolation ->
barcode decode (primary) -> ROI-cropped digit-priority OCR (fallback) ->
independent display-marker detection -> assembled into a single
`AttendanceEvidence`. Every stage below is an *existing, unmodified*
`app.ai` module already proven by the registration pipeline
(`app/ai/pipeline.py`, not touched by this file) — this module only wires
them together against a wider, multi-object attendance scene instead of a
tightly-framed ID card photo, plus the new, independent
`app.ai.display` stage.

Reliability note, same discipline as `app/ai/pipeline.py`: no single stage
may take the whole attendance flow down. Every stage is wrapped so a
failure just means "record it as unavailable evidence," never an exception
bubbling out of this function.

Isolation note: like every other `app.ai` module, this file never imports
`app.models` / `app.api` / `app.services` — it has no concept of "the
authenticated student" or "the active session," only the pixels it was
handed. See `app/ai/attendance_schemas.AttendanceEvidence`'s docstring for
why: turning this evidence into an actual pass/fail decision is
`app.services.attendance_verification_service`'s job, not this pipeline's.

Diagnostics hook: identical pattern to `app/ai/pipeline.py` — the optional
`recorder` parameter is duck-typed and guarded by `if recorder:` at every
call site, so a missing/None recorder is a complete no-op.
"""
from __future__ import annotations

import io
import secrets
import time
from pathlib import Path
from typing import Any

from PIL import Image

from app.ai import attendance_config as config
from app.ai.attendance_schemas import AttendanceEvidence, IdentityExtraction
from app.ai.barcode import decode_barcode
from app.ai.config import DEBUG_SAVE_INTERMEDIATES, PRN_UPSCALE_FACTOR
from app.ai.detector import detect_id_card, estimate_card_bbox
from app.ai.display import detect_attendance_marker
from app.ai.ocr import get_ocr_engine, is_plausible_prn
from app.ai.preprocess import preprocess_for_ocr, preprocess_prn_region
from app.ai.quality import check_image_quality
from app.ai.roi import crop_region, locate_prn_candidates
from app.ai.schemas import BarcodeResult

Box = tuple[int, int, int, int]


def _fractional_crop(image: Image.Image, box: tuple[float, float, float, float]) -> tuple[Image.Image, Box]:
    """Same fractional-to-pixel cropping as `app.ai.display`, duplicated
    (not imported) to keep the identity and marker stages fully
    independent modules, per the spec — neither should need to change if
    the other's cropping logic ever does."""
    width, height = image.size
    left, top, right, bottom = box
    pixel_box = (
        max(0, min(width, round(left * width))),
        max(0, min(height, round(top * height))),
        max(0, min(width, round(right * width))),
        max(0, min(height, round(bottom * height))),
    )
    return image.crop(pixel_box), pixel_box


def extract_attendance_evidence(
    image_bytes: bytes,
    storage_dir: Path,
    *,
    recorder: Any = None,
) -> AttendanceEvidence:
    """Run the full attendance extraction pipeline against a freshly
    captured attendance scene.

    Unlike registration, the whole scene (ID card + classroom display +
    background) is preserved — nothing here crops the stored image down to
    just one object. `storage_dir` is where the *full scene* is persisted,
    and only when quality passes.
    """
    start = time.monotonic()
    image_id = secrets.token_hex(16)
    if recorder:
        recorder.set_image_id(image_id)
        recorder.log("Capture Started")

    quality_start = time.monotonic()
    quality = check_image_quality(image_bytes)
    if recorder:
        recorder.record_quality(quality, elapsed_ms=(time.monotonic() - quality_start) * 1000)

    # Evidence-driven fix: stage-image capture used to be gated *only* by
    # `DEBUG_SAVE_INTERMEDIATES` (SNAPATTEND_AI_DEBUG=1), a separate switch
    # from whether diagnostics recording is even happening
    # (`is_diagnostics_enabled()`, which is also true whenever
    # ENVIRONMENT=development, independent of SNAPATTEND_AI_DEBUG). That
    # meant a normal dev setup got full candidate/region diagnostics but
    # *zero* stage images — confirmed as the actual cause of "stage images
    # are empty" reports, not a rendering or endpoint bug. Whenever a
    # recorder is attached at all, the caller clearly wants to inspect this
    # attempt, so capture crops unconditionally in that case too.
    capture_debug_images = DEBUG_SAVE_INTERMEDIATES or recorder is not None
    debug_stages: dict[str, Image.Image] = {}

    if not quality.passed:
        if recorder:
            recorder.log("Quality Check Failed", ", ".join(quality.messages) or None)
        return AttendanceEvidence(quality_passed=False, quality_messages=quality.messages, id_detected=False)

    if recorder:
        recorder.log("Quality Check Passed")

    warnings: list[str] = []

    try:
        image = preprocess_for_ocr(image_bytes)
    except Exception:
        warnings.append("Could not preprocess the image; using the original capture.")
        image = Image.open(io.BytesIO(image_bytes)).convert("RGB")

    if capture_debug_images:
        debug_stages["00_original"] = image

    detection = detect_id_card(image)
    if not detection.id_detected:
        warnings.append("Could not clearly detect an ID card in the frame.")

    # --- Identity stage: scoped to the card region of the scene -----------
    # (see app/ai/attendance_config.CARD_REGION_BOX) so barcode/OCR only
    # ever see the ID card, never the classroom display or background.
    card_scene_crop, _ = _fractional_crop(image, config.CARD_REGION_BOX)
    try:
        sub_bbox = estimate_card_bbox(card_scene_crop)
    except Exception:
        sub_bbox = None
    id_card_image = crop_region(card_scene_crop, sub_bbox) if sub_bbox else card_scene_crop

    if capture_debug_images:
        debug_stages["01_card_region_crop"] = card_scene_crop
        debug_stages["02_id_card_refined"] = id_card_image

    if recorder:
        recorder.log("Barcode Detection")
    barcode_start = time.monotonic()
    try:
        barcode_result = decode_barcode(id_card_image)
    except Exception as exc:
        barcode_result = BarcodeResult(
            decoded=False, attempted=True, status="failed", failure_reason=f"Unexpected barcode error ({exc})."
        )
    barcode_elapsed_ms = (time.monotonic() - barcode_start) * 1000

    engine = get_ocr_engine()
    identity = IdentityExtraction()

    if barcode_result.decoded and barcode_result.data and is_plausible_prn(barcode_result.data):
        identity = IdentityExtraction(extracted_prn=barcode_result.data.strip(), source="barcode")
    else:
        if recorder:
            recorder.log("OCR Fallback")
        ocr_start = time.monotonic()
        try:
            candidates = locate_prn_candidates(id_card_image, barcode_rect=barcode_result.rect, card_bbox=None)
        except Exception:
            candidates = []

        best_value: str | None = None
        best_confidence = -1.0
        for box in candidates:
            try:
                crop = crop_region(id_card_image, box)
                enhanced = preprocess_prn_region(crop, upscale_factor=PRN_UPSCALE_FACTOR)
                field = engine.extract_digits(enhanced)
            except Exception:
                continue
            if field.value and (field.confidence or 0.0) > best_confidence:
                best_value = field.value
                best_confidence = field.confidence or 0.0

        if best_value is None:
            try:
                whole_card_field = engine.extract_digits(id_card_image)
                if whole_card_field.value:
                    best_value = whole_card_field.value
            except Exception:
                pass

        if best_value:
            identity = IdentityExtraction(extracted_prn=best_value.strip(), source="ocr")
        else:
            identity = IdentityExtraction(failure_reason="Could not read a PRN from the ID card.")
        if recorder:
            recorder.record_ocr_timing((time.monotonic() - ocr_start) * 1000)

    if recorder:
        recorder.record_barcode(barcode_result, used_as_prn=identity.source == "barcode", elapsed_ms=barcode_elapsed_ms)
        recorder.record_engine(type(engine).__name__)
        recorder.record_identity(identity)

    # --- Marker stage: fully independent of the identity stage above -----
    # `debug_stages` is only ever non-empty when capture_debug_images is
    # true (SNAPATTEND_AI_DEBUG=1 OR a recorder is attached — see above),
    # so this passes None the rest of the time — a complete no-op for
    # detect_attendance_marker, same as before this hook existed.
    if recorder:
        recorder.log("Marker Detection")
    marker_start = time.monotonic()
    try:
        marker = detect_attendance_marker(image, debug_stages=debug_stages if capture_debug_images else None)
    except Exception as exc:
        from app.ai.attendance_schemas import DisplayMarkerResult

        marker = DisplayMarkerResult(detected=False, attempted=True, failure_reason=f"Unexpected marker error ({exc}).")
    marker_elapsed_ms = (time.monotonic() - marker_start) * 1000

    if recorder:
        recorder.record_marker(marker, elapsed_ms=marker_elapsed_ms)
        recorder.log("Marker Found" if marker.detected else "Marker Not Found", marker.failure_reason)

    if identity.extracted_prn is None:
        warnings.append("Could not read your ID card. Please retry with better lighting/framing.")
    if not marker.detected:
        warnings.append("Could not read the classroom display marker. Please retry.")

    image_reference = _persist_image(image, storage_dir, image_id)
    processing_time_ms = (time.monotonic() - start) * 1000

    if capture_debug_images:
        _save_debug_artifacts(image_id, debug_stages)
    if recorder:
        recorder.record_available_images(debug_stages.keys())
        recorder.log("Evidence Extraction Complete")

    return AttendanceEvidence(
        quality_passed=True,
        quality_messages=quality.messages,
        id_detected=detection.id_detected,
        identity=identity,
        marker=marker,
        warnings=warnings,
        image_reference=image_reference,
        processing_time_ms=round(processing_time_ms, 2),
    )


def _persist_image(image: Image.Image, storage_dir: Path, image_id: str) -> str:
    """Save the (already quality-approved) full scene and return an opaque
    id. Unlike registration, nothing about the scene is cropped away
    before storage — see this module's docstring."""
    storage_dir.mkdir(parents=True, exist_ok=True)
    image.convert("RGB").save(storage_dir / f"{image_id}.jpg", format="JPEG", quality=90)
    return image_id


def _save_debug_artifacts(image_id: str, stages: dict[str, Image.Image]) -> None:
    """Development-only: dump every intermediate stage (full scene, card
    region crop, every marker region/PSM scan's exact crop) to a
    per-attempt debug folder — mirrors `app/ai/pipeline.py`'s
    `_save_debug_artifacts` exactly, just writing to attendance's own
    directory (`app/ai/attendance_config.ATTENDANCE_DEBUG_OUTPUT_DIR`).
    Only called when `SNAPATTEND_AI_DEBUG` is explicitly enabled; a
    failure here must never affect the actual verification result, hence
    the blanket try/except.
    """
    if not stages:
        return
    debug_dir = Path(config.ATTENDANCE_DEBUG_OUTPUT_DIR) / image_id
    try:
        debug_dir.mkdir(parents=True, exist_ok=True)
        for name, stage_image in stages.items():
            stage_image.convert("RGB").save(debug_dir / f"{name}.jpg", format="JPEG", quality=90)
    except Exception:
        pass
