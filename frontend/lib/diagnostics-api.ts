import { API_BASE_URL } from "@/lib/config";
import type {
  DiagnosticsAttemptFilters,
  DiagnosticsStatusResponse,
  RegistrationAttempt,
  RegistrationAttemptSummary,
  StageImageKey,
} from "@/lib/types";

/**
 * Thin client for the development-only `/api/v1/diagnostics/*` endpoints.
 * No auth header — diagnostics endpoints aren't gated by student/teacher
 * login, only by the backend's ENVIRONMENT/SNAPATTEND_AI_DEBUG check
 * (`app.diagnostics.gating.is_diagnostics_enabled`), which returns a plain
 * 404 for every route here (except `/status`) when disabled.
 */

async function getJson<T>(path: string): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`);
  if (!response.ok) {
    throw new Error(`Diagnostics request failed (${response.status}): ${path}`);
  }
  return (await response.json()) as T;
}

export async function getDiagnosticsStatus(): Promise<DiagnosticsStatusResponse> {
  try {
    return await getJson<DiagnosticsStatusResponse>("/api/v1/diagnostics/status");
  } catch {
    // Network hiccup or backend unreachable — fail closed, same as "disabled".
    return { enabled: false };
  }
}

function buildQuery(filters: DiagnosticsAttemptFilters): string {
  const params = new URLSearchParams();
  if (filters.search) params.set("search", filters.search);
  if (filters.barcode_success !== undefined) params.set("barcode_success", String(filters.barcode_success));
  if (filters.ocr_success !== undefined) params.set("ocr_success", String(filters.ocr_success));
  if (filters.manual_entry !== undefined) params.set("manual_entry", String(filters.manual_entry));
  if (filters.quality_failed !== undefined) params.set("quality_failed", String(filters.quality_failed));
  if (filters.glare !== undefined) params.set("glare", String(filters.glare));
  if (filters.blur !== undefined) params.set("blur", String(filters.blur));
  const query = params.toString();
  return query ? `?${query}` : "";
}

export async function listDiagnosticsAttempts(
  filters: DiagnosticsAttemptFilters = {}
): Promise<RegistrationAttemptSummary[]> {
  return getJson<RegistrationAttemptSummary[]>(`/api/v1/diagnostics/attempts${buildQuery(filters)}`);
}

export async function getDiagnosticsAttempt(attemptId: string): Promise<RegistrationAttempt> {
  return getJson<RegistrationAttempt>(`/api/v1/diagnostics/attempts/${encodeURIComponent(attemptId)}`);
}

export function getDiagnosticsExportUrl(attemptId: string): string {
  return `${API_BASE_URL}/api/v1/diagnostics/attempts/${encodeURIComponent(attemptId)}/export`;
}

export function getDiagnosticsImageUrl(attemptId: string, stage: StageImageKey): string {
  return `${API_BASE_URL}/api/v1/diagnostics/attempts/${encodeURIComponent(attemptId)}/images/${stage}`;
}

/** Triggers a browser download of one attempt's JSON export. */
export function downloadDiagnosticsAttempt(attemptId: string, attemptNumber: number): void {
  const link = document.createElement("a");
  link.href = getDiagnosticsExportUrl(attemptId);
  link.download = `attempt-${attemptNumber}.json`;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
}
