"""Configuration surface for the Attendance Verification Engine (V1).

Kept entirely separate from `app/ai/config.py` (which is scoped to the
registration intelligence pipeline and is not touched by this milestone) —
attendance is a new subsystem with its own tunables, even though it reuses
most of the underlying `app.ai` machinery. Same institution-agnostic
philosophy: every constant is a generic default, overridable via
environment variable, never a hardcoded assumption about one classroom's
setup.
"""
from __future__ import annotations

import os

from dotenv import load_dotenv

# Idempotent — safe to call again even though app/ai/config.py already
# calls this at import time. See that module's docstring for why this is
# necessary at all (pydantic-settings' env_file loading doesn't populate
# the real os.environ, which is what a raw os.environ.get(...) call here
# needs).
load_dotenv()


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


# --- Attendance display marker detection -------------------------------------
# The marker is always exactly one character from this alphabet (see
# app/services/attendance_session_service.py, which generates it) — never a
# per-institution assumption, just the allowed character set from the spec.
MARKER_ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"

# Tesseract page-segmentation mode for a *cropped* marker region (see
# MARKER_REGION_BOX below — this is never run against the whole,
# multi-object scene). 6 = "assume a uniform block of text": measured
# directly against synthetic scenes while building this module, it reads
# an isolated large glyph correctly even with generous surrounding
# whitespace, at any size from ~60px to full-crop-filling. Whole-scene,
# automatic-segmentation modes (3/4/11/12) were tried first and rejected —
# they reliably fail to detect a single very large glyph at all once the
# frame also contains normal-sized text (the ID card), because Tesseract's
# layout analysis assumes roughly-uniform text scale within a segmentation
# pass. Scoping to a region first, then running a uniform-block pass just
# on that region, is what actually works.
MARKER_OCR_PSM = _env_int("SNAPATTEND_MARKER_OCR_PSM", 6)
MARKER_OCR_FALLBACK_PSM = _env_int("SNAPATTEND_MARKER_OCR_FALLBACK_PSM", 11)

# Tesseract's own per-token confidence (0-100 scale) below which a
# character token is discarded as noise before the largest-bounding-box
# selection ever runs.
MARKER_MIN_CONFIDENCE = _env_float("SNAPATTEND_MARKER_MIN_CONFIDENCE", 35.0)

# PSM used for the final OCR pass, which (unlike MARKER_OCR_PSM above) runs
# against a *tight crop of a single already-geometrically-isolated glyph*,
# never a region that could contain anything else. 10 = "treat the image as
# a single character" — the correct mode once geometry has already done the
# isolation work. 8 ("single word") is tried once as a fallback within the
# same crop if PSM 10 finds nothing, since some glyph shapes (e.g. digits
# with serifs) occasionally tokenize better that way.
MARKER_OCR_GLYPH_PSM = _env_int("SNAPATTEND_MARKER_OCR_GLYPH_PSM", 10)
MARKER_OCR_GLYPH_FALLBACK_PSM = _env_int("SNAPATTEND_MARKER_OCR_GLYPH_FALLBACK_PSM", 8)

# --- Geometric display/glyph localization -------------------------------------
# These are *physical-plausibility* filters applied before OCR ever runs —
# not OCR confidence/threshold tuning. They encode the structural
# assumptions the marker is guaranteed to satisfy (see
# app/ai/display.py's module docstring and the teacher session display,
# which now enforces the same geometry from the presentation side): the
# marker sits on a large, solid dark display panel, and is itself
# dramatically larger than any other text in the scene.

# An image is analyzed for display-panel / glyph geometry at a downscaled
# resolution (connected-component labeling cost scales with pixel count;
# this keeps it fast) — bounding boxes are then mapped back to full
# resolution before the final glyph crop is cut out for OCR, so OCR itself
# never runs on a downscaled image.
MARKER_ANALYSIS_MAX_DIMENSION = _env_int("SNAPATTEND_MARKER_ANALYSIS_MAX_DIMENSION", 360)

