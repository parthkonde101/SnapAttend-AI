import type { Metadata } from "next";
import { notFound } from "next/navigation";

import { AttendanceDiagnosticsHistory } from "@/components/diagnostics/attendance-diagnostics-history";

export const metadata: Metadata = {
  title: "Attendance Diagnostics | SnapAttend",
};

/** See the parallel gating + rationale comment in `app/dev/diagnostics/page.tsx`. */
export default function AttendanceDiagnosticsPage() {
  if (process.env.NODE_ENV !== "development") {
    notFound();
  }

  return <AttendanceDiagnosticsHistory />;
}
