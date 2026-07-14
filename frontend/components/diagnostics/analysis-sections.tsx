"use client";

import { ImageOff } from "lucide-react";

import { DiagnosticRow, ExpandableCard, StatusPill } from "@/components/diagnostics/expandable-card";
import { getDiagnosticsImageUrl } from "@/lib/diagnostics-api";
import type { RegistrationAttempt } from "@/lib/types";

function formatMs(value: number | null): string {
  if (value === null) return "—";
  return `${value.toFixed(1)} ms`;
}

function formatScore(value: number | null): string {
  if (value === null) return "—";
  return value.toFixed(2);
}

const PRN_SOURCE_LABEL: Record<string, string> = {
  barcode: "Barcode",
  ocr: "OCR",
  manual: "Manual Entry",
  none: "None",
};

// --- Section 1: Image Quality -------------------------------------------------

export function QualitySection({ quality }: { quality: RegistrationAttempt["quality"] }) {
  return (
    <ExpandableCard title="Image Quality" subtitle={quality.passed ? "Accepted" : "Rejected"} statusDot={quality.passed ? "green" : "red"}>
      <DiagnosticRow label="Resolution" value={quality.width && quality.height ? `${quality.width} × ${quality.height}` : "—"} mono />
      <DiagnosticRow label="Blur Score" value={formatScore(quality.blur_score)} mono valueClassName={quality.blur_ok ? "" : "text-red-400"} />
      <DiagnosticRow label="Brightness" value={formatScore(quality.brightness)} mono valueClassName={quality.brightness_ok ? "" : "text-red-400"} />
      <DiagnosticRow label="Contrast" value={formatScore(quality.contrast)} mono />
      <DiagnosticRow label="Glare Detection" value={<StatusPill ok={quality.glare_ok} trueLabel="Clean" falseLabel="Glare" />} />
      <DiagnosticRow label="Entire ID Visible" value={<StatusPill ok={quality.coverage_ok} />} />
      <DiagnosticRow label="Image Accepted" value={<StatusPill ok={quality.passed} />} />
      <DiagnosticRow label="Processing Time" value={formatMs(quality.processing_time_ms)} mono />
      {quality.messages.length > 0 && (
        <div className="mt-2 space-y-1 border-t border-white/10 pt-2">
          {quality.messages.map((message) => (
            <p key={message} className="text-xs text-white/40">
              {message}
            </p>
          ))}
        </div>
      )}
    </ExpandableCard>
  );
}

// --- Section 2: Barcode -------------------------------------------------------

export function BarcodeSection({ barcode }: { barcode: RegistrationAttempt["barcode"] }) {
  return (
    <ExpandableCard
      title="Barcode"
      subtitle={barcode.decoded ? "Decoded" : barcode.attempted ? "Not found" : "Not attempted"}
      statusDot={barcode.decoded ? "green" : barcode.attempted ? "amber" : "gray"}
    >
      <DiagnosticRow label="Barcode Attempted" value={<StatusPill ok={barcode.attempted} />} />
      <DiagnosticRow label="Success / Failure" value={<StatusPill ok={barcode.decoded} trueLabel="Success" falseLabel="Failure" />} />
      <DiagnosticRow label="Barcode Type" value={barcode.barcode_type ?? "—"} mono />
      <DiagnosticRow label="Decoded Value" value={barcode.decoded_value ?? "—"} mono />
      <DiagnosticRow label="Failure Reason" value={barcode.failure_reason ?? "—"} />
      <DiagnosticRow label="Time Taken" value={formatMs(barcode.processing_time_ms)} mono />
      {barcode.used_as_prn && (
        <div className="mt-2 flex items-center justify-between rounded-lg bg-emerald-500/10 px-3 py-2">
          <span className="text-xs font-medium text-emerald-400">PRN Source</span>
          <span className="text-xs font-semibold text-emerald-400">Barcode</span>
        </div>
      )}
    </ExpandableCard>
  );
}

// --- Section 3: OCR ------------------------------------------------------------

