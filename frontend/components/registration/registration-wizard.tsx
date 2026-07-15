"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { AlertCircle, Camera, IdCard, Loader2, RotateCcw, ShieldCheck } from "lucide-react";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { AuthShell } from "@/components/auth/auth-shell";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { AnalysisSheet } from "@/components/diagnostics/analysis-sheet";
import { IdCardCaptureView } from "@/components/registration/id-card-capture-view";
import { RegistrationReviewForm } from "@/components/registration/registration-review-form";
import { useCamera } from "@/hooks/use-camera";
import { useDiagnosticsEnabled } from "@/hooks/use-diagnostics-enabled";
import { apiRequest, ApiError, uploadFile } from "@/lib/api";
import { storeSession } from "@/lib/auth";
import type { AuthToken, RegistrationAnalysis, RegistrationVerifyResponse } from "@/lib/types";

const MIN_PASSWORD_LENGTH = 8;

type WizardStep =
  | "welcome"
  | "capture"
  | "analyzing"
  | "quality-failed"
  | "review"
  | "password"
  | "submitting"
  | "success";

/**
 * Orchestrates the full "Verified Student Registration" flow, in this
 * order (Milestone 6B — identity must be extracted and confirmed *before*
 * a password is ever collected, never the other way around):
 *
 *   Welcome -> Capture ID -> Run extraction -> Review/correct PRN+name ->
 *   Create Password -> Registration Complete
 *
 * No backend changes were needed for this reordering: `POST
 * /registration/analyze` was already unauthenticated (it has to run before
 * any account exists), and `POST /auth/student/register` already accepts
 * `prn` + `full_name` + `password` together in a single call — this wizard
 * simply collects the password later than it used to, then makes that same
 * call once, right before "Registration Complete". "Confirm" still calls
 * the existing, unmodified `POST /auth/student/register` to create the
 * account, then `POST /registration/verify` to persist the AI-verified
 * snapshot — if that second call fails for any reason, the account still
 * exists and the student still lands on their dashboard; verification
 * metadata is an enhancement, not a gate.
 */
