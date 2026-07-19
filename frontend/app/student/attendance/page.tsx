"use client";

import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { AlertTriangle, ArrowLeft, CheckCircle2, Info, Loader2, RotateCcw } from "lucide-react";

import { Button } from "@/components/ui/button";
import { useActiveSession } from "@/hooks/use-attendance";
import { useCurrentUser } from "@/hooks/use-auth";
import { useCamera, type CameraStatus } from "@/hooks/use-camera";
import { uploadFileWithFields, ApiError } from "@/lib/api";
import { getOrCreateDeviceId } from "@/lib/device";
import { formatCountdown } from "@/lib/utils";
import type { MarkAttendanceResponse, Student } from "@/lib/types";

type CaptureStep = "camera" | "preview" | "uploading" | "success" | "already-marked";

/**
 * Full-screen attendance capture flow, reached from the student
 * dashboard's "Mark Attendance" button while a session is active. Submits
 * directly to `/attendance/mark`, which runs the Attendance Verification
 * Engine (ID card + classroom marker, both independently verified) and
 * records attendance on the first success. Students may retry unlimited
 * times while the session stays active — a failed attempt just returns to
 * the preview step with the reason shown, never a dead end.
 */
export default function StudentAttendancePage() {
  const router = useRouter();
  // Reachable directly by URL, not just via the dashboard button — this
  // call's redirect side effect (see hooks/use-auth.ts) is what keeps the
  // mandatory change-password screen genuinely unbypassable for a student
  // who still has `password_changed === false`, not just a dashboard-only
  // gate. The fetched profile itself isn't otherwise used on this page.
  useCurrentUser<Student>("student", "/api/v1/students/me");
  const { isActive, secondsLeft, isLoading: isSessionLoading } = useActiveSession();
  const { videoRef, status: cameraStatus, error: cameraError, start, stop, capture } = useCamera();

  const [step, setStep] = useState<CaptureStep>("camera");
  const [photo, setPhoto] = useState<string | null>(null);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [warnings, setWarnings] = useState<string[]>([]);
  const hasRequestedCamera = useRef(false);

  // Auto-request the camera once we've confirmed a session is active.
  useEffect(() => {
    if (isActive && step === "camera" && !hasRequestedCamera.current) {
      hasRequestedCamera.current = true;
      start();
    }
  }, [isActive, step, start]);

  // Auto-return to the dashboard shortly after a successful (or
  // already-recorded) verification.
  useEffect(() => {
    if (step !== "success" && step !== "already-marked") return;
    const timeoutId = setTimeout(() => router.push("/student/dashboard"), 2500);
    return () => clearTimeout(timeoutId);
  }, [step, router]);

  function handleBack() {
    stop();
    router.push("/student/dashboard");
  }

  function handleCapture() {
    const dataUrl = capture();
    if (!dataUrl) return;
    stop();
    setPhoto(dataUrl);
    setStep("preview");
  }

  function handleRetake() {
    setPhoto(null);
    setUploadError(null);
    setStep("camera");
    start();
  }

  async function handleSubmit() {
    if (!photo) return;
    setStep("uploading");
    setUploadError(null);
    try {
      const blob = await (await fetch(photo)).blob();
      const deviceId = getOrCreateDeviceId();
      const result = await uploadFileWithFields<MarkAttendanceResponse>(
        "/api/v1/attendance/mark",
        blob,
        "attendance.jpg",
        deviceId ? { device_id: deviceId } : {},
        { authenticated: true }
      );
      setWarnings(result.warnings);

      if (result.success) {
        setStep("success");
      } else if (result.already_recorded) {
        setStep("already-marked");
      } else {
        setUploadError(result.reason ?? "Verification failed. Please retry.");
        setStep("preview");
      }
    } catch (err) {
      setUploadError(err instanceof ApiError ? err.message : "Upload failed. Please try again.");
      setStep("preview");
    }
  }

  const showSessionEndedState = !isSessionLoading && !isActive && step === "camera";

  return (
    <div className="dark h-dvh w-full overflow-hidden bg-gradient-to-b from-slate-950 to-black text-white">
      {isSessionLoading && (
        <div className="flex h-full items-center justify-center">
          <Loader2 className="h-8 w-8 animate-spin text-white/60" />
        </div>
      )}

      {showSessionEndedState && (
        <div className="flex h-full flex-col items-center justify-center gap-6 overflow-y-auto px-6 text-center animate-in">
          <h1 className="text-2xl font-bold">This attendance session has ended</h1>
          <p className="max-w-sm text-white/60">
            Head back to your dashboard — you&apos;ll see the next session as soon as it starts.
          </p>
          <Button variant="secondary" onClick={() => router.push("/student/dashboard")}>
            Back to dashboard
          </Button>
        </div>
      )}

      {!isSessionLoading && !showSessionEndedState && step === "camera" && (
        <CameraView
          videoRef={videoRef}
          status={cameraStatus}
          error={cameraError}
          secondsLeft={secondsLeft}
          onBack={handleBack}
          onRetryPermission={start}
          onCapture={handleCapture}
        />
      )}

      {!isSessionLoading && (step === "preview" || step === "uploading") && photo && (
        <PreviewView
          photo={photo}
          isUploading={step === "uploading"}
          error={uploadError}
          onBack={handleBack}
          onRetake={handleRetake}
          onSubmit={handleSubmit}
        />
      )}

      {step === "success" && <SuccessView warnings={warnings} onDone={() => router.push("/student/dashboard")} />}

      {step === "already-marked" && <AlreadyMarkedView onDone={() => router.push("/student/dashboard")} />}
    </div>
  );
}

