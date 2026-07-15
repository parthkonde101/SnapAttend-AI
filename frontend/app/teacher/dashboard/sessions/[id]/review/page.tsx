"use client";

import { useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { ArrowLeft, Clock, Download, Loader2, RefreshCw, UserCheck, Users, UserX } from "lucide-react";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { DashboardShell } from "@/components/dashboard/dashboard-shell";
import { SessionReviewTable } from "@/components/attendance/session-review-table";
import { useSessionReview } from "@/hooks/use-attendance";
import { ApiError, downloadAuthenticatedFile } from "@/lib/api";
import { cn, formatCountdown } from "@/lib/utils";

interface StatProps {
  icon: React.ReactNode;
  label: string;
  value: React.ReactNode;
}

function Stat({ icon, label, value }: StatProps) {
  return (
    <div className="flex items-center gap-3 rounded-xl border border-border bg-card px-4 py-3">
      <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-muted text-muted-foreground">
        {icon}
      </span>
      <div className="flex flex-col">
        <span className="text-lg font-semibold leading-tight tabular-nums">{value}</span>
        <span className="text-xs text-muted-foreground">{label}</span>
      </div>
    </div>
  );
}

/**
 * Per-session teacher attendance page. Milestone 6B: this is deliberately
 * the *same* page whether the session is live or has ended — while
 * `data.is_active` is true, `useSessionReview` polls every 4s and this
 * renders as a live feed (rows append in arrival order as students check
 * in); the moment the session ends (from here or the presentation screen),
 * polling stops and the exact same page becomes the final review screen —
 * no navigation, just the countdown badge switching to "Ended" and the
 * Export button unlocking. The roster table shows every registered
 * student, present or absent, with the evidence behind any record and an
 * immediate Present/Absent override — see
 * `app/services/attendance_review_service.py` on the backend for the
 * non-destructive override semantics this page relies on.
 */
export default function SessionReviewPage() {
  const router = useRouter();
  const params = useParams<{ id: string }>();
  const sessionId = Number(params.id);
  const hasValidId = Number.isFinite(sessionId);

  const { data, isLoading, error, secondsLeft, refetch, setStatus } = useSessionReview(hasValidId ? sessionId : null);

  const [isExporting, setIsExporting] = useState(false);
  const [exportError, setExportError] = useState<string | null>(null);

  async function handleExport() {
    setIsExporting(true);
    setExportError(null);
    try {
      await downloadAuthenticatedFile(
        `/api/v1/attendance/session-review/${sessionId}/export`,
        `Attendance_Session${sessionId}.xlsx`
      );
    } catch (err) {
      setExportError(err instanceof ApiError ? err.message : "Unable to export attendance.");
    } finally {
      setIsExporting(false);
    }
  }

  if (!hasValidId) {
    return (
      <DashboardShell>
        <Alert variant="destructive">
          <AlertDescription>Invalid session id.</AlertDescription>
        </Alert>
      </DashboardShell>
    );
  }

  return (
    <DashboardShell>
      <div className="mx-auto flex max-w-5xl flex-col gap-6">
        <div className="flex items-center justify-between">
          <Button variant="ghost" size="sm" onClick={() => router.push("/teacher/dashboard")} className="gap-1.5">
            <ArrowLeft className="h-4 w-4" />
            Back to dashboard
          </Button>
        </div>

        <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
          <div className="space-y-1">
            <div className="flex items-center gap-2">
              <h1 className="text-2xl font-bold tracking-tight sm:text-3xl">Attendance Review</h1>
              {data && (
                <span
                  className={cn(
                    "inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-semibold",
                    data.is_active
                      ? "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400"
                      : "bg-muted text-muted-foreground"
                  )}
                >
                  <span
                    className={cn(
                      "h-1.5 w-1.5 rounded-full",
                      data.is_active ? "animate-pulse bg-emerald-500" : "bg-muted-foreground"
                    )}
                  />
                  {data.is_active ? "Live" : "Ended"}
                </span>
              )}
            </div>
            <p className="text-muted-foreground">
              {data ? (
                <>
                  Session marker <span className="font-mono font-semibold">{data.marker}</span>
                </>
              ) : (
                "Loading session…"
              )}
            </p>
          </div>

          {data && (
            <Button
              variant="outline"
              className="gap-2"
              disabled={data.is_active || isExporting}
              onClick={handleExport}
              title={data.is_active ? "End the session before exporting the final attendance list." : "Download the final attendance list as an Excel file."}
            >
              {isExporting ? <Loader2 className="h-4 w-4 animate-spin" /> : <Download className="h-4 w-4" />}
              Export Excel
            </Button>
          )}
        </div>

        {data && (
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            <Stat icon={<UserCheck className="h-4 w-4" />} label="Present" value={data.present_count} />
            <Stat icon={<UserX className="h-4 w-4" />} label="Remaining" value={data.absent_count} />
            <Stat
              icon={<Users className="h-4 w-4" />}
              label="Total registered"
              value={data.present_count + data.absent_count}
            />
            <Stat
              icon={<Clock className="h-4 w-4" />}
              label={data.is_active ? "Time remaining" : "Session status"}
              value={data.is_active ? formatCountdown(secondsLeft) : "Ended"}
            />
          </div>
        )}

        {data?.is_active && (
          <Alert>
            <AlertDescription>
              This session is live — attendance updates automatically as students check in. Excel export becomes
              available once it has ended.
            </AlertDescription>
          </Alert>
        )}

        {exportError && (
          <Alert variant="destructive">
            <AlertDescription>{exportError}</AlertDescription>
          </Alert>
        )}

        <Card>
          <CardHeader className="flex-row items-center justify-between space-y-0">
            <CardTitle className="flex items-center gap-2 text-lg">
              <Users className="h-5 w-5 text-muted-foreground" />
              Roster
            </CardTitle>
            <Button variant="ghost" size="icon" onClick={() => refetch()} aria-label="Refresh" title="Refresh">
              <RefreshCw className="h-4 w-4" />
            </Button>
          </CardHeader>
          <CardContent>
            <SessionReviewTable
              sessionId={sessionId}
              students={data?.students ?? []}
              isLoading={isLoading}
              error={error}
              onSetStatus={setStatus}
            />
          </CardContent>
        </Card>
      </div>
    </DashboardShell>
  );
}
