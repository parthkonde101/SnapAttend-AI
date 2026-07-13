import type { Metadata } from "next";

import { AuthShell } from "@/components/auth/auth-shell";
import { StudentLoginForm } from "@/components/auth/student-login-form";

export const metadata: Metadata = {
  title: "Student Login | SnapAttend AI",
};

export default function StudentLoginPage() {
  return (
    <AuthShell title="Student Login" description="Sign in with your PRN to view your dashboard.">
      <StudentLoginForm />
    </AuthShell>
  );
}
