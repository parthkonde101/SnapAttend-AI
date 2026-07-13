"use client";

import { useRouter } from "next/navigation";
import { Camera, CheckCircle2, Loader2 } from "lucide-react";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { DashboardShell } from "@/components/dashboard/dashboard-shell";
import { useActiveSession } from "@/hooks/use-attendance";
import { formatCountdown } from "@/lib/utils";

export default function StudentAttendancePage() {
  const router = useRouter();
  const { session, isActive, secondsLeft, isLoading, error } = useActiveSession();

  if (isLoading) {
    return (
      <DashboardShell>
        <div className="flex justify-center py-24">
          <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
        </div>
      </DashboardShell>
    );
  }

  if (error) {
    return (
      <DashboardShell>
        <Alert variant="destructive">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      </DashboardShell>
    );
  }

  if (!isActive || !session) {
    return (
      <DashboardShell>
        <div className="mx-auto flex max-w-md flex-col items-center gap-6 py-16 text-center">
          <h1 className="text-2xl font-bold tracking-tight">This attendance session has ended</h1>
          <p className="text-muted-foreground">
            Head back to your dashboard — you&apos;ll see the next session as soon as it starts.
          </p>
          <Button onClick={() => router.push("/student/dashboard")}>Back to dashboard</Button>
        </div>
      </DashboardShell>
    );
  }

  return (
    <DashboardShell>
      <div className="mx-auto flex max-w-2xl flex-col items-center gap-8 text-center animate-in">
        <div className="space-y-2">
          <span className="inline-flex items-center gap-2 rounded-full border border-border bg-muted/50 px-4 py-1.5 text-sm font-medium text-emerald-600 dark:text-emerald-400">
            <span className="h-2 w-2 rounded-full bg-emerald-500" />
            Attendance Session Active
          </span>
          <h1 className="text-3xl font-bold tracking-tight sm:text-4xl">Get ready to check in</h1>
        </div>

        <div className="flex flex-col items-center gap-1">
          <span className="font-mono text-5xl font-semibold tabular-nums sm:text-6xl">
            {formatCountdown(secondsLeft)}
          </span>
          <span className="text-sm uppercase tracking-[0.2em] text-muted-foreground">Time remaining</span>
        </div>

        <Card className="w-full">
          <CardHeader className="items-center text-center">
            <div className="mb-2 flex h-14 w-14 items-center justify-center rounded-full bg-primary/10 text-primary">
              <Camera className="h-6 w-6" />
            </div>
            <CardTitle>Camera Capture Coming Next</CardTitle>
            <CardDescription>
              Photo capture and verification will be added in an upcoming release. For now this
              confirms your session is live.
            </CardDescription>
          </CardHeader>
          <CardContent className="flex justify-center">
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              <CheckCircle2 className="h-4 w-4" />
              Session ID: {session.session_id}
            </div>
          </CardContent>
        </Card>
      </div>
    </DashboardShell>
  );
}
