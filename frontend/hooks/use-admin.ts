"use client";

import { useCallback, useEffect, useState } from "react";

import { apiRequest } from "@/lib/api";
import type { AttendanceStatus, SessionReviewResponse, StudentAttendanceReviewItem } from "@/lib/types";

interface UseAdminSessionReviewResult {
  data: SessionReviewResponse | null;
  isLoading: boolean;
  error: string | null;
  refetch: () => Promise<void>;
  setStatus: (studentId: number, status: AttendanceStatus) => Promise<void>;
}

/**
 * Milestone 7A: the Administrator System's equivalent of
 * `hooks/use-attendance.ts`'s `useSessionReview` — same shape, same
 * optimistic-then-refetch override pattern, but pointed at
 * `/admin/sessions/*` instead of the teacher-scoped
 * `/attendance/session-review/*`. Kept as its own hook in its own file
 * (not added to `use-attendance.ts`) so the teacher-facing hook and its
 * existing behavior are untouched by this milestone.
 *
 * Deliberately simpler than `useSessionReview`: no live polling. An
 * administrator reviewing a session is doing retrospective oversight
 * (usually of an already-ended session, or occasionally spot-checking an
 * active one), not running the live-arrival classroom workflow that
 * polling exists for on the teacher page — a manual refresh (already
 * present on the page, matching the teacher review page's own refresh
 * button) is enough here.
 */
export function useAdminSessionReview(sessionId: number | null): UseAdminSessionReviewResult {
  const [data, setData] = useState<SessionReviewResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refetch = useCallback(async () => {
    if (sessionId === null) {
      setIsLoading(false);
      return;
    }
    try {
      const result = await apiRequest<SessionReviewResponse>(`/api/v1/admin/sessions/${sessionId}/review`, {
        method: "GET",
      });
      setData(result);
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

  const setStatus = useCallback(
    async (studentId: number, status: AttendanceStatus) => {
      if (sessionId === null) return;

      const previous = data;
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
        await apiRequest<StudentAttendanceReviewItem>(`/api/v1/admin/sessions/${sessionId}/override`, {
          method: "POST",
          body: { student_id: studentId, status },
        });
        await refetch();
      } catch (err) {
        setData(previous);
        setError(err instanceof Error ? err.message : "Unable to update attendance status.");
        throw err;
      }
    },
    [sessionId, data, refetch]
  );

  return { data, isLoading, error, refetch, setStatus };
}
