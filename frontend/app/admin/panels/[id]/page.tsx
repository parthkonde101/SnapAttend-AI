"use client";

import { useParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import {
  AlertCircle,
  ArrowLeft,
  BookOpen,
  CheckSquare,
  FileSpreadsheet,
  Loader2,
  LayoutGrid,
  Search,
  Square,
  Upload,
  Users,
  X,
} from "lucide-react";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { AdminDashboardShell } from "@/components/admin/admin-dashboard-shell";
import {
  assignCourseToPanel,
  getPanelOverview,
  importPanelStudents,
  listCourses,
  listPanelStudents,
  removeCourseFromPanel,
} from "@/lib/admin-api";
import { ApiError } from "@/lib/api";
import { cn } from "@/lib/utils";
import type { CourseRead, ExcelImportSummary, PanelOverview, StudentAdminRead } from "@/lib/types";

function formatDate(iso: string) {
  return new Date(iso).toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" });
}

type TabKey = "overview" | "courses" | "students" | "import";

const TABS: { key: TabKey; label: string; icon: typeof LayoutGrid }[] = [
  { key: "overview", label: "Overview", icon: LayoutGrid },
  { key: "courses", label: "Courses", icon: BookOpen },
  { key: "students", label: "Students", icon: Users },
  { key: "import", label: "Import Excel", icon: Upload },
];

/** Milestone 8B, Part 4 — Panel Management: a panel is now an academic
 * group with its own detail page (Overview/Courses/Students/Import Excel),
 * not just a name in a CRUD table. `getPanelOverview` backs the header and
 * Overview tab; Courses/Students/Import each load their own data lazily,
 * the first time their tab is opened, rather than all up front. */
export default function AdminPanelDetailPage() {
  const router = useRouter();
  const params = useParams<{ id: string }>();
  const panelId = Number(params.id);
  const hasValidId = Number.isFinite(panelId);

  const [overview, setOverview] = useState<PanelOverview | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<TabKey>("overview");

  const refetchOverview = useCallback(async () => {
    if (!hasValidId) return;
    try {
      const data = await getPanelOverview(panelId);
      setOverview(data);
      setError(null);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Unable to load panel.");
    } finally {
      setIsLoading(false);
    }
  }, [panelId, hasValidId]);

  useEffect(() => {
    refetchOverview();
  }, [refetchOverview]);

  if (!hasValidId) {
    return (
      <AdminDashboardShell>
        <Alert variant="destructive">
          <AlertDescription>Invalid panel id.</AlertDescription>
        </Alert>
      </AdminDashboardShell>
    );
  }

  return (
    <AdminDashboardShell>
      <Button variant="ghost" size="sm" className="w-fit gap-1.5" onClick={() => router.push("/admin/panels")}>
        <ArrowLeft className="h-4 w-4" />
        Back to panels
      </Button>

      {isLoading ? (
        <div className="flex justify-center py-24">
          <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
        </div>
      ) : error || !overview ? (
        <Alert variant="destructive">
          <AlertCircle />
          <AlertDescription>{error ?? "Unable to load panel."}</AlertDescription>
        </Alert>
      ) : (
        <>
          <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
            <div>
              <h1 className="text-2xl font-bold tracking-tight sm:text-3xl">{overview.panel.name}</h1>
              <p className="text-muted-foreground">Created {formatDate(overview.panel.created_at)}</p>
            </div>
            <div className="flex gap-4">
              <div className="flex flex-col items-end">
                <span className="text-2xl font-bold tabular-nums sm:text-3xl">{overview.courses.length}</span>
                <span className="text-sm text-muted-foreground">Courses</span>
              </div>
              <div className="flex flex-col items-end">
                <span className="text-2xl font-bold tabular-nums sm:text-3xl">{overview.student_count}</span>
                <span className="text-sm text-muted-foreground">Students</span>
              </div>
            </div>
          </div>

          {/* Milestone 8B, Part 4: "Each panel page should contain
              Overview / Courses / Students / Import Excel" — a plain
              button-group tab strip, matching this codebase's existing
              choice (see AdminModal) of not pulling in a new UI primitive
              (no shadcn Tabs component installed) when a few classes do
              the job. */}
          <div className="flex w-fit gap-1 rounded-lg border border-border bg-muted/30 p-1">
            {TABS.map((tab) => {
              const Icon = tab.icon;
              const isActive = activeTab === tab.key;
              return (
                <button
                  key={tab.key}
                  type="button"
                  onClick={() => setActiveTab(tab.key)}
                  className={cn(
                    "flex items-center gap-1.5 rounded-md px-3 py-1.5 text-sm font-medium transition-colors",
                    isActive ? "bg-background text-foreground shadow-sm" : "text-muted-foreground hover:text-foreground"
                  )}
                >
                  <Icon className="h-4 w-4" />
                  {tab.label}
                </button>
              );
            })}
          </div>

          {activeTab === "overview" && <OverviewTab overview={overview} />}
          {activeTab === "courses" && <CoursesTab panelId={panelId} overview={overview} onChanged={refetchOverview} />}
          {activeTab === "students" && <StudentsTab panelId={panelId} />}
          {activeTab === "import" && <ImportExcelTab panelId={panelId} onImported={refetchOverview} />}
        </>
      )}
    </AdminDashboardShell>
  );
}

function OverviewTab({ overview }: { overview: PanelOverview }) {
  return (
    <div className="grid gap-6 lg:grid-cols-2">
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">Assigned Courses</CardTitle>
        </CardHeader>
        <CardContent>
          {overview.courses.length === 0 ? (
            <p className="py-6 text-center text-sm text-muted-foreground">
              No courses assigned yet — add some in the Courses tab.
            </p>
          ) : (
            <div className="flex flex-wrap gap-1.5">
              {overview.courses.map((course) => (
                <span key={course.id} className="rounded-full bg-muted px-2.5 py-1 text-xs font-medium text-muted-foreground">
                  {course.course_name}
                  {course.course_code && <span className="ml-1 font-mono text-muted-foreground/70">{course.course_code}</span>}
                </span>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-lg">Student Roster</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-col items-center justify-center gap-1.5 py-6 text-center">
          <span className="text-3xl font-bold tabular-nums">{overview.student_count}</span>
          <span className="text-sm text-muted-foreground">
            student{overview.student_count === 1 ? "" : "s"} on the official roster for this panel
          </span>
        </CardContent>
      </Card>
    </div>
  );
}

/** Milestone 8B, Part 4 (Courses Tab): "Admin assigns multiple courses...
 * Only these courses become available for attendance within this panel."
 * — same searchable-checklist pattern as the Teachers page's Assigned
 * Courses picker, reimplemented here (not imported) since these are two
 * separate pages and the codebase's existing convention is page-local
 * components rather than a shared cross-page UI module for this kind of
 * one-off checklist. */
function CoursesTab({
  panelId,
  overview,
  onChanged,
}: {
  panelId: number;
  overview: PanelOverview;
  onChanged: () => void;
}) {
  const [allCourses, setAllCourses] = useState<CourseRead[]>([]);
  const [assignedIds, setAssignedIds] = useState<Set<number>>(() => new Set(overview.courses.map((c) => c.id)));
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [pendingId, setPendingId] = useState<number | null>(null);
  const [search, setSearch] = useState("");

  useEffect(() => {
    let cancelled = false;
    listCourses(false)
      .then((data) => {
        if (!cancelled) setAllCourses(data);
      })
      .catch((err) => {
        if (!cancelled) setError(err instanceof ApiError ? err.message : "Unable to load courses.");
      })
      .finally(() => {
        if (!cancelled) setIsLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  // Keep the checklist in sync if the overview refetches with a different
  // assigned set (e.g. after a toggle here updates the parent's overview).
  useEffect(() => {
    setAssignedIds(new Set(overview.courses.map((c) => c.id)));
  }, [overview.courses]);

  async function handleToggle(course: CourseRead) {
    setError(null);
    setPendingId(course.id);
    const isAssigned = assignedIds.has(course.id);
    try {
      if (isAssigned) {
        await removeCourseFromPanel(panelId, course.id);
      } else {
        await assignCourseToPanel(panelId, course.id);
      }
      onChanged();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Unable to update course assignment.");
    } finally {
      setPendingId(null);
    }
  }

  const query = search.trim().toLowerCase();
  const filtered = query
    ? allCourses.filter(
        (c) => c.course_name.toLowerCase().includes(query) || (c.course_code ?? "").toLowerCase().includes(query)
      )
    : allCourses;

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-lg">Assigned Courses</CardTitle>
        <p className="text-sm text-muted-foreground">
          Only courses assigned here are available for attendance sessions in this panel.
        </p>
      </CardHeader>
      <CardContent className="space-y-3">
        {error && (
          <Alert variant="destructive">
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}
        <div className="relative">
          <Search className="pointer-events-none absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search courses..."
            className="pl-8"
            aria-label="Search courses"
          />
        </div>
        {isLoading ? (
          <div className="flex justify-center py-8">
            <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
          </div>
        ) : allCourses.length === 0 ? (
          <p className="py-6 text-center text-sm text-muted-foreground">
            No courses in the catalog yet — add one on the Courses page first.
          </p>
        ) : filtered.length === 0 ? (
          <p className="py-6 text-center text-sm text-muted-foreground">No courses match &quot;{search}&quot;.</p>
        ) : (
          <ul className="max-h-80 space-y-1 overflow-y-auto">
            {filtered.map((course) => {
              const isChecked = assignedIds.has(course.id);
              return (
                <li key={course.id}>
                  <button
                    type="button"
                    onClick={() => handleToggle(course)}
                    disabled={pendingId === course.id}
                    className={cn(
                      "flex w-full items-center gap-2.5 rounded-lg border px-3 py-2 text-left text-sm transition-colors",
                      isChecked ? "border-primary bg-primary/5" : "border-border hover:bg-muted"
                    )}
                  >
                    {pendingId === course.id ? (
                      <Loader2 className="h-4 w-4 shrink-0 animate-spin text-muted-foreground" />
                    ) : isChecked ? (
                      <CheckSquare className="h-4 w-4 shrink-0 text-primary" />
                    ) : (
                      <Square className="h-4 w-4 shrink-0 text-muted-foreground" />
                    )}
                    <span className="min-w-0 flex-1 truncate">
                      <span className="font-medium">{course.course_name}</span>
                      {course.course_code && (
                        <span className="ml-1.5 font-mono text-xs text-muted-foreground">{course.course_code}</span>
                      )}
                    </span>
                  </button>
                </li>
              );
            })}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}

function StudentsTab({ panelId }: { panelId: number }) {
  const [students, setStudents] = useState<StudentAdminRead[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setIsLoading(true);
    listPanelStudents(panelId)
      .then((data) => {
        if (!cancelled) setStudents(data);
      })
      .catch((err) => {
        if (!cancelled) setError(err instanceof ApiError ? err.message : "Unable to load students.");
      })
      .finally(() => {
        if (!cancelled) setIsLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [panelId]);

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-lg">Student Roster</CardTitle>
        <p className="text-sm text-muted-foreground">
          The official roster for this panel — every student here already has a working SnapAttend login. Import or
          update it from the Import Excel tab.
        </p>
      </CardHeader>
      <CardContent>
        {error && (
          <Alert variant="destructive">
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}
        {isLoading ? (
          <div className="flex justify-center py-10">
            <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
          </div>
        ) : students.length === 0 ? (
          <p className="py-10 text-center text-sm text-muted-foreground">
            No students on file for this panel yet. Use Import Excel to add the roster.
          </p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[640px] text-left text-sm">
              <thead>
                <tr className="border-b border-border text-xs uppercase tracking-wide text-muted-foreground">
                  <th className="pb-3 pr-4 font-medium">Roll No.</th>
                  <th className="pb-3 pr-4 font-medium">PRN</th>
                  <th className="pb-3 pr-4 font-medium">Name</th>
                  <th className="pb-3 pr-4 font-medium">Batch</th>
                  <th className="pb-3 font-medium">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {students.map((student) => (
                  <tr key={student.id}>
                    <td className="py-3 pr-4 text-muted-foreground">{student.roll_number ?? "—"}</td>
                    <td className="py-3 pr-4 font-mono">{student.prn}</td>
                    <td className="py-3 pr-4 font-medium">{student.full_name}</td>
                    <td className="py-3 pr-4 text-muted-foreground">{student.batch ?? "—"}</td>
                    <td className="py-3">
                      <span
                        className={cn(
                          "inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium",
                          student.is_active
                            ? "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400"
                            : "bg-muted text-muted-foreground"
                        )}
                      >
                        {student.is_active ? "active" : "inactive"}
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
  );
}

/** Milestone 8B, Part 6 — Excel Import: accepts .xlsx, shows the exact
 * four counts the spec requires (Imported/Updated/Skipped/Errors) after
 * each upload. `excel_import_service.py` does the actual insert/update/
 * skip/validate work server-side; this tab is purely upload + summary
 * display. */
function ImportExcelTab({ panelId, onImported }: { panelId: number; onImported: () => void }) {
  const [file, setFile] = useState<File | null>(null);
  const [isUploading, setIsUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [summary, setSummary] = useState<ExcelImportSummary | null>(null);

  async function handleUpload() {
    if (!file) return;
    setError(null);
    setSummary(null);
    setIsUploading(true);
    try {
      const result = await importPanelStudents(panelId, file);
      setSummary(result);
      setFile(null);
      onImported();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Unable to import the file.");
    } finally {
      setIsUploading(false);
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-lg">Import Student List</CardTitle>
        <p className="text-sm text-muted-foreground">
          Expects columns Roll Number, PRN, Full Name (Roll Number and Batch are optional, but Roll Number must be
          unique within this panel if provided). New PRNs become working SnapAttend logins on the
          administrator-issued default password, forced to change it on first login; existing PRNs are updated;
          duplicate PRNs within the file are skipped; malformed or conflicting rows are reported as Failed with a
          reason. Passwords on existing accounts are never touched by an import.
        </p>
      </CardHeader>
      <CardContent className="space-y-4">
        {error && (
          <Alert variant="destructive">
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}

        <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
          <Input
            type="file"
            accept=".xlsx"
            onChange={(e) => setFile(e.target.files?.[0] ?? null)}
            disabled={isUploading}
            className="sm:max-w-sm"
            aria-label="Select Excel file"
          />
          <Button onClick={handleUpload} disabled={!file || isUploading} className="gap-2 sm:w-fit">
            {isUploading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Upload className="h-4 w-4" />}
            Import
          </Button>
        </div>

        {summary && (
          <div className="space-y-3 rounded-lg border border-border p-4">
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
              <SummaryStat label="Imported" value={summary.imported} tone="emerald" />
              <SummaryStat label="Updated" value={summary.updated} tone="primary" />
              <SummaryStat label="Skipped" value={summary.skipped} tone="muted" />
              <SummaryStat label="Failed" value={summary.errors.length} tone={summary.errors.length > 0 ? "destructive" : "muted"} />
            </div>

            {summary.errors.length > 0 && (
              <div className="space-y-1.5">
                <p className="flex items-center gap-1.5 text-sm font-medium text-destructive">
                  <X className="h-4 w-4" />
                  Failed rows
                </p>
                <ul className="max-h-48 space-y-1 overflow-y-auto text-sm">
                  {summary.errors.map((err, index) => (
                    <li key={index} className="rounded-md bg-destructive/5 px-2.5 py-1.5 text-destructive">
                      Row {err.row_number}: {err.message}
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        )}

        {!summary && !error && (
          <div className="flex flex-col items-center gap-2 rounded-lg border border-dashed border-border py-10 text-center text-muted-foreground">
            <FileSpreadsheet className="h-6 w-6" />
            <p className="text-sm">Select an .xlsx file to see the import summary here.</p>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function SummaryStat({
  label,
  value,
  tone,
}: {
  label: string;
  value: number;
  tone: "emerald" | "primary" | "muted" | "destructive";
}) {
  const toneClass = {
    emerald: "text-emerald-600 dark:text-emerald-400",
    primary: "text-primary",
    muted: "text-foreground",
    destructive: "text-destructive",
  }[tone];

  return (
    <div className="flex flex-col items-center gap-0.5 rounded-lg bg-muted/40 py-3 text-center">
      <span className={cn("text-2xl font-bold tabular-nums", toneClass)}>{value}</span>
      <span className="text-xs font-medium text-muted-foreground">{label}</span>
    </div>
  );
}
