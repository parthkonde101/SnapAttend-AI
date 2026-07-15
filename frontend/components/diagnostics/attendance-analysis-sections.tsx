"use client";

import { ImageOff } from "lucide-react";

import { DiagnosticRow, ExpandableCard, StatusPill } from "@/components/diagnostics/expandable-card";
import { getAttendanceDiagnosticsImageUrl } from "@/lib/attendance-diagnostics-api";
import type { AttendanceAttempt } from "@/lib/types";

function formatMs(value: number | null): string {
  if (value === null) return "—";
  return `${value.toFixed(1)} ms`;
}

function formatScore(value: number | null): string {
  if (value === null) return "—";
  return value.toFixed(2);
}

function formatRect(rect: readonly [number, number, number, number] | null | undefined): string {
  if (!rect) return "—";
  const [left, top, width, height] = rect;
  return `(${left}, ${top}) ${width}×${height}`;
}

function formatRatio(value: number): string {
  return `${(value * 100).toFixed(0)}%`;
}

// --- Section: ID Verification --------------------------------------------------

export function AttendanceIdentitySection({ identity }: { identity: AttendanceAttempt["identity"] }) {
  return (
    <ExpandableCard
      title="ID Verification"
      subtitle={identity.identity_verified ? "Matched" : identity.extracted_prn ? "No match" : "No PRN read"}
      statusDot={identity.identity_verified ? "green" : identity.extracted_prn ? "red" : "amber"}
      defaultOpen
    >
      <DiagnosticRow label="Extracted PRN" value={identity.extracted_prn ?? "—"} mono valueClassName="font-semibold" />
      <DiagnosticRow label="Source" value={identity.source ?? "—"} />
      <DiagnosticRow label="Matched Student ID" value={identity.matched_student_id ?? "—"} mono />
      <DiagnosticRow label="Identity Verified" value={<StatusPill ok={identity.identity_verified} />} />
      <DiagnosticRow label="OCR Fallback Time" value={formatMs(identity.ocr_fallback_time_ms)} mono />
      {identity.failure_reason && (
        <div className="mt-2 border-t border-white/10 pt-2">
          <p className="text-xs text-white/40">{identity.failure_reason}</p>
        </div>
      )}
    </ExpandableCard>
  );
}

// --- Section: Attendance Marker (the full evidence trail) ----------------------

