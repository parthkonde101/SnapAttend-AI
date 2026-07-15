"""Diagnostics recorder — attendance.

Parallel to `app/diagnostics/recorder.py` (the registration recorder, not
touched by this milestone): an observer that `app.ai.attendance_pipeline`
optionally reports to, duck-typed exactly like `DiagnosticsRecorder` so
that pipeline never imports this module and stays fully self-contained.
`app.services.attendance_verification_service` additionally calls
`record_verification` once it has compared the pipeline's evidence against
the authenticated student and active session — the one place this recorder
learns about verification, since `app.ai.attendance_pipeline` itself never
has access to that context (see `app/ai/attendance_schemas.py`).

Usage (from `app/api/v1/endpoints/attendance.py` via the service layer):
    recorder = AttendanceDiagnosticsRecorder() if is_diagnostics_enabled() else None
    evidence = extract_attendance_evidence(contents, storage_dir, recorder=recorder)
    ... service layer compares evidence against student/session, then ...
    if recorder is not None:
        recorder.record_verification(...)
        attempt = recorder.finalize(id_detected=evidence.id_detected, attempt_number=...)
        attendance_diagnostics_store.add(attempt)
"""
from __future__ import annotations

import time
from datetime import datetime, timezone

from app.ai.attendance_schemas import DisplayMarkerResult, IdentityExtraction
from app.ai.schemas import BarcodeResult, QualityCheckResult
from app.diagnostics.attendance_schemas import (
    AttendanceAttempt,
    AttendanceFinalDiagnostics,
    AttendanceIdentityDiagnostics,
    AttendanceMarkerDiagnostics,
    DisplayRegionCandidateDiagnostics,
    GlyphCandidateDiagnostics,
    MarkerScanAttemptDiagnostics,
)
from app.diagnostics.schemas import BarcodeDiagnostics, PipelineLogEntry, QualityDiagnostics, StageImageInfo

# Human-readable labels for the fixed (non-dynamic) debug stages every
# attempt can produce — see app/ai/attendance_pipeline.py's debug_stages
# dict. Marker stages are dynamic (up to 2 tiers x 3 crops each, depending
# on how far the geometric search got in each tier) and labeled generically
# below instead of listed here, since — unlike registration's fixed
# six-slot set — how many of them exist varies per attempt.
_STATIC_STAGE_LABELS: dict[str, str] = {
    "00_original": "Original Scene",
    "01_card_region_crop": "Card Region Crop",
    "02_id_card_refined": "ID Card (Refined)",
}

_MARKER_STAGE_LABELS: dict[str, str] = {
    "search": "Search Crop",
    "display": "Display Panel",
    "glyph": "Glyph (Merged, Unnormalized)",
    "glyph_normalized": "Glyph (Normalized — sent to OCR)",
}


def _label_for_stage(key: str) -> str:
    if key in _STATIC_STAGE_LABELS:
        return _STATIC_STAGE_LABELS[key]
    if key.startswith("marker_"):
        # e.g. "marker_00_primary_01_display" -> "Marker 0 (primary): Display Panel"
        rest = key[len("marker_") :]
        parts = rest.split("_")
        if len(parts) >= 4:
            tier_index, tier_name, _stage_index, stage_name = parts[0], parts[1], parts[2], "_".join(parts[3:])
            stage_label = _MARKER_STAGE_LABELS.get(stage_name, stage_name.replace("_", " ").title())
            try:
                index_label = str(int(tier_index))
            except ValueError:
                index_label = tier_index
            return f"Marker {index_label} ({tier_name}): {stage_label}"
    return key.replace("_", " ").title()


