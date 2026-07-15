"use client";

import { useRouter } from "next/navigation";
import { useRef, useState } from "react";
import { ClipboardList, History, Loader2, PlayCircle, RefreshCw } from "lucide-react";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { DashboardShell } from "@/components/dashboard/dashboard-shell";
import { SessionHistoryTable } from "@/components/attendance/session-history-table";
import { useSessionHistory } from "@/hooks/use-attendance";
import { useCurrentUser } from "@/hooks/use-auth";
import { SESSION_DURATION_OPTIONS_SECONDS, type SessionDurationSeconds, type Teacher } from "@/lib/types";
import { cn } from "@/lib/utils";

const DEFAULT_DURATION_SECONDS: SessionDurationSeconds = 120;

function formatDurationLabel(seconds: number) {
  const minutes = Math.round(seconds / 60);
  return `${minutes} min`;
}

export default function TeacherDashboardPage() {
  const router = useRouter();
  const { user, isLoading, error } = useCurrentUser<Teacher>("teacher", "/api/v1/teachers/me");
  const { sessions, isLoading: isHistoryLoading, error: historyError, refetch: refetchHistory } =
    useSessionHistory();
  const historyRef = useRef<HTMLDivElement>(null);
  const [selectedDuration, setSelectedDuration] = useState<SessionDurationSeconds>(DEFAULT_DURATION_SECONDS);

  function handleStartAttendance() {
    router.push(`/teacher/session?duration=${selectedDuration}`);
  }

  function handleViewAttendance() {
    historyRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  if (isLoading) {
    return (
      <DashboardShell>
        <div className="flex justify-center py-24">
          <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
        </div>
      </DashboardShell>
    );
  }

  if (error || !user) {
    return (
      <DashboardShell>
        <Alert variant="destructive">
          <AlertDescription>{error ?? "Unable to load your profile."}</AlertDescription>
        </Alert>
      </DashboardShell>
    );
  }

  return (
    <DashboardShell>
      <div className="mx-auto flex max-w-3xl flex-col gap-8">
        <div className="space-y-2 text-center sm:text-left">
          <p className="text-sm font-medium text-muted-foreground">Welcome back</p>
          <h1 className="text-3xl font-bold tracking-tight sm:text-4xl">{user.full_name}</h1>
          <p className="text-muted-foreground">Teacher ID: {user.teacher_id}</p>
        </div>

        <div className="grid gap-6 sm:grid-cols-2">
          <Card>
            <CardHeader>
              <CardTitle className="text-lg">Start Attendance</CardTitle>
              <CardDescription>Choose a duration, then open a new attendance session for your class.</CardDescription>
            </CardHeader>
            <CardContent className="flex flex-col gap-4">
              <div className="grid grid-cols-4 gap-2" role="radiogroup" aria-label="Session duration">
                {SESSION_DURATION_OPTIONS_SECONDS.map((seconds) => (
                  <button
                    key={seconds}
                    type="button"
                    role="radio"
                    aria-checked={selectedDuration === seconds}
                    onClick={() => setSelectedDuration(seconds)}
                    className={cn(
                      "rounded-lg border px-2 py-2 text-sm font-medium transition-colors",
                      selectedDuration === seconds
                        ? "border-primary bg-primary text-primary-foreground"
                        : "border-border bg-transparent text-muted-foreground hover:bg-muted"
                    )}
                  >
                    {formatDurationLabel(seconds)}
                  </button>
                ))}
              </div>
              <Button size="lg" className="w-full" onClick={handleStartAttendance}>
                <PlayCircle />
                Start Attendance
              </Button>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="text-lg">View Attendance</CardTitle>
              <CardDescription>Review past sessions and attendance records.</CardDescription>
            </CardHeader>
            <CardContent>
              <Button size="lg" variant="outline" className="w-full" onClick={handleViewAttendance}>
                <ClipboardList />
                View Attendance
              </Button>
            </CardContent>
          </Card>
        </div>

        <Card ref={historyRef}>
          <CardHeader className="flex-row items-center justify-between space-y-0">
            <div>
              <CardTitle className="flex items-center gap-2 text-lg">
                <History className="h-5 w-5 text-muted-foreground" />
                Session History
              </CardTitle>
              <CardDescription>Every attendance session you&apos;ve started.</CardDescription>
            </div>
            <Button
              variant="ghost"
              size="icon"
              onClick={() => refetchHistory()}
              aria-label="Refresh session history"
              title="Refresh"
            >
              <RefreshCw className="h-4 w-4" />
            </Button>
          </CardHeader>
          <CardContent>
            <SessionHistoryTable sessions={sessions} isLoading={isHistoryLoading} error={historyError} />
          </CardContent>
        </Card>
      </div>
    </DashboardShell>
  );
}
