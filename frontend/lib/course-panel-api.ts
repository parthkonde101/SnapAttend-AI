/**
 * Thin typed wrappers around the non-admin Course/Panel endpoints
 * (Milestone 8A — Course Normalization + Panel System). Parallel to
 * lib/admin-api.ts, kept in its own file because these calls are used
 * outside the admin surface: the public panel list powers the teacher
 * "Start Attendance" panel picker (unauthenticated — see
 * `app/api/v1/endpoints/panels.py`), and a teacher's assigned-course list
 * powers the "Start Attendance" course picker.
 */
import { apiRequest } from "@/lib/api";
import type { CourseRead, PanelRead } from "@/lib/types";

/** Every panel, alphabetical by name — or, if `courseId` is given, only
 * the panels assigned that course (Milestone 8B, Part 9: "Only compatible
 * panels appear"). Unauthenticated — see backend's `GET /api/v1/panels`
 * docstring for why this is safe to expose publicly. */
export async function listPanels(courseId?: number): Promise<PanelRead[]> {
  const suffix = courseId != null ? `?course_id=${courseId}` : "";
  return apiRequest<PanelRead[]>(`/api/v1/panels${suffix}`, { method: "GET", authenticated: false });
}

/** The courses the currently authenticated teacher is assigned to, via
 * TeacherCourse (admin-managed). Powers the "Start Attendance" course
 * picker — a teacher may only start a session against one of these. */
export async function listMyCourses(): Promise<CourseRead[]> {
  return apiRequest<CourseRead[]>("/api/v1/teachers/me/courses", { method: "GET" });
}
