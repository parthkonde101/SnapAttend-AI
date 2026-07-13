"use client";

import { useState } from "react";
import { Camera, Loader2 } from "lucide-react";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { DashboardShell } from "@/components/dashboard/dashboard-shell";
import { useCurrentUser } from "@/hooks/use-auth";
import type { Student } from "@/lib/types";

export default function StudentDashboardPage() {
  const { user, isLoading, error } = useCurrentUser<Student>("student", "/api/v1/students/me");
  const [notice, setNotice] = useState<string | null>(null);

  function handleOpenAttendance() {
    // Attendance capture/verification is not implemented yet.
    setNotice("Attendance marking is coming soon.");
  }

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

        <Card className="w-full">
          <CardHeader>
            <CardTitle>Attendance</CardTitle>
            <CardDescription>Open your attendance session when your class begins.</CardDescription>
          </CardHeader>
          <CardContent className="flex flex-col items-center gap-4">
            <Button size="lg" className="h-16 w-full max-w-sm text-lg" onClick={handleOpenAttendance}>
              <Camera />
              Open Attendance
            </Button>
            {notice && <p className="text-sm text-muted-foreground">{notice}</p>}
          </CardContent>
        </Card>
      </div>
    </DashboardShell>
  );
}