export function RegistrationWizard() {
  const router = useRouter();
  const camera = useCamera();
  const diagnosticsEnabled = useDiagnosticsEnabled();

  const [step, setStep] = useState<WizardStep>("welcome");
  const [showAnalysis, setShowAnalysis] = useState(false);

  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [passwordError, setPasswordError] = useState<string | null>(null);

  const [analysis, setAnalysis] = useState<RegistrationAnalysis | null>(null);
  const [analyzeError, setAnalyzeError] = useState<string | null>(null);

  const [reviewPrn, setReviewPrn] = useState("");
  const [reviewName, setReviewName] = useState("");
  const [submitError, setSubmitError] = useState<string | null>(null);

  const hasRequestedCamera = useRef(false);

  useEffect(() => {
    if (step === "capture" && !hasRequestedCamera.current) {
      hasRequestedCamera.current = true;
      camera.start();
    }
    if (step !== "capture") {
      hasRequestedCamera.current = false;
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [step]);

  useEffect(() => {
    // Paused while the diagnostics analysis sheet is open (dev-only) so it
    // isn't yanked away mid-inspection — see the "View Analysis" button below.
    if (step !== "success" || showAnalysis) return;
    const timeoutId = setTimeout(() => router.push("/student/dashboard"), 2000);
    return () => clearTimeout(timeoutId);
  }, [step, router, showAnalysis]);

  async function handleCapture() {
    const dataUrl = camera.capture();
    if (!dataUrl) return;
    camera.stop();
    setStep("analyzing");
    setAnalyzeError(null);

    try {
      const blob = await (await fetch(dataUrl)).blob();
      const result = await uploadFile<RegistrationAnalysis>("/api/v1/registration/analyze", blob, "id-card.jpg");
      setAnalysis(result);

      if (!result.quality_passed) {
        setStep("quality-failed");
        return;
      }

      setReviewPrn(result.prn ?? "");
      setReviewName(result.student_name ?? "");
      setStep("review");
    } catch (err) {
      setAnalyzeError(err instanceof ApiError ? err.message : "Could not analyze the photo. Please try again.");
      setStep("capture");
    }
  }

  function handleRetake() {
    setAnalysis(null);
    setSubmitError(null);
    setStep("capture");
  }

  function handleReviewContinue() {
    // Nothing is saved yet — this only moves on to password creation, per
    // the required order (identity confirmed first, password last).
    setStep("password");
  }

  function handlePasswordBack() {
    setPasswordError(null);
    setStep("review");
  }

  async function handleConfirm() {
    if (!password || !confirmPassword) {
      setPasswordError("Please enter and confirm your password.");
      return;
    }
    if (password.length < MIN_PASSWORD_LENGTH) {
      setPasswordError(`Password must be at least ${MIN_PASSWORD_LENGTH} characters.`);
      return;
    }
    if (password !== confirmPassword) {
      setPasswordError("Passwords do not match.");
      return;
    }
    setPasswordError(null);
    setStep("submitting");
    setSubmitError(null);

    const prn = reviewPrn.trim();
    const studentName = reviewName.trim();

    try {
      const { access_token } = await apiRequest<AuthToken>("/api/v1/auth/student/register", {
        method: "POST",
        body: { prn, full_name: studentName, password },
        authenticated: false,
      });
      storeSession(access_token, "student");

      try {
        await apiRequest<RegistrationVerifyResponse>("/api/v1/registration/verify", {
          method: "POST",
          body: { prn, student_name: studentName, image_reference: analysis?.image_reference ?? null },
        });
      } catch {
        // The account was created successfully — losing the verification
        // snapshot isn't worth blocking the student from their dashboard.
      }

      setStep("success");
    } catch (err) {
      setSubmitError(err instanceof ApiError ? err.message : "Something went wrong. Please try again.");
      setStep("password");
    }
  }

  if (step === "capture" || step === "analyzing") {
    return (
      <>
        <IdCardCaptureView
          videoRef={camera.videoRef}
          status={camera.status}
          error={camera.error}
          isAnalyzing={step === "analyzing"}
          onBack={() => {
            camera.stop();
            router.push("/student/login");
          }}
          onRetryPermission={camera.start}
          onCapture={handleCapture}
        />
        {step === "capture" && analyzeError && (
          <div className="fixed inset-x-0 top-20 z-30 flex justify-center px-6">
            <span className="max-w-sm rounded-full bg-destructive/90 px-4 py-2 text-center text-sm text-destructive-foreground backdrop-blur">
              {analyzeError}
            </span>
          </div>
        )}
      </>
    );
  }

  return (
    <>
      <AuthShell title="Create your account" description="Verify your student ID to get started.">
      {step === "welcome" && (
        <div className="space-y-5">
          <div className="flex flex-col items-center gap-3 py-2 text-center">
            <div className="flex h-14 w-14 items-center justify-center rounded-full bg-primary/10 text-primary">
              <IdCard className="h-7 w-7" />
            </div>
            <p className="text-sm text-muted-foreground">
              We&apos;ll scan your student ID card first to verify your PRN and name — you&apos;ll create a password
              afterward, once your identity is confirmed.
            </p>
          </div>

          <Button className="w-full gap-2" onClick={() => setStep("capture")}>
            <Camera className="h-4 w-4" />
            Scan My ID Card
          </Button>

          <p className="text-center text-sm text-muted-foreground">
            Already have an account?{" "}
            <Link href="/student/login" className="font-medium text-primary underline-offset-4 hover:underline">
              Sign in
            </Link>
          </p>
        </div>
      )}

      {step === "quality-failed" && analysis && (
        <div className="space-y-4">
          <Alert variant="destructive">
            <AlertCircle />
            <AlertDescription>
              <ul className="list-inside list-disc space-y-0.5">
                {analysis.quality_messages.map((message) => (
                  <li key={message}>{message}</li>
                ))}
              </ul>
            </AlertDescription>
          </Alert>
          <Button className="w-full gap-2" onClick={handleRetake}>
            <RotateCcw className="h-4 w-4" />
            Retake Photo
          </Button>
        </div>
      )}

      {step === "review" && (
        <RegistrationReviewForm
          prn={reviewPrn}
          studentName={reviewName}
          onPrnChange={setReviewPrn}
          onStudentNameChange={setReviewName}
          warnings={analysis?.warnings ?? []}
          barcode={analysis?.barcode ?? null}
          onRetake={handleRetake}
          onContinue={handleReviewContinue}
        />
      )}

      {(step === "password" || step === "submitting") && (
        <div className="space-y-4">
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <ShieldCheck className="h-4 w-4 text-emerald-500" />
            Identity confirmed — now create a password to finish registering.
          </div>

          {submitError && (
            <Alert variant="destructive">
              <AlertCircle />
              <AlertDescription>{submitError}</AlertDescription>
            </Alert>
          )}
          {passwordError && (
            <Alert variant="destructive">
              <AlertCircle />
              <AlertDescription>{passwordError}</AlertDescription>
            </Alert>
          )}

          <div className="space-y-2">
            <Label htmlFor="password">Password</Label>
            <Input
              id="password"
              type="password"
              autoComplete="new-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              disabled={step === "submitting"}
              required
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="confirmPassword">Confirm password</Label>
            <Input
              id="confirmPassword"
              type="password"
              autoComplete="new-password"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              disabled={step === "submitting"}
              required
            />
          </div>

          <div className="flex gap-3 pt-2">
            <Button variant="secondary" className="flex-1" onClick={handlePasswordBack} disabled={step === "submitting"}>
              Back
            </Button>
            <Button className="flex-1 gap-2" onClick={handleConfirm} disabled={step === "submitting"}>
              {step === "submitting" && <Loader2 className="h-4 w-4 animate-spin" />}
              {step === "submitting" ? "Creating account…" : "Create Account"}
            </Button>
          </div>
        </div>
      )}

      {step === "success" && (
        <div className="flex flex-col items-center gap-3 py-4 text-center">
          <div className="flex h-14 w-14 items-center justify-center rounded-full bg-emerald-500/15 text-emerald-500">
            <Camera className="h-6 w-6" />
          </div>
          <p className="font-medium">Registration Successful</p>
          <p className="text-sm text-muted-foreground">Taking you to your dashboard…</p>
          {diagnosticsEnabled && analysis?.diagnostics_attempt_id && (
            <Button variant="ghost" size="sm" className="mt-1 text-xs text-muted-foreground" onClick={() => setShowAnalysis(true)}>
              View Analysis
            </Button>
          )}
        </div>
      )}
      </AuthShell>
      {showAnalysis && analysis?.diagnostics_attempt_id && (
        <AnalysisSheet
          attemptId={analysis.diagnostics_attempt_id}
          onClose={() => {
            setShowAnalysis(false);
            router.push("/student/dashboard");
          }}
        />
      )}
    </>
  );
}
