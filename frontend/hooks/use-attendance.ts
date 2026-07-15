"use client";

import { useCallback, useEffect, useState } from "react";

import { apiRequest } from "@/lib/api";
import type {
  ActiveSessionInfo,
  ActiveSessionResponse,
  AttendanceStatus,
  SessionHistoryItem,
  SessionRecordsResponse,
  SessionReviewResponse,
  StudentAttendanceReviewItem,
} from "@/lib/types";

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

interface UseSessionRecordsResult {
  data: SessionRecordsResponse | null;
  isLoading: boolean;
  error: string | null;
  refetch: () => Promise<void>;
}

const SESSION_RECORDS_POLL_MS = 4000;

/**
 * Polls GET /api/v1/attendance/session-records/{sessionId} for the live
 * present/remaining counts and roster shown on the teacher's presentation
 * screen. Pass `null` while the session id isn't known yet — the hook
 * simply skips fetching.
 */
export function useSessionRecords(sessionId: number | null): UseSessionRecordsResult {
  const [data, setData] = useState<SessionRecordsResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refetch = useCallback(async () => {
    if (sessionId === null) {
      setIsLoading(false);
      return;
    }
    try {
      const result = await apiRequest<SessionRecordsResponse>(`/api/v1/attendance/session-records/${sessionId}`, {
        method: "GET",
      });
      setData(result);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to load attendance records.");
    } finally {
      setIsLoading(false);
    }
  }, [sessionId]);

  useEffect(() => {
    if (sessionId === null) return;
    refetch();
    const pollId = setInterval(refetch, SESSION_RECORDS_POLL_MS);
    return () => clearInterval(pollId);
  }, [sessionId, refetch]);

  return { data, isLoading, error, refetch };
}

interface UseSessionReviewResult {
  data: SessionReviewResponse | null;
  isLoading: boolean;
  error: string | null;
  /** Live countdown, seeded from the backend's `remaining_seconds` and
   * ticked locally each second between polls — same pattern as
   * useActiveSession. Frozen once the session ends. */
  secondsLeft: number;
  refetch: () => Promise<void>;
  /** Optimistically flips one student's status, then confirms with the
   * backend — used by the Present/Absent toggle so the UI updates
   * immediately instead of waiting a full round-trip. Reverts on failure. */
  setStatus: (studentId: number, status: AttendanceStatus) => Promise<void>;
}

const SESSION_REVIEW_POLL_MS = 4000;

/**
 * Fetches the full roster (present + absent) for one of the teacher's own
 * sessions and exposes the Present/Absent override action. Powers
 * /teacher/dashboard/sessions/[id]/review — which, per Milestone 6B, is
 * the *same* page whether the session is still active (live feed) or has
 * ended (final review): this hook polls every 4s while the session is
 * active and stops the instant a fetch reports it has ended (whether
 * ended from this page or the teacher's presentation screen), so the page
 * never needs to navigate anywhere when that happens — it just stops
 * updating. Every poll is a plain, full-roster GET (no separate delta/SSE
 * endpoint): at the ~60-student scale this milestone targets, that's a few
 * KB every 4 seconds, not a meaningful cost — the actual "don't reload
 * everything" concern (re-fetching each student's photo on every poll) is
 * handled where the cost actually is, in the table component's per-student
 * thumbnail cache, not here.
 */
export function useSessionReview(sessionId: number | null): UseSessionReviewResult {
  const [data, setData] = useState<SessionReviewResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [secondsLeft, setSecondsLeft] = useState(0);

  const refetch = useCallback(async () => {
    if (sessionId === null) {
      setIsLoading(false);
      return;
    }
    try {
      const result = await apiRequest<SessionReviewResponse>(`/api/v1/attendance/session-review/${sessionId}`, {
        method: "GET",
      });
      setData(result);
      setSecondsLeft(result.remaining_seconds);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to load attendance review.");
    } finally {
      setIsLoading(false);
    }
  }, [sessionId]);

  useEffect(() => {
    refetch();
  }, [refetch]);

  // Live polling: only while the session is still active. Stops the
  // moment a fetch reports is_active=false — ending the session should
  // "simply stop live updates," per Milestone 6B, never keep re-fetching a
  // roster that can no longer change.
  useEffect(() => {
    if (sessionId === null) return;
    if (data !== null && !data.is_active) return;
    const pollId = setInterval(refetch, SESSION_REVIEW_POLL_MS);
    return () => clearInterval(pollId);
  }, [sessionId, data?.is_active, refetch]);

  // Local per-second countdown between polls, resynced by each poll —
  // identical pattern to useActiveSession's countdown.
  useEffect(() => {
    if (!data?.is_active) return;
    const tickId = setInterval(() => setSecondsLeft((prev) => Math.max(0, prev - 1)), 1000);
    return () => clearInterval(tickId);
  }, [data?.is_active]);

  const setStatus = useCallback(
    async (studentId: number, status: AttendanceStatus) => {
      if (sessionId === null) return;

      const previous = data;
      // Optimistic update: flip the one row immediately (and the
      // present/absent counts with it) so the toggle feels instant. This
      // deliberately does not reposition the row — only a refetch (right
      // below, once the backend confirms) reflects the authoritative
      // arrival-order position for a row that just gained/changed status.
      setData((current) => {
        if (!current) return current;
        let presentDelta = 0;
        const students = current.students.map((item): StudentAttendanceReviewItem => {
          if (item.student_id !== studentId) return item;
          if (item.status !== status) {
            presentDelta = status === "present" ? 1 : -1;
          }
          return { ...item, status, is_teacher_override: true };
        });
        return {
          ...current,
          students,
          present_count: current.present_count + presentDelta,
          absent_count: current.absent_count - presentDelta,
        };
      });

      try {
        await apiRequest<StudentAttendanceReviewItem>(`/api/v1/attendance/session-review/${sessionId}/override`, {
          method: "POST",
          body: { student_id: studentId, status },
        });
        // Refetch (rather than just patching the one returned row) so a
        // student who just gained their first row moves into its correct
        // arrival-ordered position immediately, instead of waiting for the
        // next poll.
        await refetch();
      } catch (err) {
        setData(previous);
        setError(err instanceof Error ? err.message : "Unable to update attendance status.");
        throw err;
      }
    },
    [sessionId, data, refetch]
  );

  return { data, isLoading, error, secondsLeft, refetch, setStatus };
}
