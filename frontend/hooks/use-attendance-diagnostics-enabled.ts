"use client";

import { useEffect, useState } from "react";

import { getAttendanceDiagnosticsStatus } from "@/lib/attendance-diagnostics-api";

/**
 * Parallel to `hooks/use-diagnostics-enabled.ts` (registration, not
 * touched by this change) — same "null while loading, then a real
 * boolean" contract, backed by the attendance-diagnostics router's own
 * `/status` endpoint. Not a security boundary here either: every
 * attendance-diagnostics API route independently 404s when disabled.
 */
export function useAttendanceDiagnosticsEnabled(): boolean | null {
  const [enabled, setEnabled] = useState<boolean | null>(null);

  useEffect(() => {
    let cancelled = false;
    getAttendanceDiagnosticsStatus().then((status) => {
      if (!cancelled) setEnabled(status.enabled);
    });
    return () => {
      cancelled = true;
    };
  }, []);

  return enabled;
}
