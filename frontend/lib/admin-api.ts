/**
 * Thin typed wrappers around the /api/v1/admin/* endpoints (Milestone 7A —
 * Administrator System; extended by "Extending the attendance system" —
 * Course/Panel Management, Student Import, Attendance Filtering). Parallel
 * to lib/attendance-diagnostics-api.ts: each function is a one-line call
 * through the shared `apiRequest` helper, kept in one file so every admin
 * screen imports from the same place instead of re-deriving fetch calls
 * inline.
 */
import { apiRequest } from "@/lib/api";
import type {
  AdminPasswordResetRequest,
  AdminSessionDeleteConfirmation,
  AdminSessionListItem,
  AttendanceReportFilters,
  AttendanceReportItem,
  AuthToken,
  CourseCreateRequest,
  CourseRead,
  CourseUpdateRequest,
  DashboardStats,
  ExcelImportSummary,
  PanelCreateRequest,
  PanelOverview,
  PanelRead,
  PanelUpdateRequest,
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

export async function assignCourseToTeacher(teacherId: number, courseId: number): Promise<SimpleSuccessResponse> {
  return apiRequest<SimpleSuccessResponse>(`/api/v1/admin/teachers/${teacherId}/courses`, {
    method: "POST",
    body: { course_id: courseId },
  });
}

export async function removeCourseFromTeacher(teacherId: number, courseId: number): Promise<SimpleSuccessResponse> {
  return apiRequest<SimpleSuccessResponse>(`/api/v1/admin/teachers/${teacherId}/courses/${courseId}`, {
    method: "DELETE",
  });
}

// --- Students ------------------------------------------------------------------

export async function searchStudents(query?: string, panelId?: number): Promise<StudentAdminRead[]> {
  const params = new URLSearchParams();
  if (query && query.trim()) params.set("query", query.trim());
  if (panelId != null) params.set("panel_id", String(panelId));
  const suffix = params.toString() ? `?${params.toString()}` : "";
  return apiRequest<StudentAdminRead[]>(`/api/v1/admin/students${suffix}`, { method: "GET" });
}

export async function getStudentProfile(studentId: number): Promise<StudentProfile> {
  return apiRequest<StudentProfile>(`/api/v1/admin/students/${studentId}`, { method: "GET" });
}

export async function updateStudent(studentId: number, payload: StudentUpdateRequest): Promise<StudentAdminRead> {
  return apiRequest<StudentAdminRead>(`/api/v1/admin/students/${studentId}`, { method: "PUT", body: payload });
}

/** Resets to the administrator-issued default password (`Test@123`) and
 * re-arms the mandatory change-password flow. There is deliberately no way
 * to pass an arbitrary password here — see backend
 * `AdminStudentService.reset_to_default_password`'s docstring. */
export async function resetStudentPassword(studentId: number): Promise<SimpleSuccessResponse> {
  return apiRequest<SimpleSuccessResponse>(`/api/v1/admin/students/${studentId}/reset-password`, {
    method: "POST",
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

// --- Courses (Course Normalization) -------------------------------------------

export async function listCourses(includeArchived = true): Promise<CourseRead[]> {
  return apiRequest<CourseRead[]>(`/api/v1/admin/courses?include_archived=${includeArchived}`, { method: "GET" });
}

export async function createCourse(payload: CourseCreateRequest): Promise<CourseRead> {
  return apiRequest<CourseRead>("/api/v1/admin/courses", { method: "POST", body: payload });
}

export async function updateCourse(courseId: number, payload: CourseUpdateRequest): Promise<CourseRead> {
  return apiRequest<CourseRead>(`/api/v1/admin/courses/${courseId}`, { method: "PUT", body: payload });
}

export async function deleteCourse(courseId: number): Promise<SimpleSuccessResponse> {
  return apiRequest<SimpleSuccessResponse>(`/api/v1/admin/courses/${courseId}`, { method: "DELETE" });
}

// --- Panels (Academic Panels + Panel Management) ------------------------------

export async function listAdminPanels(): Promise<PanelRead[]> {
  return apiRequest<PanelRead[]>("/api/v1/admin/panels", { method: "GET" });
}

export async function createPanel(payload: PanelCreateRequest): Promise<PanelRead> {
  return apiRequest<PanelRead>("/api/v1/admin/panels", { method: "POST", body: payload });
}

export async function getPanelOverview(panelId: number): Promise<PanelOverview> {
  return apiRequest<PanelOverview>(`/api/v1/admin/panels/${panelId}`, { method: "GET" });
}

export async function updatePanel(panelId: number, payload: PanelUpdateRequest): Promise<PanelRead> {
  return apiRequest<PanelRead>(`/api/v1/admin/panels/${panelId}`, { method: "PUT", body: payload });
}

export async function deletePanel(panelId: number): Promise<SimpleSuccessResponse> {
  return apiRequest<SimpleSuccessResponse>(`/api/v1/admin/panels/${panelId}`, { method: "DELETE" });
}

export async function assignCourseToPanel(panelId: number, courseId: number): Promise<SimpleSuccessResponse> {
  return apiRequest<SimpleSuccessResponse>(`/api/v1/admin/panels/${panelId}/courses`, {
    method: "POST",
    body: { course_id: courseId },
  });
}

export async function removeCourseFromPanel(panelId: number, courseId: number): Promise<SimpleSuccessResponse> {
  return apiRequest<SimpleSuccessResponse>(`/api/v1/admin/panels/${panelId}/courses/${courseId}`, {
    method: "DELETE",
  });
}

export async function listPanelStudents(panelId: number): Promise<StudentAdminRead[]> {
  return apiRequest<StudentAdminRead[]>(`/api/v1/admin/panels/${panelId}/students`, { method: "GET" });
}

/** Uploads an .xlsx roster for one panel — multipart/form-data, so this
 * bypasses the JSON-only `apiRequest` helper the same way image uploads do. */
export async function importPanelStudents(panelId: number, file: File): Promise<ExcelImportSummary> {
  const { uploadFile } = await import("@/lib/api");
  return uploadFile<ExcelImportSummary>(`/api/v1/admin/panels/${panelId}/import`, file, file.name);
}

// --- Attendance Filtering -----------------------------------------------------

export async function getAttendanceReport(filters: AttendanceReportFilters): Promise<AttendanceReportItem[]> {
  const params = new URLSearchParams();
  if (filters.course_id != null) params.set("course_id", String(filters.course_id));
  if (filters.panel_id != null) params.set("panel_id", String(filters.panel_id));
  if (filters.teacher_id != null) params.set("teacher_id", String(filters.teacher_id));
  if (filters.student_id != null) params.set("student_id", String(filters.student_id));
  if (filters.date_from) params.set("date_from", filters.date_from);
  if (filters.date_to) params.set("date_to", filters.date_to);
  const suffix = params.toString() ? `?${params.toString()}` : "";
  return apiRequest<AttendanceReportItem[]>(`/api/v1/admin/attendance/report${suffix}`, { method: "GET" });
}
