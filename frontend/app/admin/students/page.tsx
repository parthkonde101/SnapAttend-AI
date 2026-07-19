"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { AlertCircle, KeyRound, Loader2, Pencil, Search, Trash2, UserCircle } from "lucide-react";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { AdminDashboardShell } from "@/components/admin/admin-dashboard-shell";
import { AdminModal } from "@/components/admin/admin-modal";
import { deleteStudent, resetStudentPassword, searchStudents, updateStudent } from "@/lib/admin-api";
import { ApiError } from "@/lib/api";
import type { StudentAdminRead } from "@/lib/types";
import { cn } from "@/lib/utils";

type ModalState =
  | { type: "edit"; student: StudentAdminRead }
  | { type: "reset"; student: StudentAdminRead }
  | { type: "delete"; student: StudentAdminRead }
  | null;

function formatDate(iso: string) {
  return new Date(iso).toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" });
}

export default function AdminStudentsPage() {
  const [query, setQuery] = useState("");
  const [students, setStudents] = useState<StudentAdminRead[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [modal, setModal] = useState<ModalState>(null);

  const refetch = useCallback(async (q: string) => {
    setIsLoading(true);
    try {
      const data = await searchStudents(q);
      setStudents(data);
      setError(null);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Unable to load students.");
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    const timeoutId = setTimeout(() => refetch(query), 300);
    return () => clearTimeout(timeoutId);
  }, [query, refetch]);

  return (
    <AdminDashboardShell>
      <div>
        <h1 className="text-2xl font-bold tracking-tight sm:text-3xl">Students</h1>
        <p className="text-muted-foreground">Search and manage registered students.</p>
      </div>

      <div className="relative max-w-sm">
        <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
        <Input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search by PRN, roll number, name, or division…"
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
          <CardTitle className="text-lg">All Students</CardTitle>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <div className="flex justify-center py-10">
              <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
            </div>
          ) : students.length === 0 ? (
            <p className="py-10 text-center text-sm text-muted-foreground">No students found.</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full min-w-[760px] text-left text-sm">
                <thead>
                  <tr className="border-b border-border text-xs uppercase tracking-wide text-muted-foreground">
                    <th className="pb-3 pr-4 font-medium">PRN</th>
                    <th className="pb-3 pr-4 font-medium">Roll No.</th>
                    <th className="pb-3 pr-4 font-medium">Name</th>
                    <th className="pb-3 pr-4 font-medium">Panel</th>
                    <th className="pb-3 pr-4 font-medium">Registered</th>
                    <th className="pb-3 pr-4 font-medium">Attendance %</th>
                    <th className="pb-3 pr-4 font-medium">Password</th>
                    <th className="pb-3 font-medium">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {students.map((student) => (
                    <tr key={student.id}>
                      <td className="py-3 pr-4 font-mono">{student.prn}</td>
                      <td className="py-3 pr-4 text-muted-foreground">{student.roll_number ?? "—"}</td>
                      <td className="py-3 pr-4 font-medium">{student.full_name}</td>
                      <td className="py-3 pr-4 text-muted-foreground">{student.panel?.name ?? "—"}</td>
                      <td className="py-3 pr-4 text-muted-foreground">{formatDate(student.created_at)}</td>
                      <td className="py-3 pr-4 tabular-nums">{student.attendance_percentage}%</td>
                      <td className="py-3 pr-4">
                        <span
                          className={cn(
                            "inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium",
                            student.password_changed
                              ? "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400"
                              : "bg-amber-500/10 text-amber-600 dark:text-amber-400"
                          )}
                        >
                          {student.password_changed ? "Set by student" : "Temporary (unchanged)"}
                        </span>
                      </td>
                      <td className="py-3">
                        <div className="flex flex-wrap gap-1">
                          <Button variant="ghost" size="icon" title="View Profile" aria-label="View Profile" asChild>
                            <Link href={`/admin/students/${student.id}`}>
                              <UserCircle className="h-4 w-4" />
                            </Link>
                          </Button>
                          <Button variant="ghost" size="icon" title="Edit" aria-label="Edit" onClick={() => setModal({ type: "edit", student })}>
                            <Pencil className="h-4 w-4" />
                          </Button>
                          <Button variant="ghost" size="icon" title="Reset Password" aria-label="Reset Password" onClick={() => setModal({ type: "reset", student })}>
                            <KeyRound className="h-4 w-4" />
                          </Button>
                          <Button variant="ghost" size="icon" title="Delete" aria-label="Delete" onClick={() => setModal({ type: "delete", student })}>
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

      {modal?.type === "edit" && (
        <EditStudentModal student={modal.student} onClose={() => setModal(null)} onSaved={() => { setModal(null); refetch(query); }} />
      )}
      {modal?.type === "reset" && (
        <ResetStudentPasswordModal student={modal.student} onClose={() => setModal(null)} onDone={() => setModal(null)} />
      )}
      {modal?.type === "delete" && (
        <DeleteStudentModal student={modal.student} onClose={() => setModal(null)} onDeleted={() => { setModal(null); refetch(query); }} />
      )}
    </AdminDashboardShell>
  );
}

function EditStudentModal({
  student,
  onClose,
  onSaved,
}: {
  student: StudentAdminRead;
  onClose: () => void;
  onSaved: () => void;
}) {
  const [fullName, setFullName] = useState(student.full_name);
  const [prn, setPrn] = useState(student.prn);
  const [rollNumber, setRollNumber] = useState(student.roll_number ?? "");
  const [division, setDivision] = useState(student.division ?? "");
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function handleSubmit() {
    setError(null);
    if (!fullName.trim() || !prn.trim()) {
      setError("Name and PRN cannot be empty.");
      return;
    }
    setIsSubmitting(true);
    try {
      await updateStudent(student.id, {
        full_name: fullName.trim(),
        prn: prn.trim(),
        roll_number: rollNumber.trim() || null,
        division: division.trim() || null,
      });
      onSaved();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Unable to update student.");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <AdminModal title="Edit Student" onClose={onClose}>
      {error && (
        <Alert variant="destructive">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}
      <div className="space-y-3">
        <div className="space-y-1.5">
          <Label htmlFor="edit-student-name">Name</Label>
          <Input id="edit-student-name" value={fullName} onChange={(e) => setFullName(e.target.value)} disabled={isSubmitting} />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="edit-student-prn">PRN</Label>
          <Input id="edit-student-prn" value={prn} onChange={(e) => setPrn(e.target.value)} disabled={isSubmitting} />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="edit-student-roll">Roll Number</Label>
          <Input
            id="edit-student-roll"
            value={rollNumber}
            onChange={(e) => setRollNumber(e.target.value)}
            disabled={isSubmitting}
            placeholder="Optional"
          />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="edit-student-division">Division</Label>
          <Input id="edit-student-division" value={division} onChange={(e) => setDivision(e.target.value)} disabled={isSubmitting} placeholder="Optional" />
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

function ResetStudentPasswordModal({
  student,
  onClose,
  onDone,
}: {
  student: StudentAdminRead;
  onClose: () => void;
  onDone: () => void;
}) {
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function handleSubmit() {
    setError(null);
    setIsSubmitting(true);
    try {
      await resetStudentPassword(student.id);
      setSuccess(true);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Unable to reset password.");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <AdminModal title={`Reset Password — ${student.full_name}`} onClose={onClose}>
      {success ? (
        <>
          <Alert>
            <AlertDescription>
              Password reset to the administrator-issued default. This student must set a new password the next
              time they log in.
            </AlertDescription>
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
          <p className="text-sm text-muted-foreground">
            This resets {student.full_name}&apos;s password to the administrator-issued default and requires them to
            set a new one on their next login. Students cannot reset their own password — this is the only way.
          </p>
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

function DeleteStudentModal({
  student,
  onClose,
  onDeleted,
}: {
  student: StudentAdminRead;
  onClose: () => void;
  onDeleted: () => void;
}) {
  const [confirmText, setConfirmText] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function handleDelete() {
    setError(null);
    setIsSubmitting(true);
    try {
      await deleteStudent(student.id);
      onDeleted();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Unable to delete student.");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <AdminModal title={`Delete ${student.full_name}?`} onClose={onClose}>
      {error && (
        <Alert variant="destructive">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}
      <p className="text-sm text-muted-foreground">
        This permanently removes the student account, every attendance record, attendance and registration photos,
        device locks, and diagnostics tied to them. This cannot be undone.
      </p>
      <div className="space-y-1.5">
        <Label htmlFor="delete-student-confirm">Type DELETE to confirm</Label>
        <Input id="delete-student-confirm" value={confirmText} onChange={(e) => setConfirmText(e.target.value)} disabled={isSubmitting} />
      </div>
      <div className="flex justify-end gap-2 pt-1">
        <Button variant="outline" onClick={onClose} disabled={isSubmitting}>
          Cancel
        </Button>
        <Button variant="destructive" onClick={handleDelete} disabled={isSubmitting || confirmText !== "DELETE"}>
          {isSubmitting && <Loader2 className="h-4 w-4 animate-spin" />}
          Delete Student
        </Button>
      </div>
    </AdminModal>
  );
}
