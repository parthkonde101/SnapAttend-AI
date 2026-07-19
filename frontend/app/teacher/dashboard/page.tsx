"use client";

import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { ClipboardList, History, Loader2, PlayCircle, RefreshCw } from "lucide-react";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { DashboardShell } from "@/components/dashboard/dashboard-shell";
import { SessionHistoryTable } from "@/components/attendance/session-history-table";
import { useSessionHistory } from "@/hooks/use-attendance";
import { useCurrentUser } from "@/hooks/use-auth";
import { listMyCourses, listPanels } from "@/lib/course-panel-api";
import { ApiError } from "@/lib/api";
import { SESSION_DURATION_OPTIONS_SECONDS, type CourseRead, type PanelRead, type SessionDurationSeconds, type Teacher } from "@/lib/types";
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

  // --- Session Creation Workflow (Course -> Panel -> Session) ---------------
  // "Extending the attendance system" spec, Part 5: a teacher must select a
  // Course they're assigned to, then a Panel assigned to that course,
  // before a session can start. Both selects are re-derived server-side
  // too (AttendanceSessionService.start_session validates both), this is
  // just the guided picker.
  const [courses, setCourses] = useState<CourseRead[]>([]);
  const [panels, setPanels] = useState<PanelRead[]>([]);
  const [courseId, setCourseId] = useState<number | "">("");
  const [panelId, setPanelId] = useState<number | "">("");
  const [pickerError, setPickerError] = useState<string | null>(null);

  useEffect(() => {
    listMyCourses()
      .then(setCourses)
      .catch((err) => setPickerError(err instanceof ApiError ? err.message : "Unable to load your courses."));
  }, []);

  useEffect(() => {
    setPanelId("");
    setPanels([]);
    if (courseId === "") return;
    listPanels(courseId)
      .then(setPanels)
      .catch((err) => setPickerError(err instanceof ApiError ? err.message : "Unable to load panels."));
  }, [courseId]);

  function handleStartAttendance() {
    if (courseId === "" || panelId === "") return;
    router.push(`/teacher/session?duration=${selectedDuration}&course_id=${courseId}&panel_id=${panelId}`);
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
              <CardDescription>Select a course and panel, choose a duration, then open a new attendance session.</CardDescription>
            </CardHeader>
            <CardContent className="flex flex-col gap-4">
              {pickerError && (
                <Alert variant="destructive">
                  <AlertDescription>{pickerError}</AlertDescription>
                </Alert>
              )}

              <div className="space-y-1.5">
                <Label htmlFor="session-course">Course</Label>
                <select
                  id="session-course"
                  value={courseId}
                  onChange={(e) => setCourseId(e.target.value ? Number(e.target.value) : "")}
                  className="flex h-10 w-full rounded-md border border-input bg-transparent px-3 py-2 text-base shadow-sm sm:text-sm"
                >
                  <option value="">
                    {courses.length === 0 ? "No courses assigned to you yet" : "Select a course…"}
                  </option>
                  {courses.map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.course_name}
                    </option>
                  ))}
                </select>
              </div>

              <div className="space-y-1.5">
                <Label htmlFor="session-panel">Panel</Label>
                <select
                  id="session-panel"
                  value={panelId}
                  onChange={(e) => setPanelId(e.target.value ? Number(e.target.value) : "")}
                  disabled={courseId === ""}
                  className="flex h-10 w-full rounded-md border border-input bg-transparent px-3 py-2 text-base shadow-sm disabled:opacity-50 sm:text-sm"
                >
                  <option value="">
                    {courseId === ""
                      ? "Select a course first"
                      : panels.length === 0
                        ? "No panels assigned to this course"
                        : "Select a panel…"}
                  </option>
                  {panels.map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.name}
                    </option>
                  ))}
                </select>
              </div>

              <div className="grid grid-cols-4 gap-2" role="radiogroup" aria-label="Session duration">
                {SESSION_DURATION_OPTIONS_SECONDS.map((seconds) => (
                  <button
                    key={seconds}
                    type="button"
                    role="radio"
                    aria-checked={selectedDuration === seconds}
                    onClick={() => setSelectedDuration(seconds)}
                    className={cn(
                      "min-h-11 rounded-lg border px-2 py-2 text-sm font-medium transition-colors",
                      selectedDuration === seconds
                        ? "border-primary bg-primary text-primary-foreground"
                        : "border-border bg-transparent text-muted-foreground hover:bg-muted"
                    )}
                  >
                    {formatDurationLabel(seconds)}
                  </button>
                ))}
              </div>
              <Button size="lg" className="w-full" onClick={handleStartAttendance} disabled={courseId === "" || panelId === ""}>
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
