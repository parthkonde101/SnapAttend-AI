"use client";

import { useEffect, useRef, useState } from "react";
import { Check, ImageOff, Loader2, X } from "lucide-react";

import { Button } from "@/components/ui/button";
import { fetchAuthenticatedImageUrl } from "@/lib/api";
import { cn } from "@/lib/utils";
import type { AttendanceStatus, StudentAttendanceReviewItem } from "@/lib/types";

interface SessionReviewTableProps {
  sessionId: number;
  students: StudentAttendanceReviewItem[];
  isLoading: boolean;
  error: string | null;
  onSetStatus: (studentId: number, status: AttendanceStatus) => Promise<void>;
  /** Milestone 7A: lets the Administrator System reuse this exact
   * component against its own `/admin/sessions/{id}/photo/{student_id}`
   * endpoint instead of the teacher-scoped one — an Administrator isn't a
   * Teacher, so it can't go through `get_current_teacher`'s ownership
   * check. Optional and defaults to the original teacher path, so the
   * existing teacher review page (its only caller until now) is
   * completely unaffected. */
  photoBasePath?: string;
}

function formatTime(iso: string | null) {
  if (!iso) return "—";
  return new Date(iso).toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit", second: "2-digit" });
}

type ConfidenceLevel = "high" | "medium" | "low";

/** Presentation-layer bucketing only — the accept/reject decision already
 * happened server-side (app.services.attendance_verification_service). This
 * just turns a 0-1 confidence into the "High/Medium/Low" a teacher can
 * scan at a glance, per "Never hide confidence — display High/Medium/Low
 * or equivalent percentages." The exact percentage is always shown
 * alongside it, so nothing is actually hidden by the bucketing. */
function confidenceLevel(value: number): ConfidenceLevel {
  if (value >= 0.75) return "high";
  if (value >= 0.4) return "medium";
  return "low";
}

const CONFIDENCE_STYLES: Record<ConfidenceLevel, string> = {
  high: "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400",
  medium: "bg-amber-500/10 text-amber-600 dark:text-amber-400",
  low: "bg-orange-500/10 text-orange-600 dark:text-orange-400",
};

const CONFIDENCE_LABEL: Record<ConfidenceLevel, string> = { high: "High", medium: "Medium", low: "Low" };

/** What a record's "verification confidence" actually is depends on *how*
 * it was accepted — see marker_verification_mode. An exact OCR match's
 * real confidence is the OCR's own number; a lenient display-evidence
 * accept was never about reading the character at all, so its real
 * confidence is the geometric display-evidence tier, not a (probably
 * null) marker reading. A teacher override has no AI confidence — it's a
 * human decision, shown as "Manual" rather than a fabricated percentage.
 * Critically, this reads directly off fields that are *never cleared* by
 * a status override (see AttendanceReviewService's non-destructive
 * override), so a student currently marked Absent after being overridden
 * still shows exactly what the AI originally found — that evidence must
 * never disappear just because the current status changed. */
function verificationDisplay(item: StudentAttendanceReviewItem): {
  modeLabel: string;
  level: ConfidenceLevel | null;
  percent: string | null;
  detail: string | null;
} {
  if (item.marker_verification_mode === "teacher_override") {
    return { modeLabel: "Teacher override", level: null, percent: null, detail: "Marked manually — no AI evidence." };
  }
  if (item.marker_verification_mode === "display_evidence") {
    const value = item.display_confidence;
    return {
      modeLabel: "Display evidence",
      level: confidenceLevel(value),
      percent: `${Math.round(value * 100)}%`,
      detail: item.marker_detected_character
        ? `Marker read as '${item.marker_detected_character}', did not exactly match — accepted on identity + display evidence.`
        : "Marker character unreadable — accepted on identity + display evidence.",
    };
  }
  if (item.marker_verification_mode === "exact_match" && item.marker_confidence !== null) {
    const value = item.marker_confidence;
    return {
      modeLabel: "Exact match",
      level: confidenceLevel(value),
      percent: `${Math.round(value * 100)}%`,
      detail: item.marker_detected_character ? `Read '${item.marker_detected_character}'.` : null,
    };
  }
  return { modeLabel: "No attempt", level: null, percent: null, detail: null };
}