# A dark connected-component blob must cover at least this fraction of the
# search region's area to be considered a candidate "display panel" at all
# — filters out shadows, dark clothing, hair, etc., which are dark but tiny
# relative to an entire projected/monitor display.
MARKER_MIN_DISPLAY_AREA_RATIO = _env_float("SNAPATTEND_MARKER_MIN_DISPLAY_AREA_RATIO", 0.05)
# How "filled"/rectangular a dark blob's bounding box must be
# (blob_pixel_count / bbox_area) to count as a display panel rather than an
# irregular dark region (e.g. a shadow along one edge of the frame).
MARKER_MIN_DISPLAY_FILL_RATIO = _env_float("SNAPATTEND_MARKER_MIN_DISPLAY_FILL_RATIO", 0.4)
# Plausible width/height range for a display panel's bounding box —
# generous, since framing/perspective/aspect varies by device and distance.
MARKER_DISPLAY_ASPECT_MIN = _env_float("SNAPATTEND_MARKER_DISPLAY_ASPECT_MIN", 0.2)
MARKER_DISPLAY_ASPECT_MAX = _env_float("SNAPATTEND_MARKER_DISPLAY_ASPECT_MAX", 4.5)
# Otsu's threshold only guarantees a candidate is *relatively* darker than
# the rest of its search region — not that it's actually dark in absolute
# terms. The spec guarantees a genuinely dark panel (0-255 grayscale, a
# real black/near-black background), so an absolute brightness ceiling is
# also required: this rejects the failure mode where, in a scene with no
# real display panel at all, Otsu still finds *some* relatively-darker
# region (e.g. beige wall vs. a white ID card) and mistakes it for one.
MARKER_MAX_DISPLAY_MEAN_BRIGHTNESS = _env_float("SNAPATTEND_MARKER_MAX_DISPLAY_MEAN_BRIGHTNESS", 100.0)

# --- Bordered-frame refinement ---------------------------------------------------
# The teacher session display renders the marker inside a thick, solid
# white border specifically so it can be found here: within a coarse dark
# region (which, in real captures, is often the *entire* screen — timer,
# status icons, and sometimes the physical keyboard included, not just the
# marker frame), this looks for that border as a short, bright band near
# each edge and — if found — narrows the display region down to just the
# border's interior. This directly targets the confound real captures
# exposed: a glyph search scoped to the whole screen has to compete with
# the timer/icons/badge (and even the ID card's own edge, if it intrudes
# into the search region) for "largest bright thing," none of which
# geometry alone can fully disambiguate from inside an oversized region.
# Safe by construction: if no clear border is found (e.g. an older/plainer
# display, or a synthetic scene with no border at all), this step finds
# nothing and the full coarse dark region is used unchanged, exactly as
# before this refinement existed.
#
# NOTE: unlike every other constant in this file, this one has not yet
# been validated against a real capture — the real captures available at
# the time this was written all predate the frame border being made this
# prominent (it was previously a faint 15%-opacity tint, confirmed too
# subtle to reliably survive camera/JPEG capture). It should be
# re-validated against a fresh real capture before being trusted.
MARKER_FRAME_BORDER_MIN_BRIGHTNESS = _env_float("SNAPATTEND_MARKER_FRAME_BORDER_MIN_BRIGHTNESS", 120.0)
# How thick the border stroke is allowed to be (as a fraction of the
# coarse region's own height/width) before a bright edge band is
# considered "not a border" (e.g. because it's actually the glyph itself,
# or a noise chain, starting right at the region's boundary).
MARKER_FRAME_BORDER_MAX_THICKNESS_RATIO = _env_float("SNAPATTEND_MARKER_FRAME_BORDER_MAX_THICKNESS_RATIO", 0.1)

