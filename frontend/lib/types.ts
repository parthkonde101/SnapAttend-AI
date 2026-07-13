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
