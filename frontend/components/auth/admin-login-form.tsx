"use client";

import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";
import { AlertCircle, Loader2 } from "lucide-react";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { adminLogin } from "@/lib/admin-api";
import { ApiError } from "@/lib/api";
import { storeSession } from "@/lib/auth";

/**
 * Dedicated administrator login form (Milestone 7A). Deliberately its own
 * component, not a reskinned `TeacherLoginForm` — it posts to
 * `/auth/admin/login`, a completely separate authentication flow that
 * issues a token with `role="admin"`, never `"teacher"`. See
 * `app/api/deps.py`'s `get_current_admin` on the backend for why that
 * distinction has to be structural, not cosmetic.
 */
export function AdminLoginForm() {
  const router = useRouter();
  const [loginId, setLoginId] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);

    if (!loginId.trim() || !password) {
      setError("Please enter your login ID and password.");
      return;
    }

    setIsSubmitting(true);
    try {
      const { access_token } = await adminLogin(loginId.trim(), password);
      storeSession(access_token, "admin");
      router.push("/admin/dashboard");
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
        <Label htmlFor="loginId">Login ID</Label>
        <Input
          id="loginId"
          name="loginId"
          placeholder="e.g. ADMIN"
          autoComplete="username"
          value={loginId}
          onChange={(e) => setLoginId(e.target.value)}
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

      <p className="text-center text-sm text-muted-foreground">Administrator access only.</p>
    </form>
  );
}
