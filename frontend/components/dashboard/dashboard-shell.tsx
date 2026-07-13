"use client";

import { useRouter } from "next/navigation";
import { Camera, LogOut } from "lucide-react";
import type { ReactNode } from "react";

import { Button } from "@/components/ui/button";
import { ThemeToggle } from "@/components/theme-toggle";
import { clearSession } from "@/lib/auth";

interface DashboardShellProps {
  children: ReactNode;
}

/** Shared authenticated layout: top bar with branding, theme toggle, and logout. */
export function DashboardShell({ children }: DashboardShellProps) {
  const router = useRouter();

  function handleLogout() {
    clearSession();
    router.push("/");
  }

  return (
    <div className="flex min-h-screen flex-col">
      <header className="sticky top-0 z-40 w-full border-b border-border/60 bg-background/80 backdrop-blur supports-[backdrop-filter]:bg-background/60">
        <div className="container flex h-16 items-center justify-between">
          <div className="flex items-center gap-2 font-semibold tracking-tight">
            <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary text-primary-foreground">
              <Camera className="h-4 w-4" />
            </span>
            <span>SnapAttend AI</span>
          </div>
          <div className="flex items-center gap-1">
            <ThemeToggle />
            <Button variant="ghost" size="icon" onClick={handleLogout} aria-label="Log out" title="Log out">
              <LogOut />
            </Button>
          </div>
        </div>
      </header>

      <main className="container flex-1 py-10">{children}</main>
    </div>
  );
}
