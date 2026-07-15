import type { Metadata } from "next";
import { notFound } from "next/navigation";

import { DiagnosticsHistory } from "@/components/diagnostics/diagnostics-history";

export const metadata: Metadata = {
  title: "Developer Diagnostics | SnapAttend AI",
};

/**
 * Milestone 6C, Part 2/3 — Production Lockdown. This route (and
 * `/dev/attendance-diagnostics`) must be genuinely unreachable outside
 * development, not merely have its contents hidden — a curious or
 * malicious student typing the URL directly in a production build must
 * get the same 404 as any nonexistent page. `notFound()` in a Server
 * Component does exactly that: Next.js renders the real not-found page
 * and responds with an actual 404 status, before any client JS (and
 * before `DiagnosticsHistory`'s own `/status`-backed check, which is a UX
 * nicety, not this route's security boundary) ever runs. Every individual
 * diagnostics API route independently 404s when disabled too (see
 * `app.diagnostics.gating.is_diagnostics_enabled`) — this is a second,
 * independent layer at the route level, not a replacement for that one.
 */
export default function DiagnosticsPage() {
  if (process.env.NODE_ENV !== "development") {
    notFound();
  }

  return <DiagnosticsHistory />;
}
