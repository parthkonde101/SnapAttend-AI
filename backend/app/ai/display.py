"""Attendance display marker detection.

Independent, pluggable pipeline stage — deliberately has zero knowledge of
the ID card / identity side of attendance verification (see
`app/ai/attendance_pipeline.py`, which calls this and the identity stage
as two separate, unrelated steps operating on different regions of the
same captured scene). This is exactly the "modular, plug in later"
architecture the spec asks for: future scene-validation / geometry /
replay-detection modules attach here without this function's contract
changing.

Design history (evidence-driven, twice over):

1. The very first design OCR'd the whole scene with a sparse-text
   page-segmentation mode and kept the largest bounding box. Rejected:
   Tesseract's automatic layout analysis assumes roughly-uniform text scale
   within one segmentation pass, so a huge projected glyph sharing a frame
   with an ID card's normal-sized print either got dropped entirely or had
   its strokes misread as unrelated small characters.

2. The second design (still OCR-first) scoped a fractional region of the
   frame first, then ran a uniform-block OCR pass over the *whole* region
   and kept the largest-area *OCR token* found. This looked correct against
   controlled synthetic scenes, but real captures surfaced its actual flaw:
   in a busy real scene, the region still contains far more than just the
   display (background clutter, partial ID card, hands, shadows), so
   Tesseract's largest recognized token was frequently a tiny, incidental
   character fragment (observed: 6x10px and 17x20px single-digit tokens)
   rather than the actual marker — because "largest OCR token" is a
   property of what Tesseract happened to segment and recognize, not a
   property of what's physically large in the scene. There is no OCR
   confidence threshold that fixes this: the wrong tokens were often
   confidently read digits, just physically tiny ones.

This module (the third design) fixes that structurally instead of by
threshold-tuning: geometry runs *before* OCR, not the other way around.
1) Find the display panel itself — a large, filled, high-contrast dark
   blob — via connected-component analysis, not OCR. 2) Crop to just that
   panel. 3) Within it, find the largest bright connected component and
   subject it to physical-plausibility filters (height relative to the
   panel, aspect ratio, absolute area, internal edge structure) — a 6x10px
   token is rejected here, before OCR ever sees it, because it cannot
   physically be the marker described by the spec (single character,
   60-70% of the display's height, dramatically larger than any other text
   in the scene — see the teacher session display, which now enforces that
   same geometry from the presentation side). 4) OCR only that isolated,
   already-validated glyph crop. If nothing survives step 1 or step 3 in
   the primary search region, one wider fallback region is tried the same
   way before giving up — never a scene-wide scan.

No OpenCV/scipy dependency — connected-component labeling and Otsu
thresholding are implemented locally with plain numpy, consistent with the
rest of `app.ai`'s toolchain (see `app/ai/detector.py`'s own
gradient-magnitude heuristics).

Diagnostics note: every stage's crop (search region, accepted display
panel, isolated glyph) and every candidate considered at the display and
glyph stages (accepted or rejected, with a plain-English reason) is
recorded on the returned `DisplayMarkerResult.scans`, and — when
`debug_stages` is passed in — the exact image handed to the next stage at
each step is captured too. See `app.diagnostics.attendance_recorder` for
how this is surfaced in the diagnostics UI.
"""
from __future__ import annotations

import numpy as np
from PIL import Image

from app.ai import attendance_config as config
from app.ai.attendance_schemas import (
    DisplayMarkerResult,
    DisplayRegionCandidate,
    GlyphCandidate,
    MarkerScanAttempt,
)

Box = tuple[int, int, int, int]

_EDGE_GRADIENT_THRESHOLD = 25.0


def _fractional_crop(image: Image.Image, box: tuple[float, float, float, float]) -> tuple[Image.Image, Box]:
    width, height = image.size
    left, top, right, bottom = box
    pixel_box = (
        max(0, min(width, round(left * width))),
        max(0, min(height, round(top * height))),
        max(0, min(width, round(right * width))),
        max(0, min(height, round(bottom * height))),
    )
    return image.crop(pixel_box), pixel_box


def _downscale_for_analysis(image: Image.Image, max_dimension: int) -> tuple[Image.Image, float]:
    """Connected-component labeling cost scales with pixel count, so
    geometric analysis runs against a downscaled copy — OCR later always
    runs against a crop cut from the original, full-resolution image, so
    this never affects OCR quality, only how fast the geometry stages run."""
    width, height = image.size
    longest = max(width, height, 1)
    if longest <= max_dimension:
        return image, 1.0
    scale = max_dimension / longest
    new_size = (max(1, round(width * scale)), max(1, round(height * scale)))
    return image.resize(new_size, Image.BILINEAR), scale


def _otsu_threshold(gray: np.ndarray) -> float:
    """Standard Otsu automatic threshold — separates a grayscale image's
    pixels into two classes (e.g. dark display panel vs. everything else,
    or bright glyph vs. dark panel background) by maximizing between-class
    variance. Adapts to each capture's own lighting instead of a fixed
    brightness cutoff."""
    hist, _ = np.histogram(gray, bins=256, range=(0, 256))
    hist = hist.astype(np.float64)
    total = hist.sum()
    if total <= 0:
        return 127.0

    levels = np.arange(256, dtype=np.float64)
    weight_bg = np.cumsum(hist)
    weight_fg = total - weight_bg
    sum_all = float((levels * hist).sum())
    sum_bg = np.cumsum(levels * hist)

    valid = (weight_bg > 0) & (weight_fg > 0)
    if not valid.any():
        return 127.0

    safe_bg = np.where(weight_bg > 0, weight_bg, 1)
    safe_fg = np.where(weight_fg > 0, weight_fg, 1)
    mean_bg = sum_bg / safe_bg
    mean_fg = (sum_all - sum_bg) / safe_fg
    variance = weight_bg * weight_fg * (mean_bg - mean_fg) ** 2
    variance = np.where(valid, variance, -1.0)
    return float(levels[int(np.argmax(variance))])


