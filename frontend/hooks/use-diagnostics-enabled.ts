"use client";

import { useEffect, useState } from "react";

import { getDiagnosticsStatus } from "@/lib/diagnostics-api";

/**
 * Whether developer diagnostics UI should render at all, per the backend
 * (`ENVIRONMENT=development` or `SNAPATTEND_AI_DEBUG=1` — see
 * `app/diagnostics/gating.py`). This is a UX convenience only, not a
 * security boundary: every diagnostics API route independently 404s when
 * disabled, so even a stray render of this UI in an unexpected build
 * can't actually read or leak anything.
 *
 * Returns `null` while the initial check is in flight, so callers can
 * avoid a flash of dev-only UI before the answer comes back.
 */
export function useDiagnosticsEnabled(): boolean | null {
  const [enabled, setEnabled] = useState<boolean | null>(null);

  useEffect(() => {
    let cancelled = false;
    getDiagnosticsStatus().then((status) => {
      if (!cancelled) setEnabled(status.enabled);
    });
    return () => {
      cancelled = true;
    };
  }, []);

  return enabled;
}
