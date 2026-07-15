/**
 * Thin typed wrappers around the /api/v1/admin/* endpoints (Milestone 7A —
 * Administrator System). Parallel to lib/attendance-diagnostics-api.ts:
 * each function is a one-line call through the shared `apiRequest` helper,
 * kept in one file so every admin screen imports from the same place
 * instead of re-deriving fetch calls inline.
 */
import { apiRequest } from "@/lib/api";
import type {
  AdminPasswordResetRequest,
  AdminSessionDeleteConfirmation,
  AdminSessionListItem,
  AuthToken,
  DashboardStats,
  SimpleSuccessResponse,
  StudentAdminRead,
  StudentProfile,
  StudentUpdateRequest,
  TeacherAdminRead,
  TeacherCreateRequest,
  TeacherUpdateRequest,
} from "@/lib/types";

export async function adminLogin(loginId: string, password: string): Promise<AuthToken> {
  return apiRequest<AuthToken>("/api/v1/auth/admin/login", {
    method: "POST",
    body: { login_id: loginId, password },
    authenticated: false,
  });
}

export async function getDashboardStats(): Promise<DashboardStats> {
  return apiRequest<DashboardStats>("/api/v1/admin/dashboard/stats", { method: "GET" });
}

// --- Teachers ----------------------------------------------------------------

export async function listTeachers(): Promise<TeacherAdminRead[]> {
  return apiRequest<TeacherAdminRead[]>("/api/v1/admin/teachers", { method: "GET" });
}

export async function createTeacher(payload: TeacherCreateRequest): Promise<TeacherAdminRead> {
  return apiRequest<TeacherAdminRead>("/api/v1/admin/teachers", { method: "POST", body: payload });
}

export async function getTeacher(teacherId: number): Promise<TeacherAdminRead> {
  return apiRequest<TeacherAdminRead>(`/api/v1/admin/teachers/${teacherId}`, { method: "GET" });
}

export async function updateTeacher(teacherId: number, payload: TeacherUpdateRequest): Promise<TeacherAdminRead> {
  return apiRequest<TeacherAdminRead>(`/api/v1/admin/teachers/${teacherId}`, { method: "PUT", body: payload });
}

export async function resetTeacherPassword(teacherId: number, newPassword: string): Promise<SimpleSuccessResponse> {
  const payload: AdminPasswordResetRequest = { new_password: newPassword };
  return apiRequest<SimpleSuccessResponse>(`/api/v1/admin/teachers/${teacherId}/reset-password`, {
    method: "POST",
    body: payload,
  });
}

export async function deleteTeacher(teacherId: number): Promise<SimpleSuccessResponse> {
  return apiRequest<SimpleSuccessResponse>(`/api/v1/admin/teachers/${teacherId}`, { method: "DELETE" });
}

// --- Students ------------------------------------------------------------------

export async function searchStudents(query?: string): Promise<StudentAdminRead[]> {
  const suffix = query && query.trim() ? `?query=${encodeURIComponent(query.trim())}` : "";
  return apiRequest<StudentAdminRead[]>(`/api/v1/admin/students${suffix}`, { method: "GET" });
}

export async function getStudentProfile(studentId: number): Promise<StudentProfile> {
  return apiRequest<StudentProfile>(`/api/v1/admin/students/${studentId}`, { method: "GET" });
}

export async function updateStudent(studentId: number, payload: StudentUpdateRequest): Promise<StudentAdminRead> {
  return apiRequest<StudentAdminRead>(`/api/v1/admin/students/${studentId}`, { method: "PUT", body: payload });
}

export async function resetStudentPassword(studentId: number, newPassword: string): Promise<SimpleSuccessResponse> {
  const payload: AdminPasswordResetRequest = { new_password: newPassword };
  return apiRequest<SimpleSuccessResponse>(`/api/v1/admin/students/${studentId}/reset-password`, {
    method: "POST",
    body: payload,
  });
}

export async function deleteStudent(studentId: number): Promise<SimpleSuccessResponse> {
  return apiRequest<SimpleSuccessResponse>(`/api/v1/admin/students/${studentId}`, { method: "DELETE" });
}

// --- Attendance sessions ---------------------------------------------------------

export async function listAdminSessions(): Promise<AdminSessionListItem[]> {
  return apiRequest<AdminSessionListItem[]>("/api/v1/admin/sessions", { method: "GET" });
}

export async function getSessionDeleteConfirmation(sessionId: number): Promise<AdminSessionDeleteConfirmation> {
  return apiRequest<AdminSessionDeleteConfirmation>(`/api/v1/admin/sessions/${sessionId}/delete-confirmation`, {
    method: "GET",
  });
}

export async function deleteAdminSession(sessionId: number, confirmation: string): Promise<SimpleSuccessResponse> {
  return apiRequest<SimpleSuccessResponse>(`/api/v1/admin/sessions/${sessionId}`, {
    method: "DELETE",
    body: { confirmation },
  });
}