def _dilate(mask: np.ndarray, iterations: int = 1) -> np.ndarray:
    """Cheap 4-connected binary dilation (OR with each shifted neighbor),
    used to merge near-touching bright components before labeling — some
    glyph renderings antialias into faint gaps that would otherwise split
    one character into several small components."""
    out = mask
    for _ in range(max(0, iterations)):
        shifted = out.copy()
        shifted[1:, :] |= out[:-1, :]
        shifted[:-1, :] |= out[1:, :]
        shifted[:, 1:] |= out[:, :-1]
        shifted[:, :-1] |= out[:, 1:]
        out = shifted
    return out


def _edge_density(gray: np.ndarray) -> float:
    if gray.shape[0] < 2 or gray.shape[1] < 2:
        return 0.0
    dx = np.abs(np.diff(gray, axis=1))[:-1, :]
    dy = np.abs(np.diff(gray, axis=0))[:, :-1]
    grad = dx + dy
    return float((grad > _EDGE_GRADIENT_THRESHOLD).mean())


def _connected_components(mask: np.ndarray) -> list[tuple[int, int, int, int, int]]:
    """4-connected connected-component labeling via a two-pass union-find,
    returning (left, top, right, bottom, area) per component — right/bottom
    exclusive. Pure numpy/Python, no scipy dependency: every provisional
    label keeps its own running bounding-box/area stats during a single
    raster pass, equivalences are tracked with union-find, and stats are
    merged by final root exactly once after the pass (merging incrementally
    at union time would silently drop pixels already counted under a label
    that gets unioned later — this two-phase approach avoids that)."""
    height, width = mask.shape
    if height == 0 or width == 0:
        return []

    parent: list[int] = [0]
    stats: list[list[int]] = [[0, 0, 0, 0, 0]]

    def find(node: int) -> int:
        root = node
        while parent[root] != root:
            root = parent[root]
        while parent[node] != root:
            parent[node], node = root, parent[node]
        return root

    def union(a: int, b: int) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra

    mask_rows = mask.tolist()
    labels_rows: list[list[int]] = [[0] * width for _ in range(height)]
    next_label = 1

    for y in range(height):
        row = mask_rows[y]
        label_row = labels_rows[y]
        prev_row = mask_rows[y - 1] if y > 0 else None
        prev_label_row = labels_rows[y - 1] if y > 0 else None
        for x in range(width):
            if not row[x]:
                continue
            left_label = label_row[x - 1] if x > 0 and row[x - 1] else 0
            up_label = prev_label_row[x] if y > 0 and prev_row[x] else 0
            if left_label and up_label:
                lbl = left_label
                if left_label != up_label:
                    union(left_label, up_label)
            elif left_label:
                lbl = left_label
            elif up_label:
                lbl = up_label
            else:
                lbl = next_label
                parent.append(next_label)
                stats.append([x, y, x, y, 0])
                next_label += 1
            label_row[x] = lbl
            s = stats[lbl]
            if x < s[0]:
                s[0] = x
            if y < s[1]:
                s[1] = y
            if x > s[2]:
                s[2] = x
            if y > s[3]:
                s[3] = y
            s[4] += 1

    if next_label == 1:
        return []

    merged: dict[int, list[int]] = {}
    for label in range(1, next_label):
        root = find(label)
        s = stats[label]
        if root not in merged:
            merged[root] = list(s)
        else:
            m = merged[root]
            m[0] = min(m[0], s[0])
            m[1] = min(m[1], s[1])
            m[2] = max(m[2], s[2])
            m[3] = max(m[3], s[3])
            m[4] += s[4]

    return [(m[0], m[1], m[2] + 1, m[3] + 1, m[4]) for m in merged.values()]


def _find_border_edge(profile: np.ndarray, cutoff: float, max_thickness: int) -> int | None:
    """`profile` is a 1-D brightness profile oriented so index 0 is the
    outer edge of the region being examined. Returns how many samples in
    from that edge the brightness drops back below `cutoff` — i.e. the
    border stroke's own thickness — or None if the outer edge isn't bright
    at all (no border here), or the bright band never drops back down
    within `max_thickness` samples (the bright region extends too far to
    be a border stroke; more likely the glyph or a noise chain starts
    right at this edge)."""
    if len(profile) == 0 or profile[0] < cutoff:
        return None
    limit = min(len(profile), max_thickness + 1)
    for i in range(1, limit):
        if profile[i] < cutoff:
            return i
    return None


