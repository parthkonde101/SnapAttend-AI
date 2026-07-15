"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { AlertCircle, Camera, KeyRound, Loader2, RotateCcw, ShieldCheck } from "lucide-react";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { AuthShell } from "@/components/auth/auth-shell";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { IdCardCaptureView } from "@/components/registration/id-card-capture-view";
import { useCamera } from "@/hooks/use-camera";
import { apiRequest, ApiError, uploadFileWithFields } from "@/lib/api";
import { storeSession } from "@/lib/auth";
import type { AuthToken, PasswordResetVerifyResponse } from "@/lib/types";

const MIN_PASSWORD_LENGTH = 8;

type WizardStep = "prn" | "capture" | "verifying" | "verify-failed" | "password" | "submitting" | "success";

/**
 * No-email, no-OTP password reset: "Forgot Password -> Enter PRN -> Capture
 * ID Card -> Verify PRN matches extracted PRN -> Create New Password ->
 * Success". The ID card is the identity proof, exactly like registration —
 * this deliberately reuses the same registration verification engine
 * (`POST /registration/analyze`'s underlying pipeline, called here via
 * `POST /auth/student/forgot-password/verify`) instead of building a
 * second one. See `app/api/v1/endpoints/auth.py` for the backend half.
 */
export function ForgotPasswordWizard() {
  const router = useRouter();
  const camera = useCamera();

  const [step, setStep] = useState<WizardStep>("prn");
  const [prn, setPrn] = useState("");
  const [prnError, setPrnError] = useState<string | null>(null);

  const [verifyError, setVerifyError] = useState<string | null>(null);
  const [resetToken, setResetToken] = useState<string | null>(null);

  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [passwordError, setPasswordError] = useState<string | null>(null);
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
    if (step !== "success") return;
    const timeoutId = setTimeout(() => router.push("/student/dashboard"), 1500);
    return () => clearTimeout(timeoutId);
  }, [step, router]);

  function handlePrnNext() {
    if (!prn.trim()) {
      setPrnError("Please enter your PRN.");
      return;
    }
    setPrnError(null);
    setStep("capture");
  }

  async function handleCapture() {
    const dataUrl = camera.capture();
    if (!dataUrl) return;
    camera.stop();
    setStep("verifying");
    setVerifyError(null);

    try {
      const blob = await (await fetch(dataUrl)).blob();
      const result = await uploadFileWithFields<PasswordResetVerifyResponse>(
        "/api/v1/auth/student/forgot-password/verify",
        blob,
        "id-card.jpg",
        { prn: prn.trim() }
      );
      setResetToken(result.reset_token);
      setStep("password");
    } catch (err) {
      setVerifyError(
        err instanceof ApiError ? err.message : "Could not verify your ID card. Please try again."
      );
      setStep("verify-failed");
    }
  }

  function handleRetake() {
    setStep("capture");
  }

  function handleEditPrn() {
    setVerifyError(null);
    setStep("prn");
  }

  async function handleResetPassword() {
    if (!password || !confirmPassword) {
      setPasswordError("Please enter and confirm your new password.");
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
    if (!resetToken) {
      setPasswordError("Your verification expired. Please start over.");
      return;
    }
    setPasswordError(null);
    setStep("submitting");
    setSubmitError(null);

    try {
      const { access_token } = await apiRequest<AuthToken>("/api/v1/auth/student/forgot-password/reset", {
        method: "POST",
        body: { new_password: password },
        authenticated: false,
        headers: { Authorization: `Bearer ${resetToken}` },
      });
      storeSession(access_token, "student");
      setStep("success");
    } catch (err) {
      setSubmitError(err instanceof ApiError ? err.message : "Something went wrong. Please try again.");
      setStep("password");
    }
  }

  if (step === "capture" || step === "verifying") {
    return (
      <IdCardCaptureView
        videoRef={camera.videoRef}
        status={camera.status}
        error={camera.error}
        isAnalyzing={step === "verifying"}
        onBack={() => {
          camera.stop();
          setStep("prn");
        }}
        onRetryPermission={camera.start}
        onCapture={handleCapture}
      />
    );
  }

  return (
    <AuthShell title="Reset your password" description="Verify your student ID to set a new password.">
      {step === "prn" && (
        <div className="space-y-4">
          {prnError && (
            <Alert variant="destructive">
              <AlertCircle />
              <AlertDescription>{prnError}</AlertDescription>
            </Alert>
          )}

          <div className="space-y-2">
            <Label htmlFor="prn">PRN</Label>
            <Input
              id="prn"
              placeholder="e.g. 2023BTCS0001"
              autoComplete="username"
              value={prn}
              onChange={(e) => setPrn(e.target.value)}
              required
            />
          </div>

          <p className="text-xs text-muted-foreground">
            Next, you&apos;ll capture a photo of your student ID — we&apos;ll confirm it matches this PRN before
            letting you set a new password. No email or OTP needed.
          </p>

          <Button className="w-full gap-2" onClick={handlePrnNext}>
            <Camera className="h-4 w-4" />
            Continue to ID capture
          </Button>

          <p className="text-center text-sm text-muted-foreground">
            <Link href="/student/login" className="font-medium text-primary underline-offset-4 hover:underline">
              Back to sign in
            </Link>
          </p>
        </div>
      )}

      {step === "verify-failed" && (
        <div className="space-y-4">
          <Alert variant="destructive">
            <AlertCircle />
            <AlertDescription>{verifyError}</AlertDescription>
          </Alert>
          <div className="flex gap-3">
            <Button variant="secondary" className="flex-1 gap-2" onClick={handleEditPrn}>
              Edit PRN
            </Button>
            <Button className="flex-1 gap-2" onClick={handleRetake}>
              <RotateCcw className="h-4 w-4" />
              Retake Photo
            </Button>
          </div>
        </div>
      )}

      {(step === "password" || step === "submitting") && (
        <div className="space-y-4">
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <ShieldCheck className="h-4 w-4 text-emerald-500" />
            Identity verified — create a new password.
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
            <Label htmlFor="newPassword">New password</Label>
            <Input
              id="newPassword"
              type="password"
              autoComplete="new-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              disabled={step === "submitting"}
              required
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="confirmNewPassword">Confirm new password</Label>
            <Input
              id="confirmNewPassword"
              type="password"
              autoComplete="new-password"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              disabled={step === "submitting"}
              required
            />
          </div>

          <Button className="w-full gap-2" onClick={handleResetPassword} disabled={step === "submitting"}>
            {step === "submitting" && <Loader2 className="h-4 w-4 animate-spin" />}
            {step === "submitting" ? "Resetting…" : "Reset Password"}
          </Button>
        </div>
      )}

      {step === "success" && (
        <div className="flex flex-col items-center gap-3 py-4 text-center">
          <div className="flex h-14 w-14 items-center justify-center rounded-full bg-emerald-500/15 text-emerald-500">
            <KeyRound className="h-6 w-6" />
          </div>
          <p className="font-medium">Password Reset</p>
          <p className="text-sm text-muted-foreground">Taking you to your dashboard…</p>
        </div>
      )}
    </AuthShell>
  );
}
