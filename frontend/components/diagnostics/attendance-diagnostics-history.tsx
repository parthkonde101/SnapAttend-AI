"use client";

import { CheckCircle2, ChevronRight, RefreshCw, XCircle } from "lucide-react";
import { useCallback, useEffect, useState } from "react";

import { AttendanceAnalysisSheet } from "@/components/diagnostics/attendance-analysis-sheet";
import { useAttendanceDiagnosticsEnabled } from "@/hooks/use-attendance-diagnostics-enabled";
import { listAttendanceDiagnosticsAttempts } from "@/lib/attendance-diagnostics-api";
import type { AttendanceAttemptSummary } from "@/lib/types";

function formatDateTime(iso: string): { date: string; time: string } {
  const d = new Date(iso);
  return {
    date: d.toLocaleDateString(undefined, { month: "short", day: "numeric" }),
    time: d.toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" }),
  };
}

function AttemptRow({ attempt, onOpen }: { attempt: AttendanceAttemptSummary; onOpen: () => void }) {
  const { date, time } = formatDateTime(attempt.created_at);
  return (
    <button
      type="button"
      onClick={onOpen}
      className="flex w-full items-center gap-3 border-b border-white/10 px-4 py-3.5 text-left active:bg-white/5"
    >
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <span className="text-sm font-semibold text-white">Attempt #{attempt.attempt_number}</span>
          <span className="text-xs text-white/40">
            {date} · {time}
          </span>
        </div>
        <p className="truncate text-sm text-white/70">
          Student {attempt.student_id ?? "—"} · Session {attempt.session_id ?? "—"}
        </p>
        <div className="mt-0.5 flex items-center gap-2 text-xs text-white/40">
          <span className="font-mono">{attempt.extracted_prn ?? "no PRN"}</span>
          <span>·</span>
          <span className="font-mono">marker {attempt.detected_marker ?? "—"}</span>
        </div>
      </div>
      <div className="flex shrink-0 items-center gap-2">
        {attempt.verified ? (
          <CheckCircle2 className="h-4 w-4 text-emerald-500" aria-label="Verified" />
        ) : (
          <XCircle className="h-4 w-4 text-white/20" aria-label="Not verified" />
        )}
        <ChevronRight className="h-4 w-4 text-white/30" />
      </div>
    </button>
  );
}

/** The `/dev/attendance-diagnostics` page body — parallel to
 * `DiagnosticsHistory` (registration, not modified). No filter chips for
 * V1 (attendance's evidence trail is inspected per-attempt, not filtered
 * across a large history the way registration's PRN/barcode facets are). */
export function AttendanceDiagnosticsHistory() {
  const enabled = useAttendanceDiagnosticsEnabled();
  const [attempts, setAttempts] = useState<AttendanceAttemptSummary[]>([]);
  const [loading, setLoading] = useState(false);
  const [openAttemptId, setOpenAttemptId] = useState<string | null>(null);

  const refresh = useCallback(() => {
    if (!enabled) return;
    setLoading(true);
    listAttendanceDiagnosticsAttempts()
      .then(setAttempts)
      .finally(() => setLoading(false));
  }, [enabled]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  if (enabled === null) {
    return <div className="flex min-h-screen items-center justify-center bg-neutral-950" />;
  }

  if (!enabled) {
    return (
      <div className="flex min-h-screen flex-col items-center justify-center gap-2 bg-neutral-950 px-8 text-center">
        <p className="text-sm text-white/60">Attendance Diagnostics is unavailable.</p>
        <p className="text-xs text-white/30">Only reachable when the backend runs in development mode.</p>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-neutral-950 pb-[max(1.5rem,env(safe-area-inset-bottom))]">
      <header className="sticky top-0 z-10 border-b border-white/10 bg-neutral-950/90 px-4 pb-3 pt-[max(1.25rem,env(safe-area-inset-top))] backdrop-blur">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-lg font-bold text-white">Attendance Diagnostics</h1>
            <p className="text-xs text-white/40">Verification Attempts</p>
          </div>
          <button
            type="button"
            onClick={refresh}
            aria-label="Refresh"
            className="flex h-9 w-9 items-center justify-center rounded-full bg-white/10 text-white active:bg-white/20"
          >
            <RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} />
          </button>
        </div>
      </header>

      <div>
        {attempts.length === 0 && !loading && (
          <p className="px-4 py-16 text-center text-sm text-white/30">No attendance attempts recorded yet.</p>
        )}
        {attempts.map((attempt) => (
          <AttemptRow key={attempt.id} attempt={attempt} onOpen={() => setOpenAttemptId(attempt.id)} />
        ))}
      </div>

      {openAttemptId && <AttendanceAnalysisSheet attemptId={openAttemptId} onClose={() => setOpenAttemptId(null)} />}
    </div>
  );
}