# A bright connected-component blob *inside* the accepted display region
# must be at least this fraction of the display region's own height to be
# physically plausible as the displayed marker — this is the direct fix for
# "detector returns tiny digits": a 6x10px or 17x20px token inside a
# display region that is, say, 300px tall is nowhere near this floor and is
# now rejected before OCR ever sees it, rather than being accepted because
# it happened to be the largest *OCR token* Tesseract produced.
MARKER_MIN_GLYPH_HEIGHT_RATIO = _env_float("SNAPATTEND_MARKER_MIN_GLYPH_HEIGHT_RATIO", 0.2)
# A real glyph is 60-70% of the display panel's height by spec (see the
# teacher session display), never the panel's *entire* height — a bright
# candidate spanning nearly all of it is far more likely the panel's own
# antialiased/compression-noise border ring than the character itself.
MARKER_MAX_GLYPH_HEIGHT_RATIO = _env_float("SNAPATTEND_MARKER_MAX_GLYPH_HEIGHT_RATIO", 0.92)
# Absolute pixel-area floor (post-downscale), a cheap extra guard against
# single-pixel noise blobs independent of the display region's own size.
MARKER_MIN_GLYPH_AREA_PX = _env_int("SNAPATTEND_MARKER_MIN_GLYPH_AREA_PX", 40)
# Plausible width/height range for one uppercase A-Z/0-9 glyph in a typical
# sans-serif presentation font (a "1" is very narrow, a "W" is close to
# square) — wide enough to admit any single character, tight enough to
# reject multi-character text fragments or line-like artifacts.
MARKER_GLYPH_ASPECT_MIN = _env_float("SNAPATTEND_MARKER_GLYPH_ASPECT_MIN", 0.12)
MARKER_GLYPH_ASPECT_MAX = _env_float("SNAPATTEND_MARKER_GLYPH_ASPECT_MAX", 1.4)
# A rendered character always has *some* internal edge structure (stroke
# boundaries, antialiasing) even once cropped tight to its own bright blob.
# A candidate with essentially none of that (near-0 edge density) is more
# likely a flat lighting artifact — a phone-flash glare spot or reflection
# hotspot — than an actual glyph, so it's rejected here before OCR.
MARKER_MIN_GLYPH_EDGE_DENSITY = _env_float("SNAPATTEND_MARKER_MIN_GLYPH_EDGE_DENSITY", 0.015)

# Brightness percentile (within the display region's own grayscale
# distribution) used as the glyph mask threshold, instead of Otsu.
# Measured against real captures, not assumed: Otsu balances between-class
# variance over the *whole* display region, and when that region is large
# and heterogeneous (a full screen including a countdown timer, status
# icons, and — since display-region detection isn't scoped tighter than
# that in this design — sometimes the physical keyboard/trackpad below
# it), Otsu's threshold sits low enough that ordinary sensor/JPEG noise
# scattered across all of that forms one continuously-connected bright
# region spanning far more than the marker glyph, even with zero extra
# dilation. A fixed high percentile isolates only the genuinely brightest
# pixels — the marker is rendered bright white specifically so it dominates
# the display's brightness distribution — which breaks that spurious
# connectivity in every real capture tested. (Fill ratio was tried as a
# discriminator instead and rejected: a real glyph's own hollow/thin-stroke
# shape gives it a similarly low fill ratio to a noise-bridged chain, so it
# does not reliably tell them apart.)
MARKER_GLYPH_BRIGHTNESS_PERCENTILE = _env_float("SNAPATTEND_MARKER_GLYPH_BRIGHTNESS_PERCENTILE", 95.0)
# Extra room added around the tightly-detected glyph bounding box before
# cropping, as a fraction of the box's own size — just enough to avoid
# clipping antialiased stroke edges. Kept small deliberately: the
# normalization stage below (MARKER_GLYPH_NORMALIZE_*) is what adds the
# *generous* padding actually used for OCR; this one only protects the crop
# itself.
MARKER_GLYPH_CROP_PADDING_RATIO = _env_float("SNAPATTEND_MARKER_GLYPH_CROP_PADDING_RATIO", 0.1)

