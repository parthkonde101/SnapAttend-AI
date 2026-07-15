export type UserRole = "student" | "teacher" | "admin";

export interface AuthToken {
  access_token: string;
  token_type: string;
}

// --- Forgot password (no email/OTP) -----------------------------------------

export interface PasswordResetVerifyResponse {
  reset_token: string;
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

// --- Administrator System (Milestone 7A) ------------------------------------
// Mirrors backend/app/schemas/admin.py. Entirely additive — nothing here is
// read by the student or teacher facing surfaces above.

export interface Admin {
  id: number;
  login_id: string;
  full_name: string;
  created_at: string;
}

export interface RecentActivityItem {
  student_name: string;
  student_prn: string;
  course: string | null;
  teacher_name: string;
  status: AttendanceStatus;
  marked_at: string;
}

export interface DashboardStats {
  total_students: number;
  total_teachers: number;
  total_sessions: number;
  active_session: ActiveSessionInfo | null;
  today_present_count: number;
  recent_activity: RecentActivityItem[];
}

export interface TeacherAdminRead {
  id: number;
  teacher_id: string;
  full_name: string;
  course: string | null;
  created_at: string;
  session_count: number;
}

export interface TeacherCreateRequest {
  full_name: string;
  teacher_id: string;
  course?: string | null;
  password: string;
}

export interface TeacherUpdateRequest {
  full_name?: string;
  teacher_id?: string;
  course?: string | null;
}

export interface AdminPasswordResetRequest {
  new_password: string;
}

export interface StudentAdminRead {
  id: number;
  prn: string;
  full_name: string;
  division: string | null;
  created_at: string;
  attendance_percentage: number;
}

export interface StudentUpdateRequest {
  full_name?: string;
  prn?: string;
  division?: string | null;
}

export interface StudentCourseAttendance {
  course: string;
  present_count: number;
  total_sessions: number;
  percentage: number;
}

export interface StudentAttendanceHistoryItem {
  session_id: number;
  course: string | null;
  teacher_name: string;
  date: string;
  status: AttendanceStatus;
  marked_at: string | null;
  verification_source: AttendanceVerificationSource;
}

export interface StudentProfile {
  student: StudentAdminRead;
  verified_prn: string | null;
  verified_name: string | null;
  verified_at: string | null;
  has_registration_photo: boolean;
  course_wise: StudentCourseAttendance[];
  history: StudentAttendanceHistoryItem[];
}

export interface AdminSessionListItem {
  session_id: number;
  course: string | null;
  teacher_id: number;
  teacher_name: string;
  date: string;
  duration_seconds: number;
  present_count: number;
  status: SessionStatus;
}

export interface AdminSessionDeleteConfirmation {
  session_id: number;
  course: string | null;
  teacher_name: string;
  date: string;
  present_count: number;
  photo_count: number;
  attendance_record_count: number;
}

export interface SimpleSuccessResponse {
  success: boolean;
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
  /** Teacher-only — never sent to students. See backend `ActiveSessionInfo`. */
  marker: string | null;
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
  marker: string;
  created_at: string;
  expires_at: string;
  duration_seconds: number;
  status: SessionStatus;
  present_count: number;
}

// --- Attendance Verification Engine (V1) --------------------------------------

/** Allowed session durations, in seconds — mirrors the backend's
 * AttendanceSessionService.ALLOWED_SESSION_DURATIONS_SECONDS. */
export const SESSION_DURATION_OPTIONS_SECONDS = [60, 120, 180, 300] as const;
export type SessionDurationSeconds = (typeof SESSION_DURATION_OPTIONS_SECONDS)[number];

export type AttendanceVerificationSource = "barcode" | "ocr" | "teacher_override" | "none";

export interface MarkAttendanceResponse {
  success: boolean;
  already_recorded: boolean;
  reason: string | null;
  verification_source: AttendanceVerificationSource;
  marker_detected: string | null;
  warnings: string[];
  diagnostics_attempt_id: string | null;
}

export interface AttendanceRecordDetail {
  student_id: number;
  prn: string;
  full_name: string;
  marked_at: string;
  verification_source: AttendanceVerificationSource;
}

export interface SessionRecordsResponse {
  session_id: number;
  marker: string;
  present_count: number;
  remaining_count: number;
  records: AttendanceRecordDetail[];
}

// --- Teacher review + verification-philosophy refinement --------------------
// Mirrors backend `app/schemas/attendance.py`'s StudentAttendanceReviewItem /
// SessionReviewResponse. Powers /teacher/sessions/[id]/review — every
// registered student, present or absent, with the evidence behind any
// present record and a Present/Absent override.

export type AttendanceStatus = "present" | "absent";
export type MarkerVerificationMode = "exact_match" | "display_evidence" | "teacher_override";

export interface StudentAttendanceReviewItem {
  student_id: number;
  prn: string;
  full_name: string;
  status: AttendanceStatus;
  verification_source: AttendanceVerificationSource;
  marked_at: string | null;
  marker_detected_character: string | null;
  marker_confidence: number | null;
  display_detected: boolean;
  display_confidence: number;
  marker_verification_mode: MarkerVerificationMode | null;
  is_teacher_override: boolean;
  overridden_at: string | null;
  has_photo: boolean;
}

export interface SessionReviewResponse {
  session_id: number;
  marker: string;
  /** Whether the session is still open — the Excel export is only available once this is false. */
  is_active: boolean;
  /** Live session countdown, in seconds. 0 once ended. */
  remaining_seconds: number;
  present_count: number;
  absent_count: number;
  students: StudentAttendanceReviewItem[];
}

export interface AttendanceOverrideRequest {
  student_id: number;
  status: AttendanceStatus;
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

// --- Developer Diagnostics — Attendance (development-only) -------------------
// Mirrors backend/app/diagnostics/attendance_schemas.py. Parallel to the
// Registration Diagnostics section above — separate types, separate
// endpoints, same visual/interaction patterns. Only ever renders when
// GET /attendance-diagnostics/status reports { enabled: true }.

export type Rect = [left: number, top: number, width: number, height: number];
export type FractionalBox = [left: number, top: number, right: number, bottom: number];

/** One dark connected-component candidate the detector considered as the
 * display panel — geometry only, evaluated before any OCR runs. */
export interface DisplayRegionCandidateDiagnostics {
  rect: Rect;
  area: number;
  fill_ratio: number;
  mean_brightness: number;
  accepted: boolean;
  rejection_reason: string | null;
}

/** One bright connected-component candidate the detector considered as the
 * marker glyph, inside an accepted display region — geometry only. A
 * rejected candidate here is exactly the "tiny digit" failure mode: too
 * small/wrong-shaped to physically be the marker, filtered out before OCR
 * ever saw it. */
export interface GlyphCandidateDiagnostics {
  rect: Rect;
  area: number;
  aspect_ratio: number;
  height_ratio: number;
  fill_ratio: number;
  edge_density: number;
  /** How many raw connected components were merged into this group — real
   * captures often split one character into several fragments via sensor
   * noise/JPEG compression; merging fixes selecting only a fragment. */
  member_count: number;
  accepted: boolean;
  rejection_reason: string | null;
  selected: boolean;
}

/** One full geometry-then-OCR pass over one search region (primary, then a
 * wider fallback if the primary search resolved to nothing). */
export interface MarkerScanAttemptDiagnostics {
  tier: string;
  fractional_box: FractionalBox;
  pixel_box: Rect;
  search_stage_image_key: string | null;
  display_regions: DisplayRegionCandidateDiagnostics[];
  display_stage_image_key: string | null;
  glyph_candidates: GlyphCandidateDiagnostics[];
  /** Tight, un-normalized crop of the merged glyph's union bounding box. */
  glyph_stage_image_key: string | null;
  /** The final normalized (canonical height + padded) image actually sent
   * to OCR — inspect this to see exactly what Tesseract saw. */
  glyph_normalized_stage_image_key: string | null;
  ocr_text: string | null;
  ocr_confidence: number | null;
  outcome: string;
}

export interface AttendanceIdentityDiagnostics {
  extracted_prn: string | null;
  source: string | null;
  matched_student_id: number | null;
  identity_verified: boolean;
  failure_reason: string | null;
  ocr_fallback_time_ms: number | null;
}

export interface AttendanceMarkerDiagnostics {
  expected_marker: string | null;
  detected_character: string | null;
  confidence: number | null;
  marker_verified: boolean;
  failure_reason: string | null;
  processing_time_ms: number | null;
  /** Plain-English explanation of exactly why the comparison passed/failed. */
  comparison_note: string | null;
  /** Every search region tried, with its full display-panel/glyph geometric
   * reasoning and the crop actually handed to OCR at the end. */
  scans: MarkerScanAttemptDiagnostics[];
}

export interface AttendanceFinalDiagnostics {
  verified: boolean;
  reason: string | null;
  verification_source: AttendanceVerificationSource;
  already_recorded: boolean;
  warnings: string[];
}

export interface AttendanceDiagnosticsStageImage {
  stage: string;
  label: string;
  filename: string | null;
  available: boolean;
}

export interface AttendanceAttempt {
  id: string;
  attempt_number: number;
  created_at: string;
  student_id: number | null;
  session_id: number | null;
  quality: QualityDiagnostics;
  barcode: BarcodeDiagnostics;
  identity: AttendanceIdentityDiagnostics;
  marker: AttendanceMarkerDiagnostics;
  final: AttendanceFinalDiagnostics;
  log: PipelineLogEntry[];
  stage_images: AttendanceDiagnosticsStageImage[];
  id_detected: boolean;
  processing_time_ms: number | null;
}

export interface AttendanceAttemptSummary {
  id: string;
  attempt_number: number;
  created_at: string;
  student_id: number | null;
  session_id: number | null;
  extracted_prn: string | null;
  detected_marker: string | null;
  verified: boolean;
  verification_source: AttendanceVerificationSource;
}

export interface AttendanceDiagnosticsAttemptFilters {
  session_id?: number;
  student_id?: number;
}
