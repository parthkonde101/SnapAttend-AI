"""Single source of truth for "should diagnostics exist at all right now".

Diagnostics must only be reachable when:
    ENVIRONMENT=development   (backend/app/core/config.settings)
    or
    SNAPATTEND_AI_DEBUG=1     (backend/app/ai/config.DEBUG_SAVE_INTERMEDIATES)

Every diagnostics endpoint checks this and returns 404 (not 403) when
disabled, so the feature's existence isn't even discoverable in
production. This is the ONLY place that decision is made — everything
else (recorder construction, endpoint registration checks, frontend
gating) defers to this function.
"""
from __future__ import annotations

from app.ai.config import DEBUG_SAVE_INTERMEDIATES
from app.core.config import settings


def is_diagnostics_enabled() -> bool:
    return settings.ENVIRONMENT == "development" or DEBUG_SAVE_INTERMEDIATES
