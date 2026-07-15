import Link from "next/link";
import { ClipboardList, Loader2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { cn, formatCountdown } from "@/lib/utils";
import type { SessionHistoryItem } from "@/lib/types";

interface SessionHistoryTableProps {
  sessions: SessionHistoryItem[];
  isLoading: boolean;
  error: string | null;
}

function formatDate(iso: string) {
  return new Date(iso).toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" });
}

function formatTime(iso: string) {
  return new Date(iso).toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" });
}

/** Read-only table of a teacher's past attendance sessions. */
export function SessionHistoryTable({ sessions, isLoading, error }: SessionHistoryTableProps) {
  if (isLoading) {
    return (
      <div className="flex justify-center py-10">
        <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (error) {
    return <p className="py-6 text-center text-sm text-destructive">{error}</p>;
  }

  if (sessions.length === 0) {
    return <p className="py-10 text-center text-sm text-muted-foreground">No attendance sessions yet.</p>;
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[560px] text-left text-sm">
        <thead>
          <tr className="border-b border-border text-xs uppercase tracking-wide text-muted-foreground">
            <th className="pb-3 pr-4 font-medium">Date</th>
            <th className="pb-3 pr-4 font-medium">Time</th>
            <th className="pb-3 pr-4 font-medium">Duration</th>
            <th className="pb-3 pr-4 font-medium">Status</th>
            <th className="pb-3 pr-4 font-medium">Present</th>
            <th className="pb-3 font-medium">Review</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-border">
          {sessions.map((item) => (
            <tr key={item.session_id}>
              <td className="py-3 pr-4">{formatDate(item.created_at)}</td>
              <td className="py-3 pr-4 text-muted-foreground">{formatTime(item.created_at)}</td>
              <td className="py-3 pr-4 font-mono tabular-nums text-muted-foreground">
                {formatCountdown(item.duration_seconds)}
              </td>
              <td className="py-3 pr-4">
                <span
                  className={cn(
                    "inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium",
                    item.status === "active"
                      ? "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400"
                      : "bg-muted text-muted-foreground"
                  )}
                >
                  <span
                    className={cn(
                      "h-1.5 w-1.5 rounded-full",
                      item.status === "active" ? "bg-emerald-500" : "bg-muted-foreground/50"
                    )}
                  />
                  {item.status === "active" ? "Active" : "Ended"}
                </span>
              </td>
              <td className="py-3 pr-4 font-medium">{item.present_count}</td>
              <td className="py-3">
                <Button variant="ghost" size="sm" className="gap-1.5" asChild>
                  <Link href={`/teacher/dashboard/sessions/${item.session_id}/review`}>
                    <ClipboardList className="h-3.5 w-3.5" />
                    Review
                  </Link>
                </Button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