def _refine_bordered_frame(gray_small: np.ndarray, bbox: Box) -> Box | None:
    """Within `bbox` (a coarse dark region already accepted as a display
    candidate), look for a nested, thick, solid-bright border stroke —
    the teacher session display's marker frame is drawn with exactly this
    kind of border — by scanning a short band in from each of the four
    edges for a brightness spike that then drops back down (the border's
    own interior boundary). If all four edges show one, returns the
    border's interior box (still in the same local coordinate space as
    `bbox`); otherwise returns None, so the caller can fall back to the
    full coarse region unchanged."""
    left, top, right, bottom = bbox
    region = gray_small[top:bottom, left:right]
    height, width = region.shape
    if height < 30 or width < 30:
        return None

    row_brightness = region.mean(axis=1)
    col_brightness = region.mean(axis=0)
    baseline = float(np.median(region))
    cutoff = max(baseline + 40.0, config.MARKER_FRAME_BORDER_MIN_BRIGHTNESS)
    max_thickness_h = max(2, round(height * config.MARKER_FRAME_BORDER_MAX_THICKNESS_RATIO))
    max_thickness_w = max(2, round(width * config.MARKER_FRAME_BORDER_MAX_THICKNESS_RATIO))

    top_edge = _find_border_edge(row_brightness, cutoff, max_thickness_h)
    bottom_edge = _find_border_edge(row_brightness[::-1], cutoff, max_thickness_h)
    left_edge = _find_border_edge(col_brightness, cutoff, max_thickness_w)
    right_edge = _find_border_edge(col_brightness[::-1], cutoff, max_thickness_w)
    if top_edge is None or bottom_edge is None or left_edge is None or right_edge is None:
        return None

    inner_top, inner_bottom = top_edge, height - bottom_edge
    inner_left, inner_right = left_edge, width - right_edge
    inner_h, inner_w = inner_bottom - inner_top, inner_right - inner_left
    if inner_h <= 0 or inner_w <= 0:
        return None
    # The border must actually be bounding *something* substantial (not
    # collapsing to a sliver) without swallowing nearly the whole region
    # (which would mean no real interior border was found at all).
    if inner_h < height * 0.3 or inner_w < width * 0.3:
        return None
    if inner_h > height * 0.98 or inner_w > width * 0.98:
        return None
    aspect = inner_w / max(1, inner_h)
    if not (0.4 <= aspect <= 2.5):
        return None

    return (left + inner_left, top + inner_top, left + inner_right, top + inner_bottom)


def _find_display_regions(
    search_crop: Image.Image, search_offset: tuple[int, int]
) -> tuple[list[DisplayRegionCandidate], Box | None]:
    """Geometric stage 1: locate the display panel within `search_crop` (an
    already coarse region of the full scene) as a large, filled, dark
    connected component — no OCR runs here at all. Returns every candidate
    considered (accepted or not, for diagnostics) and the accepted
    candidate's full-scene bounding box (left, top, right, bottom), or None
    if nothing qualified."""
    small, scale = _downscale_for_analysis(search_crop, config.MARKER_ANALYSIS_MAX_DIMENSION)
    gray_small = np.asarray(small.convert("L"), dtype=np.float32)
    if gray_small.size == 0:
        return [], None

    threshold = _otsu_threshold(gray_small)
    dark_mask = gray_small <= threshold
    components = _connected_components(dark_mask)

    crop_area = max(1, gray_small.shape[0] * gray_small.shape[1])
    offset_x, offset_y = search_offset
    candidates: list[DisplayRegionCandidate] = []
    best: DisplayRegionCandidate | None = None
    best_full_box: Box | None = None
    best_local_box: Box | None = None
    accepted_local_boxes: list[tuple[DisplayRegionCandidate, Box]] = []

    for left, top, right, bottom, area in components:
        bbox_w, bbox_h = right - left, bottom - top
        bbox_area = max(1, bbox_w * bbox_h)
        fill_ratio = area / bbox_area
        aspect = bbox_w / max(1, bbox_h)
        region_gray = gray_small[top:bottom, left:right]
        mean_brightness = float(region_gray.mean()) if region_gray.size else 255.0

        full_left = offset_x + round(left / scale)
        full_top = offset_y + round(top / scale)
        full_w = max(1, round(bbox_w / scale))
        full_h = max(1, round(bbox_h / scale))

        candidate = DisplayRegionCandidate(
            rect=(full_left, full_top, full_w, full_h),
            area=int(round(area / (scale * scale))),
            fill_ratio=round(fill_ratio, 3),
            mean_brightness=round(mean_brightness, 1),
        )

        if bbox_area / crop_area < config.MARKER_MIN_DISPLAY_AREA_RATIO:
            candidate.rejection_reason = "Too small to be a display panel relative to the search region."
        elif fill_ratio < config.MARKER_MIN_DISPLAY_FILL_RATIO:
            candidate.rejection_reason = (
                "Not filled/rectangular enough to be a display panel (likely a shadow or dark clutter)."
            )
        elif not (config.MARKER_DISPLAY_ASPECT_MIN <= aspect <= config.MARKER_DISPLAY_ASPECT_MAX):
            candidate.rejection_reason = f"Aspect ratio {aspect:.2f} is not plausible for a display panel."
        elif mean_brightness > config.MARKER_MAX_DISPLAY_MEAN_BRIGHTNESS:
            candidate.rejection_reason = (
                f"Mean brightness {mean_brightness:.0f}/255 is too high to be a solid dark display panel "
                "(only relatively darker than its surroundings, not actually dark)."
            )
        else:
            candidate.accepted = True

        candidates.append(candidate)

        if candidate.accepted:
            accepted_local_boxes.append((candidate, (left, top, right, bottom)))
            if best is None or candidate.area > best.area:
                best = candidate
                best_full_box = (full_left, full_top, full_left + full_w, full_top + full_h)
                best_local_box = (left, top, right, bottom)

    candidates.sort(key=lambda c: c.area, reverse=True)

    # Prefer a nested or bordered-frame interior over raw blob size: the
    # largest dark blob is frequently the *whole* (also solid-dark)
    # page/screen background, not the marker frame specifically.
    by_area_desc = sorted(accepted_local_boxes, key=lambda pair: pair[0].area, reverse=True)

    def _contains(outer: Box, inner: Box) -> bool:
        return outer[0] <= inner[0] and outer[1] <= inner[1] and outer[2] >= inner[2] and outer[3] >= inner[3]

    refined_local_box: Box | None = None

    # First: a bright border stroke (see the teacher session display)
    # separates the frame's own interior from the surrounding background
    # at the *dark-mask* level, so it frequently shows up here as its own
    # smaller, clearly-nested accepted candidate — not needing any pixel
    # scanning at all, just recognizing the nesting. Try the largest
    # candidate that is nested well inside a bigger one first, since that
    # nesting relationship is a stronger, more specific signal than area
    # alone that this smaller region really is "the thing inside a
    # border," not just an arbitrary smaller dark patch.
    for outer_candidate, outer_box in by_area_desc:
        for inner_candidate, inner_box in by_area_desc:
            if inner_candidate is outer_candidate:
                continue
            if inner_candidate.area >= outer_candidate.area * 0.6:
                continue
            if _contains(outer_box, inner_box):
                refined_local_box = inner_box
                break
        if refined_local_box is not None:
            break

    # Otherwise: the frame's border might not have fully separated the
    # dark mask into two components (e.g. antialiasing/JPEG noise bridged
    # them) — fall back to scanning each accepted candidate, largest
    # first, for a border stroke near its own edges.
    if refined_local_box is None:
        for _candidate, local_box in by_area_desc:
            refined_local_box = _refine_bordered_frame(gray_small, local_box)
            if refined_local_box is not None:
                break

    if refined_local_box is not None:
        r_left, r_top, r_right, r_bottom = refined_local_box
        best_full_box = (
            offset_x + round(r_left / scale),
            offset_y + round(r_top / scale),
            offset_x + round(r_right / scale),
            offset_y + round(r_bottom / scale),
        )

    return candidates, best_full_box


