import type { Metadata } from "next";

import { AuthShell } from "@/components/auth/auth-shell";
import { TeacherLoginForm } from "@/components/auth/teacher-login-form";

export const metadata: Metadata = {
  title: "Teacher Login | SnapAttend AI",
};

export default function TeacherLoginPage() {
  return (
    <AuthShell title="Teacher Login" description="Sign in with your teacher ID to manage attendance.">
      <TeacherLoginForm />
    </AuthShell>
  );
}
