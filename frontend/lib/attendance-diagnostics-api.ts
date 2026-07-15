import { API_BASE_URL } from "@/lib/config";
import type {
  AttendanceAttempt,
  AttendanceAttemptSummary,
  AttendanceDiagnosticsAttemptFilters,
  DiagnosticsStatusResponse,
} from "@/lib/types";

/**
 * Thin client for the development-only `/api/v1/attendance-diagnostics/*`
 * endpoints. Parallel to `lib/diagnostics-api.ts` (the registration
 * diagnostics client, not touched by this change) — same shape, same "no
 * auth header, gated by a 404 when disabled" contract, pointed at the
 * attendance-specific router instead.
 */

async function getJson<T>(path: string): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`);
  if (!response.ok) {
    throw new Error(`Attendance diagnostics request failed (${response.status}): ${path}`);
  }
  return (await response.json()) as T;
}

export async function getAttendanceDiagnosticsStatus(): Promise<DiagnosticsStatusResponse> {
  try {
    return await getJson<DiagnosticsStatusResponse>("/api/v1/attendance-diagnostics/status");
  } catch {
    // Network hiccup or backend unreachable — fail closed, same as "disabled".
    return { enabled: false };
  }
}

function buildQuery(filters: AttendanceDiagnosticsAttemptFilters): string {
  const params = new URLSearchParams();
  if (filters.session_id !== undefined) params.set("session_id", String(filters.session_id));
  if (filters.student_id !== undefined) params.set("student_id", String(filters.student_id));
  const query = params.toString();
  return query ? `?${query}` : "";
}

export async function listAttendanceDiagnosticsAttempts(
  filters: AttendanceDiagnosticsAttemptFilters = {}
): Promise<AttendanceAttemptSummary[]> {
  return getJson<AttendanceAttemptSummary[]>(`/api/v1/attendance-diagnostics/attempts${buildQuery(filters)}`);
}

export async function getAttendanceDiagnosticsAttempt(attemptId: string): Promise<AttendanceAttempt> {
  return getJson<AttendanceAttempt>(`/api/v1/attendance-diagnostics/attempts/${encodeURIComponent(attemptId)}`);
}

export function getAttendanceDiagnosticsExportUrl(attemptId: string): string {
  return `${API_BASE_URL}/api/v1/attendance-diagnostics/attempts/${encodeURIComponent(attemptId)}/export`;
}

/** `stage` is a dynamic key (e.g. "marker_scan_00_primary_psm6") — see
 * `AttendanceAttempt.stage_images` for the actual set on one attempt. */
export function getAttendanceDiagnosticsImageUrl(attemptId: string, stage: string): string {
  return `${API_BASE_URL}/api/v1/attendance-diagnostics/attempts/${encodeURIComponent(attemptId)}/images/${encodeURIComponent(stage)}`;
}

/** Triggers a browser download of one attempt's JSON export. */
export function downloadAttendanceDiagnosticsAttempt(attemptId: string, attemptNumber: number): void {
  const link = document.createElement("a");
  link.href = getAttendanceDiagnosticsExportUrl(attemptId);
  link.download = `attendance-attempt-${attemptNumber}.json`;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
}