def _merge_nearby_components(
    components: list[tuple[int, int, int, int, int]], gap_threshold: float
) -> list[tuple[int, int, int, int, int, int]]:
    """Groups raw connected components that likely belong to the same
    displayed character into one, via union-find over bounding-box
    proximity — real captures (not synthetic ones) showed a single glyph
    is frequently split into several disconnected bright components by
    sensor noise/JPEG compression, and selecting only the single largest
    raw fragment as "the glyph" (the previous design) is exactly what
    produced the reported symptom: small height ratios, oddly narrow
    aspect ratios, and OCR unable to read a partial character.

    Two components are merged if the gap between their bounding boxes
    (Euclidean distance between nearest edges; 0 if they already touch or
    overlap) is within `gap_threshold` pixels, applied transitively (A-B
    close and B-C close merges all three). Returns (left, top, right,
    bottom, area, member_count) per merged group — right/bottom exclusive,
    `area` is the summed pixel area of every member, `member_count` is how
    many raw components merged into it (1 if a component had no close
    neighbors)."""
    n = len(components)
    if n == 0:
        return []

    parent = list(range(n))

    def find(i: int) -> int:
        root = i
        while parent[root] != root:
            root = parent[root]
        while parent[i] != root:
            parent[i], i = root, parent[i]
        return root

    def union(i: int, j: int) -> None:
        ri, rj = find(i), find(j)
        if ri != rj:
            parent[rj] = ri

    def gap(a: tuple[int, int, int, int, int], b: tuple[int, int, int, int, int]) -> float:
        al, at, ar, ab, _ = a
        bl, bt, br, bb, _ = b
        dx = max(al - br, bl - ar, 0)
        dy = max(at - bb, bt - ab, 0)
        if dx == 0 and dy == 0:
            return 0.0
        return (dx * dx + dy * dy) ** 0.5

    for i in range(n):
        for j in range(i + 1, n):
            if gap(components[i], components[j]) <= gap_threshold:
                union(i, j)

    groups: dict[int, list[int]] = {}
    for i in range(n):
        root = find(i)
        left, top, right, bottom, area = components[i]
        if root not in groups:
            groups[root] = [left, top, right, bottom, area, 1]
        else:
            g = groups[root]
            g[0] = min(g[0], left)
            g[1] = min(g[1], top)
            g[2] = max(g[2], right)
            g[3] = max(g[3], bottom)
            g[4] += area
            g[5] += 1

    return [tuple(g) for g in groups.values()]  # type: ignore[misc]


