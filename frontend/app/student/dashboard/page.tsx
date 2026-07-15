"use client";

import { useRouter } from "next/navigation";
import { Camera, CircleSlash, Loader2 } from "lucide-react";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { DashboardShell } from "@/components/dashboard/dashboard-shell";
import { useActiveSession } from "@/hooks/use-attendance";
import { useCurrentUser } from "@/hooks/use-auth";
import type { Student } from "@/lib/types";
import { formatCountdown } from "@/lib/utils";

export default function StudentDashboardPage() {
  const router = useRouter();
  const { user, isLoading, error } = useCurrentUser<Student>("student", "/api/v1/students/me");
  const { session, isActive, secondsLeft, isLoading: isSessionLoading } = useActiveSession();

  if (isLoading) {
    return (
      <DashboardShell>
        <div className="flex justify-center py-12">
          <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
        </div>
      </DashboardShell>
    );
  }

  if (error || !user) {
    return (
      <DashboardShell>
        <Alert variant="destructive">
          <AlertDescription>{error ?? "Unable to load your profile."}</AlertDescription>
        </Alert>
      </DashboardShell>
    );
  }

  return (
    <DashboardShell>
      {/* Milestone 7C: compact single-line identity strip instead of a big
          hero block, so the primary-action card below is visible without
          scrolling on a phone. */}
      <div className="mx-auto flex w-full max-w-2xl flex-col gap-4">
        <div className="flex items-baseline justify-between gap-2">
          <h1 className="truncate text-xl font-bold tracking-tight sm:text-2xl">{user.full_name}</h1>
          <p className="shrink-0 text-sm text-muted-foreground">PRN: {user.prn}</p>
        </div>

        <Card className="w-full animate-in">
          {isSessionLoading ? (
            <CardContent className="flex justify-center py-10">
              <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
            </CardContent>
          ) : isActive && session ? (
            // Primary action first and immediately visible; session status
            // (badge + countdown) is compact and sits below the button per
            // spec, not a large hero number above it.
            <CardContent className="flex flex-col gap-4 pt-6">
              <Button
                size="lg"
                className="h-16 w-full text-lg"
                onClick={() => router.push("/student/attendance")}
              >
                <Camera />
                Open Camera
              </Button>

              <div className="flex items-center justify-between gap-3 rounded-lg bg-muted/50 px-4 py-2.5 text-sm">
                <span className="inline-flex items-center gap-1.5 font-medium text-emerald-600 dark:text-emerald-400">
                  <span className="h-1.5 w-1.5 rounded-full bg-emerald-500" />
                  Attendance Active
                </span>
                <span className="font-mono font-semibold tabular-nums text-foreground">
                  {formatCountdown(secondsLeft)}
                </span>
              </div>
            </CardContent>
          ) : (
            <CardContent className="flex flex-col items-center gap-2 py-8 text-center text-muted-foreground">
              <CircleSlash className="h-7 w-7" />
              <p className="font-medium text-foreground">No active attendance session</p>
              <p className="text-sm">You&apos;ll see a prompt here the moment your teacher opens one.</p>
            </CardContent>
          )}
        </Card>
      </div>
    </DashboardShell>
  );
}
