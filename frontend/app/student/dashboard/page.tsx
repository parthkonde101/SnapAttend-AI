"use client";

import { useRouter } from "next/navigation";
import { Camera, CircleSlash, Loader2 } from "lucide-react";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
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
        <div className="flex justify-center py-24">
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
      <div className="mx-auto flex max-w-2xl flex-col items-center gap-8 text-center">
        <div className="space-y-2">
          <p className="text-sm font-medium text-muted-foreground">Welcome back</p>
          <h1 className="text-3xl font-bold tracking-tight sm:text-4xl">{user.full_name}</h1>
          <p className="text-muted-foreground">PRN: {user.prn}</p>
        </div>

        <Card className="w-full animate-in">
          {isSessionLoading ? (
            <CardContent className="flex justify-center py-12">
              <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
            </CardContent>
          ) : isActive && session ? (
            <>
              <CardHeader>
                <span className="mx-auto mb-1 inline-flex items-center gap-2 rounded-full border border-border bg-muted/50 px-4 py-1 text-sm font-medium text-emerald-600 dark:text-emerald-400">
                  <span className="h-2 w-2 rounded-full bg-emerald-500" />
                  Attendance Active
                </span>
                <CardTitle>Your class is taking attendance</CardTitle>
                <CardDescription>Mark yourself present before the timer runs out.</CardDescription>
              </CardHeader>
              <CardContent className="flex flex-col items-center gap-6">
                <span className="font-mono text-5xl font-semibold tabular-nums">
                  {formatCountdown(secondsLeft)}
                </span>
                <Button
                  size="lg"
                  className="h-16 w-full max-w-sm text-lg"
                  onClick={() => router.push("/student/attendance")}
                >
                  <Camera />
                  Mark Attendance
                </Button>
              </CardContent>
            </>
          ) : (
            <>
              <CardHeader>
                <CardTitle>Attendance</CardTitle>
                <CardDescription>You&apos;ll see a prompt here the moment your teacher opens one.</CardDescription>
              </CardHeader>
              <CardContent className="flex flex-col items-center gap-3 py-10 text-muted-foreground">
                <CircleSlash className="h-8 w-8" />
                <p>No active attendance session.</p>
              </CardContent>
            </>
          )}
        </Card>
      </div>
    </DashboardShell>
  );
}