def _find_glyph_candidates(
    display_crop: Image.Image, display_offset: tuple[int, int]
) -> tuple[list[GlyphCandidate], Box | None]:
    """Geometric stage 2: locate the marker glyph *inside* an already-
    isolated display region — still no OCR. Every bright connected
    component is found first, nearby ones are merged into groups likely to
    be the same character (`_merge_nearby_components`), and only then are
    physical-plausibility filters (height relative to the display region,
    aspect ratio, absolute area, internal edge structure) applied to each
    *merged group* — never to a single raw fragment in isolation. This is
    what directly rejects tiny OCR-noise-shaped candidates (like the
    6x10px / 17x20px tokens from the original reported failure) while
    still recognizing a real glyph that happens to be split into several
    pieces by capture noise. Returns every merged candidate considered and
    the selected candidate's full-scene bounding box, or None."""
    small, scale = _downscale_for_analysis(display_crop, config.MARKER_ANALYSIS_MAX_DIMENSION)
    gray_small = np.asarray(small.convert("L"), dtype=np.float32)
    if gray_small.size == 0:
        return [], None

    display_height_small = max(1, gray_small.shape[0])
    # Whichever is stricter of: Otsu (adapts well to a clean, low-noise
    # crop — a solid glyph against a genuinely flat background separates
    # cleanly at whatever threshold best splits the two), and a fixed high
    # percentile of the region's own brightness distribution (needed for
    # noisy real captures, where Otsu's threshold over a large and
    # sometimes heterogeneous display region sits low enough that ordinary
    # capture noise ends up continuously connected across far more than one
    # character — see MARKER_GLYPH_BRIGHTNESS_PERCENTILE's docstring).
    # Using only percentile regressed clean, low-noise captures (it can sit
    # *below* Otsu's own threshold when the glyph occupies a large,
    # uniform share of the region); using only Otsu regressed noisy real
    # captures. Taking the stricter of the two threshold candidates in
    # every case is safe for a "bright glyph on a dark background" mask by
    # construction: it can only ever exclude pixels, never include *more*
    # background as "bright" than either method would alone.
    otsu = _otsu_threshold(gray_small)
    percentile = float(np.percentile(gray_small, config.MARKER_GLYPH_BRIGHTNESS_PERCENTILE))
    threshold = max(otsu, percentile)
    bright_mask = gray_small >= threshold
    bright_mask = _dilate(bright_mask, iterations=1)
    raw_components = _connected_components(bright_mask)

    # A raw component whose *own* bounding box already exceeds the max
    # plausible glyph height cannot be "a fragment of the character that
    # needs reassembling" — it's already bigger than the character could
    # ever legitimately be (background noise, a bezel/reflection edge, or a
    # border-hugging artifact). Critically, such a component must be kept
    # OUT of the merge pool entirely rather than merged like everything
    # else: gap-to-bounding-box distance is trivially ~0 against a huge,
    # sprawling bbox (nearly anything in the crop falls "inside" it), so
    # letting it participate would merge every nearby fragment into one
    # giant, unusable blob — confirmed against real captures, where this
    # was exactly what made real-world fragment merging misfire. It's still
    # recorded as its own standalone candidate below (and almost always
    # correctly rejected by the max-height-ratio filter), it just can't
    # absorb anything else.
    oversized_height = config.MARKER_MAX_GLYPH_HEIGHT_RATIO * display_height_small
    mergeable = [c for c in raw_components if (c[3] - c[1]) <= oversized_height]
    oversized = [c for c in raw_components if (c[3] - c[1]) > oversized_height]

    gap_threshold = config.MARKER_GLYPH_MERGE_GAP_RATIO * display_height_small
    merged_groups = _merge_nearby_components(mergeable, gap_threshold)
    merged_groups.extend((left, top, right, bottom, area, 1) for left, top, right, bottom, area in oversized)

    offset_x, offset_y = display_offset
    candidates: list[GlyphCandidate] = []
    best: GlyphCandidate | None = None
    best_full_box: Box | None = None

    for left, top, right, bottom, area, member_count in merged_groups:
        bbox_w, bbox_h = right - left, bottom - top
        bbox_area = max(1, bbox_w * bbox_h)
        aspect = bbox_w / max(1, bbox_h)
        height_ratio = bbox_h / display_height_small
        fill_ratio = area / bbox_area
        region_gray = gray_small[top:bottom, left:right]
        edge_density = _edge_density(region_gray)

        full_left = offset_x + round(left / scale)
        full_top = offset_y + round(top / scale)
        full_w = max(1, round(bbox_w / scale))
        full_h = max(1, round(bbox_h / scale))
        full_area = int(round(area / (scale * scale)))

        candidate = GlyphCandidate(
            rect=(full_left, full_top, full_w, full_h),
            area=full_area,
            aspect_ratio=round(aspect, 3),
            height_ratio=round(height_ratio, 3),
            fill_ratio=round(fill_ratio, 3),
            edge_density=round(edge_density, 3),
            member_count=member_count,
        )

        if full_area < config.MARKER_MIN_GLYPH_AREA_PX:
            candidate.rejection_reason = "Pixel area too small to physically be the displayed marker, even after merging nearby fragments."
        elif height_ratio < config.MARKER_MIN_GLYPH_HEIGHT_RATIO:
            candidate.rejection_reason = (
                f"Only {height_ratio:.0%} of the display panel's height (after merging {member_count} fragment"
                f"{'s' if member_count != 1 else ''}) — far smaller than the marker is guaranteed to be."
            )
        elif height_ratio > config.MARKER_MAX_GLYPH_HEIGHT_RATIO:
            candidate.rejection_reason = (
                f"Spans {height_ratio:.0%} of the display panel's height — too close to the panel's own "
                "border to be the glyph itself (likely an antialiasing/compression edge ring)."
            )
        elif not (config.MARKER_GLYPH_ASPECT_MIN <= aspect <= config.MARKER_GLYPH_ASPECT_MAX):
            candidate.rejection_reason = f"Aspect ratio {aspect:.2f} is not plausible for a single character."
        elif edge_density < config.MARKER_MIN_GLYPH_EDGE_DENSITY:
            candidate.rejection_reason = "No internal edge structure — likely a flat lighting artifact, not a rendered character."
        else:
            candidate.accepted = True

        candidates.append(candidate)

        # Select by bounding-box HEIGHT, not cumulative pixel area. Real
        # captures showed why this matters: a dense cluster of small,
        # unrelated on-screen text (a countdown timer, status icons) can
        # accumulate *more* raw bright-pixel area than the sparser, noisier
        # marker glyph itself, despite being far shorter — and the spec's
        # own guarantee is about physical size ("significantly larger than
        # any other text in the scene"), which is a height claim, not a
        # pixel-density claim. Area only breaks ties between
        # similarly-tall candidates.
        if candidate.accepted and (
            best is None
            or candidate.rect[3] > best.rect[3]
            or (candidate.rect[3] == best.rect[3] and candidate.area > best.area)
        ):
            best = candidate
            best_full_box = (full_left, full_top, full_left + full_w, full_top + full_h)

    candidates.sort(key=lambda c: (c.rect[3], c.area), reverse=True)
    if best is not None:
        best.selected = True
    return candidates, best_full_box


