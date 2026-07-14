import type { Metadata } from "next";

import { DiagnosticsHistory } from "@/components/diagnostics/diagnostics-history";

export const metadata: Metadata = {
  title: "Developer Diagnostics | SnapAttend AI",
};

export default function DiagnosticsPage() {
  return <DiagnosticsHistory />;
}