# --- Glyph fragment merging ------------------------------------------------------
# Real camera captures of a projected/monitor display are not the clean,
# perfectly-solid glyph fill that a rendered screenshot would produce:
# sensor noise, JPEG compression blocking, and moire from photographing a
# screen all commonly break what should be one solid character into
# several disconnected bright connected components (confirmed against real
# captures, not assumed — see app/ai/display.py's module docstring).
# Selecting only the single largest raw component as "the glyph" (the
# previous design) therefore often selected just one fragment of the
# character — small height-ratio, oddly narrow aspect ratio, and OCR
# reading nothing usable from a partial glyph, exactly the reported
# symptom. Two raw components are merged into one candidate glyph group if
# the gap between their bounding boxes is within this fraction of the
# display region's own (downscaled-analysis) height — deliberately
# generous enough to bridge a compression-noise gap between two strokes of
# the same character, without being so large it bridges genuinely separate
# on-screen elements (see MARKER_MAX_GLYPH_HEIGHT_RATIO, which still
# rejects a group if merging went too far and it now spans almost the
# entire panel).
MARKER_GLYPH_MERGE_GAP_RATIO = _env_float("SNAPATTEND_MARKER_GLYPH_MERGE_GAP_RATIO", 0.05)

# --- Glyph normalization (the image actually handed to OCR) ----------------------
# The merged glyph crop is resized to this canonical height (aspect ratio
# preserved) before OCR, so Tesseract always sees the character at a
# consistent, OCR-friendly scale regardless of how close/far the camera
# was — then padded generously on a plain dark canvas (matching the
# guaranteed-dark display background) so the character isn't touching the
# image edges. This normalized image — never a raw per-fragment crop — is
# both what OCR runs against and what gets saved to diagnostics so it can
# be inspected directly.
MARKER_GLYPH_NORMALIZE_HEIGHT = _env_int("SNAPATTEND_MARKER_GLYPH_NORMALIZE_HEIGHT", 240)
MARKER_GLYPH_NORMALIZE_PADDING_RATIO = _env_float("SNAPATTEND_MARKER_GLYPH_NORMALIZE_PADDING_RATIO", 0.35)

# --- Classroom-display evidence tiers (verification philosophy) ------------------
# The Attendance Verification Engine's job used to collapse two different
# questions into one boolean (`DisplayMarkerResult.detected`): "was a
# classroom display actually photographed" and "did OCR read its character
# correctly." Those are not the same claim — geometry alone (a dark
# panel-shaped region containing a bright, single-character-shaped region)
# is real evidence a display was captured, independent of whether OCR then
# manages to read it under blur/tilt/distance. This block gives that
# geometric evidence a score, in the same tiers `app.ai.display` already
# computes on the way to OCR, so `app.services.attendance_verification_service`
# can weigh "the display was clearly detected" on its own, separately from
# "the exact character matched" — see that module's decision logic for how
# these tiers are actually used. Deliberately three fixed reference points,
# not a continuous score: each corresponds to a real, distinct stage the
# pipeline already passes through, not a trained/calibrated probability.
MARKER_DISPLAY_CONFIDENCE_NONE = 0.0
# A dark, panel-shaped region was found, but no bright region inside it was
# plausible as a single character. Still passed every geometric
# plausibility filter a candidate needs to be accepted as a display panel
# at all (MARKER_MIN_DISPLAY_AREA_RATIO/FILL_RATIO/ASPECT_MIN/MAX and
# MARKER_MAX_DISPLAY_MEAN_BRIGHTNESS) — not "any dark pixel", a
# specifically panel-shaped, panel-sized, sufficiently-dark region. As of
# the production classroom milestone this is treated as sufficient
# classroom-display evidence on its own (`display_detected` is set true at
# this tier — see app.ai.display.detect_attendance_marker's final return):
# students are expected to focus their camera on the ID card, so the
# projected marker itself will often be too blurred, partial, tilted, or
# distorted to isolate a glyph from at all, and that is not, by itself,
# reason to doubt a real display was photographed. This is only ever
# combined with an independently-confirmed identity match
# (app.services.attendance_verification_service) — it is never sufficient
# on its own.
MARKER_DISPLAY_CONFIDENCE_PANEL_ONLY = _env_float("SNAPATTEND_MARKER_DISPLAY_CONFIDENCE_PANEL_ONLY", 0.3)
# A glyph-shaped bright region was geometrically isolated, normalized, and
# handed to OCR — regardless of what OCR then did with it. Stronger
# evidence than panel-only, but no longer the acceptance floor itself
# (see MARKER_DISPLAY_CONFIDENCE_PANEL_ONLY above) — isolating a genuine
# single-character-shaped bright region inside a dark panel is not
# something a random background object produces by chance, so this is
# treated as real (if imperfect) proof a classroom display was captured.
MARKER_DISPLAY_CONFIDENCE_GLYPH_ISOLATED = _env_float("SNAPATTEND_MARKER_DISPLAY_CONFIDENCE_GLYPH_ISOLATED", 0.6)
# OCR read the isolated glyph and produced a confident, alphabet-valid
# character. Full confidence — this is the strongest evidence tier,
# independent of whether that character then matches the session's marker
# (the *comparison* against the session marker is verification's job, not
# detection's).
MARKER_DISPLAY_CONFIDENCE_OCR_READ = _env_float("SNAPATTEND_MARKER_DISPLAY_CONFIDENCE_OCR_READ", 1.0)


