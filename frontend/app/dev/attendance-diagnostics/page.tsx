import type { Metadata } from "next";

import { AttendanceDiagnosticsHistory } from "@/components/diagnostics/attendance-diagnostics-history";

export const metadata: Metadata = {
  title: "Attendance Diagnostics | SnapAttend AI",
};

export default function AttendanceDiagnosticsPage() {
  return <AttendanceDiagnosticsHistory />;
}
