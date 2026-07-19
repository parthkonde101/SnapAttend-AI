"use client";

import { useCallback, useEffect, useState } from "react";
import { AlertCircle, BookOpen, CheckSquare, Eye, KeyRound, Loader2, Pencil, Plus, RefreshCw, Search, Square, Trash2 } from "lucide-react";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { AdminDashboardShell } from "@/components/admin/admin-dashboard-shell";
import { AdminModal } from "@/components/admin/admin-modal";
import {
  assignCourseToTeacher,
  createTeacher,
  deleteTeacher,
  listCourses,
  listTeachers,
  removeCourseFromTeacher,
  resetTeacherPassword,
  updateTeacher,
} from "@/lib/admin-api";
import { ApiError } from "@/lib/api";
import { cn } from "@/lib/utils";
import type { CourseRead, TeacherAdminRead } from "@/lib/types";

type ModalState =
  | { type: "create" }
  | { type: "view"; teacher: TeacherAdminRead }
  | { type: "edit"; teacher: TeacherAdminRead }
  | { type: "courses"; teacher: TeacherAdminRead }
  | { type: "reset"; teacher: TeacherAdminRead }
  | { type: "delete"; teacher: TeacherAdminRead }
  | null;

function formatDate(iso: string) {
  return new Date(iso).toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" });
}

