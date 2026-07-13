import type { Metadata } from "next";

import { AuthShell } from "@/components/auth/auth-shell";
import { StudentRegisterForm } from "@/components/auth/student-register-form";

export const metadata: Metadata = {
  title: "Student Registration | SnapAttend AI",
};

export default function StudentRegisterPage() {
  return (
    <AuthShell title="Create your account" description="Register with your PRN to get started.">
      <StudentRegisterForm />
    </AuthShell>
  );
}
