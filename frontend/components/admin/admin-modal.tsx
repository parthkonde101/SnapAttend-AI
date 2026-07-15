"use client";

import type { ReactNode } from "react";
import { X } from "lucide-react";

import { Button } from "@/components/ui/button";

interface AdminModalProps {
  title: string;
  onClose: () => void;
  children: ReactNode;
  widthClassName?: string;
}

/**
 * Generic modal shell shared by every admin create/edit/reset-password/
 * delete-confirmation dialog. Same visual pattern as the existing
 * `EnlargedPhotoModal` in `session-review-table.tsx` (fixed overlay,
 * rounded panel, stop-propagation on inner click) — this codebase has no
 * shadcn Dialog primitive installed, so rather than adding a new
 * dependency this reuses the one modal pattern already proven in
 * production here.
 */
export function AdminModal({ title, onClose, children, widthClassName = "max-w-md" }: AdminModalProps) {
  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4"
      role="dialog"
      aria-modal="true"
      onClick={onClose}
    >
      <div
        className={`flex max-h-[90vh] w-full ${widthClassName} flex-col gap-4 overflow-y-auto rounded-xl border border-border bg-background p-5 shadow-xl animate-in`}
        onClick={(event) => event.stopPropagation()}
      >
        <div className="flex items-center justify-between gap-4">
          <h3 className="text-base font-semibold">{title}</h3>
          <Button variant="ghost" size="icon" onClick={onClose} aria-label="Close">
            <X className="h-4 w-4" />
          </Button>
        </div>
        {children}
      </div>
    </div>
  );
}