export default function AdminTeachersPage() {
  const [teachers, setTeachers] = useState<TeacherAdminRead[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [modal, setModal] = useState<ModalState>(null);

  const refetch = useCallback(async () => {
    setIsLoading(true);
    try {
      const data = await listTeachers();
      setTeachers(data);
      setError(null);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Unable to load teachers.");
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    refetch();
  }, [refetch]);

  return (
    <AdminDashboardShell>
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight sm:text-3xl">Teachers</h1>
          <p className="text-muted-foreground">Create and manage teacher accounts.</p>
        </div>
        <Button className="gap-2" onClick={() => setModal({ type: "create" })}>
          <Plus className="h-4 w-4" />
          Create Teacher
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
          <CardTitle className="text-lg">All Teachers</CardTitle>
          <Button variant="ghost" size="icon" onClick={() => refetch()} aria-label="Refresh" title="Refresh">
            <RefreshCw className="h-4 w-4" />
          </Button>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <div className="flex justify-center py-10">
              <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
            </div>
          ) : teachers.length === 0 ? (
            <p className="py-10 text-center text-sm text-muted-foreground">No teachers yet.</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full min-w-[720px] text-left text-sm">
                <thead>
                  <tr className="border-b border-border text-xs uppercase tracking-wide text-muted-foreground">
                    <th className="pb-3 pr-4 font-medium">Login ID</th>
                    <th className="pb-3 pr-4 font-medium">Teacher Name</th>
                    <th className="pb-3 pr-4 font-medium">Assigned Courses</th>
                    <th className="pb-3 pr-4 font-medium">Created</th>
                    <th className="pb-3 font-medium">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {teachers.map((teacher) => (
                    <tr key={teacher.id}>
                      <td className="py-3 pr-4 font-mono">{teacher.teacher_id}</td>
                      <td className="py-3 pr-4 font-medium">{teacher.full_name}</td>
                      <td className="py-3 pr-4">
                        {teacher.courses.length === 0 ? (
                          <span className="text-muted-foreground">—</span>
                        ) : (
                          <div className="flex flex-wrap gap-1">
                            {teacher.courses.map((course) => (
                              <span key={course.id} className="rounded-full bg-muted px-2 py-0.5 text-xs font-medium text-muted-foreground">
                                {course.course_name}
                              </span>
                            ))}
                          </div>
                        )}
                      </td>
                      <td className="py-3 pr-4 text-muted-foreground">{formatDate(teacher.created_at)}</td>
                      <td className="py-3">
                        <div className="flex flex-wrap gap-1">
                          <Button variant="ghost" size="icon" title="View" aria-label="View" onClick={() => setModal({ type: "view", teacher })}>
                            <Eye className="h-4 w-4" />
                          </Button>
                          <Button variant="ghost" size="icon" title="Manage Courses" aria-label="Manage Courses" onClick={() => setModal({ type: "courses", teacher })}>
                            <BookOpen className="h-4 w-4" />
                          </Button>
                          <Button variant="ghost" size="icon" title="Edit" aria-label="Edit" onClick={() => setModal({ type: "edit", teacher })}>
                            <Pencil className="h-4 w-4" />
                          </Button>
                          <Button variant="ghost" size="icon" title="Reset Password" aria-label="Reset Password" onClick={() => setModal({ type: "reset", teacher })}>
                            <KeyRound className="h-4 w-4" />
                          </Button>
                          <Button variant="ghost" size="icon" title="Delete" aria-label="Delete" onClick={() => setModal({ type: "delete", teacher })}>
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
        <CreateTeacherModal onClose={() => setModal(null)} onCreated={() => { setModal(null); refetch(); }} />
      )}
      {modal?.type === "view" && <ViewTeacherModal teacher={modal.teacher} onClose={() => setModal(null)} />}
      {modal?.type === "courses" && (
        <ManageCoursesModal teacher={modal.teacher} onClose={() => setModal(null)} onChanged={() => refetch()} />
      )}
      {modal?.type === "edit" && (
        <EditTeacherModal teacher={modal.teacher} onClose={() => setModal(null)} onSaved={() => { setModal(null); refetch(); }} />
      )}
      {modal?.type === "reset" && (
        <ResetPasswordModal teacher={modal.teacher} onClose={() => setModal(null)} onDone={() => setModal(null)} />
      )}
      {modal?.type === "delete" && (
        <DeleteTeacherModal teacher={modal.teacher} onClose={() => setModal(null)} onDeleted={() => { setModal(null); refetch(); }} />
      )}
    </AdminDashboardShell>
  );
}

function CreateTeacherModal({ onClose, onCreated }: { onClose: () => void; onCreated: () => void }) {
  const [fullName, setFullName] = useState("");
  const [teacherId, setTeacherId] = useState("");
  const [course, setCourse] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function handleSubmit() {
    setError(null);
    if (!fullName.trim() || !teacherId.trim() || password.length < 8) {
      setError("Name and Login ID are required, and password must be at least 8 characters.");
      return;
    }
    setIsSubmitting(true);
    try {
      await createTeacher({
        full_name: fullName.trim(),
        teacher_id: teacherId.trim(),
        course: course.trim() || null,
        password,
      });
      onCreated();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Unable to create teacher.");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <AdminModal title="Create Teacher" onClose={onClose}>
      {error && (
        <Alert variant="destructive">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}
      <div className="space-y-3">
        <div className="space-y-1.5">
          <Label htmlFor="create-name">Name</Label>
          <Input id="create-name" value={fullName} onChange={(e) => setFullName(e.target.value)} disabled={isSubmitting} />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="create-login">Login ID</Label>
          <Input id="create-login" value={teacherId} onChange={(e) => setTeacherId(e.target.value)} disabled={isSubmitting} />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="create-course">Course</Label>
          <Input id="create-course" value={course} onChange={(e) => setCourse(e.target.value)} disabled={isSubmitting} placeholder="Optional" />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="create-password">Password</Label>
          <Input id="create-password" type="password" value={password} onChange={(e) => setPassword(e.target.value)} disabled={isSubmitting} />
        </div>
      </div>
      <div className="flex justify-end gap-2 pt-1">
        <Button variant="outline" onClick={onClose} disabled={isSubmitting}>
          Cancel
        </Button>
        <Button onClick={handleSubmit} disabled={isSubmitting}>
          {isSubmitting && <Loader2 className="h-4 w-4 animate-spin" />}
          Create Teacher
        </Button>
      </div>
    </AdminModal>
  );
}

function ViewTeacherModal({ teacher, onClose }: { teacher: TeacherAdminRead; onClose: () => void }) {
  return (
    <AdminModal title="Teacher Details" onClose={onClose}>
      <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-2 text-sm">
        <dt className="text-muted-foreground">Login ID</dt>
        <dd className="font-mono">{teacher.teacher_id}</dd>
        <dt className="text-muted-foreground">Name</dt>
        <dd>{teacher.full_name}</dd>
        <dt className="text-muted-foreground">Courses</dt>
        <dd>{teacher.courses.length > 0 ? teacher.courses.map((c) => c.course_name).join(", ") : "—"}</dd>
        <dt className="text-muted-foreground">Created</dt>
        <dd>{formatDate(teacher.created_at)}</dd>
        <dt className="text-muted-foreground">Sessions started</dt>
        <dd>{teacher.session_count}</dd>
      </dl>
      <div className="flex justify-end pt-1">
        <Button variant="outline" onClick={onClose}>
          Close
        </Button>
      </div>
    </AdminModal>
  );
}

/** Teacher<->Course many-to-many assignment ("Extending the attendance
 * system" spec, Part 1/7): a searchable checklist, same pattern as the
 * Panel detail page's Courses tab. */
function ManageCoursesModal({
  teacher,
  onClose,
  onChanged,
}: {
  teacher: TeacherAdminRead;
  onClose: () => void;
  onChanged: () => void;
}) {
  const [allCourses, setAllCourses] = useState<CourseRead[]>([]);
  const [assignedIds, setAssignedIds] = useState<Set<number>>(() => new Set(teacher.courses.map((c) => c.id)));
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

  async function handleToggle(course: CourseRead) {
    setError(null);
    setPendingId(course.id);
    const isAssigned = assignedIds.has(course.id);
    try {
      if (isAssigned) {
        await removeCourseFromTeacher(teacher.id, course.id);
        setAssignedIds((prev) => {
          const next = new Set(prev);
          next.delete(course.id);
          return next;
        });
      } else {
        await assignCourseToTeacher(teacher.id, course.id);
        setAssignedIds((prev) => new Set(prev).add(course.id));
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
    <AdminModal title={`Assigned Courses — ${teacher.full_name}`} onClose={onClose}>
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
        <p className="py-6 text-center text-sm text-muted-foreground">No courses in the catalog yet.</p>
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
      <div className="flex justify-end pt-1">
        <Button variant="outline" onClick={onClose}>
          Done
        </Button>
      </div>
    </AdminModal>
  );
}

function EditTeacherModal({
  teacher,
  onClose,
  onSaved,
}: {
  teacher: TeacherAdminRead;
  onClose: () => void;
  onSaved: () => void;
}) {
  const [fullName, setFullName] = useState(teacher.full_name);
  const [teacherId, setTeacherId] = useState(teacher.teacher_id);
  const [course, setCourse] = useState(teacher.course ?? "");
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function handleSubmit() {
    setError(null);
    if (!fullName.trim() || !teacherId.trim()) {
      setError("Name and Login ID cannot be empty.");
      return;
    }
    setIsSubmitting(true);
    try {
      await updateTeacher(teacher.id, {
        full_name: fullName.trim(),
        teacher_id: teacherId.trim(),
        course: course.trim() || null,
      });
      onSaved();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Unable to update teacher.");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <AdminModal title="Edit Teacher" onClose={onClose}>
      {error && (
        <Alert variant="destructive">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}
      <div className="space-y-3">
        <div className="space-y-1.5">
          <Label htmlFor="edit-name">Name</Label>
          <Input id="edit-name" value={fullName} onChange={(e) => setFullName(e.target.value)} disabled={isSubmitting} />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="edit-login">Login ID</Label>
          <Input id="edit-login" value={teacherId} onChange={(e) => setTeacherId(e.target.value)} disabled={isSubmitting} />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="edit-course">Course</Label>
          <Input id="edit-course" value={course} onChange={(e) => setCourse(e.target.value)} disabled={isSubmitting} />
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

function ResetPasswordModal({
  teacher,
  onClose,
  onDone,
}: {
  teacher: TeacherAdminRead;
  onClose: () => void;
  onDone: () => void;
}) {
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function handleSubmit() {
    setError(null);
    if (password.length < 8) {
      setError("Password must be at least 8 characters.");
      return;
    }
    setIsSubmitting(true);
    try {
      await resetTeacherPassword(teacher.id, password);
      setSuccess(true);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Unable to reset password.");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <AdminModal title={`Reset Password — ${teacher.full_name}`} onClose={onClose}>
      {success ? (
        <>
          <Alert>
            <AlertDescription>Password reset successfully.</AlertDescription>
          </Alert>
          <div className="flex justify-end pt-1">
            <Button onClick={onDone}>Done</Button>
          </div>
        </>
      ) : (
        <>
          {error && (
            <Alert variant="destructive">
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          )}
          <div className="space-y-1.5">
            <Label htmlFor="reset-password">New Password</Label>
            <Input id="reset-password" type="password" value={password} onChange={(e) => setPassword(e.target.value)} disabled={isSubmitting} />
          </div>
          <div className="flex justify-end gap-2 pt-1">
            <Button variant="outline" onClick={onClose} disabled={isSubmitting}>
              Cancel
            </Button>
            <Button onClick={handleSubmit} disabled={isSubmitting}>
              {isSubmitting && <Loader2 className="h-4 w-4 animate-spin" />}
              Reset Password
            </Button>
          </div>
        </>
      )}
    </AdminModal>
  );
}

function DeleteTeacherModal({
  teacher,
  onClose,
  onDeleted,
}: {
  teacher: TeacherAdminRead;
  onClose: () => void;
  onDeleted: () => void;
}) {
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function handleDelete() {
    setError(null);
    setIsSubmitting(true);
    try {
      await deleteTeacher(teacher.id);
      onDeleted();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Unable to delete teacher.");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <AdminModal title={`Delete ${teacher.full_name}?`} onClose={onClose}>
      {error && (
        <Alert variant="destructive">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}
      <p className="text-sm text-muted-foreground">
        This permanently removes the teacher account. Teachers who own historical attendance sessions cannot be
        deleted — the account must be kept so those records are never orphaned.
      </p>
      <div className="flex justify-end gap-2 pt-1">
        <Button variant="outline" onClick={onClose} disabled={isSubmitting}>
          Cancel
        </Button>
        <Button variant="destructive" onClick={handleDelete} disabled={isSubmitting}>
          {isSubmitting && <Loader2 className="h-4 w-4 animate-spin" />}
          Delete Teacher
        </Button>
      </div>
    </AdminModal>
  );
}
