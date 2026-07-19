"use client";

import { useEffect, useState } from "react";
import {
  Activity,
  CalendarClock,
  ClipboardCheck,
  GraduationCap,
  Loader2,
  RadioTower,
  Users,
} from "lucide-react";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { AdminDashboardShell } from "@/components/admin/admin-dashboard-shell";
import { useCurrentUser } from "@/hooks/use-auth";
import { getDashboardStats } from "@/lib/admin-api";
import { ApiError } from "@/lib/api";
import type { Admin, DashboardStats } from "@/lib/types";
import { cn, formatCountdown } from "@/lib/utils";

function formatDateTime(iso: string) {
  return new Date(iso).toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

interface StatCardProps {
  icon: React.ReactNode;
  label: string;
  value: React.ReactNode;
  hint?: string;
  /** Small status dot next to the value — "live"/"idle"/none. Used only by
   * the Active Session card, but kept generic here so every card still
   * shares one component and one exact layout. */
  tone?: "live" | "idle";
}

/**
 * One KPI tile. Every card renders the exact same three-slot structure —
 * eyebrow label + icon badge on top, big value in the middle, hint (or a
 * reserved blank line if there isn't one) pinned to the bottom via
 * `mt-auto` — so six cards with wildly different content (a plain count vs.
 * "3 present" + a countdown hint) still come out pixel-identical in height,
 * with the value/hint baseline aligning across every card in a row without
 * depending on flexbox stretch tricks or lucky content lengths.
 */
function StatCard({ icon, label, value, hint, tone }: StatCardProps) {
  return (
    <Card className="h-full">
      <div className="flex h-full flex-col gap-4 p-4 sm:p-6">
        <div className="flex items-center justify-between gap-3">
          <span className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">{label}</span>
          <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary">
            {icon}
          </span>
        </div>
        <div className="mt-auto flex flex-col gap-1">
          <span className="flex items-center gap-2 text-3xl font-bold leading-none tracking-tight tabular-nums">
            {tone && (
              <span
                className={cn(
                  "h-2 w-2 shrink-0 rounded-full",
                  tone === "live" ? "animate-pulse bg-emerald-500" : "bg-muted-foreground/40"
                )}
              />
            )}
            {value}
          </span>
          <span className="min-h-[1rem] text-xs text-muted-foreground">{hint ?? " "}</span>
        </div>
      </div>
    </Card>
  );
}

/** Milestone 7A — the administrator control center's landing page: six
 * summary cards plus a recent activity feed. Read-only overview; every
 * management action lives on its own page (Students/Teachers/Sessions). */
export default function AdminDashboardPage() {
  const { user, isLoading: isUserLoading, error: userError } = useCurrentUser<Admin>("admin", "/api/v1/admin/me");
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [statsError, setStatsError] = useState<string | null>(null);
  const [isStatsLoading, setIsStatsLoading] = useState(true);

  useEffect(() => {
    if (!user) return;
    let cancelled = false;

    getDashboardStats()
      .then((data) => {
        if (!cancelled) setStats(data);
      })
      .catch((err) => {
        if (!cancelled) setStatsError(err instanceof ApiError ? err.message : "Unable to load dashboard stats.");
      })
      .finally(() => {
        if (!cancelled) setIsStatsLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [user]);

  if (isUserLoading) {
    return (
      <AdminDashboardShell>
        <div className="flex justify-center py-24">
          <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
        </div>
      </AdminDashboardShell>
    );
  }

  if (userError || !user) {
    return (
      <AdminDashboardShell>
        <Alert variant="destructive">
          <AlertDescription>{userError ?? "Unable to load your profile."}</AlertDescription>
        </Alert>
      </AdminDashboardShell>
    );
  }

  return (
    <AdminDashboardShell>
      <div className="space-y-1">
        <p className="text-sm font-medium text-muted-foreground">Welcome back</p>
        <h1 className="text-3xl font-bold tracking-tight sm:text-4xl">{user.full_name}</h1>
      </div>

      {statsError && (
        <Alert variant="destructive">
          <AlertDescription>{statsError}</AlertDescription>
        </Alert>
      )}

      {isStatsLoading ? (
        <div className="flex justify-center py-16">
          <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
        </div>
      ) : stats ? (
        <>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6">
            <StatCard icon={<GraduationCap className="h-5 w-5" />} label="Total Students" value={stats.total_students} />
            <StatCard icon={<Users className="h-5 w-5" />} label="Total Teachers" value={stats.total_teachers} />
            <StatCard icon={<CalendarClock className="h-5 w-5" />} label="Total Attendance Sessions" value={stats.total_sessions} />
            <StatCard
              icon={<RadioTower className="h-5 w-5" />}
              label="Active Session"
              value={stats.active_session ? `${stats.active_session.present_count} present` : "None"}
              hint={stats.active_session ? `${formatCountdown(stats.active_session.remaining_seconds)} remaining` : "No session running right now"}
              tone={stats.active_session ? "live" : "idle"}
            />
            <StatCard icon={<ClipboardCheck className="h-5 w-5" />} label="Today's Attendance" value={stats.today_present_count} />
            <StatCard icon={<Activity className="h-5 w-5" />} label="Recent Activity" value={stats.recent_activity.length} hint="Latest check-ins below" />
          </div>

          <Card>
            <CardHeader className="flex flex-row items-center justify-between gap-3 space-y-0">
              <div className="flex items-center gap-2">
                <Activity className="h-5 w-5 text-muted-foreground" />
                <CardTitle className="text-lg">Recent Activity</CardTitle>
              </div>
              {stats.recent_activity.length > 0 && (
                <span className="text-xs font-medium text-muted-foreground">
                  {stats.recent_activity.length} {stats.recent_activity.length === 1 ? "entry" : "entries"}
                </span>
              )}
            </CardHeader>
            <CardContent>
              {stats.recent_activity.length === 0 ? (
                <p className="py-6 text-center text-sm text-muted-foreground">No attendance activity yet.</p>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full min-w-[560px] text-left text-sm">
                    <thead>
                      <tr className="border-b border-border text-xs font-medium uppercase tracking-wide text-muted-foreground">
                        <th className="pb-3 pr-4">Student</th>
                        <th className="pb-3 pr-4">Course</th>
                        <th className="pb-3 pr-4">Teacher</th>
                        <th className="pb-3 pr-4">Status</th>
                        <th className="pb-3">Time</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-border">
                      {stats.recent_activity.map((item, index) => (
                        <tr key={`${item.student_prn}-${item.marked_at}-${index}`}>
                          <td className="py-3 pr-4">
                            <div className="font-medium">{item.student_name}</div>
                            <div className="text-xs text-muted-foreground">{item.student_prn}</div>
                          </td>
                          <td className="py-3 pr-4 text-muted-foreground">{item.course ?? "—"}</td>
                          <td className="py-3 pr-4 text-muted-foreground">{item.teacher_name}</td>
                          <td className="py-3 pr-4">
                            <span
                              className={cn(
                                "inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium",
                                item.status === "present"
                                  ? "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400"
                                  : "bg-muted text-muted-foreground"
                              )}
                            >
                              <span
                                className={cn(
                                  "h-1.5 w-1.5 rounded-full",
                                  item.status === "present" ? "bg-emerald-500" : "bg-muted-foreground/50"
                                )}
                              />
                              {item.status === "present" ? "Present" : "Absent"}
                            </span>
                          </td>
                          <td className="py-3 text-muted-foreground">{formatDateTime(item.marked_at)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </CardContent>
          </Card>
        </>
      ) : null}
    </AdminDashboardShell>
  );
}
