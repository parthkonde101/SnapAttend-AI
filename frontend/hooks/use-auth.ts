"use client";

import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { apiRequest, ApiError } from "@/lib/api";
import { clearSession, getToken } from "@/lib/auth";
import type { Student, UserRole } from "@/lib/types";

interface UseCurrentUserResult<T> {
  user: T | null;
  isLoading: boolean;
  error: string | null;
}

/** The one student page exempt from the forced change-password redirect
 * below — it must be reachable, or a student on the default password could
 * never actually change it. */
const CHANGE_PASSWORD_PATH = "/student/change-password";

/**
 * Fetches the profile of the currently authenticated student or teacher.
 * Redirects to the matching login page if there is no valid session.
 *
 * For students specifically (spec: "Student Import System" / mandatory
 * first-login password change), also redirects to the Change Password
 * screen whenever the fetched profile has `password_changed === false` —
 * this is what makes the screen genuinely unbypassable: every student page
 * built on this hook (dashboard, attendance, etc.) enforces the same
 * check, not just the login flow.
 */
export function useCurrentUser<T>(role: UserRole, endpoint: string): UseCurrentUserResult<T> {
  const router = useRouter();
  const pathname = usePathname();
  const [user, setUser] = useState<T | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let isMounted = true;

    async function loadUser() {
      if (!getToken()) {
        router.replace(`/${role}/login`);
        return;
      }

      try {
        const data = await apiRequest<T>(endpoint, { method: "GET" });
        if (!isMounted) return;

        if (role === "student" && pathname !== CHANGE_PASSWORD_PATH) {
          const student = data as unknown as Student;
          if (student.password_changed === false) {
            router.replace(CHANGE_PASSWORD_PATH);
            return;
          }
        }

        setUser(data);
        setIsLoading(false);
      } catch (err) {
        if (!isMounted) return;

        if (err instanceof ApiError && err.status === 401) {
          clearSession();
          router.replace(`/${role}/login`);
          return;
        }

        setError(err instanceof Error ? err.message : "Failed to load your profile.");
        setIsLoading(false);
      }
    }

    loadUser();

    return () => {
      isMounted = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [role, endpoint, pathname]);

  return { user, isLoading, error };
}
