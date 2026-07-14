export type UserRole = "student" | "teacher";

export interface AuthToken {
  access_token: string;
  token_type: string;
}

export interface Student {
  id: number;
  prn: string;
  full_name: string;
  created_at: string;
}

export interface Teacher {
  id: number;
  teacher_id: string;
  full_name: string;
  created_at: string;
}

export interface AttendanceSession {
  id: number;
  session_code: string;
  teacher_id: number;
  expires_at: string;
  is_active: boolean;
  created_at: string;
}

// --- Attendance Session Engine ---------------------------------------------

export interface ActiveSessionInfo {
  session_id: number;
  session_code: string;
  created_at: string;
  expires_at: string;
  duration_seconds: number;
  remaining_seconds: number;
  present_count: number;
}

export interface ActiveSessionResponse {
  active: boolean;
  session: ActiveSessionInfo | null;
}

export type SessionStatus = "active" | "ended";

export interface SessionHistoryItem {
  session_id: number;
  session_code: string;
  created_at: string;
  expires_at: string;
  duration_seconds: number;
  status: SessionStatus;
  present_count: number;
}

// --- Smart Camera Capture ---------------------------------------------------

export interface PhotoUploadResponse {
  success: boolean;
  imageId: string;
}

// --- Registration Intelligence Pipeline -------------------------------------

/** Mirrors the backend's RegistrationAnalysis (app/ai/schemas.py). */
export interface RegistrationAnalysis {
  quality_passed: boolean;
  quality_messages: string[];
  id_detected: boolean;
  barcode: string | null;
  prn: string | null;
  student_name: string | null;
  warnings: string[];
  raw_text: string[];
  image_reference: string | null;
  /** Development-use only — not rendered in the registration UI. */
  barcode_type: string | null;
  /** Development-use only — one of: not_attempted, decoded, not_found, failed. */
  barcode_status: string;
  /** Development-use only. */
  barcode_failure_reason: string | null;
  /** Development-use only — set only when diagnostics are enabled server-side. */
  diagnostics_attempt_id: string | null;
}

export interface RegistrationVerifyResponse {
  verified_prn: string;
  verified_name: string;
  id_image_path: string | null;
  verified_at: string;
}

// --- Developer Diagnostics (development-only) --------------------------------
// Mirrors backend/app/diagnostics/schemas.py. This entire section only ever
// renders when GET /diagnostics/status reports { enabled: true }.

export type PrnSource = "barcode" | "ocr" | "manual" | "none";
export type BarcodeDiagnosticsStatus = "not_attempted" | "decoded" | "not_found" | "failed";

export interface PipelineLogEntry {
  step: string;
  message: string | null;
  timestamp: string;
  elapsed_ms: number;
}

export interface QualityDiagnostics {
  width: number | null;
  height: number | null;
  resolution_ok: boolean;
  blur_score: number | null;
  blur_ok: boolean;
  brightness: number | null;
  brightness_ok: boolean;
  contrast: number | null;
  glare_ratio: number | null;
  glare_ok: boolean;
  coverage_ok: boolean;
  passed: boolean;
  messages: string[];
  processing_time_ms: number | null;
}

export interface BarcodeDiagnostics {
  attempted: boolean;
  status: BarcodeDiagnosticsStatus;
  decoded: boolean;
  barcode_type: string | null;
  decoded_value: string | null;
  failure_reason: string | null;
  used_as_prn: boolean;
  processing_time_ms: number | null;
}

export interface OcrCandidateDiagnostics {
  source: string;
  region_index: number | null;
  value: string | null;
  confidence: number | null;
  digit_score: number | null;
  pattern_score: number | null;
  near_label: boolean | null;
  chosen: boolean;
}

export interface OcrDiagnostics {
  engine: string | null;
  roi_detected: boolean;
  roi_count: number;
  candidates: OcrCandidateDiagnostics[];
  chosen_candidate: OcrCandidateDiagnostics | null;
  final_prn: string | null;
  processing_time_ms: number | null;
}

export interface FinalResultDiagnostics {
  verified_name: string | null;
  verified_prn: string | null;
  prn_source: PrnSource;
  registration_completed: boolean;
  warnings: string[];
}

export type StageImageKey = "original" | "preprocessed" | "barcode_region" | "prn_region" | "enhanced_prn" | "final_ocr_input";

export interface StageImageInfo {
  stage: StageImageKey;
  label: string;
  filename: string | null;
  available: boolean;
}

export interface RegistrationAttempt {
  id: string;
  attempt_number: number;
  created_at: string;
  quality: QualityDiagnostics;
  barcode: BarcodeDiagnostics;
  ocr: OcrDiagnostics;
  final: FinalResultDiagnostics;
  log: PipelineLogEntry[];
  stage_images: StageImageInfo[];
  id_detected: boolean;
}

export interface RegistrationAttemptSummary {
  id: string;
  attempt_number: number;
  created_at: string;
  student_name: string | null;
  prn: string | null;
  prn_source: PrnSource;
  barcode_success: boolean;
  quality_passed: boolean;
  registration_completed: boolean;
}

export interface DiagnosticsStatusResponse {
  enabled: boolean;
}

export interface DiagnosticsAttemptFilters {
  search?: string;
  barcode_success?: boolean;
  ocr_success?: boolean;
  manual_entry?: boolean;
  quality_failed?: boolean;
  glare?: boolean;
  blur?: boolean;
}
