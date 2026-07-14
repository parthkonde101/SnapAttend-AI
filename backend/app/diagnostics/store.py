"""In-memory history of registration diagnostics attempts.

Deliberately ephemeral (resets on server restart) and deliberately not a
database table: this is development-only tooling for tuning the AI
pipeline, not user-facing data, so it doesn't warrant a migration or any
coupling to the `students`/`attendance` schema. A bounded ring buffer
keeps memory use flat regardless of how long a dev server runs.
"""
from __future__ import annotations

import threading
from collections import OrderedDict

from app.diagnostics.schemas import RegistrationAttempt, RegistrationAttemptSummary

_MAX_ATTEMPTS = 200


class DiagnosticsStore:
    def __init__(self, max_size: int = _MAX_ATTEMPTS) -> None:
        self._max_size = max_size
        self._lock = threading.Lock()
        self._attempts: "OrderedDict[str, RegistrationAttempt]" = OrderedDict()
        self._counter = 0

    def next_attempt_number(self) -> int:
        with self._lock:
            self._counter += 1
            return self._counter

    def add(self, attempt: RegistrationAttempt) -> None:
        with self._lock:
            self._attempts[attempt.id] = attempt
            self._attempts.move_to_end(attempt.id)
            while len(self._attempts) > self._max_size:
                self._attempts.popitem(last=False)

    def get(self, attempt_id: str) -> RegistrationAttempt | None:
        with self._lock:
            return self._attempts.get(attempt_id)

    def update(self, attempt_id: str, **changes) -> RegistrationAttempt | None:
        """Apply a partial update (used by `/registration/verify` to record
        the final confirmed name/PRN once the student finishes review)."""
        with self._lock:
            attempt = self._attempts.get(attempt_id)
            if attempt is None:
                return None
            updated = attempt.model_copy(update=changes)
            self._attempts[attempt_id] = updated
            return updated

    def list(
        self,
        *,
        search: str | None = None,
        barcode_success: bool | None = None,
        ocr_success: bool | None = None,
        manual_entry: bool | None = None,
        quality_failed: bool | None = None,
        glare: bool | None = None,
        blur: bool | None = None,
    ) -> list[RegistrationAttemptSummary]:
        with self._lock:
            attempts = list(reversed(self._attempts.values()))  # newest first

        def matches(attempt: RegistrationAttempt) -> bool:
            if search:
                needle = search.strip().lower()
                haystack = " ".join(
                    filter(
                        None,
                        [
                            attempt.final.verified_prn,
                            attempt.final.verified_name,
                            attempt.created_at.isoformat(),
                        ],
                    )
                ).lower()
                if needle not in haystack:
                    return False
            if barcode_success is not None and attempt.barcode.decoded != barcode_success:
                return False
            if ocr_success is not None:
                had_ocr_success = attempt.final.prn_source == "ocr"
                if had_ocr_success != ocr_success:
                    return False
            if manual_entry is not None and (attempt.final.prn_source == "manual") != manual_entry:
                return False
            if quality_failed is not None and (not attempt.quality.passed) != quality_failed:
                return False
            if glare is not None and (not attempt.quality.glare_ok) != glare:
                return False
            if blur is not None and (not attempt.quality.blur_ok) != blur:
                return False
            return True

        return [
            RegistrationAttemptSummary(
                id=a.id,
                attempt_number=a.attempt_number,
                created_at=a.created_at,
                student_name=a.final.verified_name,
                prn=a.final.verified_prn,
                prn_source=a.final.prn_source,
                barcode_success=a.barcode.decoded,
                quality_passed=a.quality.passed,
                registration_completed=a.final.registration_completed,
            )
            for a in attempts
            if matches(a)
        ]


diagnostics_store = DiagnosticsStore()
