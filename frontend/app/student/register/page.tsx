import type { Metadata } from "next";

import { RegistrationWizard } from "@/components/registration/registration-wizard";

export const metadata: Metadata = {
  title: "Student Registration | SnapAttend",
};

export default function StudentRegisterPage() {
  return <RegistrationWizard />;
}