export function OcrSection({ ocr }: { ocr: RegistrationAttempt["ocr"] }) {
  const rejected = ocr.candidates.filter((c) => !c.chosen);

  return (
    <ExpandableCard title="OCR" subtitle={ocr.final_prn ? `Final PRN: ${ocr.final_prn}` : "No PRN found"} statusDot={ocr.final_prn ? "green" : "amber"}>
      <DiagnosticRow label="OCR Engine" value={ocr.engine ?? "—"} mono />
      <DiagnosticRow label="ROI Detected" value={<StatusPill ok={ocr.roi_detected} />} />
      <DiagnosticRow label="ROI Count" value={ocr.roi_count} mono />
      <DiagnosticRow label="OCR Candidates" value={ocr.candidates.length} mono />
      <DiagnosticRow label="Final PRN" value={ocr.final_prn ?? "—"} mono valueClassName="font-semibold" />
      <DiagnosticRow label="Processing Time" value={formatMs(ocr.processing_time_ms)} mono />

      {ocr.chosen_candidate && (
        <div className="mt-3 rounded-lg border border-emerald-500/30 bg-emerald-500/5 p-3">
          <p className="mb-1.5 text-xs font-semibold text-emerald-400">Chosen Candidate — {ocr.chosen_candidate.source}</p>
          <DiagnosticRow label="Value" value={ocr.chosen_candidate.value ?? "—"} mono />
          <DiagnosticRow label="Digit Score" value={formatScore(ocr.chosen_candidate.digit_score)} mono />
          <DiagnosticRow label="Pattern Score" value={formatScore(ocr.chosen_candidate.pattern_score)} mono />
          <DiagnosticRow label="Confidence" value={formatScore(ocr.chosen_candidate.confidence)} mono />
        </div>
      )}

      {rejected.length > 0 && (
        <div className="mt-3">
          <p className="mb-1.5 text-xs font-semibold text-white/50">Rejected Candidates</p>
          <div className="space-y-2">
            {rejected.map((candidate, idx) => (
              <div key={`${candidate.source}-${idx}`} className="rounded-lg bg-white/5 p-2.5">
                <div className="mb-1 flex items-center justify-between">
                  <span className="text-xs font-medium text-white/70">{candidate.source}</span>
                  <span className="font-mono text-xs text-white/50">{candidate.value ?? "—"}</span>
                </div>
                <div className="flex gap-3 text-[11px] text-white/40">
                  <span>digit {formatScore(candidate.digit_score)}</span>
                  <span>pattern {formatScore(candidate.pattern_score)}</span>
                  <span>conf {formatScore(candidate.confidence)}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </ExpandableCard>
  );
}

// --- Section 4: Final Result ---------------------------------------------------

export function FinalResultSection({ final }: { final: RegistrationAttempt["final"] }) {
  return (
    <ExpandableCard
      title="Final Result"
      subtitle={final.registration_completed ? "Registration successful" : "Not completed"}
      statusDot={final.registration_completed ? "green" : "gray"}
      defaultOpen
    >
      <DiagnosticRow label="Verified Name" value={final.verified_name ?? "—"} />
      <DiagnosticRow label="Verified PRN" value={final.verified_prn ?? "—"} mono valueClassName="font-semibold" />
      <DiagnosticRow label="PRN Source" value={PRN_SOURCE_LABEL[final.prn_source] ?? final.prn_source} />
      <DiagnosticRow label="Registration Successful" value={<StatusPill ok={final.registration_completed} />} />
      {final.warnings.length > 0 && (
        <div className="mt-2 space-y-1 border-t border-white/10 pt-2">
          <p className="text-xs font-semibold text-amber-400">Warnings</p>
          {final.warnings.map((warning) => (
            <p key={warning} className="text-xs text-white/50">
              {warning}
            </p>
          ))}
        </div>
      )}
    </ExpandableCard>
  );
}

// --- Section 5: Pipeline Images -------------------------------------------------

export function PipelineImagesSection({
  attemptId,
  stageImages,
  onOpenImage,
}: {
  attemptId: string;
  stageImages: RegistrationAttempt["stage_images"];
  onOpenImage: (src: string, label: string) => void;
}) {
  return (
    <ExpandableCard title="Pipeline Images" subtitle={`${stageImages.filter((s) => s.available).length}/${stageImages.length} generated`} statusDot="gray">
      <div className="grid grid-cols-3 gap-2.5">
        {stageImages.map((stage) => {
          const src = stage.available ? getDiagnosticsImageUrl(attemptId, stage.stage) : null;
          return (
            <button
              key={stage.stage}
              type="button"
              disabled={!src}
              onClick={() => src && onOpenImage(src, stage.label)}
              className="flex flex-col items-center gap-1.5 disabled:cursor-default"
            >
              <div className="flex aspect-[3/4] w-full items-center justify-center overflow-hidden rounded-lg border border-white/10 bg-white/5">
                {src ? (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img src={src} alt={stage.label} className="h-full w-full object-cover" />
                ) : (
                  <ImageOff className="h-5 w-5 text-white/20" />
                )}
              </div>
              <span className="text-center text-[11px] leading-tight text-white/50">
                {stage.available ? stage.label : "Not Generated"}
              </span>
            </button>
          );
        })}
      </div>
    </ExpandableCard>
  );
}

// --- Section 6: Pipeline Log -----------------------------------------------------

export function PipelineLogSection({ log }: { log: RegistrationAttempt["log"] }) {
  return (
    <ExpandableCard title="Pipeline Log" subtitle={`${log.length} step(s)`} statusDot="gray">
      <div className="space-y-0">
        {log.map((entry, idx) => (
          <div key={idx} className="flex gap-3 py-1.5">
            <div className="flex flex-col items-center pt-0.5">
              <span className="h-1.5 w-1.5 shrink-0 rounded-full bg-white/40" />
              {idx < log.length - 1 && <span className="mt-0.5 w-px flex-1 bg-white/10" style={{ minHeight: "1.25rem" }} />}
            </div>
            <div className="flex-1 pb-1">
              <div className="flex items-baseline justify-between gap-2">
                <span className="text-sm text-white">{entry.step}</span>
                <span className="shrink-0 font-mono text-[11px] text-white/30">+{entry.elapsed_ms.toFixed(0)}ms</span>
              </div>
              {entry.message && <p className="text-xs text-white/40">{entry.message}</p>}
            </div>
          </div>
        ))}
      </div>
    </ExpandableCard>
  );
}