interface CameraViewProps {
  videoRef: React.RefObject<HTMLVideoElement | null>;
  status: CameraStatus;
  error: string | null;
  secondsLeft: number;
  onBack: () => void;
  onRetryPermission: () => void;
  onCapture: () => void;
}

function CameraView({ videoRef, status, error, secondsLeft, onBack, onRetryPermission, onCapture }: CameraViewProps) {
  const isReady = status === "ready";

  // Milestone 7C: rebuilt as a three-row flex column (top bar / preview /
  // controls) instead of everything layered with `position: absolute` over
  // a full-bleed video. The preview row is `flex-1 min-h-0`, so it always
  // takes exactly the space left over after the top bar and the capture
  // button — the button is a real flow sibling below the preview, not an
  // absolutely-positioned overlay that could end up sitting on top of the
  // instructions text on a short viewport. Guides/instructions are still
  // overlaid, but confined to the preview row's own bounds, so they can
  // never reach into the controls row.
  return (
    <div className="flex h-full w-full flex-col overflow-hidden bg-black">
      <div
        className="z-20 flex shrink-0 items-center justify-between p-4"
        style={{ paddingTop: "max(1rem, env(safe-area-inset-top))" }}
      >
        <Button
          variant="ghost"
          size="icon"
          onClick={onBack}
          aria-label="Back"
          className="border border-white/20 bg-black/40 text-white backdrop-blur hover:bg-black/60 hover:text-white"
        >
          <ArrowLeft className="h-5 w-5" />
        </Button>
        {isReady && (
          <span className="rounded-full border border-white/20 bg-black/40 px-3 py-1 font-mono text-sm tabular-nums text-white/80 backdrop-blur">
            {formatCountdown(secondsLeft)}
          </span>
        )}
      </div>

      <div className="relative min-h-0 flex-1 overflow-hidden">
        <video ref={videoRef} autoPlay playsInline muted className="absolute inset-0 h-full w-full object-cover" />

        {isReady && (
          <>
            {/* Subtle vignette for contrast — purely cosmetic, never crops or alters the captured frame. */}
            <div className="pointer-events-none absolute inset-0 z-[5] bg-gradient-to-b from-black/45 via-transparent to-black/45" />

            <div className="animate-in pointer-events-none absolute inset-0 z-10 flex flex-col items-center justify-center gap-4 px-5 py-3">
              <div className="grid w-full max-w-md grid-cols-[7fr_3fr] items-center gap-3">
                {/* Left guide: large portrait box for the ID card. */}
                <div className="relative rounded-2xl border-2 border-white/85" style={{ aspectRatio: "0.63" }}>
                  <span className="absolute -left-0.5 -top-0.5 h-6 w-6 rounded-tl-2xl border-l-4 border-t-4 border-white" />
                  <span className="absolute -right-0.5 -top-0.5 h-6 w-6 rounded-tr-2xl border-r-4 border-t-4 border-white" />
                  <span className="absolute -bottom-0.5 -left-0.5 h-6 w-6 rounded-bl-2xl border-b-4 border-l-4 border-white" />
                  <span className="absolute -bottom-0.5 -right-0.5 h-6 w-6 rounded-br-2xl border-b-4 border-r-4 border-white" />
                </div>

                {/* Right guide: smaller framing box for the projected session code. Framing only — never crops or processes the image. */}
                <div
                  className="relative rounded-xl border-2 border-dashed border-white/55"
                  style={{ aspectRatio: "0.85" }}
                />
              </div>

              <div className="flex flex-col items-center gap-1 text-center">
                <p className="rounded-full bg-black/45 px-3 py-1 text-xs text-white/90 backdrop-blur sm:text-sm">
                  Hold your ID card close until it fills the left guide.
                </p>
                <p className="hidden text-xs text-white/60 sm:block">Keep the classroom marker visible inside the right guide.</p>
              </div>
            </div>
          </>
        )}

        {(status === "idle" || status === "requesting") && (
          <div className="absolute inset-0 z-10 flex flex-col items-center justify-center gap-4 bg-black/70">
            <span className="relative flex h-14 w-14 items-center justify-center">
              <span className="absolute inset-0 animate-ping rounded-full bg-white/20" />
              <Loader2 className="h-8 w-8 animate-spin text-white/80" />
            </span>
            <p className="text-white/70">Requesting camera access…</p>
          </div>
        )}

        {(status === "denied" || status === "unsupported" || status === "error") && (
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

      {isReady && (
        <div
          className="z-20 flex shrink-0 justify-center bg-black py-4"
          style={{ paddingBottom: "max(1rem, env(safe-area-inset-bottom))" }}
        >
          <button
            type="button"
            onClick={onCapture}
            aria-label="Capture photo"
            className="flex h-16 w-16 items-center justify-center rounded-full border-4 border-white/90 bg-white/10 backdrop-blur transition-transform active:scale-95 sm:h-20 sm:w-20"
          >
            <span className="h-12 w-12 rounded-full bg-white sm:h-16 sm:w-16" />
          </button>
        </div>
      )}
    </div>
  );
}

interface PreviewViewProps {
  photo: string;
  isUploading: boolean;
  error: string | null;
  onBack: () => void;
  onRetake: () => void;
  onSubmit: () => void;
}

function PreviewView({ photo, isUploading, error, onBack, onRetake, onSubmit }: PreviewViewProps) {
  return (
    <div className="flex h-full w-full flex-col bg-black">
      <div
        className="z-20 flex shrink-0 items-center p-4"
        style={{ paddingTop: "max(1rem, env(safe-area-inset-top))" }}
      >
        <Button
          variant="ghost"
          size="icon"
          onClick={onBack}
          disabled={isUploading}
          aria-label="Back"
          className="border border-white/20 bg-black/40 text-white backdrop-blur hover:bg-black/60 hover:text-white"
        >
          <ArrowLeft className="h-5 w-5" />
        </Button>
      </div>

      <div className="animate-in relative min-h-0 flex-1">
        {/* Local capture preview — a plain <img> is correct here, not a next/image asset. */}
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img src={photo} alt="Captured ID card" className="absolute inset-0 h-full w-full object-cover" />
      </div>

      <div
        className="animate-in relative z-20 flex shrink-0 flex-col gap-3 bg-gradient-to-t from-black via-black/95 to-transparent p-5 pt-10"
        style={{ paddingBottom: "max(1.25rem, env(safe-area-inset-bottom))" }}
      >
        {error && (
          <p className="rounded-lg bg-destructive/10 px-4 py-2 text-center text-sm text-destructive">{error}</p>
        )}
        <div className="flex gap-3">
          <Button variant="secondary" size="lg" className="flex-1 gap-2" onClick={onRetake} disabled={isUploading}>
            <RotateCcw className="h-4 w-4" />
            Retake
          </Button>
          <Button size="lg" className="flex-1 gap-2" onClick={onSubmit} disabled={isUploading}>
            {isUploading ? <Loader2 className="h-4 w-4 animate-spin" /> : <CheckCircle2 className="h-4 w-4" />}
            {isUploading ? "Uploading…" : "Submit"}
          </Button>
        </div>
      </div>
    </div>
  );
}

function SuccessView({ warnings, onDone }: { warnings: string[]; onDone: () => void }) {
  return (
    <div className="flex h-full flex-col items-center justify-center gap-6 overflow-y-auto px-8 text-center animate-in">
      <div className="flex h-20 w-20 items-center justify-center rounded-full bg-emerald-500/15 text-emerald-400">
        <CheckCircle2 className="h-10 w-10" />
      </div>
      <div className="space-y-2">
        <h1 className="text-2xl font-bold">Attendance marked!</h1>
        <p className="max-w-sm text-white/60">Your ID and the classroom marker were both verified.</p>
        {warnings.length > 0 && <p className="max-w-sm text-xs text-white/40">{warnings.join(" ")}</p>}
      </div>
      <Button variant="secondary" onClick={onDone}>
        Back to dashboard
      </Button>
    </div>
  );
}

function AlreadyMarkedView({ onDone }: { onDone: () => void }) {
  return (
    <div className="flex h-full flex-col items-center justify-center gap-6 overflow-y-auto px-8 text-center animate-in">
      <div className="flex h-20 w-20 items-center justify-center rounded-full bg-sky-500/15 text-sky-400">
        <Info className="h-10 w-10" />
      </div>
      <div className="space-y-2">
        <h1 className="text-2xl font-bold">Already marked present.</h1>
        <p className="max-w-sm text-white/60">You&apos;ve already been marked present for this session.</p>
      </div>
      <Button variant="secondary" onClick={onDone}>
        Back to dashboard
      </Button>
    </div>
  );
}
