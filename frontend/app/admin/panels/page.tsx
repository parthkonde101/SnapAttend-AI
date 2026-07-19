"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { AlertCircle, Eye, Loader2, Pencil, Plus, RefreshCw, Rows3, Trash2 } from "lucide-react";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { AdminDashboardShell } from "@/components/admin/admin-dashboard-shell";
import { AdminModal } from "@/components/admin/admin-modal";
import { createPanel, deletePanel, listAdminPanels, updatePanel } from "@/lib/admin-api";
import { ApiError } from "@/lib/api";
import type { PanelRead } from "@/lib/types";

type ModalState =
  | { type: "create" }
  | { type: "edit"; panel: PanelRead }
  | { type: "delete"; panel: PanelRead }
  | null;

function formatDate(iso: string) {
  return new Date(iso).toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" });
}

/** Milestone 8A — Panel System: admin CRUD for the `panels` table. A
 * panel is the unit a student registers into and a teacher selects when
 * starting a session — see the Student Registration and Start Attendance
 * flows for where these feed in. */
export default function AdminPanelsPage() {
  const [panels, setPanels] = useState<PanelRead[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [modal, setModal] = useState<ModalState>(null);

  const refetch = useCallback(async () => {
    setIsLoading(true);
    try {
      const data = await listAdminPanels();
      setPanels(data);
      setError(null);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Unable to load panels.");
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
          <h1 className="text-2xl font-bold tracking-tight sm:text-3xl">Panels</h1>
          <p className="text-muted-foreground">Manage the panels students register into and teachers select for a session.</p>
        </div>
        <Button className="gap-2" onClick={() => setModal({ type: "create" })}>
          <Plus className="h-4 w-4" />
          Add Panel
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
          <CardTitle className="text-lg">All Panels</CardTitle>
          <Button variant="ghost" size="icon" onClick={() => refetch()} aria-label="Refresh" title="Refresh">
            <RefreshCw className="h-4 w-4" />
          </Button>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <div className="flex justify-center py-10">
              <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
            </div>
          ) : panels.length === 0 ? (
            <div className="flex flex-col items-center gap-2 py-10 text-center text-muted-foreground">
              <Rows3 className="h-6 w-6" />
              <p className="text-sm">No panels yet. Add one to get started.</p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full min-w-[480px] text-left text-sm">
                <thead>
                  <tr className="border-b border-border text-xs uppercase tracking-wide text-muted-foreground">
                    <th className="pb-3 pr-4 font-medium">Panel Name</th>
                    <th className="pb-3 pr-4 font-medium">Academic Year</th>
                    <th className="pb-3 pr-4 font-medium">Created</th>
                    <th className="pb-3 font-medium">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {panels.map((panel) => (
                    <tr key={panel.id}>
                      <td className="py-3 pr-4 font-medium">
                        {/* Milestone 8B, Part 4: the panel name now opens
                            the detail page (Overview/Courses/Students/
                            Import Excel) — Edit/Delete stay as quick
                            row actions for the panel's own name. */}
                        <Link href={`/admin/panels/${panel.id}`} className="hover:underline">
                          {panel.name}
                        </Link>
                      </td>
                      <td className="py-3 pr-4 text-muted-foreground">{panel.academic_year ?? "—"}</td>
                      <td className="py-3 pr-4 text-muted-foreground">{formatDate(panel.created_at)}</td>
                      <td className="py-3">
                        <div className="flex flex-wrap gap-1">
                          <Button variant="ghost" size="icon" title="View" aria-label="View" asChild>
                            <Link href={`/admin/panels/${panel.id}`}>
                              <Eye className="h-4 w-4" />
                            </Link>
                          </Button>
                          <Button variant="ghost" size="icon" title="Edit" aria-label="Edit" onClick={() => setModal({ type: "edit", panel })}>
                            <Pencil className="h-4 w-4" />
                          </Button>
                          <Button variant="ghost" size="icon" title="Delete" aria-label="Delete" onClick={() => setModal({ type: "delete", panel })}>
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
        <CreatePanelModal onClose={() => setModal(null)} onCreated={() => { setModal(null); refetch(); }} />
      )}
      {modal?.type === "edit" && (
        <EditPanelModal panel={modal.panel} onClose={() => setModal(null)} onSaved={() => { setModal(null); refetch(); }} />
      )}
      {modal?.type === "delete" && (
        <DeletePanelModal panel={modal.panel} onClose={() => setModal(null)} onDeleted={() => { setModal(null); refetch(); }} />
      )}
    </AdminDashboardShell>
  );
}

function CreatePanelModal({ onClose, onCreated }: { onClose: () => void; onCreated: () => void }) {
  const [name, setName] = useState("");
  const [academicYear, setAcademicYear] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function handleSubmit() {
    setError(null);
    if (!name.trim()) {
      setError("Panel name is required.");
      return;
    }
    setIsSubmitting(true);
    try {
      await createPanel({ name: name.trim(), academic_year: academicYear.trim() || null });
      onCreated();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Unable to create panel.");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <AdminModal title="Add Panel" onClose={onClose}>
      {error && (
        <Alert variant="destructive">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}
      <div className="space-y-1.5">
        <Label htmlFor="create-panel-name">Panel Name</Label>
        <Input id="create-panel-name" value={name} onChange={(e) => setName(e.target.value)} disabled={isSubmitting} placeholder='e.g. "TY CSE A"' />
      </div>
      <div className="space-y-1.5">
        <Label htmlFor="create-panel-year">Academic Year</Label>
        <Input
          id="create-panel-year"
          value={academicYear}
          onChange={(e) => setAcademicYear(e.target.value)}
          disabled={isSubmitting}
          placeholder="Optional, e.g. 2025-26"
        />
      </div>
      <div className="flex justify-end gap-2 pt-1">
        <Button variant="outline" onClick={onClose} disabled={isSubmitting}>
          Cancel
        </Button>
        <Button onClick={handleSubmit} disabled={isSubmitting}>
          {isSubmitting && <Loader2 className="h-4 w-4 animate-spin" />}
          Add Panel
        </Button>
      </div>
    </AdminModal>
  );
}

function EditPanelModal({
  panel,
  onClose,
  onSaved,
}: {
  panel: PanelRead;
  onClose: () => void;
  onSaved: () => void;
}) {
  const [name, setName] = useState(panel.name);
  const [academicYear, setAcademicYear] = useState(panel.academic_year ?? "");
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function handleSubmit() {
    setError(null);
    if (!name.trim()) {
      setError("Panel name cannot be empty.");
      return;
    }
    setIsSubmitting(true);
    try {
      await updatePanel(panel.id, { name: name.trim(), academic_year: academicYear.trim() || null });
      onSaved();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Unable to update panel.");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <AdminModal title="Edit Panel" onClose={onClose}>
      {error && (
        <Alert variant="destructive">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}
      <div className="space-y-1.5">
        <Label htmlFor="edit-panel-name">Panel Name</Label>
        <Input id="edit-panel-name" value={name} onChange={(e) => setName(e.target.value)} disabled={isSubmitting} />
      </div>
      <div className="space-y-1.5">
        <Label htmlFor="edit-panel-year">Academic Year</Label>
        <Input
          id="edit-panel-year"
          value={academicYear}
          onChange={(e) => setAcademicYear(e.target.value)}
          disabled={isSubmitting}
          placeholder="Optional, e.g. 2025-26"
        />
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

function DeletePanelModal({
  panel,
  onClose,
  onDeleted,
}: {
  panel: PanelRead;
  onClose: () => void;
  onDeleted: () => void;
}) {
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function handleDelete() {
    setError(null);
    setIsSubmitting(true);
    try {
      await deletePanel(panel.id);
      onDeleted();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Unable to delete panel.");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <AdminModal title={`Delete ${panel.name}?`} onClose={onClose}>
      {error && (
        <Alert variant="destructive">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}
      <p className="text-sm text-muted-foreground">
        Students registered to this panel and sessions that referenced it keep their historical record, but they
        lose their panel assignment — students in this panel will no longer see panel-filtered sessions until an
        admin reassigns them. This cannot be undone.
      </p>
      <div className="flex justify-end gap-2 pt-1">
        <Button variant="outline" onClick={onClose} disabled={isSubmitting}>
          Cancel
        </Button>
        <Button variant="destructive" onClick={handleDelete} disabled={isSubmitting}>
          {isSubmitting && <Loader2 className="h-4 w-4 animate-spin" />}
          Delete Panel
        </Button>
      </div>
    </AdminModal>
  );
}
