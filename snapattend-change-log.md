# SnapAttend — Change Log

Covers every change made to the codebase in this working session. **Nothing has been committed to git** — everything below is sitting as uncommitted working-tree changes, by design (you asked for no commits throughout).

---

## 1. Major milestone: Unified Student Roster (student registration removed)

**Goal:** collapse the two-table `Student` / `StudentMaster` model into one. There is no more student self-registration — every account is created by an administrator's Excel import, starts on a default password, and is forced through a mandatory Change Password screen on first login.

### Backend

**Deleted:**
- `app/models/student_master.py` — the `StudentMaster` ORM model
- `app/schemas/student_master.py`
- `app/schemas/registration.py`
- `app/services/admin_student_master_service.py`
- `app/api/v1/endpoints/registration.py` — `/registration/analyze`, `/registration/verify-prn`, `/registration/verify`
- `app/api/v1/endpoints/diagnostics.py` — the registration-diagnostics viewer endpoints
- `app/diagnostics/store.py`, `recorder.py`, `schemas.py`, `images.py` — registration-diagnostics-only support files

**Added:**
- `alembic/versions/0014_unified_student_roster.py` — new migration (see below)
- `app/diagnostics/shared_schemas.py` — pulled `QualityDiagnostics`, `BarcodeDiagnostics`, `PipelineLogEntry`, `StageImageInfo` out of the deleted `schemas.py` into their own module, since the **attendance** diagnostics viewer still needs them

