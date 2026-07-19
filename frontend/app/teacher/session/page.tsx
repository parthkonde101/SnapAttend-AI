"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useRef, useState } from "react";
import { Camera, Loader2, Square, UserCheck, Users } from "lucide-react";

import { Button } from "@/components/ui/button";
import { useActiveSession, useSessionRecords } from "@/hooks/use-attendance";
import { apiRequest, ApiError } from "@/lib/api";
import { formatCountdown } from "@/lib/utils";
import { SESSION_DURATION_OPTIONS_SECONDS, type SessionDurationSeconds } from "@/lib/types";

/**
 * Fullscreen presentation screen, meant to be projected on a classroom
 * smart board. Deliberately has no navbar, sidebar, or menus — see
 * `middleware.ts` for the auth guard and `app/teacher/dashboard` for the
 * entry point ("Start Attendance").
 */
export default function TeacherSessionPage() {
  return (
    <Suspense
      fallback={
        <div className="dark flex h-dvh w-full items-center justify-center bg-black">
          <Loader2 className="h-8 w-8 animate-spin text-white/60" />
        </div>
      }
    >
      <TeacherSessionPageContent />
    </Suspense>
  );
}

function TeacherSessionPageContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { session, isActive, secondsLeft, isLoading, refetch } = useActiveSession();
  const { data: records } = useSessionRecords(isActive ? session?.session_id ?? null : null);

  const [hasEnsuredSession, setHasEnsuredSession] = useState(false);
  const [startError, setStartError] = useState<string | null>(null);
  const [isEnding, setIsEnding] = useState(false);
  const attemptedStart = useRef(false);

  // Ensure a session exists: resume the active one if this page was
  // refreshed mid-session, otherwise start a fresh session using the
  // duration chosen on the dashboard (?duration=<seconds>, falling back to
  // the backend's own 2-minute default if missing/invalid).
  useEffect(() => {
    if (isLoading) return;

    if (isActive) {
      setHasEnsuredSession(true);
      return;
    }

    if (!hasEnsuredSession && !attemptedStart.current) {
      attemptedStart.current = true;
      const requestedDuration = Number(searchParams.get("duration"));
      const duration = SESSION_DURATION_OPTIONS_SECONDS.includes(requestedDuration as SessionDurationSeconds)
        ? requestedDuration
        : undefined;

      const courseId = Number(searchParams.get("course_id"));
      const panelId = Number(searchParams.get("panel_id"));
      if (!courseId || !panelId) {
        setStartError("No course/panel was selected. Go back to the dashboard and pick a course and panel first.");
        return;
      }

      apiRequest("/api/v1/attendance/start-session", {
        method: "POST",
        body: { course_id: courseId, panel_id: panelId, duration_seconds: duration },
      })
        .then(() => {
          setHasEnsuredSession(true);
          refetch();
        })
        .catch((err) => {
          setStartError(err instanceof ApiError ? err.message : "Could not start the attendance session.");
        });
    }
  }, [isLoading, isActive, hasEnsuredSession, refetch, searchParams]);

  async function handleEndSession() {
    setIsEnding(true);
    try {
      await apiRequest("/api/v1/attendance/end-session", { method: "POST" });
    } catch {
      // Even if this fails (e.g. it already expired), fall through to a
      // refetch so the screen reflects reality.
    } finally {
      await refetch();
      setIsEnding(false);
    }
  }

  const hasEnded = hasEnsuredSession && !isActive && !startError;

  return (
    // Solid near-black page background (not a gradient) — every pixel a
    // student's camera sees around the marker frame should be genuinely
    // dark, not just relatively darker than its surroundings. See
    // backend/app/ai/display.py's display-panel geometry stage, which
    // specifically checks for this (MARKER_MAX_DISPLAY_MEAN_BRIGHTNESS).
    //
    // Milestone 7C: rebuilt from one long centered column (which needed to
    // scroll on phones) into a two-region flex layout that never exceeds
    // the viewport — marker region + compact info region stacked on
    // phones, side-by-side from `lg` up. The whole page is `h-dvh
    // overflow-hidden`, so nothing here can ever require page scroll; if
    // content would overflow, only the info region's own roster list
    // scrolls internally (desktop only — dropped on phones entirely to
    // guarantee everything fits above the fold).
    <div className="dark flex h-dvh w-full flex-col overflow-hidden bg-black text-white lg:flex-row lg:items-center lg:justify-center lg:gap-16 lg:p-10">
      {startError && (
        <div className="flex flex-1 flex-col items-center justify-center gap-6 px-6 text-center animate-in">
          <p className="max-w-md text-lg text-white/80">{startError}</p>
          <Button variant="secondary" onClick={() => router.push("/teacher/dashboard")}>
            Back to dashboard
          </Button>
        </div>
      )}

      {!startError && !hasEnsuredSession && (
        <div className="flex flex-1 flex-col items-center justify-center gap-4 text-white/70 animate-in">
          <Loader2 className="h-8 w-8 animate-spin" />
          <p className="text-lg">Preparing session…</p>
        </div>
      )}

      {!startError && hasEnsuredSession && isActive && session && (
        <>
          {/*
           * Marker detection area — deliberately isolated from every other
           * element on this screen (countdown, session stats, roster) so
           * nothing else competes with it for OCR attention. Fixed square
           * frame, solid black background, bright white glyph:
           *   - Frame size is driven by a `--marker-size` custom property
           *     (min(vh, vw, cap), tuned per breakpoint below) so it's
           *     always the largest square that fits its region without
           *     ever overflowing — this container's *size* never changes
           *     between renders, only the character and the countdown
           *     beneath it do.
           *   - Glyph font-size stays a fixed 65% of the frame size at
           *     every breakpoint — the same ratio as before — landing
           *     inside the 60-70% "of the display height" the marker is
           *     required to occupy, with the remaining ~35% split as
           *     margin on every side — exactly the "generous empty space"
           *     the detector's geometric glyph search relies on
           *     (backend/app/ai/display.py, MARKER_MIN/MAX_GLYPH_HEIGHT_RATIO).
           *   - This frame is the primary target the detector's
           *     display-panel search is built to find: a large, filled,
           *     high-contrast dark rectangle, unmistakably distinct from
           *     the rest of the (also dark, but unframed) page.
           *   - The border stays a constant 10px thick, solid, fully-opaque
           *     white ring at every screen size (never thinned down for
           *     mobile) — evidence-driven: real captures showed a subtle
           *     border doesn't reliably survive camera/JPEG compression, so
           *     display-region detection can't yet lock onto "just the
           *     frame" and instead treats the whole (also-dark) screen as
           *     one region. A bold, unmistakable border is what a
           *     frame-refinement pass can actually detect against
           *     real-world noise.
           */}
          <div className="flex min-h-0 flex-1 flex-col items-center justify-center gap-2 p-3 lg:flex-none lg:gap-4 lg:p-0">
            <div className="flex items-center gap-1.5 text-white/50 lg:hidden">
              <Camera className="h-3.5 w-3.5" />
              <span className="text-[10px] font-medium tracking-[0.25em] uppercase">SnapAttend</span>
            </div>

            <div
              className="relative flex shrink-0 items-center justify-center rounded-[8%] border-[10px] border-white bg-black [--marker-size:min(42vh,80vw,440px)] sm:[--marker-size:min(48vh,74vw,520px)] lg:[--marker-size:min(78vh,44vw,660px)]"
              style={{ width: "var(--marker-size)", height: "var(--marker-size)" }}
            >
              <span
                className="select-none font-black leading-none tracking-normal text-white"
                style={{ fontSize: "calc(var(--marker-size) * 0.65)" }}
              >
                {session.marker ?? "—"}
              </span>
            </div>
          </div>

          {/* Compact session info — phones: shrink-0 strip below the
              marker; desktop: fixed-width side column. Only the countdown
              (and, live, the present/remaining counts) update in place —
              nothing here ever changes the marker region's size. */}
          <div className="flex shrink-0 flex-col items-center gap-2.5 border-t border-white/10 bg-black/40 px-4 py-3 text-center animate-in lg:w-72 lg:items-start lg:border-t-0 lg:bg-transparent lg:p-0 lg:text-left">
            <span className="hidden items-center gap-2 text-white/50 lg:flex">
              <Camera className="h-5 w-5" />
              <span className="text-sm font-medium tracking-[0.3em] uppercase">SnapAttend</span>
            </span>

            <span className="rounded-full border border-white/15 bg-white/5 px-3.5 py-1 text-[11px] font-medium uppercase tracking-[0.2em] text-emerald-300 lg:px-5 lg:py-1.5 lg:text-sm">
              Attendance Active
            </span>

            <div className="flex items-baseline gap-2 lg:flex-col lg:items-start lg:gap-1">
              <span className="font-mono text-3xl font-semibold tabular-nums text-white/90 lg:text-5xl">
                {formatCountdown(secondsLeft)}
              </span>
              <span className="text-[11px] uppercase tracking-[0.25em] text-white/40 lg:text-sm">Time Remaining</span>
            </div>

            <div className="flex items-center gap-5 lg:w-full lg:justify-between lg:gap-4">
              <div className="flex items-center gap-2 text-white/80">
                <Users className="h-4 w-4 text-white/50 lg:h-5 lg:w-5" />
                <span className="text-lg font-semibold lg:text-2xl">{records?.present_count ?? session.present_count}</span>
                <span className="text-[11px] uppercase tracking-[0.2em] text-white/40 lg:text-xs">Present</span>
              </div>
              {records && (
                <div className="flex items-center gap-2 text-white/60">
                  <UserCheck className="h-4 w-4 text-white/30 lg:h-5 lg:w-5" />
                  <span className="text-lg font-semibold lg:text-2xl">{records.remaining_count}</span>
                  <span className="text-[11px] uppercase tracking-[0.2em] text-white/40 lg:text-xs">Left</span>
                </div>
              )}
            </div>

            {/* Roster list: desktop-only. Dropped on phones so the info
                strip stays compact enough to guarantee no page scroll —
                the full roster is always available on the Teacher Live
                Review page. */}
            {records && records.records.length > 0 && (
              <div className="hidden max-h-56 w-full overflow-y-auto rounded-xl border border-white/10 bg-white/5 p-3 text-left lg:block">
                <ul className="divide-y divide-white/10">
                  {records.records.map((record) => (
                    <li key={record.student_id} className="flex items-center justify-between py-2 text-sm text-white/80">
                      <span className="flex items-center gap-2">
                        {record.roll_number && (
                          <span className="font-mono text-xs text-white/40">{record.roll_number}</span>
                        )}
                        {record.full_name}
                      </span>
                      <span className="font-mono text-xs text-white/40">
                        {new Date(record.marked_at).toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" })}
                      </span>
                    </li>
                  ))}
                </ul>
              </div>
            )}

            <Button
              variant="ghost"
              size="sm"
              onClick={handleEndSession}
              disabled={isEnding}
              className="mt-1 gap-2 border border-white/20 bg-white/5 text-white hover:bg-white/15 hover:text-white lg:mt-2 lg:h-11 lg:px-6"
            >
              {isEnding ? <Loader2 className="h-4 w-4 animate-spin" /> : <Square className="h-4 w-4" />}
              End Session
            </Button>
          </div>
        </>
      )}

      {hasEnded && (
        <div className="flex flex-1 flex-col items-center justify-center gap-6 px-6 text-center animate-in">
          <span className="rounded-full border border-white/15 bg-white/5 px-5 py-1.5 text-sm font-medium uppercase tracking-[0.25em] text-white/50">
            Attendance Session Ended
          </span>
          {session && (
            <div className="flex items-center gap-3 text-2xl font-medium text-white/80">
              <Users className="h-6 w-6 text-white/50" />
              {session.present_count} students marked present
            </div>
          )}
          <Button variant="secondary" onClick={() => router.push("/teacher/dashboard")}>
            Back to dashboard
          </Button>
        </div>
      )}
    </div>
  );
}
