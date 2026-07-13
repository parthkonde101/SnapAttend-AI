"use client";

import { useCallback, useEffect, useState } from "react";

import { apiRequest } from "@/lib/api";
import type { ActiveSessionInfo, ActiveSessionResponse, SessionHistoryItem } from "@/lib/types";

const ACTIVE_SESSION_POLL_MS = 3000;

interface UseActiveSessionResult {
  session: ActiveSessionInfo | null;
  isActive: boolean;
  secondsLeft: number;
  isLoading: boolean;
  error: string | null;
  refetch: () => Promise<void>;
}

/**
 * Polls GET /api/v1/attendance/active-session and keeps a live, locally
 * ticking countdown in sync with the backend. Shared by the teacher
 * presentation screen and every student-facing attendance surface so
 * there is exactly one implementation of "is there a session right now,
 * and how much time is left".
 */
export function useActiveSession(): UseActiveSessionResult {
  const [session, setSession] = useState<ActiveSessionInfo | null>(null);
  const [isActive, setIsActive] = useState(false);
  const [secondsLeft, setSecondsLeft] = useState(0);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refetch = useCallback(async () => {
    try {
      const data = await apiRequest<ActiveSessionResponse>("/api/v1/attendance/active-session", {
        method: "GET",
      });
      setSession(data.session);
      setIsActive(data.active);
      setSecondsLeft(data.session ? data.session.remaining_seconds : 0);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to check attendance status.");
    } finally {
      setIsLoading(false);
    }
  }, []);

  // Poll the backend for the source of truth.
  useEffect(() => {
    refetch();
    const pollId = setInterval(refetch, ACTIVE_SESSION_POLL_MS);
    return () => clearInterval(pollId);
  }, [refetch]);

  // Tick the countdown down locally every second between polls, so the
  // timer feels live instead of jumping every 3 seconds.
  useEffect(() => {
    if (!isActive) return;
    const tickId = setInterval(() => {
      setSecondsLeft((prev) => Math.max(0, prev - 1));
    }, 1000);
    return () => clearInterval(tickId);
  }, [isActive]);

  // The instant the local countdown hits zero, reflect that immediately
  // and double-check with the backend.
  useEffect(() => {
    if (isActive && secondsLeft === 0) {
      setIsActive(false);
      refetch();
    }
  }, [isActive, secondsLeft, refetch]);

  return { session, isActive, secondsLeft, isLoading, error, refetch };
}

interface UseSessionHistoryResult {
  sessions: SessionHistoryItem[];
  isLoading: boolean;
  error: string | null;
  refetch: () => Promise<void>;
}

/** Fetches the current teacher's past attendance sessions. */
export function useSessionHistory(): UseSessionHistoryResult {
  const [sessions, setSessions] = useState<SessionHistoryItem[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refetch = useCallback(async () => {
    setIsLoading(true);
    try {
      const data = await apiRequest<SessionHistoryItem[]>("/api/v1/attendance/session-history", {
        method: "GET",
      });
      setSessions(data);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to load session history.");
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    refetch();
  }, [refetch]);

  return { sessions, isLoading, error, refetch };
}
