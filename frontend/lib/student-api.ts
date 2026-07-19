/**
 * Thin typed wrapper around the authenticated student self-service
 * endpoints (Milestone: Unified Student Roster). There is no more
 * self-registration — the only thing a student can do to their own
 * account is change their own password, via the mandatory Change
 * Password screen (`app/student/change-password/page.tsx`).
 */
import { apiRequest } from "@/lib/api";
import type { Student, StudentChangePasswordRequest } from "@/lib/types";

export async function changeOwnPassword(payload: StudentChangePasswordRequest): Promise<Student> {
  return apiRequest<Student>("/api/v1/students/me/change-password", { method: "POST", body: payload });
}