def _normalize_glyph_crop(glyph_crop: Image.Image) -> Image.Image:
    """Produce the final, OCR-ready image from a merged glyph crop: resize
    to a canonical height (aspect ratio preserved) so Tesseract always sees
    the character at a consistent scale regardless of camera distance, then
    pad generously on a plain dark canvas (matching the guaranteed-dark
    display background) so the glyph isn't touching the image edges. This
    is the *only* image OCR runs against — never a raw per-fragment crop —
    and it's exactly what gets saved to diagnostics as the final normalized
    glyph, per the requirement that it be directly inspectable."""
    width, height = glyph_crop.size
    if width <= 0 or height <= 0:
        return glyph_crop

    target_height = max(1, config.MARKER_GLYPH_NORMALIZE_HEIGHT)
    scale = target_height / height
    target_width = max(1, round(width * scale))
    resized = glyph_crop.convert("RGB").resize((target_width, target_height), Image.LANCZOS)

    pad = round(target_height * config.MARKER_GLYPH_NORMALIZE_PADDING_RATIO)
    canvas = Image.new("RGB", (target_width + 2 * pad, target_height + 2 * pad), (0, 0, 0))
    canvas.paste(resized, (pad, pad))
    return canvas


def _ocr_glyph(glyph_crop: Image.Image) -> tuple[str | None, float | None]:
    """Run OCR against a tight, already geometrically-isolated single-glyph
    crop only — never a region that could contain anything else. Tries
    `MARKER_OCR_GLYPH_PSM` (single character) then, if that finds nothing,
    `MARKER_OCR_GLYPH_FALLBACK_PSM` (single word) against the same crop.

    Tesseract's models are trained overwhelmingly on dark text on a light
    background. `_normalize_glyph_crop` always hands this function a bright
    glyph padded onto a solid black canvas (by construction — the whole
    detector is built around a bright marker on a dark display), which is
    the opposite polarity. Verified directly (not assumed): the same
    isolated "P" crop that OCR'd as nothing at every PSM in its native
    white-on-black form read correctly at 87% confidence once inverted to
    black-on-white, and inverting a crop that already OCR'd correctly
    (white-on-black "2") did not break it — it stayed correct at a higher
    confidence. Inverting here is therefore a strict improvement, not a
    guess: every glyph handed to this function is bright-on-dark, so the
    inversion is unconditional rather than gated on any per-image test.
    """
    import pytesseract
    from PIL import ImageOps

    inverted_crop = ImageOps.invert(glyph_crop.convert("RGB"))

    for psm in (config.MARKER_OCR_GLYPH_PSM, config.MARKER_OCR_GLYPH_FALLBACK_PSM):
        tess_config = f"--psm {psm} -c tessedit_char_whitelist={config.MARKER_ALPHABET}"
        data = pytesseract.image_to_data(
            inverted_crop, config=tess_config, output_type=pytesseract.Output.DICT
        )
        tokens = data.get("text", [])
        for i in range(len(tokens)):
            token = (tokens[i] or "").strip().upper()
            if len(token) != 1 or token not in config.MARKER_ALPHABET:
                continue
            try:
                confidence = float(data["conf"][i])
            except (KeyError, TypeError, ValueError):
                confidence = -1.0
            if confidence < config.MARKER_MIN_CONFIDENCE:
                continue
            return token, round(confidence / 100.0, 3)
    return None, None


