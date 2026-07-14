"use client";

import { X } from "lucide-react";

interface ImageViewerProps {
  src: string;
  label: string;
  onClose: () => void;
}

/** Full-screen tappable image viewer — opened from a stage thumbnail. */
export function ImageViewer({ src, label, onClose }: ImageViewerProps) {
  return (
    <div className="animate-in fade-in fixed inset-0 z-[60] flex flex-col bg-black duration-150" onClick={onClose}>
      <div className="flex items-center justify-between px-4 pb-2 pt-[max(1rem,env(safe-area-inset-top))]">
        <span className="text-sm font-medium text-white/80">{label}</span>
        <button
          type="button"
          onClick={onClose}
          aria-label="Close"
          className="flex h-9 w-9 items-center justify-center rounded-full bg-white/10 text-white active:bg-white/20"
        >
          <X className="h-4.5 w-4.5" />
        </button>
      </div>
      <div className="flex flex-1 items-center justify-center overflow-auto p-4">
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img src={src} alt={label} className="max-h-full max-w-full rounded-lg object-contain" onClick={(e) => e.stopPropagation()} />
      </div>
    </div>
  );
}