def _parse_box(raw: str | None, default: tuple[float, float, float, float]) -> tuple[float, float, float, float]:
    if not raw:
        return default
    try:
        left, top, right, bottom = (float(part) for part in raw.split(","))
        return (left, top, right, bottom)
    except (TypeError, ValueError):
        return default


# --- Attendance scene composition ---------------------------------------------
# The student capture UI (see frontend `student/attendance/page.tsx`) guides
# the student to frame their ID card on the left and the classroom display
# on the right — these fractional regions (of the *full* captured frame,
# left/top/right/bottom as 0-1) encode that same convention on the backend
# side, so each object is analyzed in isolation instead of the whole,
# multi-object scene being handed to one OCR pass (see MARKER_OCR_PSM
# above for why that doesn't work). Approximate by design — exact
# display-geometry/distance-aware localization is explicitly out of scope
# for V1 (a future independent module, per the spec) and would replace
# these constants without changing any caller.
CARD_REGION_BOX = _parse_box(os.environ.get("SNAPATTEND_ATTENDANCE_CARD_REGION"), (0.0, 0.03, 0.64, 0.97))
MARKER_REGION_BOX = _parse_box(os.environ.get("SNAPATTEND_ATTENDANCE_MARKER_REGION"), (0.60, 0.03, 1.0, 0.97))
# If nothing is found in MARKER_REGION_BOX (e.g. imprecise framing), retry
# once against this wider region before giving up.
MARKER_REGION_FALLBACK_BOX = _parse_box(
    os.environ.get("SNAPATTEND_ATTENDANCE_MARKER_REGION_FALLBACK"), (0.3, 0.0, 1.0, 1.0)
)

# --- Debug -----------------------------------------------------------------------
# Development-only: persist every intermediate image (full scene, card
# region crop, every marker region/PSM scan's exact crop) to disk for
# inspecting exactly what the Attendance Verification Engine saw on a given
# attempt. Gated by the *same* `SNAPATTEND_AI_DEBUG` switch registration
# already uses (see `app/ai/config.DEBUG_SAVE_INTERMEDIATES`, imported —
# not redefined — by `app/ai/attendance_pipeline.py`), so there is one dev
# toggle for all AI debug behavior. Only the output directory is
# attendance-specific, kept fully separate from registration's own debug
# folder.
ATTENDANCE_DEBUG_OUTPUT_DIR = os.environ.get("SNAPATTEND_ATTENDANCE_DEBUG_DIR", "uploads/attendance-debug")

# --- Identity verification -----------------------------------------------------
# Whether extracted-PRN-to-student matching is case sensitive. PRNs in this
# system are alphanumeric identifiers, not free text, so a case-insensitive
# compare (the default) is more forgiving of OCR case noise without
# weakening the match — it's still an exact match on every character.
PRN_MATCH_CASE_SENSITIVE = os.environ.get("SNAPATTEND_PRN_MATCH_CASE_SENSITIVE", "0").strip().lower() in (
    "1",
    "true",
    "yes",
    "on",
)
