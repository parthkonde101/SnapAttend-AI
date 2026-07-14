"""Configuration surface for the registration intelligence pipeline.

Every constant here is a generic, institution-agnostic default informed by
common portrait student/staff ID card conventions (a printed identifier
somewhere near a barcode, roughly numeric, roughly this many digits) — not
by any single university's exact layout. None of them are pixel
coordinates: regions are expressed as fractions of the card/frame, or
relative to a barcode's own detected size, so they hold up across camera
framing and card proportions without code changes.

To tune for a new institution, override the relevant environment variable
(or, if you prefer, edit the constants below directly) — nothing in
`roi.py`, `ocr.py`, or `pipeline.py` needs to change.

A note on where these environment variables can live: `app.core.config.Settings`
(used by the rest of the backend) reads `backend/.env` via pydantic-settings,
which parses that file internally and does NOT copy its values into the
real process environment (`os.environ`) — so a raw `os.environ.get(...)`
call elsewhere in the codebase never sees a variable that only exists in
`.env`. This module reads `os.environ` directly (see `_env_*` below), so
it calls `load_dotenv()` itself first — that call *does* copy `.env` into
`os.environ`, which is what makes e.g. `SNAPATTEND_AI_DEBUG=1` set in
`backend/.env` actually take effect here. Real shell-exported environment
variables always take priority over `.env` either way.
"""
from __future__ import annotations

import os

from dotenv import load_dotenv

# Idempotent, and a no-op if no .env file is found — safe to call
# unconditionally at import time. `override=False` (the default) means an
# already-exported real environment variable always wins over `.env`.
load_dotenv()


def _env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


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


# --- PRN validation ----------------------------------------------------------
# Most PRN / roll-number / enrollment-number schemes are numeric (or
# numeric-with-a-few-letters) and fall in this length range. Widen/narrow
# per institution without touching any extraction logic.
PRN_MIN_LENGTH = _env_int("SNAPATTEND_PRN_MIN_LENGTH", 6)
PRN_MAX_LENGTH = _env_int("SNAPATTEND_PRN_MAX_LENGTH", 15)

# --- ROI: barcode-relative PRN search ----------------------------------------
# When a barcode is located, the PRN is frequently printed immediately
# above or below it — these factors describe *how far* to search relative
# to the barcode's own size, never an absolute pixel offset.
PRN_BAND_HEIGHT_FACTOR = _env_float("SNAPATTEND_PRN_BAND_HEIGHT_FACTOR", 1.4)
PRN_BAND_HORIZONTAL_PADDING = _env_float("SNAPATTEND_PRN_BAND_H_PADDING", 0.15)

# --- ROI: fractional fallback regions ----------------------------------------
# Used only when no barcode was found at all. Each is a (left, top, right,
# bottom) box expressed as a fraction of the detected card bounds (or the
# full frame, if no card bounds could be estimated) — never absolute
# pixels. Ordered by priority (tried first to last). These are coarse,
# generic guesses about where a printed ID number tends to sit on a
# portrait ID card (below a name/photo block, above/near a barcode);
# override via SNAPATTEND_ROI_FALLBACK_REGIONS ("l,t,r,b;l,t,r,b;...") to
# tune for a specific institution's layout without a code change.
_DEFAULT_ROI_FALLBACK_REGIONS: tuple[tuple[float, float, float, float], ...] = (
    (0.04, 0.55, 0.96, 0.78),  # lower-middle band — common ID-number placement
    (0.04, 0.32, 0.96, 0.55),  # middle band — under a name/photo layout
    (0.04, 0.78, 0.96, 0.98),  # bottom strip — near a bottom-aligned barcode
)


def _parse_roi_regions(raw: str | None) -> tuple[tuple[float, float, float, float], ...]:
    if not raw:
        return _DEFAULT_ROI_FALLBACK_REGIONS
    try:
        regions = []
        for chunk in raw.split(";"):
            if not chunk.strip():
                continue
            left, top, right, bottom = (float(part) for part in chunk.split(","))
            regions.append((left, top, right, bottom))
        return tuple(regions) if regions else _DEFAULT_ROI_FALLBACK_REGIONS
    except (TypeError, ValueError):
        return _DEFAULT_ROI_FALLBACK_REGIONS