**Rewritten:**
- `app/models/student.py` — `Student` now has `batch`, `password_changed`, `is_active`, `updated_at`. Removed `verified_prn`, `verified_name`, `id_image_path`, `verified_at` (registration artifacts) and `division` (superseded by `batch`).
- `app/schemas/student.py` — removed `StudentRegister`; added `StudentChangePasswordRequest`; `ExcelImportSummary`/`ImportRowError` moved here from the deleted `student_master.py`.
- `app/services/excel_import_service.py` — now upserts directly into `Student`. New PRNs get the default password `test@123` (hashed) + `password_changed=False`; **re-importing an existing PRN never touches its password.** Kept the PRN-parsing bugfix (`normalize_prn`) from the earlier Excel-import milestone unchanged.
- `app/services/admin_student_service.py` — dropped registration-photo/verified-* logic; added `reset_to_default_password()` and `list_for_panel()` (panel roster listing, now reading straight from `Student`).
- `app/api/v1/endpoints/auth.py` — removed `POST /auth/student/register` and the ID-card-photo forgot-password flow (`/forgot-password/verify`, `/forgot-password/reset`). Login endpoints (student/teacher/admin) unchanged.
- `app/api/v1/endpoints/admin.py` — panel Students/Import/Overview endpoints now read from `Student`; added `POST /admin/students/{id}/reset-to-default`; removed the registration-photo endpoint.
- `app/api/v1/endpoints/students.py` — added `POST /students/me/change-password` (the mandatory Change Password screen's backend).
- `app/schemas/admin.py` — `StudentAdminRead`/`StudentUpdateRequest`/`StudentProfile` updated for the new field set, dropped `registration_status`.
- `app/api/deps.py`, `app/core/security.py` — removed the now-unused `password_reset` token role and `get_password_reset_student` dependency.

**Migration `0014_unified_student_roster`:**
1. Adds `batch`, `password_changed`, `is_active`, `updated_at` to `students`.
2. Resets **every** existing student's password to the hashed default (`test@123`) and `password_changed=false` — this is a one-time migration step, not the ongoing Excel-import behavior.
3. Upserts every `student_master` row into `students`, matched by PRN.
4. Drops `student_master` and its indexes.
5. Drops the old `verified_prn`/`verified_name`/`id_image_path`/`verified_at`/`division` columns.

Teachers, courses, panels, sessions, and attendance records are untouched throughout.

### Frontend

**Deleted:**
- `components/registration/registration-wizard.tsx`, `registration-review-form.tsx`, `id-card-capture-view.tsx`
- `components/auth/student-register-form.tsx` (was already dead code), `forgot-password-wizard.tsx`
- `components/diagnostics/diagnostics-history.tsx`, `analysis-sheet.tsx`
- `lib/diagnostics-api.ts`, `hooks/use-diagnostics-enabled.ts`
- `app/dev/diagnostics/page.tsx`, `app/student/register/page.tsx`

**Added:**
- `app/student/change-password/page.tsx` — the mandatory Change Password screen
- `lib/student-api.ts` — `changeOwnPassword()`

**Rewritten:**
- `lib/types.ts` — removed all StudentMaster/registration types; `Student`/`StudentAdminRead` updated for `batch`/`is_active`/`password_changed`
- `hooks/use-auth.ts` — now redirects any student with `password_changed === false` straight to `/student/change-password`, from the shared profile-fetch hook every page uses (so it can't be bypassed by navigating directly)
- `app/student/forgot-password/page.tsx` — replaced the ID-card-photo wizard with a "contact your administrator" message
- `app/admin/panels/[id]/page.tsx` — Students/Import tabs now read/write `Student` directly, "Student Master" wording removed
- `app/admin/students/page.tsx`, `app/admin/students/[id]/page.tsx` — rewritten for the new fields; registration photo/verified-* sections removed
- `components/diagnostics/analysis-sections.tsx` — trimmed to just the three sections the attendance diagnostics viewer still uses
- `components/auth/student-login-form.tsx`, `app/page.tsx` — removed dead "Register" links

### Follow-up request: admin "Reset to Default Password"

Since the self-service forgot-password flow is gone, you asked for an admin-side way to put a student back on `test@123` when they contact an administrator. Added:
- Backend: `POST /admin/students/{id}/reset-to-default`
- Frontend: a "Reset to Default Password" action on both the Students list and a student's profile page, distinct from the existing "set an arbitrary password" action

---

## 2. Bugs found and fixed along the way

- **`backend/alembic/env.py` — reported by you.** Still imported `StudentMaster` in its aggregate model-import list, breaking `alembic upgrade head` with `ImportError: cannot import name 'StudentMaster'`. Fixed, plus a full sweep of the entire `backend/` tree (not just `app/`) for any other stale `StudentMaster`/`student_master`/`verify-prn` references — found and fixed one leftover docstring in `admin.py`.
- **`attendance_verification_service.py`** — identity matching during attendance still checked a student's OCR-extracted PRN against `student.verified_prn` (a field only ever populated by the now-removed registration flow). Removed that fallback; matching is now against `student.prn` alone.
- **`app/page.tsx`** — the marketing homepage had a dead `/student/register` link. Replaced with a line pointing students to their administrator.

---

## 3. Attendance capture UX: fixing the ID-card / classroom-marker blur problem

**The problem:** the capture screen needs one photo containing both the student's ID card (near, needs to be sharp for OCR/barcode) and the classroom display marker (far, needs to be sharp for detection). That's a real depth-of-field conflict — phones can't easily keep both sharp in one shot, and the phone's autofocus/lens-switching behavior was leaving the marker blurred.

**Things tried and reverted** (at your request, back to the exact pre-session baseline):
- Enlarging the ID-card guide box (`grid-cols-[7fr_3fr]` → `[8fr_2fr]`, `max-w-md` → `max-w-lg`)
- Restructuring the camera view to full-bleed (video filling the whole screen, controls as overlays instead of separate flex rows)
- A best-effort "nudge the camera to its widest zoom" attempt in `hooks/use-camera.ts` (only works on some Android phones — iOS has no API for it at all)

All three were fully reverted — `hooks/use-camera.ts` and `app/student/attendance/page.tsx` are confirmed byte-for-byte identical to the last commit for the parts that matter, except for one pre-existing, unrelated 9:16 aspect-ratio fix that predates this session and was deliberately left alone.

**Current, kept changes:**
- **Guide layout reshaped** (`app/student/attendance/page.tsx`): the ID-card guide is now flush against the left edge and stretches the full preview height (instead of a moderate, centered box), on the theory that a bigger required card size forces the student physically closer to the lens. The right side is left open (no box) for the classroom marker/background, giving it more usable frame.
- **Mobile "page zooms while typing" fixed** (`components/ui/input.tsx`): every text input now renders at 16px on mobile (`text-base`, reverting to the original 14px `text-sm` at the `sm:` breakpoint and up). Under 16px is what triggers iOS Safari/Chrome-Android's auto-zoom-on-focus; this removes the trigger without disabling pinch-zoom accessibility. Fixed once at the shared component, so it covers every input in the app.

Both of these are still awaiting your device testing.

---

## 4. Verification performed

- `python -m py_compile` across the entire backend (`app/`, `alembic/`, `scripts/`) — clean at every stage
- `npx tsc --noEmit` across the frontend — clean at every stage
- Manual grep sweeps for stale references after each deletion round

**Known limitation:** I could not run `uvicorn` or `alembic upgrade head` live in this sandbox — the project's `.venv` is a macOS virtualenv (its Python binary symlinks to `/opt/homebrew/...`, which doesn't exist here), and the sandbox has no network access to install a fresh compatible set of packages (`pydantic-core` in particular is a compiled binary with no pure-Python fallback). Static verification (compile + type-check + grep) is as far as I could confirm in-session — worth running both commands yourself for the final green light before relying on this.

---

## 5. Suggested next steps

1. Run `alembic upgrade head` and start `uvicorn` locally to confirm the backend boots clean.
2. Test the attendance capture screen (guide layout + input zoom fix) across a real spread of devices — the guide-layout change is the current working theory for the blur problem, not yet confirmed.
3. Decide whether the "Reset to Default Password" admin action needs any additional safeguards (e.g., confirmation copy, audit trail) before real use.
4. If the reshaped guide layout doesn't hold up, the two more structural options we discussed and didn't implement are still on the table: repositioning instructions (hold the card near the display, not the phone) or splitting capture into two sequential photos.

---

## 6. Major milestone: marker-only attendance capture (ID card removed from attendance)

**Goal:** the blur problem in section 3 above is now moot — you asked to remove ID card capture from attendance entirely. Attendance is now: authenticated login + active session + classroom marker detection + the existing duplicate/device-lock safeguards. No photo-based identity check happens any more; the logged-in student is the identity.

### Backend

**Deleted** (identity-extraction modules, orphaned once the attendance identity stage was removed — the registration pipeline that originally owned them had already been fully orphaned since the Unified Student Roster milestone):
- `app/ai/pipeline.py` (registration pipeline — confirmed zero live callers)
- `app/ai/detector.py`, `app/ai/roi.py`, `app/ai/barcode.py`, `app/ai/ocr.py`

**Rewritten:**
- `app/ai/attendance_pipeline.py` — now just quality gate -> preprocess -> marker detection. Removed ID detection, card-region cropping, barcode decode, and ROI/OCR PRN extraction. `app/ai/display.py` (marker detection itself) and `app/ai/attendance_config.py` (marker tuning) are **untouched** — confirmed `display.py` never depended on any of the deleted identity modules (it calls `pytesseract` directly for the isolated glyph, never through `app/ai/ocr.py`).
- `app/ai/attendance_schemas.py` — removed `IdentityExtraction` and the `identity`/`id_detected` fields from `AttendanceEvidence`.
- `app/services/attendance_verification_service.py` — removed the extracted-PRN-vs-student matching block entirely. Attendance now hinges purely on marker verification for the already-authenticated student: exact OCR match, or the existing display-evidence leniency (a real, panel-shaped classroom display detected even if OCR couldn't read the exact character) — same tolerance as before, just no longer gated behind a second "identity_verified" condition.
- `app/ai/schemas.py` — trimmed to just `QualityCheckResult` (still shared by the quality gate).
- `app/ai/config.py` — trimmed to just the shared `SNAPATTEND_AI_DEBUG` toggle (every PRN/ROI/text-band/OCR tuning constant was registration-only and is gone with `pipeline.py`).
- `app/ai/preprocess.py` — dropped the PRN-region enhancement chain (upscale/denoise/adaptive-threshold/etc.), kept the shared whole-scene `preprocess_for_ocr`.
- `app/ai/quality.py` — the "entire ID must be visible" coverage check is now framed generically ("part of the frame looks cut off") since there's no more ID card to reference; the underlying heuristic (nothing pressed against all four edges) was never card-specific.
- `app/diagnostics/attendance_schemas.py`, `attendance_recorder.py`, `attendance_store.py`, `shared_schemas.py` — removed the identity/barcode diagnostics sections (`AttendanceIdentityDiagnostics`, `BarcodeDiagnostics`, `extracted_prn`, `id_detected`) since there's nothing left for them to record.
- `app/ai/__init__.py` — docstring/exports updated to drop the deleted registration modules.

**Not touched** (per your constraints): teacher session creation, marker generation, marker verification/detection logic (`app/ai/display.py`, `app/ai/attendance_config.py`), the `Attendance` DB table/model, admin features, login system, the teacher review page/export, and `MarkAttendanceResponse`'s `verification_source` API contract (still accepts `"barcode"/"ocr"` for historical records — new records now just record `"none"`, since there's no more identity source).

### Frontend

- `app/student/attendance/page.tsx` — `CameraView` rebuilt: removed the ID-card guide box, its alignment corners, and the "Hold your ID card close…" copy. Replaced with a single centered soft guide and "Point your camera at the classroom marker." `SuccessView` copy updated ("The classroom marker was verified.").
- `components/diagnostics/attendance-analysis-sections.tsx`, `attendance-analysis-sheet.tsx`, `attendance-diagnostics-history.tsx`, `analysis-sections.tsx` — removed the dev-only "ID Verification" and "Barcode" diagnostics sections and the PRN column in the attempt history list.
- `lib/types.ts` — removed `AttendanceIdentityDiagnostics`, `BarcodeDiagnostics`/`BarcodeDiagnosticsStatus`, and the `identity`/`barcode`/`id_detected`/`extracted_prn` fields from the attendance diagnostics types, to stay in sync with the backend contract above.

### Verification performed

- `python -m py_compile` across the entire backend — clean.
- `npx tsc --noEmit` across the frontend — clean.
- Full grep sweep across `backend/` and `frontend/` for every deleted symbol (`detect_id_card`, `decode_barcode`, `IdentityExtraction`, `BarcodeDiagnostics`, etc.) — zero remaining live references, only explanatory comments describing what was removed.
- Confirmed via `git diff --stat` that teacher review/session/admin/login files are untouched by this milestone.
- Same sandbox limitation as before: could not run `uvicorn`/`alembic upgrade head` live — static verification only.

Nothing in this milestone has been committed either — same as everything above.
