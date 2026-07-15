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
        <div className="dark flex min-h-screen w-full items-center justify-center bg-black">
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

      apiRequest("/api/v1/attendance/start-session", { method: "POST", body: { duration_seconds: duration } })
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
    <div className="dark min-h-screen w-full bg-black text-white">
      <div className="flex min-h-screen w-full flex-col items-center justify-center gap-10 px-6 py-10">
        <div className="flex items-center gap-2 text-white/60">
          <Camera className="h-5 w-5" />
          <span className="text-sm font-medium tracking-[0.3em] uppercase">SnapAttend</span>
        </div>

        {startError && (
          <div className="flex flex-col items-center gap-6 text-center animate-in">
            <p className="max-w-md text-lg text-white/80">{startError}</p>
            <Button variant="secondary" onClick={() => router.push("/teacher/dashboard")}>
              Back to dashboard
            </Button>
          </div>
        )}

        {!startError && !hasEnsuredSession && (
          <div className="flex flex-col items-center gap-4 text-white/70 animate-in">
            <Loader2 className="h-8 w-8 animate-spin" />
            <p className="text-lg">Preparing session…</p>
          </div>
        )}

        {!startError && hasEnsuredSession && isActive && session && (
          <div className="flex w-full flex-col items-center gap-10 text-center animate-in">
            <span className="rounded-full border border-white/15 bg-white/5 px-5 py-1.5 text-sm font-medium uppercase tracking-[0.25em] text-emerald-300">
              Attendance Active
            </span>

            {/*
             * Marker detection area — deliberately isolated from every other
             * element on this screen (countdown, session stats, roster) so
             * nothing else competes with it for OCR attention. Fixed square
             * frame, solid black background, bright white glyph:
             *   - Frame size is driven by min(vh, vw, cap) so it's always
             *     the largest square that fits the viewport without ever
             *     overflowing — this container's *size* never changes
             *     between renders, only the character inside it does.
             *   - Glyph font-size is a fixed fraction of the frame size
             *     (~65%), landing inside the 60-70% "of the display height"
             *     the marker is required to occupy, with the remaining
             *     ~35% split as margin on every side — exactly the
             *     "generous empty space" the detector's geometric glyph
             *     search relies on (backend/app/ai/display.py,
             *     MARKER_MIN/MAX_GLYPH_HEIGHT_RATIO).
             *   - This frame is the primary target the detector's
             *     display-panel search is built to find: a large, filled,
             *     high-contrast dark rectangle, unmistakably distinct from
             *     the rest of the (also dark, but unframed) page.
             *   - The border itself is now a thick, solid, fully-opaque
             *     white ring (not a faint tint) — evidence-driven: real
             *     captures showed a subtle border doesn't reliably survive
             *     camera/JPEG compression, so display-region detection
             *     can't yet lock onto "just the frame" and instead treats
             *     the whole (also-dark) screen as one region. A bold,
             *     unmistakable border is what a frame-refinement pass can
             *     actually detect against real-world noise.
             */}
            <div
              className="relative flex shrink-0 items-center justify-center rounded-[8%] border-[10px] border-white bg-black"
              style={{ width: "min(72vh, 72vw, 620px)", height: "min(72vh, 72vw, 620px)" }}
            >
              <span
                className="select-none font-black leading-none tracking-normal text-white"
                style={{ fontSize: "min(46vh, 46vw, 400px)" }}
              >
                {session.marker ?? "—"}
              </span>
            </div>

            <div className="flex flex-col items-center gap-2">
              <span
                className="font-mono font-semibold tabular-nums text-white/90"
                style={{ fontSize: "clamp(2.5rem, 8vw, 6rem)" }}
              >
                {formatCountdown(secondsLeft)}
              </span>
              <span className="text-sm uppercase tracking-[0.3em] text-white/40">Time Remaining</span>
            </div>

            <div className="flex w-full max-w-md items-stretch justify-center gap-8">
              <div className="flex flex-col items-center gap-2">
                <div className="flex items-center gap-3 text-4xl font-semibold sm:text-5xl">
                  <Users className="h-8 w-8 text-white/50" />
                  {records?.present_count ?? session.present_count}
                </div>
                <span className="text-sm uppercase tracking-[0.3em] text-white/40">Present</span>
              </div>
              {records && (
                <div className="flex flex-col items-center gap-2">
                  <div className="flex items-center gap-3 text-4xl font-semibold text-white/60 sm:text-5xl">
                    <UserCheck className="h-8 w-8 text-white/30" />
                    {records.remaining_count}
                  </div>
                  <span className="text-sm uppercase tracking-[0.3em] text-white/40">Remaining</span>
                </div>
              )}
            </div>

            {records && records.records.length > 0 && (
              <div className="max-h-48 w-full max-w-md overflow-y-auto rounded-xl border border-white/10 bg-white/5 p-3 text-left">
                <ul className="divide-y divide-white/10">
                  {records.records.map((record) => (
                    <li key={record.student_id} className="flex items-center justify-between py-2 text-sm text-white/80">
                      <span>{record.full_name}</span>
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
              size="lg"
              onClick={handleEndSession}
              disabled={isEnding}
              className="mt-4 gap-2 border border-white/20 bg-white/5 text-white hover:bg-white/15 hover:text-white"
            >
              {isEnding ? <Loader2 className="h-4 w-4 animate-spin" /> : <Square className="h-4 w-4" />}
              End Session
            </Button>
          </div>
        )}

        {hasEnded && (
          <div className="flex flex-col items-center gap-6 text-center animate-in">
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
    </div>
  );
}
