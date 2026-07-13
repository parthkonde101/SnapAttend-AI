import Link from "next/link";
import { Camera } from "lucide-react";

import { ThemeToggle } from "@/components/theme-toggle";

export function Navbar() {
  return (
    <header className="sticky top-0 z-40 w-full border-b border-border/60 bg-background/80 backdrop-blur supports-[backdrop-filter]:bg-background/60">
      <div className="container flex h-16 items-center justify-between">
        <Link href="/" className="flex items-center gap-2 font-semibold tracking-tight">
          <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary text-primary-foreground">
            <Camera className="h-4 w-4" />
          </span>
          <span>SnapAttend AI</span>
        </Link>
        <nav className="flex items-center gap-1">
          <ThemeToggle />
        </nav>
      </div>
    </header>
  );
}
