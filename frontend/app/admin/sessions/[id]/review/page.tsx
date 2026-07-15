"use client";

import { useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { ArrowLeft, Download, Loader2, RefreshCw, Users } from "lucide-react";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { AdminDashboardShell } from "@/components/admin/admin-dashboard-shell";
import { SessionReviewTable } from "@/components/attendance/session-review-table";
import { useAdminSessionReview } from "@/hooks/use-admin";
import { ApiError, downloadAuthenticatedFile } from "@/lib/api";

/**
 * Milestone 7A: "Reuse the existing Teacher Review page. Administrator
 * should see exactly the same page." — this renders the identical
 * `SessionReviewTable` component the teacher review page uses (same
 * thumbnails, same confidence/mode display, same override controls),
 * wired to the admin-scoped review/override/photo endpoints via
 * `useAdminSessionReview` instead of the teacher-scoped ones. See that
 * component's new `photoBasePath` prop and `AttendanceReviewService`'s
 * `get_session_for_admin`/`set_status_as_admin` on the backend for how
 * this stays additive rather than a fork of the teacher page's logic.
 */
export default function AdminSessionReviewPage() {
  const router = useRouter();
  const params = useParams<{ id: string }>();
  const sessionId = Number(params.id);
  const hasValidId = Number.isFinite(sessionId);

  const { data, isLoading, error, refetch, setStatus } = useAdminSessionReview(hasValidId ? sessionId : null);

  const [isExporting, setIsExporting] = useState(false);
  const [exportError, setExportError] = useState<string | null>(null);

  async function handleExport() {
    setIsExporting(true);
    setExportError(null);
    try {
      await downloadAuthenticatedFile(
        `/api/v1/admin/sessions/${sessionId}/export`,
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
      <AdminDashboardShell>
        <Alert variant="destructive">
          <AlertDescription>Invalid session id.</AlertDescription>
        </Alert>
      </AdminDashboardShell>
    );
  }

  return (
    <AdminDashboardShell>
      <Button variant="ghost" size="sm" className="w-fit gap-1.5" onClick={() => router.push("/admin/sessions")}>
        <ArrowLeft className="h-4 w-4" />
        Back to sessions
      </Button>

      <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div className="space-y-1">
          <h1 className="text-2xl font-bold tracking-tight sm:text-3xl">Attendance Review</h1>
          <p className="text-muted-foreground">
            {data ? (
              <>
                Session marker <span className="font-mono font-semibold">{data.marker}</span> ·{" "}
                <span className="font-medium text-foreground">{data.present_count}</span> present ·{" "}
                <span className="font-medium text-foreground">{data.absent_count}</span> absent
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

      {data?.is_active && (
        <Alert>
          <AlertDescription>This session is still active. Excel export becomes available once it has ended.</AlertDescription>
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
            photoBasePath="/api/v1/admin/sessions"
          />
        </CardContent>
      </Card>
    </AdminDashboardShell>
  );
}
