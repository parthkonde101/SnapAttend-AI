"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { AlertCircle, ClipboardList, Loader2, RefreshCw, Search } from "lucide-react";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { AdminDashboardShell } from "@/components/admin/admin-dashboard-shell";
import { getAttendanceReport, listAdminPanels, listCourses, listTeachers } from "@/lib/admin-api";
import { ApiError } from "@/lib/api";
import { cn } from "@/lib/utils";
import type { AttendanceReportItem, CourseRead, PanelRead, TeacherAdminRead } from "@/lib/types";

function formatDate(iso: string) {
  return new Date(iso).toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" });
}

function formatTime(iso: string) {
  return new Date(iso).toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" });
}

/** "Extending the attendance system" spec, Part 6 — Attendance Filtering:
 * every attendance record system-wide, filterable by Course, Panel,
 * Teacher, Date, and Student. Course/Panel/Teacher/Date filter server-side
 * (GET /admin/attendance/report); the Student box filters the already-
 * fetched rows client-side by PRN or name, since the backend filter takes
 * a numeric student_id rather than a name/PRN lookup. */
export default function AdminReportsPage() {
  const [courses, setCourses] = useState<CourseRead[]>([]);
  const [panels, setPanels] = useState<PanelRead[]>([]);
  const [teachers, setTeachers] = useState<TeacherAdminRead[]>([]);

  const [courseId, setCourseId] = useState<string>("");
  const [panelId, setPanelId] = useState<string>("");
  const [teacherId, setTeacherId] = useState<string>("");
  const [dateFrom, setDateFrom] = useState<string>("");
  const [dateTo, setDateTo] = useState<string>("");
  const [studentQuery, setStudentQuery] = useState("");

  const [rows, setRows] = useState<AttendanceReportItem[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([listCourses(false), listAdminPanels(), listTeachers()])
      .then(([c, p, t]) => {
        setCourses(c);
        setPanels(p);
        setTeachers(t);
      })
      .catch(() => {
        // Filter dropdowns are a convenience — a failure here shouldn't block the report itself.
      });
  }, []);

  const refetch = useCallback(async () => {
    setIsLoading(true);
    try {
      const data = await getAttendanceReport({
        course_id: courseId ? Number(courseId) : undefined,
        panel_id: panelId ? Number(panelId) : undefined,
        teacher_id: teacherId ? Number(teacherId) : undefined,
        date_from: dateFrom ? new Date(dateFrom).toISOString() : undefined,
        date_to: dateTo ? new Date(`${dateTo}T23:59:59`).toISOString() : undefined,
      });
      setRows(data);
      setError(null);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Unable to load the attendance report.");
    } finally {
      setIsLoading(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [courseId, panelId, teacherId, dateFrom, dateTo]);

  useEffect(() => {
    refetch();
  }, [refetch]);

  const filteredRows = useMemo(() => {
    const q = studentQuery.trim().toLowerCase();
    if (!q) return rows;
    return rows.filter(
      (row) => row.student_prn.toLowerCase().includes(q) || row.student_name.toLowerCase().includes(q)
    );
  }, [rows, studentQuery]);

  return (
    <AdminDashboardShell>
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight sm:text-3xl">Attendance Report</h1>
          <p className="text-muted-foreground">Every attendance record, filterable by course, panel, teacher, date, and student.</p>
        </div>
        <Button variant="ghost" size="icon" onClick={() => refetch()} aria-label="Refresh" title="Refresh">
          <RefreshCw className="h-4 w-4" />
        </Button>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-lg">Filters</CardTitle>
        </CardHeader>
        <CardContent className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
          <div className="space-y-1.5">
            <Label htmlFor="filter-course">Course</Label>
            <select
              id="filter-course"
              value={courseId}
              onChange={(e) => setCourseId(e.target.value)}
              className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-base shadow-sm sm:text-sm"
            >
              <option value="">All courses</option>
              {courses.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.course_name}
                </option>
              ))}
            </select>
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="filter-panel">Panel</Label>
            <select
              id="filter-panel"
              value={panelId}
              onChange={(e) => setPanelId(e.target.value)}
              className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-base shadow-sm sm:text-sm"
            >
              <option value="">All panels</option>
              {panels.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name}
                </option>
              ))}
            </select>
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="filter-teacher">Teacher</Label>
            <select
              id="filter-teacher"
              value={teacherId}
              onChange={(e) => setTeacherId(e.target.value)}
              className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-base shadow-sm sm:text-sm"
            >
              <option value="">All teachers</option>
              {teachers.map((t) => (
                <option key={t.id} value={t.id}>
                  {t.full_name}
                </option>
              ))}
            </select>
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="filter-from">From</Label>
            <Input id="filter-from" type="date" value={dateFrom} onChange={(e) => setDateFrom(e.target.value)} />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="filter-to">To</Label>
            <Input id="filter-to" type="date" value={dateTo} onChange={(e) => setDateTo(e.target.value)} />
          </div>
        </CardContent>
      </Card>

      <div className="relative max-w-sm">
        <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
        <Input
          value={studentQuery}
          onChange={(e) => setStudentQuery(e.target.value)}
          placeholder="Filter by student PRN or name…"
          className="pl-9"
        />
      </div>

      {error && (
        <Alert variant="destructive">
          <AlertCircle />
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      <Card>
        <CardHeader>
          <CardTitle className="text-lg">Records ({filteredRows.length})</CardTitle>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <div className="flex justify-center py-10">
              <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
            </div>
          ) : filteredRows.length === 0 ? (
            <div className="flex flex-col items-center gap-2 py-10 text-center text-muted-foreground">
              <ClipboardList className="h-6 w-6" />
              <p className="text-sm">No attendance records match these filters.</p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full min-w-[900px] text-left text-sm">
                <thead>
                  <tr className="border-b border-border text-xs uppercase tracking-wide text-muted-foreground">
                    <th className="pb-3 pr-4 font-medium">Date</th>
                    <th className="pb-3 pr-4 font-medium">Course</th>
                    <th className="pb-3 pr-4 font-medium">Panel</th>
                    <th className="pb-3 pr-4 font-medium">Teacher</th>
                    <th className="pb-3 pr-4 font-medium">Roll No.</th>
                    <th className="pb-3 pr-4 font-medium">Student</th>
                    <th className="pb-3 pr-4 font-medium">PRN</th>
                    <th className="pb-3 font-medium">Status</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {filteredRows.map((row, index) => (
                    <tr key={`${row.session_id}-${row.student_id}-${index}`}>
                      <td className="py-3 pr-4 text-muted-foreground">
                        {formatDate(row.date)} · {formatTime(row.date)}
                      </td>
                      <td className="py-3 pr-4">{row.course ?? "—"}</td>
                      <td className="py-3 pr-4">{row.panel ?? "—"}</td>
                      <td className="py-3 pr-4 text-muted-foreground">{row.teacher_name}</td>
                      <td className="py-3 pr-4 text-muted-foreground">{row.student_roll_number ?? "—"}</td>
                      <td className="py-3 pr-4 font-medium">{row.student_name}</td>
                      <td className="py-3 pr-4 font-mono">{row.student_prn}</td>
                      <td className="py-3">
                        <span
                          className={cn(
                            "inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium",
                            row.status === "present"
                              ? "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400"
                              : "bg-muted text-muted-foreground"
                          )}
                        >
                          <span className={cn("h-1.5 w-1.5 rounded-full", row.status === "present" ? "bg-emerald-500" : "bg-muted-foreground/50")} />
                          {row.status === "present" ? "Present" : "Absent"}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>
    </AdminDashboardShell>
  );
}
