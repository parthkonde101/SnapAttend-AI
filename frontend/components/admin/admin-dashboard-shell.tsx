"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import type { ReactNode } from "react";
import {
  BarChart3,
  BookOpen,
  Camera,
  ClipboardList,
  LayoutDashboard,
  LogOut,
  Rows3,
  Settings,
  Users,
  GraduationCap,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { ThemeToggle } from "@/components/theme-toggle";
import { cn } from "@/lib/utils";
import { clearSession } from "@/lib/auth";

interface NavItem {
  label: string;
  href: string;
  icon: typeof LayoutDashboard;
  comingSoon?: boolean;
}

const NAV_ITEMS: NavItem[] = [
  { label: "Dashboard", href: "/admin/dashboard", icon: LayoutDashboard },
  { label: "Students", href: "/admin/students", icon: GraduationCap },
  { label: "Teachers", href: "/admin/teachers", icon: Users },
  { label: "Courses", href: "/admin/courses", icon: BookOpen },
  { label: "Panels", href: "/admin/panels", icon: Rows3 },
  { label: "Attendance Sessions", href: "/admin/sessions", icon: ClipboardList },
  { label: "Attendance Report", href: "/admin/reports", icon: BarChart3 },
  { label: "Settings", href: "/admin/settings", icon: Settings },
];

interface AdminDashboardShellProps {
  children: ReactNode;
}

/**
 * Shared authenticated layout for every /admin/* screen (Milestone 7A).
 * Deliberately a sibling of `DashboardShell` (components/dashboard/), not
 * a replacement — the student/teacher app keeps its existing top-bar-only
 * layout untouched. Same design tokens (border-border, bg-background,
 * text-muted-foreground, rounded-lg/xl) and the same header pattern
 * (brand mark, theme toggle, logout) as `DashboardShell`, just with a left
 * sidebar for admin-specific navigation per the milestone spec.
 */
export function AdminDashboardShell({ children }: AdminDashboardShellProps) {
  const router = useRouter();
  const pathname = usePathname();

  function handleLogout() {
    clearSession();
    router.push("/");
  }

  return (
    <div className="flex min-h-dvh flex-col">
      <header className="sticky top-0 z-40 w-full border-b border-border/60 bg-background/80 backdrop-blur supports-[backdrop-filter]:bg-background/60">
        <div className="flex h-14 items-center justify-between px-4 sm:h-16 sm:px-6">
          <div className="flex items-center gap-2 font-semibold tracking-tight">
            <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary text-primary-foreground">
              <Camera className="h-4 w-4" />
            </span>
            <span>SnapAttend</span>
            <span className="ml-1 rounded-full bg-muted px-2 py-0.5 text-xs font-medium text-muted-foreground">
              Admin
            </span>
          </div>
          <div className="flex items-center gap-1">
            <ThemeToggle />
            <Button variant="ghost" size="icon" onClick={handleLogout} aria-label="Log out" title="Log out">
              <LogOut />
            </Button>
          </div>
        </div>

        {/* Milestone 7B: the sidebar below is hidden under the sm
            breakpoint, which previously left phones with zero navigation
            into Students/Teachers/Sessions/Settings. This horizontally
            scrollable pill row is the mobile-only substitute — no new
            navigation logic, just a second rendering of the same
            NAV_ITEMS. */}
        <nav className="flex gap-1.5 overflow-x-auto border-t border-border/60 px-3 py-2 sm:hidden">
          {NAV_ITEMS.map((item) => {
            const isActive = pathname === item.href || pathname.startsWith(`${item.href}/`);
            const Icon = item.icon;

            if (item.comingSoon) {
              return (
                <span
                  key={item.href}
                  className="flex shrink-0 cursor-not-allowed items-center gap-1.5 rounded-full px-3 py-1.5 text-xs text-muted-foreground/50"
                >
                  <Icon className="h-3.5 w-3.5" />
                  {item.label}
                </span>
              );
            }

            return (
              <Link
                key={item.href}
                href={item.href}
                className={cn(
                  "flex shrink-0 items-center gap-1.5 rounded-full px-3 py-1.5 text-xs font-medium transition-colors",
                  isActive
                    ? "bg-primary text-primary-foreground"
                    : "bg-muted text-muted-foreground hover:text-foreground"
                )}
              >
                <Icon className="h-3.5 w-3.5" />
                {item.label}
              </Link>
            );
          })}
        </nav>
      </header>

      <div className="flex flex-1">
        <aside className="hidden w-60 shrink-0 border-r border-border/60 bg-muted/20 sm:block">
          <nav className="flex flex-col gap-1 p-4">
            {NAV_ITEMS.map((item) => {
              const isActive = pathname === item.href || pathname.startsWith(`${item.href}/`);
              const Icon = item.icon;

              if (item.comingSoon) {
                return (
                  <span
                    key={item.href}
                    className="flex cursor-not-allowed items-center gap-2.5 rounded-lg px-3 py-2 text-sm text-muted-foreground/50"
                    title="Coming soon"
                  >
                    <Icon className="h-4 w-4" />
                    {item.label}
                    <span className="ml-auto rounded-full bg-muted px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wide">
                      Soon
                    </span>
                  </span>
                );
              }

              return (
                <Link
                  key={item.href}
                  href={item.href}
                  className={cn(
                    "flex items-center gap-2.5 rounded-lg px-3 py-2 text-sm font-medium transition-colors",
                    isActive
                      ? "bg-primary text-primary-foreground"
                      : "text-muted-foreground hover:bg-muted hover:text-foreground"
                  )}
                >
                  <Icon className="h-4 w-4" />
                  {item.label}
                </Link>
              );
            })}
          </nav>
        </aside>

        <main className="flex-1 overflow-x-hidden px-4 py-8 sm:px-8">
          <div className="mx-auto flex max-w-6xl flex-col gap-6">{children}</div>
        </main>
      </div>
    </div>
  );
}