export function AttendanceMarkerSection({
  attemptId,
  marker,
  onOpenImage,
}: {
  attemptId: string;
  marker: AttendanceAttempt["marker"];
  onOpenImage: (src: string, label: string) => void;
}) {
  return (
    <ExpandableCard
      title="Attendance Marker"
      subtitle={marker.marker_verified ? "Matched" : marker.detected_character ? "Mismatch" : "Not detected"}
      statusDot={marker.marker_verified ? "green" : marker.detected_character ? "red" : "amber"}
      defaultOpen
    >
      <DiagnosticRow label="Expected Marker" value={marker.expected_marker ?? "—"} mono valueClassName="font-semibold" />
      <DiagnosticRow label="Detected Character" value={marker.detected_character ?? "—"} mono valueClassName="font-semibold" />
      <DiagnosticRow label="Confidence" value={formatScore(marker.confidence)} mono />
      <DiagnosticRow label="Marker Verified" value={<StatusPill ok={marker.marker_verified} />} />
      <DiagnosticRow label="Processing Time" value={formatMs(marker.processing_time_ms)} mono />

      {marker.comparison_note && (
        <div className="mt-3 rounded-lg border border-white/10 bg-white/5 p-3">
          <p className="mb-1 text-xs font-semibold text-white/60">Why this result</p>
          <p className="text-xs text-white/70">{marker.comparison_note}</p>
        </div>
      )}

      {marker.failure_reason && (
        <div className="mt-2 border-t border-white/10 pt-2">
          <p className="text-xs text-white/40">{marker.failure_reason}</p>
        </div>
      )}

      {marker.scans.length > 0 && (
        <div className="mt-3 space-y-4">
          <p className="text-xs font-semibold text-white/50">
            Detection Passes ({marker.scans.length}) — geometry first, OCR last
          </p>
          {marker.scans.map((scan, scanIdx) => (
            <div key={scanIdx} className="rounded-lg border border-white/10 bg-white/[0.03] p-3">
              <div className="mb-2 flex items-center justify-between">
                <span className="text-xs font-semibold capitalize text-white/80">
                  Pass {scanIdx}: {scan.tier} region
                </span>
                {scan.search_stage_image_key && (
                  <button
                    type="button"
                    onClick={() =>
                      onOpenImage(
                        getAttendanceDiagnosticsImageUrl(attemptId, scan.search_stage_image_key!),
                        `Pass ${scanIdx}: search crop`
                      )
                    }
                    className="text-[11px] font-medium text-sky-400 active:text-sky-300"
                  >
                    Search crop →
                  </button>
                )}
              </div>
              <p className="mb-2 text-[11px] text-white/50">{scan.outcome}</p>

              {/* Stage 1: display-panel geometry */}
              <div className="mb-2">
                <div className="mb-1 flex items-center justify-between">
                  <span className="text-[11px] font-semibold text-white/40">
                    1. Display Panel Search ({scan.display_regions.length} candidate
                    {scan.display_regions.length === 1 ? "" : "s"})
                  </span>
                  {scan.display_stage_image_key && (
                    <button
                      type="button"
                      onClick={() =>
                        onOpenImage(
                          getAttendanceDiagnosticsImageUrl(attemptId, scan.display_stage_image_key!),
                          `Pass ${scanIdx}: display panel`
                        )
                      }
                      className="text-[11px] font-medium text-sky-400 active:text-sky-300"
                    >
                      Display crop →
                    </button>
                  )}
                </div>
                <div className="space-y-1">
                  {scan.display_regions.map((region, idx) => (
                    <div
                      key={idx}
                      className={`rounded-md p-2 text-[11px] ${region.accepted ? "border border-emerald-500/30 bg-emerald-500/5" : "bg-white/5 text-white/40"}`}
                    >
                      <div className="flex flex-wrap items-center gap-x-3 gap-y-0.5">
                        <span className={region.accepted ? "font-medium text-emerald-400" : ""}>
                          {region.accepted ? "Accepted" : "Rejected"}
                        </span>
                        <span>rect {formatRect(region.rect)}</span>
                        <span>fill {formatRatio(region.fill_ratio)}</span>
                        <span>brightness {region.mean_brightness.toFixed(0)}/255</span>
                      </div>
                      {region.rejection_reason && <p className="mt-0.5 text-white/40">{region.rejection_reason}</p>}
                    </div>
                  ))}
                  {scan.display_regions.length === 0 && (
                    <p className="text-[11px] text-white/30">No dark, panel-shaped region found in this crop.</p>
                  )}
                </div>
              </div>

              {/* Stage 2: glyph geometry (only reached if a display panel was accepted) */}
              {(scan.glyph_candidates.length > 0 || scan.display_stage_image_key) && (
                <div className="mb-2">
                  <div className="mb-1 flex items-center justify-between">
                    <span className="text-[11px] font-semibold text-white/40">
                      2. Glyph Search ({scan.glyph_candidates.length} candidate
                      {scan.glyph_candidates.length === 1 ? "" : "s"})
                    </span>
                    {scan.glyph_stage_image_key && (
                      <button
                        type="button"
                        onClick={() =>
                          onOpenImage(
                            getAttendanceDiagnosticsImageUrl(attemptId, scan.glyph_stage_image_key!),
                            `Pass ${scanIdx}: merged glyph (unnormalized)`
                          )
                        }
                        className="text-[11px] font-medium text-sky-400 active:text-sky-300"
                      >
                        Merged crop →
                      </button>
                    )}
                  </div>
                  <div className="space-y-1">
                    {scan.glyph_candidates.map((glyph, idx) => (
                      <div
                        key={idx}
                        className={`rounded-md p-2 text-[11px] ${
                          glyph.selected
                            ? "border border-emerald-500/40 bg-emerald-500/10"
                            : glyph.accepted
                              ? "border border-emerald-500/20 bg-emerald-500/5"
                              : "bg-white/5 text-white/40"
                        }`}
                      >
                        <div className="flex flex-wrap items-center gap-x-3 gap-y-0.5">
                          <span className={glyph.selected ? "font-medium text-emerald-400" : glyph.accepted ? "text-emerald-400/80" : ""}>
                            {glyph.selected ? "Sent to OCR" : glyph.accepted ? "Accepted" : "Rejected"}
                          </span>
                          <span>rect {formatRect(glyph.rect)}</span>
                          <span>height {formatRatio(glyph.height_ratio)} of panel</span>
                          <span>aspect {glyph.aspect_ratio.toFixed(2)}</span>
                          <span>fill {formatRatio(glyph.fill_ratio)}</span>
                          <span>edges {glyph.edge_density.toFixed(3)}</span>
                          <span>
                            {glyph.member_count} fragment{glyph.member_count === 1 ? "" : "s"} merged
                          </span>
                        </div>
                        {glyph.rejection_reason && <p className="mt-0.5 text-white/40">{glyph.rejection_reason}</p>}
                      </div>
                    ))}
                    {scan.glyph_candidates.length === 0 && (
                      <p className="text-[11px] text-white/30">
                        No bright, glyph-shaped component found inside the display panel.
                      </p>
                    )}
                  </div>
                </div>
              )}

              {/* Stage 3: OCR, run only against the normalized merged glyph */}
              {scan.glyph_stage_image_key && (
                <div>
                  <div className="flex items-center justify-between">
                    <span className="text-[11px] font-semibold text-white/40">3. OCR (normalized glyph only)</span>
                    {scan.glyph_normalized_stage_image_key && (
                      <button
                        type="button"
                        onClick={() =>
                          onOpenImage(
                            getAttendanceDiagnosticsImageUrl(attemptId, scan.glyph_normalized_stage_image_key!),
                            `Pass ${scanIdx}: normalized glyph sent to OCR`
                          )
                        }
                        className="text-[11px] font-medium text-sky-400 active:text-sky-300"
                      >
                        Normalized crop →
                      </button>
                    )}
                  </div>
                  <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-0.5 text-[11px] text-white/60">
                    <span>
                      text <span className="font-mono font-semibold text-white">{scan.ocr_text ?? "—"}</span>
                    </span>
                    <span>confidence {formatScore(scan.ocr_confidence)}</span>
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </ExpandableCard>
  );
}

// --- Section: Final Result ---------------------------------------------------

export function AttendanceFinalSection({ final }: { final: AttendanceAttempt["final"] }) {
  return (
    <ExpandableCard
      title="Final Result"
      subtitle={final.verified ? "Attendance recorded" : final.already_recorded ? "Already recorded" : "Not recorded"}
      statusDot={final.verified ? "green" : final.already_recorded ? "gray" : "red"}
      defaultOpen
    >
      <DiagnosticRow label="Verified" value={<StatusPill ok={final.verified} />} />
      <DiagnosticRow label="Already Recorded" value={<StatusPill ok={final.already_recorded} />} />
      <DiagnosticRow label="Verification Source" value={final.verification_source} />
      <DiagnosticRow label="Reason" value={final.reason ?? "—"} />
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

// --- Section: Pipeline Images (dynamic stage set) -------------------------------

export function AttendancePipelineImagesSection({
  attemptId,
  stageImages,
  onOpenImage,
}: {
  attemptId: string;
  stageImages: AttendanceAttempt["stage_images"];
  onOpenImage: (src: string, label: string) => void;
}) {
  return (
    <ExpandableCard
      title="Pipeline Images"
      subtitle={`${stageImages.filter((s) => s.available).length}/${stageImages.length} generated`}
      statusDot="gray"
    >
      {stageImages.length === 0 ? (
        <p className="text-xs text-white/40">
          No debug images were captured for this attempt — enable SNAPATTEND_AI_DEBUG=1 on the backend to capture the
          exact crops handed to each pipeline stage.
        </p>
      ) : (
        <div className="grid grid-cols-3 gap-2.5">
          {stageImages.map((stage) => {
            const src = stage.available ? getAttendanceDiagnosticsImageUrl(attemptId, stage.stage) : null;
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
      )}
    </ExpandableCard>
  );
}
