"use client";

import { ChevronDown } from "lucide-react";
import { useState, type ReactNode } from "react";

interface ExpandableCardProps {
  title: string;
  subtitle?: string;
  statusDot?: "green" | "red" | "gray" | "amber";
  defaultOpen?: boolean;
  children: ReactNode;
}

const DOT_COLOR: Record<NonNullable<ExpandableCardProps["statusDot"]>, string> = {
  green: "bg-emerald-500",
  red: "bg-red-500",
  amber: "bg-amber-500",
  gray: "bg-white/30",
};

/**
 * Collapsible section used throughout the diagnostics analysis sheet.
 * Animates height via the CSS grid `0fr -> 1fr` trick (no JS height
 * measurement needed, works smoothly on iOS Safari).
 */
export function ExpandableCard({ title, subtitle, statusDot, defaultOpen = false, children }: ExpandableCardProps) {
  const [open, setOpen] = useState(defaultOpen);

  return (
    <div className="overflow-hidden rounded-2xl border border-white/10 bg-white/[0.03]">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center justify-between gap-3 px-4 py-3.5 text-left active:bg-white/5"
      >
        <span className="flex items-center gap-2.5 min-w-0">
          {statusDot && <span className={`h-2 w-2 shrink-0 rounded-full ${DOT_COLOR[statusDot]}`} />}
          <span className="flex min-w-0 flex-col">
            <span className="text-[15px] font-semibold text-white">{title}</span>
            {subtitle && <span className="truncate text-xs text-white/50">{subtitle}</span>}
          </span>
        </span>
        <ChevronDown
          className={`h-4 w-4 shrink-0 text-white/40 transition-transform duration-300 ${open ? "rotate-180" : ""}`}
        />
      </button>
      <div
        className="grid transition-[grid-template-rows] duration-300 ease-out"
        style={{ gridTemplateRows: open ? "1fr" : "0fr" }}
      >
        <div className="overflow-hidden">
          <div className="border-t border-white/10 px-4 py-3.5">{children}</div>
        </div>
      </div>
    </div>
  );
}

interface DiagnosticRowProps {
  label: string;
  value: ReactNode;
  mono?: boolean;
  valueClassName?: string;
}

/** One label/value line, used inside every section's expanded body. */
export function DiagnosticRow({ label, value, mono, valueClassName }: DiagnosticRowProps) {
  return (
    <div className="flex items-baseline justify-between gap-3 py-1.5 text-sm">
      <span className="text-white/50">{label}</span>
      <span className={`text-right text-white ${mono ? "font-mono tabular-nums" : ""} ${valueClassName ?? ""}`}>
        {value}
      </span>
    </div>
  );
}

interface StatusPillProps {
  ok: boolean | null;
  trueLabel?: string;
  falseLabel?: string;
  neutralLabel?: string;
}

/** Small colored pill for boolean-ish statuses (Yes/No/Unknown). */
export function StatusPill({ ok, trueLabel = "Yes", falseLabel = "No", neutralLabel = "—" }: StatusPillProps) {
  if (ok === null) {
    return <span className="rounded-full bg-white/10 px-2 py-0.5 text-xs text-white/60">{neutralLabel}</span>;
  }
  return (
    <span
      className={`rounded-full px-2 py-0.5 text-xs font-medium ${
        ok ? "bg-emerald-500/15 text-emerald-400" : "bg-red-500/15 text-red-400"
      }`}
    >
      {ok ? trueLabel : falseLabel}
    </span>
  );
}
