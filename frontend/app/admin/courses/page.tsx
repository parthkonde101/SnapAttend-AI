"use client";

import { useCallback, useEffect, useState } from "react";
import { AlertCircle, Archive, ArchiveRestore, BookOpen, Loader2, Pencil, Plus, RefreshCw, Trash2 } from "lucide-react";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { AdminDashboardShell } from "@/components/admin/admin-dashboard-shell";
import { AdminModal } from "@/components/admin/admin-modal";
import { createCourse, deleteCourse, listCourses, updateCourse } from "@/lib/admin-api";
import { ApiError } from "@/lib/api";
import type { CourseRead } from "@/lib/types";
import { cn } from "@/lib/utils";

type ModalState =
  | { type: "create" }
  | { type: "edit"; course: CourseRead }
  | { type: "delete"; course: CourseRead }
  | null;

function formatDate(iso: string) {
  return new Date(iso).toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" });
}

/** Milestone 8A — Course Normalization: admin CRUD for the `courses`
 * table. A course's teacher assignments are managed from the Teachers
 * page (per-teacher "Manage Courses" action), not here — this page is
 * purely the course catalog itself. */
export default function AdminCoursesPage() {
  const [courses, setCourses] = useState<CourseRead[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [modal, setModal] = useState<ModalState>(null);
  // Milestone 8B, Part 2: "Archive Course (optional)" — a per-row toggle
  // separate from the create/edit/delete modals above, since archiving is
  // a single one-click action rather than a form. Tracked by course id so
  // only the row being toggled shows a spinner, not the whole table.
  const [archivingId, setArchivingId] = useState<number | null>(null);

  const refetch = useCallback(async () => {
    setIsLoading(true);
    try {
      const data = await listCourses();
      setCourses(data);
      setError(null);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Unable to load courses.");
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    refetch();
  }, [refetch]);

  async function handleToggleArchive(course: CourseRead) {
    setArchivingId(course.id);
    setError(null);
    try {
      await updateCourse(course.id, { is_archived: !course.is_archived });
      await refetch();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Unable to update course.");
    } finally {
      setArchivingId(null);
    }
  }

  return (
    <AdminDashboardShell>
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight sm:text-3xl">Courses</h1>
          <p className="text-muted-foreground">Manage the course catalog. Assign courses to teachers from the Teachers page.</p>
        </div>
        <Button className="gap-2" onClick={() => setModal({ type: "create" })}>
          <Plus className="h-4 w-4" />
          Add Course
        </Button>
      </div>

      {error && (
        <Alert variant="destructive">
          <AlertCircle />
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      <Card>
        <CardHeader className="flex-row items-center justify-between space-y-0">
          <CardTitle className="text-lg">All Courses</CardTitle>
          <Button variant="ghost" size="icon" onClick={() => refetch()} aria-label="Refresh" title="Refresh">
            <RefreshCw className="h-4 w-4" />
          </Button>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <div className="flex justify-center py-10">
              <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
            </div>
          ) : courses.length === 0 ? (
            <div className="flex flex-col items-center gap-2 py-10 text-center text-muted-foreground">
              <BookOpen className="h-6 w-6" />
              <p className="text-sm">No courses yet. Add one to get started.</p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full min-w-[560px] text-left text-sm">
                <thead>
                  <tr className="border-b border-border text-xs uppercase tracking-wide text-muted-foreground">
                    <th className="pb-3 pr-4 font-medium">Course Code</th>
                    <th className="pb-3 pr-4 font-medium">Course Name</th>
                    <th className="pb-3 pr-4 font-medium">Status</th>
                    <th className="pb-3 pr-4 font-medium">Created</th>
                    <th className="pb-3 font-medium">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {courses.map((course) => (
                    <tr key={course.id} className={course.is_archived ? "opacity-60" : undefined}>
                      <td className="py-3 pr-4 font-mono">{course.course_code ?? "—"}</td>
                      <td className="py-3 pr-4 font-medium">{course.course_name}</td>
                      <td className="py-3 pr-4">
                        <span
                          className={cn(
                            "inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium",
                            course.is_archived ? "bg-muted text-muted-foreground" : "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400"
                          )}
                        >
                          <span className={cn("h-1.5 w-1.5 rounded-full", course.is_archived ? "bg-muted-foreground" : "bg-emerald-500")} />
                          {course.is_archived ? "Archived" : "Active"}
                        </span>
                      </td>
                      <td className="py-3 pr-4 text-muted-foreground">{formatDate(course.created_at)}</td>
                      <td className="py-3">
                        <div className="flex flex-wrap gap-1">
                          <Button variant="ghost" size="icon" title="Edit" aria-label="Edit" onClick={() => setModal({ type: "edit", course })}>
                            <Pencil className="h-4 w-4" />
                          </Button>
                          <Button
                            variant="ghost"
                            size="icon"
                            title={course.is_archived ? "Unarchive" : "Archive"}
                            aria-label={course.is_archived ? "Unarchive" : "Archive"}
                            disabled={archivingId === course.id}
                            onClick={() => handleToggleArchive(course)}
                          >
                            {archivingId === course.id ? (
                              <Loader2 className="h-4 w-4 animate-spin" />
                            ) : course.is_archived ? (
                              <ArchiveRestore className="h-4 w-4" />
                            ) : (
                              <Archive className="h-4 w-4" />
                            )}
                          </Button>
                          <Button variant="ghost" size="icon" title="Delete" aria-label="Delete" onClick={() => setModal({ type: "delete", course })}>
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

      {modal?.type === "create" && (
        <CreateCourseModal onClose={() => setModal(null)} onCreated={() => { setModal(null); refetch(); }} />
      )}
      {modal?.type === "edit" && (
        <EditCourseModal course={modal.course} onClose={() => setModal(null)} onSaved={() => { setModal(null); refetch(); }} />
      )}
      {modal?.type === "delete" && (
        <DeleteCourseModal course={modal.course} onClose={() => setModal(null)} onDeleted={() => { setModal(null); refetch(); }} />
      )}
    </AdminDashboardShell>
  );
}

function CreateCourseModal({ onClose, onCreated }: { onClose: () => void; onCreated: () => void }) {
  const [courseCode, setCourseCode] = useState("");
  const [courseName, setCourseName] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function handleSubmit() {
    setError(null);
    if (!courseCode.trim() || !courseName.trim()) {
      setError("Course code and name are required.");
      return;
    }
    setIsSubmitting(true);
    try {
      await createCourse({ course_code: courseCode.trim(), course_name: courseName.trim() });
      onCreated();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Unable to create course.");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <AdminModal title="Add Course" onClose={onClose}>
      {error && (
        <Alert variant="destructive">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}
      <div className="space-y-3">
        <div className="space-y-1.5">
          <Label htmlFor="create-course-code">Course Code</Label>
          <Input id="create-course-code" value={courseCode} onChange={(e) => setCourseCode(e.target.value)} disabled={isSubmitting} />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="create-course-name">Course Name</Label>
          <Input id="create-course-name" value={courseName} onChange={(e) => setCourseName(e.target.value)} disabled={isSubmitting} />
        </div>
      </div>
      <div className="flex justify-end gap-2 pt-1">
        <Button variant="outline" onClick={onClose} disabled={isSubmitting}>
          Cancel
        </Button>
        <Button onClick={handleSubmit} disabled={isSubmitting}>
          {isSubmitting && <Loader2 className="h-4 w-4 animate-spin" />}
          Add Course
        </Button>
      </div>
    </AdminModal>
  );
}

function EditCourseModal({
  course,
  onClose,
  onSaved,
}: {
  course: CourseRead;
  onClose: () => void;
  onSaved: () => void;
}) {
  const [courseCode, setCourseCode] = useState(course.course_code ?? "");
  const [courseName, setCourseName] = useState(course.course_name);
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function handleSubmit() {
    setError(null);
    if (!courseCode.trim() || !courseName.trim()) {
      setError("Course code and name cannot be empty.");
      return;
    }
    setIsSubmitting(true);
    try {
      await updateCourse(course.id, { course_code: courseCode.trim(), course_name: courseName.trim() });
      onSaved();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Unable to update course.");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <AdminModal title="Edit Course" onClose={onClose}>
      {error && (
        <Alert variant="destructive">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}
      <div className="space-y-3">
        <div className="space-y-1.5">
          <Label htmlFor="edit-course-code">Course Code</Label>
          <Input id="edit-course-code" value={courseCode} onChange={(e) => setCourseCode(e.target.value)} disabled={isSubmitting} />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="edit-course-name">Course Name</Label>
          <Input id="edit-course-name" value={courseName} onChange={(e) => setCourseName(e.target.value)} disabled={isSubmitting} />
        </div>
      </div>
      <div className="flex justify-end gap-2 pt-1">
        <Button variant="outline" onClick={onClose} disabled={isSubmitting}>
          Cancel
        </Button>
        <Button onClick={handleSubmit} disabled={isSubmitting}>
          {isSubmitting && <Loader2 className="h-4 w-4 animate-spin" />}
          Save Changes
        </Button>
      </div>
    </AdminModal>
  );
}

function DeleteCourseModal({
  course,
  onClose,
  onDeleted,
}: {
  course: CourseRead;
  onClose: () => void;
  onDeleted: () => void;
}) {
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function handleDelete() {
    setError(null);
    setIsSubmitting(true);
    try {
      await deleteCourse(course.id);
      onDeleted();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Unable to delete course.");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <AdminModal title={`Delete ${course.course_name}?`} onClose={onClose}>
      {error && (
        <Alert variant="destructive">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}
      <p className="text-sm text-muted-foreground">
        This removes the course from the catalog and every teacher&apos;s assignment to it. Sessions that already
        reference this course keep their historical record — only future sessions can no longer select it.
      </p>
      <div className="flex justify-end gap-2 pt-1">
        <Button variant="outline" onClick={onClose} disabled={isSubmitting}>
          Cancel
        </Button>
        <Button variant="destructive" onClick={handleDelete} disabled={isSubmitting}>
          {isSubmitting && <Loader2 className="h-4 w-4 animate-spin" />}
          Delete Course
        </Button>
      </div>
    </AdminModal>
  );
}
