"use client";

import { Download, Loader2, X } from "lucide-react";
import { useEffect, useState } from "react";

import {
  BarcodeSection,
  FinalResultSection,
  OcrSection,
  PipelineImagesSection,
  PipelineLogSection,
  QualitySection,
} from "@/components/diagnostics/analysis-sections";
import { ImageViewer } from "@/components/diagnostics/image-viewer";
import { downloadDiagnosticsAttempt, getDiagnosticsAttempt } from "@/lib/diagnostics-api";
import type { RegistrationAttempt } from "@/lib/types";

interface AnalysisSheetProps {
  attemptId: string;
  onClose: () => void;
}

/**
 * Full-screen mobile sheet showing the complete diagnostic record for one
 * registration attempt (Sections 1-6). Used both from the registration
 * success screen ("View Analysis") and from the Developer Diagnostics
 * history list — same component, just a different `attemptId`.
 */
export function AnalysisSheet({ attemptId, onClose }: AnalysisSheetProps) {
  const [attempt, setAttempt] = useState<RegistrationAttempt | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [viewerImage, setViewerImage] = useState<{ src: string; label: string } | null>(null);

  useEffect(() => {
    let cancelled = false;
    setAttempt(null);
    setError(null);
    getDiagnosticsAttempt(attemptId)
      .then((data) => {
        if (!cancelled) setAttempt(data);
      })
      .catch(() => {
        if (!cancelled) setError("Couldn't load this analysis. It may have expired (diagnostics history resets on server restart).");
      });
    return () => {
      cancelled = true;
    };
  }, [attemptId]);

  // Lock background scroll while the sheet is open — feels native on iOS.
  useEffect(() => {
    const original = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = original;
    };
  }, []);

  return (
    <div className="animate-in fade-in slide-in-from-bottom-6 fixed inset-0 z-50 flex h-[100dvh] flex-col bg-neutral-950 duration-300">
      <header className="sticky top-0 z-10 flex items-center justify-between border-b border-white/10 bg-neutral-950/90 px-4 pb-3 pt-[max(1rem,env(safe-area-inset-top))] backdrop-blur">
        <div className="min-w-0">
          <h2 className="text-base font-semibold text-white">Registration Analysis</h2>
          {attempt && <p className="truncate text-xs text-white/40">Attempt #{attempt.attempt_number}</p>}
        </div>
        <div className="flex shrink-0 items-center gap-2">
          {attempt && (
            <button
              type="button"
              onClick={() => downloadDiagnosticsAttempt(attempt.id, attempt.attempt_number)}
              aria-label="Export as JSON"
              className="flex h-9 w-9 items-center justify-center rounded-full bg-white/10 text-white active:bg-white/20"
            >
              <Download className="h-4 w-4" />
            </button>
          )}
          <button
            type="button"
            onClick={onClose}
            aria-label="Close"
            className="flex h-9 w-9 items-center justify-center rounded-full bg-white/10 text-white active:bg-white/20"
          >
            <X className="h-4.5 w-4.5" />
          </button>
        </div>
      </header>

      <div className="flex-1 overflow-y-auto px-4 pb-[max(1.5rem,env(safe-area-inset-bottom))] pt-4">
        {!attempt && !error && (
          <div className="flex flex-col items-center justify-center gap-3 py-20 text-white/50">
            <Loader2 className="h-6 w-6 animate-spin" />
            <p className="text-sm">Loading analysis…</p>
          </div>
        )}

        {error && (
          <div className="flex flex-col items-center justify-center gap-2 py-20 text-center">
            <p className="max-w-xs text-sm text-white/60">{error}</p>
          </div>
        )}

        {attempt && (
          <div className="space-y-3 pb-4">
            <FinalResultSection final={attempt.final} />
            <QualitySection quality={attempt.quality} />
            <BarcodeSection barcode={attempt.barcode} />
            <OcrSection ocr={attempt.ocr} />
            <PipelineImagesSection
              attemptId={attempt.id}
              stageImages={attempt.stage_images}
              onOpenImage={(src, label) => setViewerImage({ src, label })}
            />
            <PipelineLogSection log={attempt.log} />
          </div>
        )}
      </div>

      {viewerImage && <ImageViewer src={viewerImage.src} label={viewerImage.label} onClose={() => setViewerImage(null)} />}
    </div>
  );
}
