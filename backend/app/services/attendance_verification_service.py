"""Attendance verification: turns a captured scene into a pass/fail
decision and (on the first success) a stored `Attendance` record.

This is the "AttendanceVerifier" stage from the spec's pipeline diagram —
deliberately a service-layer concern, not part of `app.ai.attendance_pipeline`,
because verifying identity/marker means comparing extracted evidence
against the authenticated student and the active session, both DB-aware
concepts that `app.ai` is not allowed to depend on (see
`app/ai/attendance_schemas.AttendanceEvidence`'s docstring). This service
is what has both halves available.

Verification requires, per the spec: student exists (guaranteed — this
service only runs for an authenticated student), session active (checked
by the caller before this runs), attendance marker detected, marker
matches the current session, attendance not already recorded, and — the
identity half — the ID card in the photo actually belongs to *this*
student (not just any registered student).
"""
from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.ai import attendance_config as config
from app.ai.attendance_pipeline import extract_attendance_evidence
from app.ai.attendance_schemas import DisplayMarkerResult
from app.models.attendance import Attendance
from app.models.attendance_session import AttendanceSession
from app.models.student import Student
from app.schemas.attendance import MarkAttendanceResponse


def _normalize_prn(value: str) -> str:
    return value.strip() if config.PRN_MATCH_CASE_SENSITIVE else value.strip().upper()


def _marker_comparison_note(marker: DisplayMarkerResult, expected_marker: str, *, accepted_on_display_evidence: bool) -> str:
    """Plain-English explanation of exactly why the marker comparison
    passed or failed — computed here (not guessed at, not left implicit)
    since this is the one place both the detected evidence and the
    session's actual expected marker are both available. Surfaced verbatim
    in the diagnostics UI's Marker section.

    Per the verification-philosophy refinement, an exact OCR match is no
    longer the only way this can end in acceptance — `accepted_on_display_evidence`
    is true when a real classroom display was geometrically detected (see
    `DisplayMarkerResult.display_detected`) and identity verification was
    already strong enough on its own that the exact character wasn't
    required. The note says so explicitly, both cases, so nothing about the
    lenient path is silently invisible to a teacher inspecting diagnostics.
    """
    if marker.detected and marker.character and marker.character.upper() == expected_marker.upper():
        return f"Detected '{marker.character}' matches the expected marker '{expected_marker}'."
    if accepted_on_display_evidence:
        detected_desc = f"detected '{marker.character}'" if marker.character else "OCR could not confidently read a character"
        return (
            f"A classroom display was clearly detected (geometric evidence tier {marker.display_confidence:.1f}), "
            f"but {detected_desc}, which does not exactly match the expected marker '{expected_marker}'. Accepted "
            "based on strong identity verification plus classroom-display evidence, per the current verification "
            "philosophy (exact marker OCR is evidence of location, not the primary authentication factor)."
        )
    if not marker.attempted:
        return f"Marker OCR was not attempted ({marker.failure_reason or 'reason unknown'})."
    if not marker.display_detected:
        return (
            f"No classroom display could be geometrically detected in any scanned region — insufficient evidence "
            f"the photo was taken in front of the marker display. ({marker.failure_reason or 'no qualifying candidate found'})"
        )
    if not marker.detected or not marker.character:
        return f"No marker character was detected in any scanned region. Expected '{expected_marker}'. ({marker.failure_reason or 'no qualifying candidate found'})"
    return f"Detected '{marker.character}' does not match the expected marker '{expected_marker}'."


