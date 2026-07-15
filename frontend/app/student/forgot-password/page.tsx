import type { Metadata } from "next";

import { ForgotPasswordWizard } from "@/components/auth/forgot-password-wizard";

export const metadata: Metadata = {
  title: "Reset Password | SnapAttend",
};

export default function StudentForgotPasswordPage() {
  return <ForgotPasswordWizard />;
}