def detect_attendance_marker(
    image: Image.Image, *, debug_stages: dict[str, Image.Image] | None = None
) -> DisplayMarkerResult:
    """Locate the projected session marker within `image` (the full,
    unmodified attendance scene) via geometry first, OCR last.

    Best-effort and never raises: any failure (OCR engine unavailable, no
    display-shaped region found, no glyph-shaped region found inside it, or
    OCR failing to read the isolated glyph) comes back as `detected=False`
    with a human-readable `failure_reason` describing exactly which stage
    fell through — the caller (`app.ai.attendance_pipeline`) treats this as
    "no marker found" and verification simply fails with a clear reason,
    never a crash.

    `debug_stages`, if given a dict, is populated with the exact crop image
    at every stage (search region, accepted display panel, isolated glyph)
    for every tier attempted — keyed by that stage's key on the
    corresponding `MarkerScanAttempt`. A `None` (the default) is a complete
    no-op.
    """
    try:
        import pytesseract  # noqa: F401  (import-availability probe only)
    except Exception as exc:
        return DisplayMarkerResult(
            detected=False,
            attempted=False,
            failure_reason=f"OCR library unavailable ({exc}). Install the `tesseract` binary — see the README.",
        )

    image_width, image_height = image.size
    scans: list[MarkerScanAttempt] = []

    # Tracks the strongest *geometric* evidence seen across every tier tried
    # so far, independent of whether OCR ultimately reads a character —
    # see app.ai.attendance_config's display-confidence-tier block. This is
    # what lets the verification service treat "a display was clearly
    # photographed" as real evidence even on a scan where OCR comes back
    # empty, instead of that evidence being silently discarded the moment
    # this function falls through to the next tier or returns detected=False.
    best_display_confidence = config.MARKER_DISPLAY_CONFIDENCE_NONE
    best_display_rect: Box | None = None

    def _note_evidence(confidence: float, rect: Box | None) -> None:
        nonlocal best_display_confidence, best_display_rect
        if confidence > best_display_confidence:
            best_display_confidence = confidence
            best_display_rect = rect

    for tier_index, (fractional_box, tier_name) in enumerate(
        ((config.MARKER_REGION_BOX, "primary"), (config.MARKER_REGION_FALLBACK_BOX, "fallback"))
    ):
        search_crop, pixel_box = _fractional_crop(image, fractional_box)
        search_stage_image_key: str | None = None
        if debug_stages is not None:
            search_stage_image_key = f"marker_{tier_index:02d}_{tier_name}_00_search"
            debug_stages[search_stage_image_key] = search_crop

        try:
            display_candidates, display_full_box = _find_display_regions(search_crop, (pixel_box[0], pixel_box[1]))
        except Exception as exc:
            scans.append(
                MarkerScanAttempt(
                    tier=tier_name,
                    fractional_box=fractional_box,
                    pixel_box=pixel_box,
                    search_stage_image_key=search_stage_image_key,
                    outcome=f"Display-region search raised an error ({exc}).",
                )
            )
            continue

        if display_full_box is None:
            scans.append(
                MarkerScanAttempt(
                    tier=tier_name,
                    fractional_box=fractional_box,
                    pixel_box=pixel_box,
                    search_stage_image_key=search_stage_image_key,
                    display_regions=display_candidates,
                    outcome="No display-panel-shaped region found in this search area.",
                )
            )
            continue

        clamped_display_box: Box = (
            max(0, min(image_width, display_full_box[0])),
            max(0, min(image_height, display_full_box[1])),
            max(0, min(image_width, display_full_box[2])),
            max(0, min(image_height, display_full_box[3])),
        )
        if clamped_display_box[2] <= clamped_display_box[0] or clamped_display_box[3] <= clamped_display_box[1]:
            scans.append(
                MarkerScanAttempt(
                    tier=tier_name,
                    fractional_box=fractional_box,
                    pixel_box=pixel_box,
                    search_stage_image_key=search_stage_image_key,
                    display_regions=display_candidates,
                    outcome="Detected display region collapsed to zero area after clamping to the frame.",
                )
            )
            continue

        display_crop = image.crop(clamped_display_box)
        display_stage_image_key: str | None = None
        if debug_stages is not None:
            display_stage_image_key = f"marker_{tier_index:02d}_{tier_name}_01_display"
            debug_stages[display_stage_image_key] = display_crop

        try:
            glyph_candidates, glyph_full_box = _find_glyph_candidates(
                display_crop, (clamped_display_box[0], clamped_display_box[1])
            )
        except Exception as exc:
            scans.append(
                MarkerScanAttempt(
                    tier=tier_name,
                    fractional_box=fractional_box,
                    pixel_box=pixel_box,
                    search_stage_image_key=search_stage_image_key,
                    display_regions=display_candidates,
                    display_stage_image_key=display_stage_image_key,
                    outcome=f"Glyph search raised an error ({exc}).",
                )
            )
            continue

        if glyph_full_box is None:
            scans.append(
                MarkerScanAttempt(
                    tier=tier_name,
                    fractional_box=fractional_box,
                    pixel_box=pixel_box,
                    search_stage_image_key=search_stage_image_key,
                    display_regions=display_candidates,
                    display_stage_image_key=display_stage_image_key,
                    glyph_candidates=glyph_candidates,
                    outcome="Display panel found, but no glyph inside it was large/shaped enough to be the marker.",
                )
            )
            _note_evidence(config.MARKER_DISPLAY_CONFIDENCE_PANEL_ONLY, clamped_display_box)
            continue

        # Step 4: crop the *entire merged* glyph (union bbox across every
        # fragment that got merged in _find_glyph_candidates) — a small
        # pixel-tight padding only, just enough to avoid clipping
        # antialiased stroke edges.
        pad_x = round((glyph_full_box[2] - glyph_full_box[0]) * config.MARKER_GLYPH_CROP_PADDING_RATIO)
        pad_y = round((glyph_full_box[3] - glyph_full_box[1]) * config.MARKER_GLYPH_CROP_PADDING_RATIO)
        padded_glyph_box: Box = (
            max(0, glyph_full_box[0] - pad_x),
            max(0, glyph_full_box[1] - pad_y),
            min(image_width, glyph_full_box[2] + pad_x),
            min(image_height, glyph_full_box[3] + pad_y),
        )
        glyph_crop = image.crop(padded_glyph_box)
        glyph_stage_image_key: str | None = None
        if debug_stages is not None:
            glyph_stage_image_key = f"marker_{tier_index:02d}_{tier_name}_02_glyph"
            debug_stages[glyph_stage_image_key] = glyph_crop

        # Step 5: normalize (canonical height + generous padding on a dark
        # canvas) — this, not the raw merged crop above, is what OCR
        # actually runs against, and what gets saved as the final
        # inspectable glyph image.
        normalized_crop = _normalize_glyph_crop(glyph_crop)
        glyph_normalized_stage_image_key: str | None = None
        if debug_stages is not None:
            glyph_normalized_stage_image_key = f"marker_{tier_index:02d}_{tier_name}_03_glyph_normalized"
            debug_stages[glyph_normalized_stage_image_key] = normalized_crop

        # Step 6: OCR only the normalized glyph — never per raw component.
        try:
            ocr_text, ocr_confidence = _ocr_glyph(normalized_crop)
        except Exception as exc:
            scans.append(
                MarkerScanAttempt(
                    tier=tier_name,
                    fractional_box=fractional_box,
                    pixel_box=pixel_box,
                    search_stage_image_key=search_stage_image_key,
                    display_regions=display_candidates,
                    display_stage_image_key=display_stage_image_key,
                    glyph_candidates=glyph_candidates,
                    glyph_stage_image_key=glyph_stage_image_key,
                    glyph_normalized_stage_image_key=glyph_normalized_stage_image_key,
                    outcome=f"OCR on the normalized glyph raised an error ({exc}).",
                )
            )
            continue

        if ocr_text is None:
            scans.append(
                MarkerScanAttempt(
                    tier=tier_name,
                    fractional_box=fractional_box,
                    pixel_box=pixel_box,
                    search_stage_image_key=search_stage_image_key,
                    display_regions=display_candidates,
                    display_stage_image_key=display_stage_image_key,
                    glyph_candidates=glyph_candidates,
                    glyph_stage_image_key=glyph_stage_image_key,
                    glyph_normalized_stage_image_key=glyph_normalized_stage_image_key,
                    outcome="Glyph geometrically isolated and normalized, but OCR could not confidently read a character from it.",
                )
            )
            _note_evidence(config.MARKER_DISPLAY_CONFIDENCE_GLYPH_ISOLATED, glyph_full_box)
            continue

        scans.append(
            MarkerScanAttempt(
                tier=tier_name,
                fractional_box=fractional_box,
                pixel_box=pixel_box,
                search_stage_image_key=search_stage_image_key,
                display_regions=display_candidates,
                display_stage_image_key=display_stage_image_key,
                glyph_candidates=glyph_candidates,
                glyph_stage_image_key=glyph_stage_image_key,
                glyph_normalized_stage_image_key=glyph_normalized_stage_image_key,
                ocr_text=ocr_text,
                ocr_confidence=ocr_confidence,
                outcome=f"Detected '{ocr_text}'.",
            )
        )
        rect: Box = (
            glyph_full_box[0],
            glyph_full_box[1],
            glyph_full_box[2] - glyph_full_box[0],
            glyph_full_box[3] - glyph_full_box[1],
        )
        return DisplayMarkerResult(
            detected=True,
            character=ocr_text,
            confidence=ocr_confidence,
            rect=rect,
            display_detected=True,
            display_confidence=config.MARKER_DISPLAY_CONFIDENCE_OCR_READ,
            scans=scans,
        )

    # No tier produced an OCR-read character, but `best_display_confidence`
    # may still carry real geometric evidence from a tier that isolated a
    # glyph-shaped region without OCR managing to read it (or found only a
    # bare display panel) — surface that here rather than discarding it,
    # since app.services.attendance_verification_service now treats
    # `display_detected` as evidence in its own right. `rect` is populated
    # from whichever tier produced that strongest evidence, for the same
    # "development use" inspection purpose it already served.
    # `best_display_rect` is stored as (left, top, right, bottom), matching
    # every other box in this function — convert to the (left, top, width,
    # height) shape `rect` uses everywhere else before returning it.
    best_rect: Box | None = None
    if best_display_rect is not None:
        best_rect = (
            best_display_rect[0],
            best_display_rect[1],
            best_display_rect[2] - best_display_rect[0],
            best_display_rect[3] - best_display_rect[1],
        )
    return DisplayMarkerResult(
        detected=False,
        attempted=True,
        failure_reason=scans[-1].outcome if scans else "No marker character found.",
        rect=best_rect,
        # Production classroom deployment (real students, real projectors):
        # a bare accepted display-panel candidate — a genuinely dark,
        # panel-shaped, appropriately-sized region, already filtered by
        # MARKER_MIN_DISPLAY_AREA_RATIO/FILL_RATIO/ASPECT/MAX_MEAN_BRIGHTNESS
        # before it's ever accepted at all — now counts as sufficient
        # classroom-display evidence on its own, not just glyph-isolated or
        # better. Students are expected to focus their camera on the ID
        # card, so the projected marker will often be blurry, partial,
        # tilted, or otherwise not clean enough to isolate a single glyph
        # from at all; requiring glyph isolation as the evidence floor was
        # rejecting real, plausible classroom photos for exactly the
        # blur/angle reasons the marker is *expected* to suffer. This is
        # safe to loosen because identity verification
        # (app.services.attendance_verification_service) remains an
        # absolute, independent gate — display evidence at any tier is
        # never sufficient on its own, only in combination with an already
        # -confirmed identity match.
        display_detected=best_display_confidence >= config.MARKER_DISPLAY_CONFIDENCE_PANEL_ONLY,
        display_confidence=best_display_confidence,
        scans=scans,
    )