DEFAULT_ROI_FALLBACK_REGIONS = _parse_roi_regions(os.environ.get("SNAPATTEND_ROI_FALLBACK_REGIONS"))

# --- ROI: structural text-band detection --------------------------------------
# Locates candidate PRN regions from the image's own structure (rows of
# printed text, separated by whitespace/ruled-line gaps) instead of a
# blind fractional guess — tried before the fractional fallback above,
# after barcode-relative regions. See `app/ai/detector.detect_text_bands`.
# A row counts as "text" once this fraction of its pixels are strong
# edges; tune down for faint print, up for noisy/textured card backgrounds.
TEXT_BAND_ROW_DENSITY_THRESHOLD = _env_float("SNAPATTEND_TEXT_BAND_DENSITY", 0.03)
# Rows are smoothed over this many neighbors first so a single noisy row
# doesn't fracture one line of text into several bands.
TEXT_BAND_SMOOTHING_WINDOW = _env_int("SNAPATTEND_TEXT_BAND_SMOOTHING", 5)
# Two text bands separated by a gap no taller than this (in rows) are
# merged into one — keeps a printed horizontal rule/separator line from
# splitting a single field's ascenders/descenders into two bands.
TEXT_BAND_MERGE_GAP_ROWS = _env_int("SNAPATTEND_TEXT_BAND_MERGE_GAP", 10)
# Bands shorter than this fraction of the card's height are discarded as
# noise (this is also what filters out thin ruled separator lines
# themselves — they show up as a band far below this height).
TEXT_BAND_MIN_HEIGHT_RATIO = _env_float("SNAPATTEND_TEXT_BAND_MIN_HEIGHT", 0.015)
# Bands taller than this fraction of the card's height are discarded too
# (almost certainly a mis-merged region spanning multiple fields, not one
# isolated line — not useful as a tight PRN crop).
TEXT_BAND_MAX_HEIGHT_RATIO = _env_float("SNAPATTEND_TEXT_BAND_MAX_HEIGHT", 0.25)
# Extra vertical room added above/below each detected band before
# cropping, as a fraction of the band's own height — detected bands are
# tight around ink, and OCR does better with a little breathing room.
TEXT_BAND_VERTICAL_PADDING = _env_float("SNAPATTEND_TEXT_BAND_V_PADDING", 0.5)
# Horizontal inset from the card's left/right edges for every band crop,
# as a fraction of card width — keeps a card's printed border out of frame.
TEXT_BAND_HORIZONTAL_MARGIN = _env_float("SNAPATTEND_TEXT_BAND_H_MARGIN", 0.03)
# Upper bound on how many structural candidates are tried per capture —
# bounds OCR cost on a card with many short text lines.
TEXT_BAND_MAX_CANDIDATES = _env_int("SNAPATTEND_TEXT_BAND_MAX_CANDIDATES", 6)

# --- OCR tuning ----------------------------------------------------------------
# Tesseract page-segmentation mode used for digit-priority passes over a
# small cropped region. 6 = "assume a uniform block of text", forgiving of
# a label sharing the crop with the number. Try 7 ("single text line") if
# an institution's PRN crops are consistently tight single lines.
PRN_OCR_PSM = _env_int("SNAPATTEND_PRN_OCR_PSM", 6)
PRN_UPSCALE_FACTOR = _env_float("SNAPATTEND_PRN_UPSCALE_FACTOR", 3.0)

# --- Debug ---------------------------------------------------------------------
# Development-only: persist every intermediate image (preprocessed frame,
# each PRN-region candidate crop, its enhanced version) to disk for tuning
# against real ID cards. Off by default; never required in production.
DEBUG_SAVE_INTERMEDIATES = _env_bool("SNAPATTEND_AI_DEBUG", False)
DEBUG_OUTPUT_DIR = os.environ.get("SNAPATTEND_AI_DEBUG_DIR", "uploads/registration-debug")