/** Teacher review roster: every registered student, present or absent, with
 * a scroll-friendly inline photo thumbnail, the AI evidence behind any
 * record (preserved even after an override), and an immediate
 * Present/Absent toggle. */
export function SessionReviewTable({
  sessionId,
  students,
  isLoading,
  error,
  onSetStatus,
  photoBasePath = "/api/v1/attendance/session-review",
}: SessionReviewTableProps) {
  const [pendingStudentId, setPendingStudentId] = useState<number | null>(null);
  const [enlargedStudentId, setEnlargedStudentId] = useState<number | null>(null);
  const [photoUrls, setPhotoUrls] = useState<Record<number, string>>({});
  const [photoErrors, setPhotoErrors] = useState<Record<number, boolean>>({});
  const fetchedIds = useRef<Set<number>>(new Set());

  // Load every row's photo as an authenticated blob up front (an <img> tag
  // can't attach the Authorization header itself) so thumbnails render
  // inline immediately — per "teacher can immediately compare classroom
  // backgrounds while scrolling," not one photo at a time behind a click.
  // Cached by student_id so a roster refresh (e.g. after an override)
  // never re-fetches a photo that's already loaded.
  useEffect(() => {
    const toFetch = students.filter((s) => s.has_photo && !fetchedIds.current.has(s.student_id));
    if (toFetch.length === 0) return;

    toFetch.forEach((student) => fetchedIds.current.add(student.student_id));

    toFetch.forEach((student) => {
      fetchAuthenticatedImageUrl(`${photoBasePath}/${sessionId}/photo/${student.student_id}`)
        .then((url) => {
          setPhotoUrls((prev) => ({ ...prev, [student.student_id]: url }));
        })
        .catch(() => {
          setPhotoErrors((prev) => ({ ...prev, [student.student_id]: true }));
        });
    });
  }, [sessionId, students, photoBasePath]);

  // Revoke every object URL when the table itself unmounts (navigating away
  // from the review page) so repeated visits don't leak blob memory.
  useEffect(() => {
    return () => {
      Object.values(photoUrls).forEach((url) => URL.revokeObjectURL(url));
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function handleToggle(studentId: number, nextStatus: AttendanceStatus) {
    setPendingStudentId(studentId);
    try {
      await onSetStatus(studentId, nextStatus);
    } catch {
      // useSessionReview already reverts the optimistic update and surfaces
      // the error via its own `error` state — nothing extra needed here.
    } finally {
      setPendingStudentId(null);
    }
  }

  if (isLoading) {
    return (
      <div className="flex justify-center py-10">
        <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (error) {
    return <p className="py-6 text-center text-sm text-destructive">{error}</p>;
  }

  if (students.length === 0) {
    return <p className="py-10 text-center text-sm text-muted-foreground">No registered students yet.</p>;
  }

  const enlargedStudent = students.find((s) => s.student_id === enlargedStudentId) ?? null;

  return (
    <>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[820px] text-left text-sm">
          <thead>
            <tr className="border-b border-border text-xs uppercase tracking-wide text-muted-foreground">
              <th className="pb-3 pr-4 font-medium">Photo</th>
              <th className="pb-3 pr-4 font-medium">Student</th>
              <th className="pb-3 pr-4 font-medium">Attendance</th>
              <th className="pb-3 pr-4 font-medium">Verification</th>
              <th className="pb-3 pr-4 font-medium">Marked At</th>
              <th className="pb-3 font-medium">Override</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {students.map((item) => {
              const isPending = pendingStudentId === item.student_id;
              const photoUrl = photoUrls[item.student_id];
              const photoFailed = photoErrors[item.student_id];
              const verification = verificationDisplay(item);

              return (
                <tr key={item.student_id}>
                  <td className="py-2 pr-4">
                    {item.has_photo && photoUrl ? (
                      <button
                        type="button"
                        onClick={() => setEnlargedStudentId(item.student_id)}
                        className="block h-16 w-16 overflow-hidden rounded-lg border border-border transition-opacity hover:opacity-80"
                        aria-label={`Enlarge attendance photo for ${item.full_name}`}
                      >
                        {/* eslint-disable-next-line @next/next/no-img-element */}
                        <img src={photoUrl} alt={`Attendance capture for ${item.full_name}`} className="h-full w-full object-cover" />
                      </button>
                    ) : item.has_photo && !photoFailed ? (
                      <div className="flex h-16 w-16 items-center justify-center rounded-lg border border-dashed border-border">
                        <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />
                      </div>
                    ) : (
                      <div className="flex h-16 w-16 items-center justify-center rounded-lg border border-dashed border-border text-muted-foreground">
                        <ImageOff className="h-5 w-5" />
                      </div>
                    )}
                  </td>
                  <td className="py-2 pr-4">
                    <div className="font-medium">{item.full_name}</div>
                    <div className="font-mono text-xs text-muted-foreground">{item.prn}</div>
                  </td>
                  <td className="py-2 pr-4">
                    <span
                      className={cn(
                        "inline-flex w-fit items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium",
                        item.status === "present"
                          ? "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400"
                          : "bg-muted text-muted-foreground"
                      )}
                    >
                      <span
                        className={cn(
                          "h-1.5 w-1.5 rounded-full",
                          item.status === "present" ? "bg-emerald-500" : "bg-muted-foreground/50"
                        )}
                      />
                      {item.status === "present" ? "Present" : "Absent"}
                    </span>
                  </td>
                  <td className="py-2 pr-4">
                    <div className="flex flex-col gap-1">
                      <div className="flex items-center gap-1.5">
                        <span className="text-xs text-muted-foreground">{verification.modeLabel}</span>
                        {verification.level && (
                          <span
                            className={cn(
                              "inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium",
                              CONFIDENCE_STYLES[verification.level]
                            )}
                          >
                            {CONFIDENCE_LABEL[verification.level]} · {verification.percent}
                          </span>
                        )}
                      </div>
                      {verification.detail && (
                        <span className="max-w-xs text-xs text-muted-foreground">{verification.detail}</span>
                      )}
                    </div>
                  </td>
                  <td className="py-2 pr-4 font-mono text-xs tabular-nums text-muted-foreground">
                    {formatTime(item.marked_at)}
                  </td>
                  <td className="py-2">
                    <div className="flex gap-1.5">
                      <Button
                        variant={item.status === "present" ? "secondary" : "outline"}
                        size="sm"
                        disabled={isPending}
                        onClick={() => handleToggle(item.student_id, "present")}
                        aria-pressed={item.status === "present"}
                        title="Mark present"
                      >
                        {isPending ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Check className="h-3.5 w-3.5" />}
                        Present
                      </Button>
                      <Button
                        variant={item.status === "absent" ? "secondary" : "outline"}
                        size="sm"
                        disabled={isPending}
                        onClick={() => handleToggle(item.student_id, "absent")}
                        aria-pressed={item.status === "absent"}
                        title="Mark absent"
                      >
                        {isPending ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <X className="h-3.5 w-3.5" />}
                        Absent
                      </Button>
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {enlargedStudent && photoUrls[enlargedStudent.student_id] && (
        <EnlargedPhotoModal
          imageUrl={photoUrls[enlargedStudent.student_id]}
          studentName={enlargedStudent.full_name}
          onClose={() => setEnlargedStudentId(null)}
        />
      )}
    </>
  );
}

interface EnlargedPhotoModalProps {
  imageUrl: string;
  studentName: string;
  onClose: () => void;
}

/** Enlarges a thumbnail that's already loaded — no second fetch, since the
 * table only ever renders a clickable thumbnail once its blob has already
 * arrived. */
function EnlargedPhotoModal({ imageUrl, studentName, onClose }: EnlargedPhotoModalProps) {
  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-6"
      role="dialog"
      aria-modal="true"
      onClick={onClose}
    >
      <div
        className="flex max-h-[85vh] max-w-2xl flex-col gap-3 rounded-xl bg-background p-4 shadow-xl"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="flex items-center justify-between gap-4">
          <h3 className="text-sm font-semibold">Attendance photo — {studentName}</h3>
          <Button variant="ghost" size="icon" onClick={onClose} aria-label="Close">
            <X className="h-4 w-4" />
          </Button>
        </div>
        <div className="flex min-h-[200px] items-center justify-center overflow-auto rounded-lg bg-muted">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src={imageUrl} alt={`Attendance capture for ${studentName}`} className="max-h-[70vh] w-auto rounded-lg" />
        </div>
      </div>
    </div>
  );
}