class AttendanceDiagnosticsRecorder:
    def __init__(self) -> None:
        self._start = time.monotonic()
        self._log: list[PipelineLogEntry] = []
        self._quality: QualityDiagnostics | None = None
        self._barcode: BarcodeDiagnostics | None = None
        self._engine_name: str | None = None
        self._identity = AttendanceIdentityDiagnostics()
        self._marker = AttendanceMarkerDiagnostics()
        self._final = AttendanceFinalDiagnostics()
        self._image_id: str | None = None
        self._student_id: int | None = None
        self._session_id: int | None = None
        self._processing_time_ms: float | None = None
        self._available_images: set[str] = set()

    def set_image_id(self, image_id: str) -> None:
        self._image_id = image_id

    def set_context(self, *, student_id: int | None = None, session_id: int | None = None) -> None:
        """Called by the service layer (not the AI pipeline, which has no
        concept of students/sessions) once those are known."""
        if student_id is not None:
            self._student_id = student_id
        if session_id is not None:
            self._session_id = session_id

    # --- Pipeline log ------------------------------------------------------
    def log(self, step: str, message: str | None = None) -> None:
        self._log.append(
            PipelineLogEntry(
                step=step,
                message=message,
                timestamp=datetime.now(timezone.utc),
                elapsed_ms=round((time.monotonic() - self._start) * 1000, 2),
            )
        )

    # --- Image quality -------------------------------------------------------
    def record_quality(self, quality: QualityCheckResult, *, elapsed_ms: float) -> None:
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

    # --- Barcode / identity ----------------------------------------------------
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

    def record_engine(self, name: str) -> None:
        self._engine_name = name

    def record_identity(self, identity: IdentityExtraction) -> None:
        self._identity = self._identity.model_copy(
            update={
                "extracted_prn": identity.extracted_prn,
                "source": identity.source,
                "failure_reason": identity.failure_reason,
            }
        )

    def record_ocr_timing(self, elapsed_ms: float) -> None:
        """Called by `app.ai.attendance_pipeline` only when the OCR
        fallback path actually ran (barcode didn't apply) — was missing
        entirely until a real pipeline run against a debug-enabled recorder
        surfaced it as an `AttributeError` while building marker
        diagnostics, which would otherwise have made `/attendance/mark`
        fail outright any time diagnostics was enabled and barcode
        decoding didn't produce a usable PRN (i.e. most real attempts,
        since barcode decoding requires the optional `zxing-cpp` package).
        """
        self._identity = self._identity.model_copy(update={"ocr_fallback_time_ms": round(elapsed_ms, 2)})

    # --- Marker ----------------------------------------------------------------
    def record_marker(self, marker: DisplayMarkerResult, *, elapsed_ms: float) -> None:
        self._marker = AttendanceMarkerDiagnostics(
            detected_character=marker.character,
            confidence=marker.confidence,
            failure_reason=marker.failure_reason,
            processing_time_ms=round(elapsed_ms, 2),
            scans=[
                MarkerScanAttemptDiagnostics(
                    tier=scan.tier,
                    fractional_box=scan.fractional_box,
                    pixel_box=scan.pixel_box,
                    search_stage_image_key=scan.search_stage_image_key,
                    display_regions=[
                        DisplayRegionCandidateDiagnostics(
                            rect=d.rect,
                            area=d.area,
                            fill_ratio=d.fill_ratio,
                            mean_brightness=d.mean_brightness,
                            accepted=d.accepted,
                            rejection_reason=d.rejection_reason,
                        )
                        for d in scan.display_regions
                    ],
                    display_stage_image_key=scan.display_stage_image_key,
                    glyph_candidates=[
                        GlyphCandidateDiagnostics(
                            rect=g.rect,
                            area=g.area,
                            aspect_ratio=g.aspect_ratio,
                            height_ratio=g.height_ratio,
                            fill_ratio=g.fill_ratio,
                            edge_density=g.edge_density,
                            member_count=g.member_count,
                            accepted=g.accepted,
                            rejection_reason=g.rejection_reason,
                            selected=g.selected,
                        )
                        for g in scan.glyph_candidates
                    ],
                    glyph_stage_image_key=scan.glyph_stage_image_key,
                    glyph_normalized_stage_image_key=scan.glyph_normalized_stage_image_key,
                    ocr_text=scan.ocr_text,
                    ocr_confidence=scan.ocr_confidence,
                    outcome=scan.outcome,
                )
                for scan in marker.scans
            ],
        )

    # --- Pipeline images ---------------------------------------------------------
    def record_available_images(self, names) -> None:
        """`names` is whatever keys `attendance_pipeline.py`'s `debug_stages`
        dict ended up with — only populated at all when
        `SNAPATTEND_AI_DEBUG=1`. Mirrors the registration recorder's method
        of the same name."""
        self._available_images = set(names)

    # --- Final verification decision (service-layer concern) -------------------
    def record_verification(
        self,
        *,
        identity_verified: bool,
        matched_student_id: int | None,
        marker_verified: bool,
        expected_marker: str | None,
        marker_comparison_note: str | None = None,
        verified: bool,
        reason: str | None,
        verification_source: str,
        already_recorded: bool,
        warnings: list[str],
    ) -> None:
        self._identity = self._identity.model_copy(
            update={"matched_student_id": matched_student_id, "identity_verified": identity_verified}
        )
        self._marker = self._marker.model_copy(
            update={
                "expected_marker": expected_marker,
                "marker_verified": marker_verified,
                "comparison_note": marker_comparison_note,
            }
        )
        self._final = AttendanceFinalDiagnostics(
            verified=verified,
            reason=reason,
            verification_source=verification_source,  # type: ignore[arg-type]
            already_recorded=already_recorded,
            warnings=list(warnings),
        )

    def record_processing_time(self, elapsed_ms: float) -> None:
        self._processing_time_ms = round(elapsed_ms, 2)

    # --- assembly --------------------------------------------------------------
    def _resolve_stage_images(self) -> list[StageImageInfo]:
        """Unlike registration's fixed six-slot set, attendance's debug
        stages are a dynamic set (how many marker region/PSM scans ran
        varies per attempt) — so every key `record_available_images` was
        given becomes its own slot here, sorted for a stable display order,
        rather than mapped onto a fixed static list."""
        return [
            StageImageInfo(stage=key, label=_label_for_stage(key), filename=key, available=True)
            for key in sorted(self._available_images)
        ]

    def finalize(self, *, id_detected: bool, attempt_number: int) -> AttendanceAttempt:
        image_id = self._image_id or f"attendance-attempt-{attempt_number}"
        return AttendanceAttempt(
            id=image_id,
            attempt_number=attempt_number,
            created_at=datetime.now(timezone.utc),
            student_id=self._student_id,
            session_id=self._session_id,
            quality=self._quality or QualityDiagnostics(),
            barcode=self._barcode or BarcodeDiagnostics(),
            identity=self._identity,
            marker=self._marker,
            final=self._final,
            log=self._log,
            stage_images=self._resolve_stage_images(),
            id_detected=id_detected,
            processing_time_ms=self._processing_time_ms,
        )
