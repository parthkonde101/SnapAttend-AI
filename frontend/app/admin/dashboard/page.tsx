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
import { formatCountdown } from "@/lib/utils";

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
}

function StatCard({ icon, label, value, hint }: StatCardProps) {
  return (
    <Card>
      <CardContent className="flex items-center gap-4 pt-6">
        <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-primary/10 text-primary">
          {icon}
        </span>
        <div className="flex flex-col">
          <span className="text-2xl font-bold leading-tight tabular-nums">{value}</span>
          <span className="text-sm text-muted-foreground">{label}</span>
          {hint && <span className="text-xs text-muted-foreground/70">{hint}</span>}
        </div>
      </CardContent>
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
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            <StatCard icon={<GraduationCap className="h-5 w-5" />} label="Total Students" value={stats.total_students} />
            <StatCard icon={<Users className="h-5 w-5" />} label="Total Teachers" value={stats.total_teachers} />
            <StatCard icon={<CalendarClock className="h-5 w-5" />} label="Total Attendance Sessions" value={stats.total_sessions} />
            <StatCard
              icon={<RadioTower className="h-5 w-5" />}
              label="Active Session"
              value={stats.active_session ? `${stats.active_session.present_count} present` : "None"}
              hint={stats.active_session ? `${formatCountdown(stats.active_session.remaining_seconds)} remaining` : "No session running right now"}
            />
            <StatCard icon={<ClipboardCheck className="h-5 w-5" />} label="Today's Attendance" value={stats.today_present_count} />
            <StatCard icon={<Activity className="h-5 w-5" />} label="Recent Activity" value={stats.recent_activity.length} hint="Latest check-ins below" />
          </div>

          <Card>
            <CardHeader>
              <CardTitle className="text-lg">Recent Activity</CardTitle>
            </CardHeader>
            <CardContent>
              {stats.recent_activity.length === 0 ? (
                <p className="py-6 text-center text-sm text-muted-foreground">No attendance activity yet.</p>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full min-w-[560px] text-left text-sm">
                    <thead>
                      <tr className="border-b border-border text-xs uppercase tracking-wide text-muted-foreground">
                        <th className="pb-3 pr-4 font-medium">Student</th>
                        <th className="pb-3 pr-4 font-medium">Course</th>
                        <th className="pb-3 pr-4 font-medium">Teacher</th>
                        <th className="pb-3 pr-4 font-medium">Status</th>
                        <th className="pb-3 font-medium">Time</th>
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
                              className={
                                item.status === "present"
                                  ? "text-emerald-600 dark:text-emerald-400"
                                  : "text-muted-foreground"
                              }
                            >
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
