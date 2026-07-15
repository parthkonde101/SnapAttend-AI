"use client";

import { useParams, useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { ArrowLeft, ImageIcon, Loader2 } from "lucide-react";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { AdminDashboardShell } from "@/components/admin/admin-dashboard-shell";
import { AdminModal } from "@/components/admin/admin-modal";
import { getStudentProfile } from "@/lib/admin-api";
import { ApiError, fetchAuthenticatedImageUrl } from "@/lib/api";
import type { StudentProfile } from "@/lib/types";

function formatDate(iso: string) {
  return new Date(iso).toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" });
}

function formatDateTime(iso: string) {
  return new Date(iso).toLocaleString(undefined, { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" });
}

/** Milestone 7A — Student Profile: registration details, attendance
 * summary/percentage, course-wise breakdown, full history, and the
 * uploaded registration image. Everything comes from one call to
 * GET /admin/students/{id}. */
export default function AdminStudentProfilePage() {
  const router = useRouter();
  const params = useParams<{ id: string }>();
  const studentId = Number(params.id);
  const hasValidId = Number.isFinite(studentId);

  const [profile, setProfile] = useState<StudentProfile | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [photoUrl, setPhotoUrl] = useState<string | null>(null);
  const [showEnlarged, setShowEnlarged] = useState(false);
  const fetchedPhoto = useRef(false);

  useEffect(() => {
    if (!hasValidId) return;
    let cancelled = false;
    getStudentProfile(studentId)
      .then((data) => {
        if (!cancelled) setProfile(data);
      })
      .catch((err) => {
        if (!cancelled) setError(err instanceof ApiError ? err.message : "Unable to load student profile.");
      })
      .finally(() => {
        if (!cancelled) setIsLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [studentId, hasValidId]);

  useEffect(() => {
    if (!profile?.has_registration_photo || fetchedPhoto.current) return;
    fetchedPhoto.current = true;
    fetchAuthenticatedImageUrl(`/api/v1/admin/students/${studentId}/registration-photo`)
      .then(setPhotoUrl)
      .catch(() => setPhotoUrl(null));
  }, [profile?.has_registration_photo, studentId]);

  useEffect(() => {
    return () => {
      if (photoUrl) URL.revokeObjectURL(photoUrl);
    };
  }, [photoUrl]);

  if (!hasValidId) {
    return (
      <AdminDashboardShell>
        <Alert variant="destructive">
          <AlertDescription>Invalid student id.</AlertDescription>
        </Alert>
      </AdminDashboardShell>
    );
  }

  return (
    <AdminDashboardShell>
      <Button variant="ghost" size="sm" className="w-fit gap-1.5" onClick={() => router.push("/admin/students")}>
        <ArrowLeft className="h-4 w-4" />
        Back to students
      </Button>

      {isLoading ? (
        <div className="flex justify-center py-24">
          <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
        </div>
      ) : error || !profile ? (
        <Alert variant="destructive">
          <AlertDescription>{error ?? "Unable to load student profile."}</AlertDescription>
        </Alert>
      ) : (
        <>
          <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
            <div>
              <h1 className="text-2xl font-bold tracking-tight sm:text-3xl">{profile.student.full_name}</h1>
              <p className="text-muted-foreground">
                PRN {profile.student.prn} · {profile.student.division ?? "No division on file"}
              </p>
            </div>
            <div className="flex flex-col items-start gap-1 sm:items-end">
              <span className="text-3xl font-bold tabular-nums">{profile.student.attendance_percentage}%</span>
              <span className="text-sm text-muted-foreground">Overall attendance</span>
            </div>
          </div>

          <div className="grid gap-6 lg:grid-cols-3">
            <Card className="lg:col-span-1">
              <CardHeader>
                <CardTitle className="text-lg">Registration Details</CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-2 text-sm">
                  <dt className="text-muted-foreground">Verified Name</dt>
                  <dd>{profile.verified_name ?? "—"}</dd>
                  <dt className="text-muted-foreground">Verified PRN</dt>
                  <dd>{profile.verified_prn ?? "—"}</dd>
                  <dt className="text-muted-foreground">Verified At</dt>
                  <dd>{profile.verified_at ? formatDateTime(profile.verified_at) : "—"}</dd>
                  <dt className="text-muted-foreground">Registered</dt>
                  <dd>{formatDate(profile.student.created_at)}</dd>
                </dl>

                <div className="space-y-2">
                  <p className="text-sm font-medium">Registration Photo</p>
                  {!profile.has_registration_photo ? (
                    <p className="text-sm text-muted-foreground">No registration photo on file.</p>
                  ) : photoUrl ? (
                    <button
                      type="button"
                      onClick={() => setShowEnlarged(true)}
                      className="block overflow-hidden rounded-lg border border-border"
                    >
                      {/* eslint-disable-next-line @next/next/no-img-element */}
                      <img src={photoUrl} alt="Registration ID card" className="h-40 w-full object-cover" />
                    </button>
                  ) : (
                    <div className="flex h-40 items-center justify-center rounded-lg border border-dashed border-border text-muted-foreground">
                      <ImageIcon className="h-6 w-6" />
                    </div>
                  )}
                </div>
              </CardContent>
            </Card>

            <Card className="lg:col-span-2">
              <CardHeader>
                <CardTitle className="text-lg">Course-wise Attendance</CardTitle>
              </CardHeader>
              <CardContent>
                {profile.course_wise.length === 0 ? (
                  <p className="py-6 text-center text-sm text-muted-foreground">No course attendance data yet.</p>
                ) : (
                  <div className="space-y-3">
                    {profile.course_wise.map((item) => (
                      <div key={item.course} className="space-y-1">
                        <div className="flex items-center justify-between text-sm">
                          <span className="font-medium">{item.course}</span>
                          <span className="text-muted-foreground">
                            {item.present_count}/{item.total_sessions} · {item.percentage}%
                          </span>
                        </div>
                        <div className="h-2 overflow-hidden rounded-full bg-muted">
                          <div
                            className="h-full rounded-full bg-primary"
                            style={{ width: `${Math.min(100, item.percentage)}%` }}
                          />
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>
          </div>

          <Card>
            <CardHeader>
              <CardTitle className="text-lg">Attendance History</CardTitle>
            </CardHeader>
            <CardContent>
              {profile.history.length === 0 ? (
                <p className="py-10 text-center text-sm text-muted-foreground">No attendance history yet.</p>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full min-w-[640px] text-left text-sm">
                    <thead>
                      <tr className="border-b border-border text-xs uppercase tracking-wide text-muted-foreground">
                        <th className="pb-3 pr-4 font-medium">Date</th>
                        <th className="pb-3 pr-4 font-medium">Course</th>
                        <th className="pb-3 pr-4 font-medium">Teacher</th>
                        <th className="pb-3 pr-4 font-medium">Status</th>
                        <th className="pb-3 font-medium">Marked At</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-border">
                      {profile.history.map((item) => (
                        <tr key={item.session_id}>
                          <td className="py-3 pr-4">{formatDate(item.date)}</td>
                          <td className="py-3 pr-4 text-muted-foreground">{item.course ?? "—"}</td>
                          <td className="py-3 pr-4 text-muted-foreground">{item.teacher_name}</td>
                          <td className="py-3 pr-4">
                            <span
                              className={
                                item.status === "present"
                                  ? "text-emerald-600 dark:text-emerald-400"
                                  : "text-muted-foreground"
                              }
                            >
                              {item.status === "present" ? "Present" : "Absent"}
                            </span>
                          </td>
                          <td className="py-3 text-muted-foreground">
                            {item.marked_at ? formatDateTime(item.marked_at) : "—"}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </CardContent>
          </Card>
        </>
      )}

      {showEnlarged && photoUrl && (
        <AdminModal title="Registration Photo" onClose={() => setShowEnlarged(false)} widthClassName="max-w-2xl">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src={photoUrl} alt="Registration ID card enlarged" className="max-h-[75vh] w-full rounded-lg object-contain" />
        </AdminModal>
      )}
    </AdminDashboardShell>
  );
}
