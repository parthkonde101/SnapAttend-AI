import type { Metadata } from "next";

import { AuthShell } from "@/components/auth/auth-shell";
import { AdminLoginForm } from "@/components/auth/admin-login-form";

export const metadata: Metadata = {
  title: "Admin Login | SnapAttend",
};

export default function AdminLoginPage() {
  return (
    <AuthShell title="Administrator Login" description="Sign in to manage SnapAttend.">
      <AdminLoginForm />
    </AuthShell>
  );
}
