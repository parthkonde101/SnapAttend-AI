"""Developer diagnostics for the registration intelligence pipeline.

Development-only, observational tooling: this package watches what
`app.ai.pipeline` does on each `/registration/analyze` call and keeps a
record for inspection (a "Registration Attempt"), but it never influences
what the pipeline returns to the student. The dependency only runs one
way — this package imports read-only constants/types from `app.ai`;
nothing in `app.ai` imports from here.

Modules:
    gating.py      Whether diagnostics are enabled at all (dev-only switch).
    schemas.py      Pydantic models describing a recorded attempt.
    recorder.py     Observer object `app.ai.pipeline` optionally reports to.
    store.py         In-memory (ephemeral, dev-only) history of attempts.
    images.py        Resolves a stage name to its saved debug image file.
"""
from app.diagnostics.gating import is_diagnostics_enabled
from app.diagnostics.recorder import DiagnosticsRecorder
from app.diagnostics.schemas import RegistrationAttempt, RegistrationAttemptSummary
from app.diagnostics.store import diagnostics_store

__all__ = [
    "is_diagnostics_enabled",
    "DiagnosticsRecorder",
    "RegistrationAttempt",
    "RegistrationAttemptSummary",
    "diagnostics_store",
]
