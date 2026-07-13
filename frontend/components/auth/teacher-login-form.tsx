"use client";

import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";
import { AlertCircle, Loader2 } from "lucide-react";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { apiRequest, ApiError } from "@/lib/api";
import { storeSession } from "@/lib/auth";
import type { AuthToken } from "@/lib/types";

export function TeacherLoginForm() {
  const router = useRouter();
  const [teacherId, setTeacherId] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);

    if (!teacherId.trim() || !password) {
      setError("Please enter your teacher ID and password.");
      return;
    }

    setIsSubmitting(true);
    try {
      const { access_token } = await apiRequest<AuthToken>("/api/v1/auth/teacher/login", {
        method: "POST",
        body: { teacher_id: teacherId.trim(), password },
        authenticated: false,
      });
      storeSession(access_token, "teacher");
      router.push("/teacher/dashboard");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong. Please try again.");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4" noValidate>
      {error && (
        <Alert variant="destructive">
          <AlertCircle />
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      <div className="space-y-2">
        <Label htmlFor="teacherId">Teacher ID</Label>
        <Input
          id="teacherId"
          name="teacherId"
          placeholder="e.g. T001"
          autoComplete="username"
          value={teacherId}
          onChange={(e) => setTeacherId(e.target.value)}
          disabled={isSubmitting}
          required
        />
      </div>

      <div className="space-y-2">
        <Label htmlFor="password">Password</Label>
        <Input
          id="password"
          name="password"
          type="password"
          autoComplete="current-password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          disabled={isSubmitting}
          required
        />
      </div>

      <Button type="submit" className="w-full" disabled={isSubmitting}>
        {isSubmitting && <Loader2 className="animate-spin" />}
        Sign in
      </Button>

      <p className="text-center text-sm text-muted-foreground">
        Teacher accounts are provisioned by an administrator.
      </p>
    </form>
  );
}
