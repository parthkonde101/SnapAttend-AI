"""Preprocessing steps applied between the quality gate and OCR.

Each function does one thing and is independently testable. Perspective
correction is deliberately stubbed — see `correct_perspective` — so the
pipeline's shape (and every caller) is stable today, and a real
implementation can be dropped in later without touching anything else.

`preprocess_for_ocr` (whole-card: normalize -> perspective -> resize) is
unchanged from earlier milestones and is still what drives name
extraction — nothing below touches it. `preprocess_prn_region` is a
second, separate chain applied only to the small PRN-region crop located
by `app/ai/roi.py`, tuned for a tiny, often low-contrast printed-number
image rather than a whole photographed card.
"""
from __future__ import annotations

import io

import numpy as np
from PIL import Image, ImageFilter, ImageOps

OCR_TARGET_MAX_DIMENSION = 1600


def resize_for_ocr(image: Image.Image, max_dimension: int = OCR_TARGET_MAX_DIMENSION) -> Image.Image:
    """Downscale (never upscale) so OCR runs on a consistent, bounded frame size."""
    width, height = image.size
    longest_side = max(width, height)
    if longest_side <= max_dimension:
        return image

    scale = max_dimension / longest_side
    return image.resize((round(width * scale), round(height * scale)), Image.LANCZOS)


def normalize(image: Image.Image) -> Image.Image:
    """Respect EXIF orientation and equalize contrast before OCR."""
    oriented = ImageOps.exif_transpose(image) or image
    return ImageOps.autocontrast(oriented.convert("RGB"), cutoff=1)


def correct_perspective(image: Image.Image) -> Image.Image:
    """Placeholder for perspective / deskew correction.

    A full implementation would detect the card's four corners and warp
    them to a fronto-parallel rectangle (e.g. a homography via
    `PIL.Image.transform(..., Image.PERSPECTIVE, ...)` or OpenCV). That is
    a standalone piece of work on its own, so for now this is an identity
    transform. The call site and return contract already match what a
    real implementation needs, so wiring it in later is a one-module
    change — nothing in `pipeline.py` or downstream would need to change.
    """
    return image


def preprocess_for_ocr(image_bytes: bytes) -> Image.Image:
    """Full preprocessing chain: load -> normalize -> perspective -> resize."""
    image = Image.open(io.BytesIO(image_bytes))
    image = normalize(image)
    image = correct_perspective(image)
    image = resize_for_ocr(image)
    return image


# --- PRN-region-specific enhancement chain -----------------------------------
# Applied only to small, already-cropped PRN regions (see app/ai/roi.py) —
# never to the whole-card image, so the working name-extraction path above
# is completely unaffected by any of this.


def upscale(image: Image.Image, factor: float) -> Image.Image:
    """Upscale a small crop before OCR — tiny printed ID-number regions
    typically need 2x-4x magnification for reliable digit recognition."""
    if factor <= 1.0:
        return image
    width, height = image.size
    return image.resize((max(1, round(width * factor)), max(1, round(height * factor))), Image.LANCZOS)


def to_grayscale(image: Image.Image) -> Image.Image:
    return image.convert("L")


def equalize_contrast(image: Image.Image) -> Image.Image:
    """Stretch contrast so faint or low-contrast printed numbers stand out
    from the card background.

    Deliberately autocontrast-only, not full histogram equalization
    (`ImageOps.equalize`). Measured directly against real PRN-region crops
    while diagnosing why structural ROI candidates were producing empty OCR
    results: on a small crop that's mostly uniform background with a thin
    band of dark text (the typical case here), `ImageOps.equalize`
    redistributes intensities across the *whole* histogram so the narrow
    band of text-pixel values gets stretched non-monotonically — it
    reliably fractures thin digit strokes into disconnected specks (visibly
    confirmed: a crop that OCRs perfectly before this step, and again after
    swapping in plain autocontrast, produced garbage through the rest of
    the chain when full equalization ran here). Autocontrast alone already
    achieves the intended goal — stretching the crop's actual tonal range
    to use the full 0-255 range — without redistributing the histogram's
    interior, so digit strokes stay intact.
    """
    return ImageOps.autocontrast(image, cutoff=1)


def denoise(image: Image.Image) -> Image.Image:
    """Cheap denoise: a small median filter clears sensor/JPEG speckle
    without smearing digit edges the way a large blur kernel would."""
    return image.filter(ImageFilter.MedianFilter(size=3))


def sharpen(image: Image.Image) -> Image.Image:
    """Unsharp mask to crisp up digit edges after denoising/upscaling."""
    return image.filter(ImageFilter.UnsharpMask(radius=2, percent=150, threshold=2))


def adaptive_threshold(image: Image.Image, block_size: int = 25, offset: float = 10.0) -> Image.Image:
    """Local-mean adaptive threshold — binarizes each pixel against the
    mean of its own neighborhood rather than one global cutoff, which holds
    up far better than a single global threshold under uneven lighting or a
    glare gradient across the card. Implemented with a numpy integral image
    (cumulative sum) so it stays dependency-light — no OpenCV needed.
    """
    gray = np.asarray(image.convert("L"), dtype=np.float64)
    height, width = gray.shape
    pad = max(1, block_size // 2)
    padded = np.pad(gray, pad, mode="edge")

    # Integral image (with a leading zero row/col) so any block's sum is
    # four array lookups away.
    integral = np.pad(np.cumsum(np.cumsum(padded, axis=0), axis=1), ((1, 0), (1, 0)))

    window = pad * 2 + 1
    bottom = integral[window:, window:]
    top = integral[:height, window:]
    left = integral[window:, :width]
    top_left = integral[:height, :width]
    local_sum = bottom - top - left + top_left
    local_mean = local_sum / float(window * window)

    binary = (gray > (local_mean - offset)).astype(np.uint8) * 255
    return Image.fromarray(binary, mode="L")


def morphological_cleanup(image: Image.Image, size: int = 1) -> Image.Image:
    """Optional light open (erode-then-dilate) pass to remove salt-and-
    pepper speckle left over from thresholding, without eroding digit
    strokes away. Off by default in `preprocess_prn_region` — turn on for
    cards whose backgrounds threshold noisily."""
    footprint = size * 2 + 1
    opened = image.filter(ImageFilter.MinFilter(size=footprint))
    return opened.filter(ImageFilter.MaxFilter(size=footprint))


def preprocess_prn_region(
    image: Image.Image,
    *,
    upscale_factor: float = 3.0,
    apply_threshold: bool = True,
    apply_morphology: bool = False,
) -> Image.Image:
    """Full enhancement chain for a small, already-cropped PRN region:
    grayscale -> denoise -> contrast equalize -> sharpen -> upscale ->
    (optional) adaptive threshold -> (optional) morphological cleanup.

    Every step above is independently testable; this just composes them in
    an order that works well for tiny, often low-contrast printed-number
    crops. Each stage is a hook — swap or reorder without touching callers.
    """
    stage = to_grayscale(image)
    stage = denoise(stage)
    stage = equalize_contrast(stage)
    stage = sharpen(stage)
    stage = upscale(stage, upscale_factor)
    if apply_threshold:
        stage = adaptive_threshold(stage)
    if apply_morphology:
        stage = morphological_cleanup(stage)
    return stage
