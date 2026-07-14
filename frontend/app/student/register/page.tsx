import type { Metadata } from "next";

import { RegistrationWizard } from "@/components/registration/registration-wizard";

export const metadata: Metadata = {
  title: "Student Registration | SnapAttend AI",
};

export default function StudentRegisterPage() {
  return <RegistrationWizard />;
}
