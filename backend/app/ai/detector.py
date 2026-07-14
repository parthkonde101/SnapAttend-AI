"""Lightweight heuristic ID-card presence detector.

Not a trained model — a cheap classical-CV heuristic (edge density) that
answers "does this frame plausibly contain a card with printed text and
edges" well enough to gate/flag OCR. Swappable for a real detector later
without touching any other module — `pipeline.py` only depends on the
`DetectionResult` shape returned here.
"""
from __future__ import annotations

import numpy as np
from PIL import Image

from app.ai import config
from app.ai.schemas import DetectionResult

EDGE_DENSITY_THRESHOLD = 0.04
_GRADIENT_MAGNITUDE_THRESHOLD = 25.0

Box = tuple[int, int, int, int]


def detect_id_card(image: Image.Image) -> DetectionResult:
    """Estimate whether the frame contains a card-like object via edge density."""
    gray = np.asarray(image.convert("L"), dtype=np.float32)

    dx = np.abs(np.diff(gray, axis=1))[:-1, :]
    dy = np.abs(np.diff(gray, axis=0))[:, :-1]
    gradient_magnitude = dx + dy

    edge_density = float((gradient_magnitude > _GRADIENT_MAGNITUDE_THRESHOLD).mean())
    confidence = min(1.0, edge_density / (EDGE_DENSITY_THRESHOLD * 3))

    return DetectionResult(
        id_detected=edge_density >= EDGE_DENSITY_THRESHOLD,
        confidence=round(confidence, 3),
    )


def estimate_card_bbox(image: Image.Image) -> tuple[int, int, int, int] | None:
    """Best-effort bounding box of the card-like (high-edge-density) content
    in the frame, used only to scope ROI fallback regions (`app/ai/roi.py`)
    more tightly than the raw camera frame — never a hardcoded region.

    Reuses the same gradient-magnitude heuristic as `detect_id_card`, just
    keeping the bounding box of where that content actually sits instead of
    collapsing it to a single density number. Returns `None` if nothing
    stands out clearly enough to bound (callers fall back to the full
    frame in that case).
    """
    gray = np.asarray(image.convert("L"), dtype=np.float32)
    dx = np.abs(np.diff(gray, axis=1))[:-1, :]
    dy = np.abs(np.diff(gray, axis=0))[:, :-1]
    gradient_magnitude = dx + dy
    mask = gradient_magnitude > _GRADIENT_MAGNITUDE_THRESHOLD

    if not mask.any():
        return None

    rows = np.where(mask.any(axis=1))[0]
    cols = np.where(mask.any(axis=0))[0]
    if rows.size == 0 or cols.size == 0:
        return None

    height, width = gray.shape
    top, bottom = int(rows[0]), min(height, int(rows[-1]) + 2)
    left, right = int(cols[0]), min(width, int(cols[-1]) + 2)
    return (max(0, left), max(0, top), right, bottom)


def detect_text_bands(image: Image.Image, bounds: Box | None = None) -> list[Box]:
    """Segment `image` (or just `bounds` within it) into candidate text-
    line regions via row projection, instead of guessing a fixed fraction
    of the frame.

    Method: classify each row as "text" or "gap" by its edge density
    (reusing the same gradient-magnitude heuristic as `detect_id_card`),
    smooth that 1-D profile slightly so one noisy row can't fracture a
    single line into two, then take contiguous "text" runs as bands.
    Bands separated by only a thin gap — e.g. the whitespace around a
    printed horizontal separator rule — are merged back into one, and
    anything shorter than a plausible single text line (noise) or taller
    than one (a mis-merged multi-field block) is discarded.

    This adapts to *this specific card's* actual layout — however many
    fields it has, wherever they sit — rather than a fixed proportion of
    the frame. Returned top-to-bottom; which band (if any) actually
    contains the PRN is decided later by scoring each one's OCR output
    (see `app/ai/pipeline.py`), not by this function.
    """
    width, height = image.size
    left, top, right, bottom = bounds if bounds is not None else (0, 0, width, height)
    left, top = max(0, left), max(0, top)
    right, bottom = min(width, right), min(height, bottom)
    if right - left < 4 or bottom - top < 4:
        return []

    gray = np.asarray(image.convert("L"), dtype=np.float32)[top:bottom, left:right]
    region_height, region_width = gray.shape

    dx = np.abs(np.diff(gray, axis=1))
    dy = np.abs(np.diff(gray, axis=0))
    edges = np.zeros_like(gray, dtype=bool)
    edges[:, :-1] |= dx > _GRADIENT_MAGNITUDE_THRESHOLD
    edges[:-1, :] |= dy > _GRADIENT_MAGNITUDE_THRESHOLD

    row_density = edges.mean(axis=1)
    window = max(1, config.TEXT_BAND_SMOOTHING_WINDOW)
    smoothed = np.convolve(row_density, np.ones(window) / window, mode="same")
    is_text = smoothed > config.TEXT_BAND_ROW_DENSITY_THRESHOLD

    raw_bands: list[tuple[int, int]] = []
    start: int | None = None
    for y, active in enumerate(is_text):
        if active and start is None:
            start = y
        elif not active and start is not None:
            raw_bands.append((start, y))
            start = None
    if start is not None:
        raw_bands.append((start, region_height))

    merged: list[list[int]] = []
    for band_start, band_end in raw_bands:
        if merged and band_start - merged[-1][1] <= config.TEXT_BAND_MERGE_GAP_ROWS:
            merged[-1][1] = band_end
        else:
            merged.append([band_start, band_end])

    min_height = region_height * config.TEXT_BAND_MIN_HEIGHT_RATIO
    max_height = region_height * config.TEXT_BAND_MAX_HEIGHT_RATIO
    h_margin = round(region_width * config.TEXT_BAND_HORIZONTAL_MARGIN)

    bands: list[Box] = []
    for band_start, band_end in merged:
        band_height = band_end - band_start
        if not (min_height <= band_height <= max_height):
            continue
        pad = round(band_height * config.TEXT_BAND_VERTICAL_PADDING)
        box = (
            left + h_margin,
            top + max(0, band_start - pad),
            right - h_margin,
            top + min(region_height, band_end + pad),
        )
        if box[2] > box[0] and box[3] > box[1]:
            bands.append(box)

    return bands[: config.TEXT_BAND_MAX_CANDIDATES]
