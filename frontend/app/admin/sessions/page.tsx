"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { AlertCircle, ClipboardList, Download, Loader2, RefreshCw, Trash2 } from "lucide-react";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { AdminDashboardShell } from "@/components/admin/admin-dashboard-shell";
import { AdminModal } from "@/components/admin/admin-modal";
import { deleteAdminSession, getSessionDeleteConfirmation, listAdminSessions } from "@/lib/admin-api";
import { ApiError, downloadAuthenticatedFile } from "@/lib/api";
import type { AdminSessionDeleteConfirmation, AdminSessionListItem } from "@/lib/types";
import { cn, formatCountdown } from "@/lib/utils";

function formatDate(iso: string) {
  return new Date(iso).toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" });
}

function formatTime(iso: string) {
  return new Date(iso).toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" });
}

export default function AdminSessionsPage() {
  const [sessions, setSessions] = useState<AdminSessionListItem[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [exportingId, setExportingId] = useState<number | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<AdminSessionListItem | null>(null);

  const refetch = useCallback(async () => {
    setIsLoading(true);
    try {
      const data = await listAdminSessions();
      setSessions(data);
      setError(null);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Unable to load attendance sessions.");
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    refetch();
  }, [refetch]);

  async function handleExport(session: AdminSessionListItem) {
    setExportingId(session.session_id);
    try {
      await downloadAuthenticatedFile(
        `/api/v1/admin/sessions/${session.session_id}/export`,
        `Attendance_Session${session.session_id}.xlsx`
      );
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Unable to export attendance.");
    } finally {
      setExportingId(null);
    }
  }

  return (
    <AdminDashboardShell>
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight sm:text-3xl">Attendance Sessions</h1>
          <p className="text-muted-foreground">Every attendance session across every teacher.</p>
        </div>
        <Button variant="ghost" size="icon" onClick={() => refetch()} aria-label="Refresh" title="Refresh">
          <RefreshCw className="h-4 w-4" />
        </Button>
      </div>

      {error && (
        <Alert variant="destructive">
          <AlertCircle />
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      <Card>
        <CardHeader>
          <CardTitle className="text-lg">All Sessions</CardTitle>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <div className="flex justify-center py-10">
              <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
            </div>
          ) : sessions.length === 0 ? (
            <p className="py-10 text-center text-sm text-muted-foreground">No attendance sessions yet.</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full min-w-[900px] text-left text-sm">
                <thead>
                  <tr className="border-b border-border text-xs uppercase tracking-wide text-muted-foreground">
                    <th className="pb-3 pr-4 font-medium">Course</th>
                    <th className="pb-3 pr-4 font-medium">Teacher</th>
                    <th className="pb-3 pr-4 font-medium">Date</th>
                    <th className="pb-3 pr-4 font-medium">Duration</th>
                    <th className="pb-3 pr-4 font-medium">Present</th>
                    <th className="pb-3 pr-4 font-medium">Status</th>
                    <th className="pb-3 font-medium">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {sessions.map((session) => (
                    <tr key={session.session_id}>
                      <td className="py-3 pr-4">{session.course ?? "—"}</td>
                      <td className="py-3 pr-4 text-muted-foreground">{session.teacher_name}</td>
                      <td className="py-3 pr-4 text-muted-foreground">
                        {formatDate(session.date)} · {formatTime(session.date)}
                      </td>
                      <td className="py-3 pr-4 font-mono tabular-nums text-muted-foreground">
                        {formatCountdown(session.duration_seconds)}
                      </td>
                      <td className="py-3 pr-4 font-medium">{session.present_count}</td>
                      <td className="py-3 pr-4">
                        <span
                          className={cn(
                            "inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium",
                            session.status === "active"
                              ? "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400"
                              : "bg-muted text-muted-foreground"
                          )}
                        >
                          <span
                            className={cn(
                              "h-1.5 w-1.5 rounded-full",
                              session.status === "active" ? "bg-emerald-500" : "bg-muted-foreground/50"
                            )}
                          />
                          {session.status === "active" ? "Active" : "Ended"}
                        </span>
                      </td>
                      <td className="py-3">
                        <div className="flex flex-wrap gap-1">
                          <Button variant="ghost" size="sm" className="gap-1.5" asChild>
                            <Link href={`/admin/sessions/${session.session_id}/review`}>
                              <ClipboardList className="h-3.5 w-3.5" />
                              Review
                            </Link>
                          </Button>
                          <Button
                            variant="ghost"
                            size="icon"
                            title="Export Excel"
                            aria-label="Export Excel"
                            disabled={session.status === "active" || exportingId === session.session_id}
                            onClick={() => handleExport(session)}
                          >
                            {exportingId === session.session_id ? (
                              <Loader2 className="h-4 w-4 animate-spin" />
                            ) : (
                              <Download className="h-4 w-4" />
                            )}
                          </Button>
                          <Button
                            variant="ghost"
                            size="icon"
                            title="Delete Session"
                            aria-label="Delete Session"
                            onClick={() => setDeleteTarget(session)}
                          >
                            <Trash2 className="h-4 w-4 text-destructive" />
                          </Button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>

      {deleteTarget && (
        <DeleteSessionModal
          session={deleteTarget}
          onClose={() => setDeleteTarget(null)}
          onDeleted={() => {
            setDeleteTarget(null);
            refetch();
          }}
        />
      )}
    </AdminDashboardShell>
  );
}

function DeleteSessionModal({
  session,
  onClose,
  onDeleted,
}: {
  session: AdminSessionListItem;
  onClose: () => void;
  onDeleted: () => void;
}) {
  const [confirmation, setConfirmation] = useState<AdminSessionDeleteConfirmation | null>(null);
  const [isLoadingConfirmation, setIsLoadingConfirmation] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [confirmText, setConfirmText] = useState("");
  const [deleteError, setDeleteError] = useState<string | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);

  useEffect(() => {
    let cancelled = false;
    getSessionDeleteConfirmation(session.session_id)
      .then((data) => {
        if (!cancelled) setConfirmation(data);
      })
      .catch((err) => {
        if (!cancelled) setLoadError(err instanceof ApiError ? err.message : "Unable to load session details.");
      })
      .finally(() => {
        if (!cancelled) setIsLoadingConfirmation(false);
      });
    return () => {
      cancelled = true;
    };
  }, [session.session_id]);

  async function handleDelete() {
    setDeleteError(null);
    setIsDeleting(true);
    try {
      await deleteAdminSession(session.session_id, confirmText);
      onDeleted();
    } catch (err) {
      setDeleteError(err instanceof ApiError ? err.message : "Unable to delete session.");
    } finally {
      setIsDeleting(false);
    }
  }

  return (
    <AdminModal title="Delete Attendance Session?" onClose={onClose}>
      {isLoadingConfirmation ? (
        <div className="flex justify-center py-8">
          <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
        </div>
      ) : loadError || !confirmation ? (
        <Alert variant="destructive">
          <AlertDescription>{loadError ?? "Unable to load session details."}</AlertDescription>
        </Alert>
      ) : (
        <>
          <Alert variant="destructive">
            <AlertDescription>
              This permanently removes the session and everything belonging to it — attendance records, photos,
              diagnostics, device locks, and overrides. This cannot be undone.
            </AlertDescription>
          </Alert>
          <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-2 rounded-lg border border-border p-3 text-sm">
            <dt className="text-muted-foreground">Course</dt>
            <dd>{confirmation.course ?? "—"}</dd>
            <dt className="text-muted-foreground">Teacher</dt>
            <dd>{confirmation.teacher_name}</dd>
            <dt className="text-muted-foreground">Date</dt>
            <dd>{formatDate(confirmation.date)}</dd>
            <dt className="text-muted-foreground">Present Count</dt>
            <dd>{confirmation.present_count}</dd>
            <dt className="text-muted-foreground">Photos</dt>
            <dd>{confirmation.photo_count}</dd>
            <dt className="text-muted-foreground">Attendance Records</dt>
            <dd>{confirmation.attendance_record_count}</dd>
          </dl>

          {deleteError && (
            <Alert variant="destructive">
              <AlertDescription>{deleteError}</AlertDescription>
            </Alert>
          )}

          <div className="space-y-1.5">
            <Label htmlFor="delete-session-confirm">Type DELETE to confirm</Label>
            <Input id="delete-session-confirm" value={confirmText} onChange={(e) => setConfirmText(e.target.value)} disabled={isDeleting} />
          </div>

          <div className="flex justify-end gap-2 pt-1">
            <Button variant="outline" onClick={onClose} disabled={isDeleting}>
              Cancel
            </Button>
            <Button variant="destructive" onClick={handleDelete} disabled={isDeleting || confirmText !== "DELETE"}>
              {isDeleting && <Loader2 className="h-4 w-4 animate-spin" />}
              Delete Session
            </Button>
          </div>
        </>
      )}
    </AdminModal>
  );
}