class AttendanceVerificationService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def already_marked(self, *, student_id: int, session_id: int) -> bool:
        stmt = select(Attendance).where(Attendance.student_id == student_id, Attendance.session_id == session_id)
        return self.db.scalar(stmt) is not None

    def verify_and_record(
        self,
        *,
        student: Student,
        session: AttendanceSession,
        image_bytes: bytes,
        storage_dir: Path,
        recorder: Any = None,
    ) -> MarkAttendanceResponse:
        start = time.monotonic()

        # Cheap early exit: no need to run the AI pipeline at all against a
        # photo whose outcome can't change anything, per "failed attempts
        # must never consume a student's opportunity to attend" — a
        # duplicate check is the one case that's true regardless of what's
        # in the photo, so it's worth skipping the (comparatively
        # expensive) pipeline entirely.
        if self.already_marked(student_id=student.id, session_id=session.id):
            return MarkAttendanceResponse(success=False, already_recorded=True, reason="Attendance already recorded.")

        if recorder:
            recorder.set_context(student_id=student.id, session_id=session.id)

        evidence = extract_attendance_evidence(image_bytes, storage_dir, recorder=recorder)

        if not evidence.quality_passed:
            reason = ", ".join(evidence.quality_messages) or "Image quality too low. Please retry."
            diagnostics_attempt_id: str | None = None
            if recorder:
                recorder.record_verification(
                    identity_verified=False,
                    matched_student_id=None,
                    marker_verified=False,
                    expected_marker=session.marker,
                    verified=False,
                    reason=reason,
                    verification_source="none",
                    already_recorded=False,
                    warnings=evidence.quality_messages,
                )
                diagnostics_attempt_id = self._finalize_diagnostics(recorder, evidence.id_detected)
            return MarkAttendanceResponse(
                success=False, reason=reason, warnings=evidence.quality_messages, diagnostics_attempt_id=diagnostics_attempt_id
            )

        # --- Identity: does the extracted PRN belong to *this* student? ----
        extracted_prn = evidence.identity.extracted_prn
        identity_verified = False
        matched_student_id: int | None = None

        if extracted_prn:
            own_candidates = {p for p in (student.prn, student.verified_prn) if p}
            own_normalized = {_normalize_prn(p) for p in own_candidates}
            if _normalize_prn(extracted_prn) in own_normalized:
                identity_verified = True
                matched_student_id = student.id
            else:
                other = self.db.scalar(
                    select(Student).where((Student.prn == extracted_prn) | (Student.verified_prn == extracted_prn))
                )
                matched_student_id = other.id if other is not None else None

        # --- Marker / classroom-display evidence ----------------------------
        # Verification philosophy (production classroom milestone): the
        # classroom display is evidence the photo was taken in the active
        # classroom, not the primary authentication factor — identity above
        # is. An exact OCR match is still the strongest possible evidence and
        # always accepted. But requiring it unconditionally punished genuine
        # students for blur/tilt/distance the display is *expected* to
        # suffer (students focus their camera on the ID card, not the
        # projector). So a second, still-real acceptance path exists:
        # `display_detected` is true whenever a real, panel-shaped dark
        # region was found in the scene — as of this milestone, that alone
        # is enough (glyph isolation is no longer required, only preferred
        # — see app.ai.attendance_config.MARKER_DISPLAY_CONFIDENCE_PANEL_ONLY
        # for exactly which geometric filters a candidate must still pass).
        # Not just "the photo had a dark area somewhere" — those filters
        # mean it can't be satisfied by an unrelated dark background object.
        # That's treated as real (if OCR-imperfect) proof of classroom
        # presence, and is only ever sufficient on its own when identity is
        # *already* independently confirmed — a photo with weak/no identity
        # evidence gets no benefit from display evidence at all.
        exact_marker_match = bool(
            evidence.marker.detected
            and evidence.marker.character
            and evidence.marker.character.upper() == session.marker.upper()
        )
        accepted_on_display_evidence = (
            identity_verified and not exact_marker_match and evidence.marker.display_detected
        )
        marker_verified = exact_marker_match or accepted_on_display_evidence

        verified = identity_verified and marker_verified

        # Only meaningful when `verified` ends up true (used solely to tag
        # the Attendance row created below) — "display_evidence" if that's
        # literally why acceptance happened, "exact_match" otherwise.
        marker_verification_mode = "display_evidence" if accepted_on_display_evidence else "exact_match"

        reason: str | None = None
        if extracted_prn is None:
            reason = "Could not read your ID card. Please retry with better lighting and framing."
        elif not identity_verified:
            reason = (
                "This ID card belongs to a different registered student."
                if matched_student_id is not None
                else "This ID card is not registered to any student."
            )
        elif not evidence.marker.display_detected:
            reason = "Could not detect the classroom display in your photo. Please retry, making sure the projector or TV showing the marker is visible in frame."
        elif not marker_verified:
            reason = "The marker in your photo does not match the current session. Please retry."

        if accepted_on_display_evidence:
            evidence.warnings.append(
                "Classroom display detected, but the exact marker character could not be confidently read. "
                "Attendance was accepted based on your verified identity plus display evidence."
            )

        already_recorded = False
        if verified:
            record = Attendance(
                student_id=student.id,
                session_id=session.id,
                verification_source=evidence.identity.source or "ocr",
                marker=session.marker,
                verification_duration_ms=evidence.processing_time_ms,
                image_reference=evidence.image_reference,
                status="present",
                marker_detected_character=evidence.marker.character,
                marker_confidence=evidence.marker.confidence,
                display_detected=evidence.marker.display_detected,
                display_confidence=evidence.marker.display_confidence,
                marker_verification_mode=marker_verification_mode,
            )
            self.db.add(record)
            try:
                self.db.commit()
            except IntegrityError:
                # Lost a race with another successful attempt for the same
                # (student, session) between the early check above and this
                # commit — the unique constraint is the real backstop.
                self.db.rollback()
                already_recorded = True
                verified = False
                reason = "Attendance already recorded."
            else:
                self.db.refresh(record)

        diagnostics_attempt_id: str | None = None
        if recorder:
            recorder.record_verification(
                identity_verified=identity_verified,
                matched_student_id=matched_student_id,
                marker_verified=marker_verified,
                expected_marker=session.marker,
                marker_comparison_note=_marker_comparison_note(
                    evidence.marker, session.marker, accepted_on_display_evidence=accepted_on_display_evidence
                ),
                verified=verified,
                reason=reason,
                verification_source=evidence.identity.source or "none",
                already_recorded=already_recorded,
                warnings=evidence.warnings,
            )
            recorder.record_processing_time((time.monotonic() - start) * 1000)
            diagnostics_attempt_id = self._finalize_diagnostics(recorder, evidence.id_detected)

        return MarkAttendanceResponse(
            success=verified,
            already_recorded=already_recorded,
            reason=reason,
            verification_source=evidence.identity.source or "none",
            marker_detected=evidence.marker.character,
            warnings=evidence.warnings,
            diagnostics_attempt_id=diagnostics_attempt_id,
        )

    @staticmethod
    def _finalize_diagnostics(recorder: Any, id_detected: bool) -> str | None:
        """Best-effort: never let a diagnostics bug affect the actual
        verification response, matching the registration endpoint's
        `_record_verification_diagnostics` guard."""
        try:
            from app.diagnostics.attendance_store import attendance_diagnostics_store

            attempt = recorder.finalize(id_detected=id_detected, attempt_number=attendance_diagnostics_store.next_attempt_number())
            attendance_diagnostics_store.add(attempt)
            return attempt.id
        except Exception:
            return None
