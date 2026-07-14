"""Region-of-interest helpers for locating the likely PRN crop.

Three strategies, tried in priority order by `pipeline.py`:

1. Barcode-relative — if a barcode was located on the card, the PRN is
   frequently printed immediately above or below it. This adapts to
   wherever the barcode actually *is* on this particular capture, so it
   carries no per-institution assumption at all.
2. Structural text bands — the image's own row structure (contiguous rows
   of printed text, separated by whitespace or a ruled separator line —
   see `app/ai/detector.detect_text_bands`) segmented into candidate
   regions. Still fully content-adaptive: no assumption about *which*
   field is where, just "here is where the lines of text actually are."
3. Fractional fallback — a small, ordered set of generic bands (see
   `app/ai/config.py`) relative to the detected card bounds (or the full
   frame). Last resort, only reached if neither of the above produced
   anything (e.g. a very low-contrast capture with no clear text edges).

Every region returned here is a (left, top, right, bottom) pixel box,
already clamped to the image bounds — never a hardcoded absolute
coordinate baked into this module.
"""
from __future__ import annotations

from PIL import Image

from app.ai import config
from app.ai.detector import detect_text_bands

Box = tuple[int, int, int, int]


def crop_region(image: Image.Image, box: Box) -> Image.Image:
    """Crop `box` (left, top, right, bottom) out of `image`."""
    return image.crop(box)


def _clamp_box(box: tuple[float, float, float, float], width: int, height: int) -> Box:
    left, top, right, bottom = box
    return (
        max(0, min(width, round(left))),
        max(0, min(height, round(top))),
        max(0, min(width, round(right))),
        max(0, min(height, round(bottom))),
    )


def _barcode_relative_regions(barcode_rect: Box, image_size: tuple[int, int]) -> list[Box]:
    width, height = image_size
    left, top, bar_w, bar_h = barcode_rect
    right, bottom = left + bar_w, top + bar_h

    band_height = bar_h * config.PRN_BAND_HEIGHT_FACTOR
    pad_x = bar_w * config.PRN_BAND_HORIZONTAL_PADDING

    below = (left - pad_x, bottom, right + pad_x, bottom + band_height)
    above = (left - pad_x, top - band_height, right + pad_x, top)
    return [_clamp_box(b, width, height) for b in (below, above)]


def _fractional_regions(bounds: Box, image_size: tuple[int, int]) -> list[Box]:
    width, height = image_size
    bleft, btop, bright, bbottom = bounds
    bwidth, bheight = bright - bleft, bbottom - btop

    regions: list[Box] = []
    for fl, ft, fr, fb in config.DEFAULT_ROI_FALLBACK_REGIONS:
        box = (
            bleft + fl * bwidth,
            btop + ft * bheight,
            bleft + fr * bwidth,
            btop + fb * bheight,
        )
        regions.append(_clamp_box(box, width, height))
    return regions


def locate_prn_candidates(
    image: Image.Image,
    *,
    barcode_rect: Box | None = None,
    card_bbox: Box | None = None,
) -> list[Box]:
    """Return an ordered list of candidate crop boxes to try OCR against.

    Barcode-relative regions (if a barcode was found) come first, since
    they're anchored to actual content on this card. Structural text bands
    (this card's own rows of printed text — see
    `app/ai/detector.detect_text_bands`) come next: still fully content-
    adaptive, no arbitrary fractional guess. Fractional fallback regions —
    scoped to `card_bbox` when available, otherwise the full frame — are
    the last resort, only reached if neither of the above found anything
    usable (e.g. a very low-contrast capture).
    """
    width, height = image.size
    bounds = card_bbox if card_bbox is not None else (0, 0, width, height)
    candidates: list[Box] = []

    if barcode_rect is not None:
        candidates.extend(_barcode_relative_regions(barcode_rect, (width, height)))

    try:
        candidates.extend(detect_text_bands(image, bounds=bounds))
    except Exception:
        pass

    if not candidates:
        candidates.extend(_fractional_regions(bounds, (width, height)))

    # Drop degenerate boxes (e.g. clamped down to zero area).
    return [box for box in candidates if box[2] > box[0] and box[3] > box[1]]
