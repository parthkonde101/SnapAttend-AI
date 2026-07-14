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
