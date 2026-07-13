"use client";

import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { Camera, Loader2, Square, Users } from "lucide-react";

import { Button } from "@/components/ui/button";
import { useActiveSession } from "@/hooks/use-attendance";
import { apiRequest, ApiError } from "@/lib/api";
import { formatCountdown } from "@/lib/utils";

/**
 * Fullscreen presentation screen, meant to be projected on a classroom
 * smart board. Deliberately has no navbar, sidebar, or menus — see
 * `middleware.ts` for the auth guard and `app/teacher/dashboard` for the
 * entry point ("Start Attendance").
 */
export default function TeacherSessionPage() {
  const router = useRouter();
  const { session, isActive, secondsLeft, isLoading, refetch } = useActiveSession();

  const [hasEnsuredSession, setHasEnsuredSession] = useState(false);
  const [startError, setStartError] = useState<string | null>(null);
  const [isEnding, setIsEnding] = useState(false);
  const attemptedStart = useRef(false);

  // Ensure a session exists: resume the active one if this page was
  // refreshed mid-session, otherwise start a fresh 90 second session.
  useEffect(() => {
    if (isLoading) return;

    if (isActive) {
      setHasEnsuredSession(true);
      return;
    }

    if (!hasEnsuredSession && !attemptedStart.current) {
      attemptedStart.current = true;
      apiRequest("/api/v1/attendance/start-session", { method: "POST" })
        .then(() => {
          setHasEnsuredSession(true);
          refetch();
        })
        .catch((err) => {
          setStartError(err instanceof ApiError ? err.message : "Could not start the attendance session.");
        });
    }
  }, [isLoading, isActive, hasEnsuredSession, refetch]);

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
    <div className="dark min-h-screen w-full bg-gradient-to-br from-slate-950 via-slate-900 to-black text-white">
      <div className="flex min-h-screen w-full flex-col items-center justify-center px-6 py-10">
        <div className="mb-10 flex items-center gap-2 text-white/60">
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

            <div
              className="select-none font-bold leading-none tracking-[0.15em]"
              style={{ fontSize: "clamp(5rem, 24vw, 300px)" }}
            >
              {session.session_code}
            </div>

            <div className="flex flex-col items-center gap-2">
              <span
                className="font-mono font-semibold tabular-nums text-white/90"
                style={{ fontSize: "clamp(2.5rem, 8vw, 6rem)" }}
              >
                {formatCountdown(secondsLeft)}
              </span>
              <span className="text-sm uppercase tracking-[0.3em] text-white/40">Time remaining</span>
            </div>

            <div className="flex flex-col items-center gap-2">
              <div className="flex items-center gap-3 text-4xl font-semibold sm:text-5xl">
                <Users className="h-8 w-8 text-white/50" />
                {session.present_count}
              </div>
              <span className="text-sm uppercase tracking-[0.3em] text-white/40">Students Present</span>
            </div>

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
