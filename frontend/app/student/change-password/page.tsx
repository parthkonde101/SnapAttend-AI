"use client";

import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";
import { AlertCircle, KeyRound, Loader2 } from "lucide-react";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { DashboardShell } from "@/components/dashboard/dashboard-shell";
import { useCurrentUser } from "@/hooks/use-auth";
import { changeOwnPassword } from "@/lib/student-api";
import { ApiError } from "@/lib/api";
import type { Student } from "@/lib/types";

const MIN_PASSWORD_LENGTH = 8;

/**
 * Milestone: Unified Student Roster, Part 4 — Login: every Excel-imported
 * account starts on the administrator-issued default password with
 * `password_changed = false`. `hooks/use-auth.ts` redirects a student
 * straight here on login until they set their own password — "students
 * must not be able to bypass this page." This page itself calls
 * `useCurrentUser` the same way every other student page does, which is
 * what makes it exempt from that same redirect (see `CHANGE_PASSWORD_PATH`
 * in that hook).
 */
export default function StudentChangePasswordPage() {
  const router = useRouter();
  const { user, isLoading, error: loadError } = useCurrentUser<Student>("student", "/api/v1/students/me");

  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [formError, setFormError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setFormError(null);

    if (!currentPassword) {
      setFormError("Please enter your current password.");
      return;
    }
    if (newPassword.length < MIN_PASSWORD_LENGTH) {
      setFormError(`New password must be at least ${MIN_PASSWORD_LENGTH} characters.`);
      return;
    }
    if (newPassword !== confirmPassword) {
      setFormError("New passwords do not match.");
      return;
    }
    if (newPassword === currentPassword) {
      setFormError("New password must be different from your current password.");
      return;
    }

    setIsSubmitting(true);
    try {
      // The session token itself is unchanged by this call — only
      // `password_changed` flips server-side. The next `useCurrentUser`
      // fetch on the dashboard sees that and stops redirecting here.
      await changeOwnPassword({ current_password: currentPassword, new_password: newPassword });
      router.replace("/student/dashboard");
    } catch (err) {
      setFormError(err instanceof ApiError ? err.message : "Unable to change your password. Please try again.");
    } finally {
      setIsSubmitting(false);
    }
  }

  if (isLoading) {
    return (
      <DashboardShell>
        <div className="flex justify-center py-12">
          <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
        </div>
      </DashboardShell>
    );
  }

  if (loadError || !user) {
    return (
      <DashboardShell>
        <Alert variant="destructive">
          <AlertDescription>{loadError ?? "Unable to load your profile."}</AlertDescription>
        </Alert>
      </DashboardShell>
    );
  }

  return (
    <DashboardShell>
      <div className="mx-auto w-full max-w-md">
        <Card className="animate-in">
          <CardHeader className="items-center space-y-2 text-center">
            <div className="flex h-12 w-12 items-center justify-center rounded-full bg-primary/10 text-primary">
              <KeyRound className="h-6 w-6" />
            </div>
            <CardTitle>Set a new password</CardTitle>
            <CardDescription>
              Your account was created with a temporary password. Set your own password to continue to your
              dashboard.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleSubmit} className="space-y-4" noValidate>
              {formError && (
                <Alert variant="destructive">
                  <AlertCircle />
                  <AlertDescription>{formError}</AlertDescription>
                </Alert>
              )}

              <div className="space-y-2">
                <Label htmlFor="currentPassword">Current password</Label>
                <Input
                  id="currentPassword"
                  type="password"
                  autoComplete="current-password"
                  value={currentPassword}
                  onChange={(e) => setCurrentPassword(e.target.value)}
                  disabled={isSubmitting}
                  required
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="newPassword">New password</Label>
                <Input
                  id="newPassword"
                  type="password"
                  autoComplete="new-password"
                  value={newPassword}
                  onChange={(e) => setNewPassword(e.target.value)}
                  disabled={isSubmitting}
                  required
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="confirmPassword">Confirm new password</Label>
                <Input
                  id="confirmPassword"
                  type="password"
                  autoComplete="new-password"
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  disabled={isSubmitting}
                  required
                />
              </div>

              <Button type="submit" className="w-full gap-2" disabled={isSubmitting}>
                {isSubmitting && <Loader2 className="h-4 w-4 animate-spin" />}
                Set new password
              </Button>
            </form>
          </CardContent>
        </Card>
      </div>
    </DashboardShell>
  );
}
