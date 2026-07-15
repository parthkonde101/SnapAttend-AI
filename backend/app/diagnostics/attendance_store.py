"""In-memory history of attendance diagnostics attempts.

Parallel to `app/diagnostics/store.py` (the registration store, not
touched by this milestone). Same design: deliberately ephemeral
(resets on server restart), a bounded ring buffer, development-only
tooling — never a database table, never coupled to the `attendance`
schema.
"""
from __future__ import annotations

import threading
from collections import OrderedDict

from app.diagnostics.attendance_schemas import AttendanceAttempt, AttendanceAttemptSummary

_MAX_ATTEMPTS = 200


class AttendanceDiagnosticsStore:
    def __init__(self, max_size: int = _MAX_ATTEMPTS) -> None:
        self._max_size = max_size
        self._lock = threading.Lock()
        self._attempts: "OrderedDict[str, AttendanceAttempt]" = OrderedDict()
        self._counter = 0

    def next_attempt_number(self) -> int:
        with self._lock:
            self._counter += 1
            return self._counter

    def add(self, attempt: AttendanceAttempt) -> None:
        with self._lock:
            self._attempts[attempt.id] = attempt
            self._attempts.move_to_end(attempt.id)
            while len(self._attempts) > self._max_size:
                self._attempts.popitem(last=False)

    def get(self, attempt_id: str) -> AttendanceAttempt | None:
        with self._lock:
            return self._attempts.get(attempt_id)

    def list(
        self,
        *,
        session_id: int | None = None,
        student_id: int | None = None,
    ) -> list[AttendanceAttemptSummary]:
        with self._lock:
            attempts = list(reversed(self._attempts.values()))  # newest first

        def matches(attempt: AttendanceAttempt) -> bool:
            if session_id is not None and attempt.session_id != session_id:
                return False
            if student_id is not None and attempt.student_id != student_id:
                return False
            return True

        return [
            AttendanceAttemptSummary(
                id=a.id,
                attempt_number=a.attempt_number,
                created_at=a.created_at,
                student_id=a.student_id,
                session_id=a.session_id,
                extracted_prn=a.identity.extracted_prn,
                detected_marker=a.marker.detected_character,
                verified=a.final.verified,
                verification_source=a.final.verification_source,
            )
            for a in attempts
            if matches(a)
        ]


attendance_diagnostics_store = AttendanceDiagnosticsStore()
