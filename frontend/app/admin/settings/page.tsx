import type { Metadata } from "next";
import { Settings } from "lucide-react";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { AdminDashboardShell } from "@/components/admin/admin-dashboard-shell";

export const metadata: Metadata = {
  title: "Settings | SnapAttend AI Admin",
};

/** Milestone 7A: placeholder page. Nothing functional yet, per spec. */
export default function AdminSettingsPage() {
  return (
    <AdminDashboardShell>
      <div>
        <h1 className="text-2xl font-bold tracking-tight sm:text-3xl">Settings</h1>
        <p className="text-muted-foreground">System configuration.</p>
      </div>

      <Card>
        <CardHeader>
          <div className="mb-2 flex h-10 w-10 items-center justify-center rounded-lg bg-primary/10 text-primary">
            <Settings className="h-5 w-5" />
          </div>
          <CardTitle className="text-lg">Coming Soon</CardTitle>
          <CardDescription>System settings will be available here in a future update.</CardDescription>
        </CardHeader>
        <CardContent />
      </Card>
    </AdminDashboardShell>
  );
}
