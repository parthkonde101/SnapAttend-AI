"use client";

import { AlertCircle, BadgeCheck, RotateCcw, ScanLine } from "lucide-react";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

interface RegistrationReviewFormProps {
  prn: string;
  studentName: string;
  onPrnChange: (value: string) => void;
  onStudentNameChange: (value: string) => void;
  warnings: string[];
  barcode: string | null;
  onRetake: () => void;
  /** Advances to password creation — nothing is persisted by this step
   * itself (see registration-wizard.tsx: the account is only created once
   * a password has also been collected, per Milestone 6B's required
   * order). */
  onContinue: () => void;
}

/**
 * Shown after a registration photo passes the quality gate and the AI
 * pipeline has run. Pre-filled with whatever OCR extracted (which may be
 * empty for either field) — the student reviews and edits before
 * continuing on to create a password. Nothing is saved until the whole
 * wizard's final "Create Account" step.
 */
export function RegistrationReviewForm({
  prn,
  studentName,
  onPrnChange,
  onStudentNameChange,
  warnings,
  barcode,
  onRetake,
  onContinue,
}: RegistrationReviewFormProps) {
  const canContinue = prn.trim().length > 0 && studentName.trim().length > 0;

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2 text-sm text-muted-foreground">
        <BadgeCheck className="h-4 w-4 text-emerald-500" />
        Review the details we found on your ID and correct anything that&apos;s wrong.
      </div>

      {warnings.length > 0 && (
        <Alert>
          <AlertCircle />
          <AlertDescription>
            <ul className="list-inside list-disc space-y-0.5">
              {warnings.map((warning) => (
                <li key={warning}>{warning}</li>
              ))}
            </ul>
          </AlertDescription>
        </Alert>
      )}

      <div className="space-y-2">
        <Label htmlFor="reviewPrn">PRN</Label>
        <Input
          id="reviewPrn"
          value={prn}
          onChange={(e) => onPrnChange(e.target.value)}
          placeholder="Enter your PRN"
          required
        />
      </div>

      <div className="space-y-2">
        <Label htmlFor="reviewName">Full name</Label>
        <Input
          id="reviewName"
          value={studentName}
          onChange={(e) => onStudentNameChange(e.target.value)}
          placeholder="Enter your full name"
          required
        />
      </div>

      {barcode && (
        <div className="flex items-center gap-2 rounded-md border border-border bg-muted/40 px-3 py-2 text-xs text-muted-foreground">
          <ScanLine className="h-3.5 w-3.5" />
          Barcode detected: <span className="font-mono">{barcode}</span>
        </div>
      )}

      <div className="flex gap-3 pt-2">
        <Button variant="secondary" className="flex-1 gap-2" onClick={onRetake}>
          <RotateCcw className="h-4 w-4" />
          Retake Photo
        </Button>
        <Button className="flex-1" onClick={onContinue} disabled={!canContinue}>
          Continue
        </Button>
      </div>
    </div>
  );
}
