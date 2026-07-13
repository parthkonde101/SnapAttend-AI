"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { apiRequest, ApiError } from "@/lib/api";
import { clearSession, getToken } from "@/lib/auth";
import type { UserRole } from "@/lib/types";

interface UseCurrentUserResult<T> {
  user: T | null;
  isLoading: boolean;
  error: string | null;
}

/**
 * Fetches the profile of the currently authenticated student or teacher.
 * Redirects to the matching login page if there is no valid session.
 */
export function useCurrentUser<T>(role: UserRole, endpoint: string): UseCurrentUserResult<T> {
  const router = useRouter();
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
        if (isMounted) {
          setUser(data);
          setIsLoading(false);
        }
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
  }, [role, endpoint]);

  return { user, isLoading, error };
}
