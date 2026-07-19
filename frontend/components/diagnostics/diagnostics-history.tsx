"use client";

import { CheckCircle2, ChevronRight, RefreshCw, Search, XCircle } from "lucide-react";
import { useCallback, useEffect, useState } from "react";

import { AnalysisSheet } from "@/components/diagnostics/analysis-sheet";
import { useDiagnosticsEnabled } from "@/hooks/use-diagnostics-enabled";
import { listDiagnosticsAttempts } from "@/lib/diagnostics-api";
import type { DiagnosticsAttemptFilters, RegistrationAttemptSummary } from "@/lib/types";

interface FilterChip {
  key: string;
  label: string;
  apply: (filters: DiagnosticsAttemptFilters) => DiagnosticsAttemptFilters;
  /** Chip key(s) that must be cleared when this one is selected (mutually exclusive facets). */
  excludes?: string[];
}

const FILTER_CHIPS: FilterChip[] = [
  { key: "barcode_success", label: "Barcode Success", apply: (f) => ({ ...f, barcode_success: true }), excludes: ["barcode_failed"] },
  { key: "barcode_failed", label: "Barcode Failed", apply: (f) => ({ ...f, barcode_success: false }), excludes: ["barcode_success"] },
  { key: "ocr_success", label: "OCR Success", apply: (f) => ({ ...f, ocr_success: true }) },
  { key: "manual_entry", label: "Manual Entry", apply: (f) => ({ ...f, manual_entry: true }) },
  { key: "quality_failed", label: "Quality Failed", apply: (f) => ({ ...f, quality_failed: true }) },
  { key: "glare", label: "Glare", apply: (f) => ({ ...f, glare: true }) },
  { key: "blur", label: "Blur", apply: (f) => ({ ...f, blur: true }) },
];

function formatDateTime(iso: string): { date: string; time: string } {
  const d = new Date(iso);
  return {
    date: d.toLocaleDateString(undefined, { month: "short", day: "numeric" }),
    time: d.toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" }),
  };
}

const PRN_SOURCE_LABEL: Record<string, string> = {
  barcode: "Barcode",
  ocr: "OCR",
  manual: "Manual",
  none: "—",
};

function AttemptRow({ attempt, onOpen }: { attempt: RegistrationAttemptSummary; onOpen: () => void }) {
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
        <p className="truncate text-sm text-white/70">{attempt.student_name ?? "Unnamed"}</p>
        <div className="mt-0.5 flex items-center gap-2 text-xs text-white/40">
          <span className="font-mono">{attempt.prn ?? "no PRN"}</span>
          <span>·</span>
          <span>{PRN_SOURCE_LABEL[attempt.prn_source] ?? attempt.prn_source}</span>
        </div>
      </div>
      <div className="flex shrink-0 items-center gap-2">
        {attempt.barcode_success ? (
          <CheckCircle2 className="h-4 w-4 text-emerald-500" aria-label="Barcode success" />
        ) : (
          <XCircle className="h-4 w-4 text-white/20" aria-label="Barcode not used" />
        )}
        {attempt.registration_completed ? (
          <CheckCircle2 className="h-4 w-4 text-emerald-500" aria-label="Registration successful" />
        ) : (
          <XCircle className="h-4 w-4 text-white/20" aria-label="Registration not completed" />
        )}
        <ChevronRight className="h-4 w-4 text-white/30" />
      </div>
    </button>
  );
}

/** The `/dev/diagnostics` page body — history list with search/filter, tap to inspect. */
export function DiagnosticsHistory() {
  const enabled = useDiagnosticsEnabled();
  const [search, setSearch] = useState("");
  const [activeChips, setActiveChips] = useState<Set<string>>(new Set());
  const [attempts, setAttempts] = useState<RegistrationAttemptSummary[]>([]);
  const [loading, setLoading] = useState(false);
  const [openAttemptId, setOpenAttemptId] = useState<string | null>(null);

  const toggleChip = (chip: FilterChip) => {
    setActiveChips((prev) => {
      const next = new Set(prev);
      if (next.has(chip.key)) {
        next.delete(chip.key);
      } else {
        next.add(chip.key);
        chip.excludes?.forEach((k) => next.delete(k));
      }
      return next;
    });
  };

  const refresh = useCallback(() => {
    if (!enabled) return;
    setLoading(true);
    let filters: DiagnosticsAttemptFilters = search.trim() ? { search: search.trim() } : {};
    for (const chip of FILTER_CHIPS) {
      if (activeChips.has(chip.key)) filters = chip.apply(filters);
    }
    listDiagnosticsAttempts(filters)
      .then(setAttempts)
      .finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [enabled, search, activeChips]);

  useEffect(() => {
    const timeoutId = setTimeout(refresh, 200); // debounce search typing
    return () => clearTimeout(timeoutId);
  }, [refresh]);

  if (enabled === null) {
    return <div className="flex min-h-screen items-center justify-center bg-neutral-950" />;
  }

  if (!enabled) {
    return (
      <div className="flex min-h-screen flex-col items-center justify-center gap-2 bg-neutral-950 px-8 text-center">
        <p className="text-sm text-white/60">Developer Diagnostics is unavailable.</p>
        <p className="text-xs text-white/30">Only reachable when the backend runs in development mode.</p>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-neutral-950 pb-[max(1.5rem,env(safe-area-inset-bottom))]">
      <header className="sticky top-0 z-10 border-b border-white/10 bg-neutral-950/90 px-4 pb-3 pt-[max(1.25rem,env(safe-area-inset-top))] backdrop-blur">
        <div className="mb-3 flex items-center justify-between">
          <div>
            <h1 className="text-lg font-bold text-white">Developer Diagnostics</h1>
            <p className="text-xs text-white/40">Registration Attempts</p>
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

        <div className="relative mb-3">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-white/30" />
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search PRN, name, or date"
            className="w-full rounded-xl border border-white/10 bg-white/5 py-2.5 pl-9 pr-3 text-base text-white placeholder:text-white/30 focus:border-white/30 focus:outline-none sm:text-sm"
          />
        </div>

        <div className="-mx-4 flex gap-2 overflow-x-auto px-4 pb-1" style={{ scrollbarWidth: "none" }}>
          {FILTER_CHIPS.map((chip) => {
            const active = activeChips.has(chip.key);
            return (
              <button
                key={chip.key}
                type="button"
                onClick={() => toggleChip(chip)}
                className={`shrink-0 whitespace-nowrap rounded-full border px-3 py-1.5 text-xs font-medium transition-colors ${
                  active ? "border-white bg-white text-black" : "border-white/15 bg-transparent text-white/60"
                }`}
              >
                {chip.label}
              </button>
            );
          })}
        </div>
      </header>

      <div>
        {attempts.length === 0 && !loading && (
          <p className="px-4 py-16 text-center text-sm text-white/30">No attempts match these filters.</p>
        )}
        {attempts.map((attempt) => (
          <AttemptRow key={attempt.id} attempt={attempt} onOpen={() => setOpenAttemptId(attempt.id)} />
        ))}
      </div>

      {openAttemptId && <AnalysisSheet attemptId={openAttemptId} onClose={() => setOpenAttemptId(null)} />}
    </div>
  );
}
