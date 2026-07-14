"use client";

import { AlertTriangle, ArrowLeft, Loader2 } from "lucide-react";
import type { RefObject } from "react";

import { Button } from "@/components/ui/button";
import type { CameraStatus } from "@/hooks/use-camera";

interface IdCardCaptureViewProps {
  videoRef: RefObject<HTMLVideoElement | null>;
  status: CameraStatus;
  error: string | null;
  /** True while a just-captured photo is being analyzed — suppresses the live guide/capture button. */
  isAnalyzing?: boolean;
  onBack: () => void;
  onRetryPermission: () => void;
  onCapture: () => void;
}

/**
 * Dedicated full-screen camera used only during student registration.
 * Deliberately separate from the attendance capture overlay
 * (`app/student/attendance/page.tsx`) — registration uses a single
 * portrait guide sized to a full ID card (good lighting, entire card
 * visible, minimal glare), not the dual landscape/code guide used for
 * marking attendance.
 */
export function IdCardCaptureView({
  videoRef,
  status,
  error,
  isAnalyzing = false,
  onBack,
  onRetryPermission,
  onCapture,
}: IdCardCaptureViewProps) {
  const isReady = status === "ready" && !isAnalyzing;

  return (
    <div className="dark relative min-h-screen w-full overflow-hidden bg-black text-white">
      <video ref={videoRef} autoPlay playsInline muted className="absolute inset-0 h-full w-full object-cover" />

      <div className="absolute inset-x-0 top-0 z-20 flex items-center p-4">
        <Button
          variant="ghost"
          size="icon"
          onClick={onBack}
          aria-label="Back"
          className="border border-white/20 bg-black/40 text-white backdrop-blur hover:bg-black/60 hover:text-white"
        >
          <ArrowLeft className="h-5 w-5" />
        </Button>
      </div>

      {isReady && (
        <>
          {/* Subtle vignette for contrast — purely cosmetic, never crops or alters the captured frame. */}
          <div className="pointer-events-none absolute inset-0 z-[5] bg-gradient-to-b from-black/45 via-transparent to-black/55" />

          <div className="animate-in pointer-events-none absolute inset-0 z-10 flex flex-col items-center justify-center gap-5 px-8">
            <div
              className="relative w-full max-w-[280px] rounded-2xl border-2 border-white/85"
              style={{ aspectRatio: "0.63" }}
            >
              <span className="absolute -left-0.5 -top-0.5 h-6 w-6 rounded-tl-2xl border-l-4 border-t-4 border-white" />
              <span className="absolute -right-0.5 -top-0.5 h-6 w-6 rounded-tr-2xl border-r-4 border-t-4 border-white" />
              <span className="absolute -bottom-0.5 -left-0.5 h-6 w-6 rounded-bl-2xl border-b-4 border-l-4 border-white" />
              <span className="absolute -bottom-0.5 -right-0.5 h-6 w-6 rounded-br-2xl border-b-4 border-r-4 border-white" />
            </div>

            <div className="flex flex-col items-center gap-1.5 text-center">
              <p className="rounded-full bg-black/45 px-4 py-1.5 text-sm text-white/90 backdrop-blur">
                Position your ID card within the frame
              </p>
              <p className="text-sm text-white/70">Make sure the entire card is visible and well lit.</p>
              <p className="text-xs text-white/45">Avoid glare — tilt the card slightly if needed.</p>
            </div>
          </div>

          <div className="absolute inset-x-0 bottom-0 z-20 flex justify-center pb-10">
            <button
              type="button"
              onClick={onCapture}
              aria-label="Capture ID photo"
              className="flex h-20 w-20 items-center justify-center rounded-full border-4 border-white/90 bg-white/10 backdrop-blur transition-transform active:scale-95"
            >
              <span className="h-16 w-16 rounded-full bg-white" />
            </button>
          </div>
        </>
      )}

      {isAnalyzing && (
        <div className="absolute inset-0 z-10 flex flex-col items-center justify-center gap-4 bg-black/70">
          <span className="relative flex h-14 w-14 items-center justify-center">
            <span className="absolute inset-0 animate-ping rounded-full bg-white/20" />
            <Loader2 className="h-8 w-8 animate-spin text-white/80" />
          </span>
          <p className="text-white/70">Analyzing your ID…</p>
        </div>
      )}

      {!isAnalyzing && (status === "idle" || status === "requesting") && (
        <div className="absolute inset-0 z-10 flex flex-col items-center justify-center gap-4 bg-black/70">
          <span className="relative flex h-14 w-14 items-center justify-center">
            <span className="absolute inset-0 animate-ping rounded-full bg-white/20" />
            <Loader2 className="h-8 w-8 animate-spin text-white/80" />
          </span>
          <p className="text-white/70">Requesting camera access…</p>
        </div>
      )}

      {!isAnalyzing && (status === "denied" || status === "unsupported" || status === "error") && (
        <div className="absolute inset-0 z-10 flex flex-col items-center justify-center gap-4 bg-black/80 px-8 text-center">
          <AlertTriangle className="h-10 w-10 text-white/60" />
          <p className="max-w-sm text-white/80">{error}</p>
          {status === "denied" && (
            <Button variant="secondary" onClick={onRetryPermission}>
              Try Again
            </Button>
          )}
        </div>
      )}
    </div>
  );
}
