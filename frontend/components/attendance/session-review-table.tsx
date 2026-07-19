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
  // Spec Part 14 ("Attendance Review Filters"): purely a client-side view
  // filter over the roster already in memory — no refetch, no reload, so
  // switching tabs is instant. `students` itself (the full roster) stays
  // untouched everywhere else in this component — the "newly marked"
  // highlight/auto-scroll effect and the photo-prefetch effect both need
  // to keep seeing every student regardless of which tab is selected, so
  // only the two render blocks below read `filteredStudents`.
  const [statusFilter, setStatusFilter] = useState<"all" | AttendanceStatus>("all");
  const [photoUrls, setPhotoUrls] = useState<Record<number, string>>({});
  const [photoErrors, setPhotoErrors] = useState<Record<number, boolean>>({});
  const [highlightedIds, setHighlightedIds] = useState<Set<number>>(new Set());
  const fetchedIds = useRef<Set<number>>(new Set());
  const scrollContainerRef = useRef<HTMLDivElement>(null);
  const prevMarkedAtRef = useRef<Map<number, string | null>>(new Map());

  // Milestone 7B/7C, Part 8: the roster always contains every registered
  // student (present or absent) — its *length* never changes as attendance
  // comes in. What actually happens live is a student's row moving from
  // the unmarked tail into its sorted position at the end of the "already
  // marked" block (see AttendanceReviewService.build_session_review's
  // sort_key: marked students ordered by marked_at ascending, unmarked
  // ones after). So "just arrived" is detected here as marked_at flipping
  // from null to non-null between renders, not by the array growing — and
  // that's also what drives both the highlight flash and the near-bottom
  // auto-scroll below, so a teacher who's scrolled up never has their
  // position yanked, but one already watching the boundary sees new
  // arrivals settle into view.
  useEffect(() => {
    const prevMap = prevMarkedAtRef.current;
    const isFirstRun = prevMap.size === 0;
    const newlyMarkedIds: number[] = [];

    students.forEach((item) => {
      const prevMarkedAt = prevMap.get(item.student_id);
      if (!isFirstRun && !prevMarkedAt && item.marked_at) {
        newlyMarkedIds.push(item.student_id);
      }
      prevMap.set(item.student_id, item.marked_at);
    });

    if (newlyMarkedIds.length === 0) return;

    setHighlightedIds((prev) => {
      const next = new Set(prev);
      newlyMarkedIds.forEach((id) => next.add(id));
      return next;
    });

    const container = scrollContainerRef.current;
    if (container) {
      const distanceFromBottom = container.scrollHeight - container.scrollTop - container.clientHeight;
      const wasNearBottom = distanceFromBottom < 200;
      if (wasNearBottom) {
        requestAnimationFrame(() => {
          container.scrollTo({ top: container.scrollHeight, behavior: "smooth" });
        });
      }
    }

    const timeoutId = setTimeout(() => {
      setHighlightedIds((prev) => {
        const next = new Set(prev);
        newlyMarkedIds.forEach((id) => next.delete(id));
        return next;
      });
    }, 2000);
    return () => clearTimeout(timeoutId);
  }, [students]);

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

  const presentCount = students.filter((item) => item.status === "present").length;
  const absentCount = students.length - presentCount;
  const filteredStudents =
    statusFilter === "all" ? students : students.filter((item) => item.status === statusFilter);

  return (
    <>
      <StatusFilterBar
        value={statusFilter}
        onChange={setStatusFilter}
        allCount={students.length}
        presentCount={presentCount}
        absentCount={absentCount}
      />

      {filteredStudents.length === 0 ? (
        <p className="py-10 text-center text-sm text-muted-foreground">No students match this filter.</p>
      ) : (
        <>
      {/* Milestone 7B: single scroll container shared by both the desktop
          table and the mobile compact list below, so the near-bottom
          auto-scroll effect above works regardless of which one is
          currently visible. Bounded height + sticky header keeps this
          efficiently scannable across 80-200 rows without the page itself
          scrolling the live session header out of view. */}
      <div ref={scrollContainerRef} className="max-h-[65vh] overflow-y-auto overscroll-contain rounded-lg border border-border">
        {/* Desktop / tablet: compact table, unchanged information density. */}
        <div className="hidden overflow-x-auto sm:block">
          <table className="w-full min-w-[820px] text-left text-sm">
            <thead className="sticky top-0 z-10 bg-background">
              <tr className="border-b border-border text-xs uppercase tracking-wide text-muted-foreground">
                <th className="px-4 py-3 font-medium">Photo</th>
                <th className="py-3 pr-4 font-medium">Roll No.</th>
                <th className="py-3 pr-4 font-medium">Student</th>
                <th className="py-3 pr-4 font-medium">Attendance</th>
                <th className="py-3 pr-4 font-medium">Verification</th>
                <th className="py-3 pr-4 font-medium">Marked At</th>
                <th className="py-3 pr-4 font-medium">Override</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {filteredStudents.map((item) => {
                const isPending = pendingStudentId === item.student_id;
                const photoUrl = photoUrls[item.student_id];
                const photoFailed = photoErrors[item.student_id];
                const verification = verificationDisplay(item);

                return (
                  <tr key={item.student_id} className={cn(highlightedIds.has(item.student_id) && "animate-row-highlight")}>
                    <td className="px-4 py-2">
                      <PhotoThumb
                        hasPhoto={item.has_photo}
                        photoUrl={photoUrl}
                        photoFailed={photoFailed}
                        fullName={item.full_name}
                        onEnlarge={() => setEnlargedStudentId(item.student_id)}
                      />
                    </td>
                    <td className="py-2 pr-4 text-muted-foreground">{item.roll_number ?? "—"}</td>
                    <td className="py-2 pr-4">
                      <div className="font-medium">{item.full_name}</div>
                      <div className="font-mono text-xs text-muted-foreground">{item.prn}</div>
                    </td>
                    <td className="py-2 pr-4">
                      <StatusBadge status={item.status} />
                    </td>
                    <td className="py-2 pr-4">
                      <VerificationInfo verification={verification} />
                    </td>
                    <td className="py-2 pr-4 font-mono text-xs tabular-nums text-muted-foreground">
                      {formatTime(item.marked_at)}
                    </td>
                    <td className="py-2 pr-4">
                      <OverrideButtons
                        status={item.status}
                        isPending={isPending}
                        onPresent={() => handleToggle(item.student_id, "present")}
                        onAbsent={() => handleToggle(item.student_id, "absent")}
                      />
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>

        {/* Phones: table columns don't fit without horizontal scroll, so
            below `sm` this renders the same information as compact stacked
            rows instead — photo/name/PRN stay primary, verification detail
            drops to a single de-emphasized line, actions move below. */}
        <div className="divide-y divide-border sm:hidden">
          {filteredStudents.map((item) => {
            const isPending = pendingStudentId === item.student_id;
            const photoUrl = photoUrls[item.student_id];
            const photoFailed = photoErrors[item.student_id];
            const verification = verificationDisplay(item);

            return (
              <div
                key={item.student_id}
                className={cn("flex flex-col gap-2 p-3", highlightedIds.has(item.student_id) && "animate-row-highlight")}
              >
                <div className="flex items-center gap-3">
                  <PhotoThumb
                    hasPhoto={item.has_photo}
                    photoUrl={photoUrl}
                    photoFailed={photoFailed}
                    fullName={item.full_name}
                    onEnlarge={() => setEnlargedStudentId(item.student_id)}
                  />
                  <div className="min-w-0 flex-1">
                    <div className="truncate font-medium">
                      {item.roll_number && <span className="mr-1.5 text-muted-foreground">{item.roll_number}</span>}
                      {item.full_name}
                    </div>
                    <div className="font-mono text-xs text-muted-foreground">{item.prn}</div>
                    <div className="mt-1 flex flex-wrap items-center gap-1.5">
                      <StatusBadge status={item.status} />
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
                  </div>
                </div>
                <div className="flex items-center justify-between gap-2 text-xs text-muted-foreground">
                  <span>
                    {verification.modeLabel} · {formatTime(item.marked_at)}
                  </span>
                </div>
                <OverrideButtons
                  status={item.status}
                  isPending={isPending}
                  onPresent={() => handleToggle(item.student_id, "present")}
                  onAbsent={() => handleToggle(item.student_id, "absent")}
                  fullWidth
                />
              </div>
            );
          })}
        </div>
      </div>
        </>
      )}

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

/** Milestone 7B: ~72x72px thumbnail — large enough for a teacher to spot a
 * wrong classroom/environment or a suspicious upload without opening the
 * full image, per Part 8. Shared between the desktop table and the mobile
 * compact list so both stay in sync automatically. */
function PhotoThumb({
  hasPhoto,
  photoUrl,
  photoFailed,
  fullName,
  onEnlarge,
}: {
  hasPhoto: boolean;
  photoUrl: string | undefined;
  photoFailed: boolean | undefined;
  fullName: string;
  onEnlarge: () => void;
}) {
  if (hasPhoto && photoUrl) {
    return (
      <button
        type="button"
        onClick={onEnlarge}
        className="block h-[72px] w-[72px] shrink-0 overflow-hidden rounded-lg border border-border transition-opacity hover:opacity-80"
        aria-label={`Enlarge attendance photo for ${fullName}`}
      >
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img src={photoUrl} alt={`Attendance capture for ${fullName}`} className="h-full w-full object-cover" />
      </button>
    );
  }
  if (hasPhoto && !photoFailed) {
    return (
      <div className="flex h-[72px] w-[72px] shrink-0 items-center justify-center rounded-lg border border-dashed border-border">
        <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />
      </div>
    );
  }
  return (
    <div className="flex h-[72px] w-[72px] shrink-0 items-center justify-center rounded-lg border border-dashed border-border text-muted-foreground">
      <ImageOff className="h-5 w-5" />
    </div>
  );
}

const STATUS_FILTERS: { key: "all" | AttendanceStatus; label: string }[] = [
  { key: "all", label: "All Students" },
  { key: "present", label: "Present" },
  { key: "absent", label: "Absent" },
];

/** Spec Part 14 ("Attendance Review Filters"): three tabs — All Students,
 * Present, Absent — each with a live count, so a teacher can jump straight
 * to the students they still need to check without scrolling past the
 * rest of the class. Purely a view filter over data already in memory
 * (see `statusFilter` in SessionReviewTable), so switching tabs is
 * instant — no reload, no refetch. */
function StatusFilterBar({
  value,
  onChange,
  allCount,
  presentCount,
  absentCount,
}: {
  value: "all" | AttendanceStatus;
  onChange: (value: "all" | AttendanceStatus) => void;
  allCount: number;
  presentCount: number;
  absentCount: number;
}) {
  const counts: Record<"all" | AttendanceStatus, number> = {
    all: allCount,
    present: presentCount,
    absent: absentCount,
  };

  return (
    <div className="mb-3 flex flex-wrap gap-1.5" role="tablist" aria-label="Filter students by attendance status">
      {STATUS_FILTERS.map((filter) => {
        const isActive = value === filter.key;
        return (
          <Button
            key={filter.key}
            type="button"
            role="tab"
            aria-selected={isActive}
            variant={isActive ? "secondary" : "outline"}
            size="sm"
            onClick={() => onChange(filter.key)}
            className="gap-1.5"
          >
            {filter.label}
            <span
              className={cn(
                "rounded-full px-1.5 py-0.5 text-[10px] font-semibold tabular-nums",
                isActive ? "bg-background/60" : "bg-muted text-muted-foreground"
              )}
            >
              {counts[filter.key]}
            </span>
          </Button>
        );
      })}
    </div>
  );
}

function StatusBadge({ status }: { status: AttendanceStatus }) {
  return (
    <span
      className={cn(
        "inline-flex w-fit items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium",
        status === "present" ? "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400" : "bg-muted text-muted-foreground"
      )}
    >
      <span className={cn("h-1.5 w-1.5 rounded-full", status === "present" ? "bg-emerald-500" : "bg-muted-foreground/50")} />
      {status === "present" ? "Present" : "Absent"}
    </span>
  );
}

/** Desktop-only: the fuller verification breakdown (mode + confidence +
 * detail line). Kept visually secondary — smaller, muted text — next to
 * the primary photo/name/status/confidence per Part 8. */
function VerificationInfo({ verification }: { verification: ReturnType<typeof verificationDisplay> }) {
  return (
    <div className="flex flex-col gap-1">
      <div className="flex items-center gap-1.5">
        <span className="text-xs text-muted-foreground">{verification.modeLabel}</span>
        {verification.level && (
          <span className={cn("inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium", CONFIDENCE_STYLES[verification.level])}>
            {CONFIDENCE_LABEL[verification.level]} · {verification.percent}
          </span>
        )}
      </div>
      {verification.detail && <span className="max-w-xs text-xs text-muted-foreground">{verification.detail}</span>}
    </div>
  );
}

function OverrideButtons({
  status,
  isPending,
  onPresent,
  onAbsent,
  fullWidth = false,
}: {
  status: AttendanceStatus;
  isPending: boolean;
  onPresent: () => void;
  onAbsent: () => void;
  fullWidth?: boolean;
}) {
  return (
    <div className={cn("flex gap-1.5", fullWidth && "w-full")}>
      <Button
        variant={status === "present" ? "secondary" : "outline"}
        size="sm"
        disabled={isPending}
        onClick={onPresent}
        aria-pressed={status === "present"}
        title="Mark present"
        className={cn(fullWidth && "flex-1")}
      >
        {isPending ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Check className="h-3.5 w-3.5" />}
        Present
      </Button>
      <Button
        variant={status === "absent" ? "secondary" : "outline"}
        size="sm"
        disabled={isPending}
        onClick={onAbsent}
        aria-pressed={status === "absent"}
        title="Mark absent"
        className={cn(fullWidth && "flex-1")}
      >
        {isPending ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <X className="h-3.5 w-3.5" />}
        Absent
      </Button>
    </div>
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
