"""Pre-OCR image quality gate.

Runs cheap heuristics so obviously unusable photos (too small, too blurry,
too dark, blown out by glare) are rejected before spending time on OCR —
and, per product requirement, before the image is ever written to disk.

Deliberately dependency-light: Pillow + numpy only, no OpenCV. Each check
is independently testable by calling it with a synthetic array.
"""
from __future__ import annotations

import io

import numpy as np
from PIL import Image

from app.ai.schemas import QualityCheckResult

MIN_WIDTH = 640
MIN_HEIGHT = 480
BLUR_VARIANCE_THRESHOLD = 60.0
MIN_MEAN_BRIGHTNESS = 40.0
MAX_MEAN_BRIGHTNESS = 235.0
MAX_BLOWN_HIGHLIGHT_RATIO = 0.08

# Partial-visibility ("card cut off by the frame edge") heuristic. Coarse by
# design and deliberately conservative — a false positive here rejects a
# perfectly good photo, so this only fires when strong edge content presses
# against *all four* borders (about as unambiguous a "cropped" signal as a
# cheap heuristic can give without a trained model).
_BORDER_MARGIN_RATIO = 0.02
_BORDER_EDGE_THRESHOLD = 20.0
_BORDER_EDGE_DENSITY_MIN = 0.12
_BORDER_TOUCH_SIDES_TO_FAIL = 4


def estimate_blur(gray: np.ndarray) -> float:
    """Variance of the discrete Laplacian — a standard, cheap blur proxy.

    Sharp images have high-frequency edges (high variance); blurry images
    look smoothed out (low variance).
    """
    kernel_center, kernel_edge = -4.0, 1.0
    padded = np.pad(gray, 1, mode="edge").astype(np.float32)
    h, w = gray.shape
    laplacian = (
        kernel_edge * padded[0:h, 1 : w + 1]
        + kernel_edge * padded[1 : h + 1, 0:w]
        + kernel_center * padded[1 : h + 1, 1 : w + 1]
        + kernel_edge * padded[1 : h + 1, 2 : w + 2]
        + kernel_edge * padded[2 : h + 2, 1 : w + 1]
    )
    return float(laplacian.var())


def estimate_full_card_visible(gray: np.ndarray) -> bool:
    """Rough heuristic for "is any part of the card likely cut off by the
    frame edge": true (visible) unless strong edge/text content presses
    against all four image borders at once. Only checking a thin margin at
    each edge keeps this cheap and independently testable against a
    synthetic array, same as `estimate_blur`.
    """
    height, width = gray.shape
    margin = max(2, int(round(min(height, width) * _BORDER_MARGIN_RATIO)))

    dx = np.abs(np.diff(gray, axis=1))
    dy = np.abs(np.diff(gray, axis=0))
    edges = np.zeros_like(gray, dtype=bool)
    edges[:, :-1] |= dx > _BORDER_EDGE_THRESHOLD
    edges[:-1, :] |= dy > _BORDER_EDGE_THRESHOLD

    touches = 0
    if edges[:margin, :].mean() > _BORDER_EDGE_DENSITY_MIN:
        touches += 1
    if edges[-margin:, :].mean() > _BORDER_EDGE_DENSITY_MIN:
        touches += 1
    if edges[:, :margin].mean() > _BORDER_EDGE_DENSITY_MIN:
        touches += 1
    if edges[:, -margin:].mean() > _BORDER_EDGE_DENSITY_MIN:
        touches += 1

    return touches < _BORDER_TOUCH_SIDES_TO_FAIL


def check_image_quality(image_bytes: bytes) -> QualityCheckResult:
    """Validate resolution, blur, brightness, and basic glare before OCR."""
    try:
        image = Image.open(io.BytesIO(image_bytes))
        image.load()
    except Exception:
        return QualityCheckResult(
            passed=False,
            messages=["Image could not be read. Please try capturing again."],
            resolution_ok=False,
            blur_ok=False,
            brightness_ok=False,
            glare_ok=False,
            coverage_ok=False,
        )

    messages: list[str] = []

    width, height = image.size
    resolution_ok = width >= MIN_WIDTH and height >= MIN_HEIGHT
    if not resolution_ok:
        messages.append("Image resolution is too low. Move closer and try again.")

    gray = np.asarray(image.convert("L"), dtype=np.float32)

    blur_score = estimate_blur(gray)
    blur_ok = blur_score >= BLUR_VARIANCE_THRESHOLD
    if not blur_ok:
        messages.append("Image is too blurry. Hold the camera steady and refocus.")

    mean_brightness = float(gray.mean())
    brightness_ok = MIN_MEAN_BRIGHTNESS <= mean_brightness <= MAX_MEAN_BRIGHTNESS
    if mean_brightness < MIN_MEAN_BRIGHTNESS:
        messages.append("Image too dark. Move to better lighting.")
    elif mean_brightness > MAX_MEAN_BRIGHTNESS:
        messages.append("Image too bright. Reduce glare or move away from direct light.")

    # Informational only — standard deviation of intensity. Doesn't feed
    # into `passed`; surfaced purely for developer diagnostics.
    contrast = float(gray.std())

    blown_ratio = float((gray >= 250).mean())
    glare_ok = blown_ratio <= MAX_BLOWN_HIGHLIGHT_RATIO
    if not glare_ok:
        messages.append("Reduce glare — tilt the card or move away from direct light.")

    coverage_ok = estimate_full_card_visible(gray)
    if not coverage_ok:
        messages.append("Entire ID must be visible. Move back slightly and recapture.")

    passed = resolution_ok and blur_ok and brightness_ok and glare_ok and coverage_ok
    if passed:
        messages.append("Image acceptable.")

    return QualityCheckResult(
        passed=passed,
        messages=messages,
        resolution_ok=resolution_ok,
        blur_ok=blur_ok,
        brightness_ok=brightness_ok,
        glare_ok=glare_ok,
        coverage_ok=coverage_ok,
        width=width,
        height=height,
        blur_score=round(blur_score, 2),
        brightness=round(mean_brightness, 2),
        contrast=round(contrast, 2),
        glare_ratio=round(blown_ratio, 4),
    )
