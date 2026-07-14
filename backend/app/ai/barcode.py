"""Barcode / QR decoding for the printed ID card.

Optional and best-effort: if decoding fails for any reason (no barcode
present, unreadable, or the underlying library not installed), the caller
gets `BarcodeResult(decoded=False, ...)` and registration continues
normally — barcode data is never required. This module is attempted
*before* OCR in `pipeline.py`, since a decoded barcode is a cheap,
high-confidence identifier source when the card has one; OCR is the
fallback, not the other way around.

Swappable engine, same pattern as `app/ai/ocr.py`: `BarcodeEngine` is the
interface, `ZxingBarcodeEngine` (default) and `PyzbarBarcodeEngine`
(available, opt-in) are concrete implementations, and `get_barcode_engine()`
is the single factory the rest of this module's `decode_barcode()` calls.
Nothing outside this file needs to know which concrete engine is active.

The `attempted`/`failure_reason`/`rect` fields on `BarcodeResult` exist for
two different reasons: `attempted`/`failure_reason` are development-
visibility only (surfaced on `RegistrationAnalysis` so barcode decoding
can be tuned/debugged independently of OCR); `rect` is consumed internally
by `app/ai/roi.py` to anchor the PRN search region to wherever the barcode
actually is on this capture — it is never exposed on `RegistrationAnalysis`.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from functools import lru_cache

from PIL import Image

from app.ai.schemas import BarcodeResult

Box = tuple[int, int, int, int]


class BarcodeEngine(ABC):
    """Interface every barcode backend must satisfy."""

    @abstractmethod
    def decode(self, image: Image.Image) -> BarcodeResult:
        """Attempt to locate and decode a barcode/QR code in `image`."""
        raise NotImplementedError


def _bounding_box_from_position(position) -> Box | None:
    """`zxing-cpp` reports a (possibly rotated) quadrilateral via its
    `position` attribute, not an axis-aligned rect — reduce it to the
    axis-aligned bounding box `app/ai/roi.py`'s barcode-anchoring expects,
    regardless of how the card/barcode is rotated in frame."""
    if position is None:
        return None
    try:
        points = [position.top_left, position.top_right, position.bottom_left, position.bottom_right]
        xs = [p.x for p in points]
        ys = [p.y for p in points]
        left, top = min(xs), min(ys)
        width, height = max(xs) - left, max(ys) - top
        return (int(left), int(top), int(width), int(height))
    except Exception:
        return None


class ZxingBarcodeEngine(BarcodeEngine):
    """`zxing-cpp`-backed implementation (default engine).

    Chosen specifically to avoid the failure class that motivated
    replacing `pyzbar` as the default: `pyzbar` doesn't bundle the `zbar`
    C library — it locates a *system-installed* `libzbar` shared library
    via `ctypes.util.find_library` at import time, and that lookup is a
    long-standing, well-documented source of "Unable to find zbar shared
    library" errors (Homebrew installing to a non-standard path,
    an architecture mismatch between the Python interpreter and the
    installed dylib on Apple Silicon, etc.) — the library can be fully
    installed and still not be found. `zxing-cpp` statically bundles its
    native decoder *inside* the Python wheel; there is no external shared
    library to locate at runtime, so this entire class of error cannot
    happen once the package itself is installed via pip.

    Imported lazily inside `decode` — importing this *module* must never
    require `zxing-cpp` to be installed, matching the OCR engine pattern
    in `app/ai/ocr.py`. If it's missing, `failure_reason` gives the exact
    `pip install` command needed — no separate system-library install step.
    """

    def decode(self, image: Image.Image) -> BarcodeResult:
        try:
            import zxingcpp
        except Exception as exc:
            return BarcodeResult(
                decoded=False,
                attempted=False,
                status="not_attempted",
                failure_reason=(
                    f"Barcode library unavailable ({exc}). Install it with: pip install zxing-cpp — "
                    "no system library required, the native decoder ships inside the wheel."
                ),
            )

        try:
            results = zxingcpp.read_barcodes(image)
        except Exception as exc:
            return BarcodeResult(
                decoded=False, attempted=True, status="failed", failure_reason=f"Barcode decoding raised an error ({exc})."
            )

        if not results:
            return BarcodeResult(
                decoded=False, attempted=True, status="not_found", failure_reason="No barcode found in the frame."
            )

        first = results[0]
        symbology = str(getattr(first, "format", "")) or None
        rect = _bounding_box_from_position(getattr(first, "position", None))
        data = (getattr(first, "text", None) or "").strip() or None

        if not data:
            return BarcodeResult(
                decoded=False,
                attempted=True,
                status="failed",
                symbology=symbology,
                rect=rect,
                failure_reason="Barcode located but its contents could not be decoded as text.",
            )

        return BarcodeResult(decoded=True, data=data, symbology=symbology, attempted=True, status="decoded", rect=rect)


class PyzbarBarcodeEngine(BarcodeEngine):
    """`pyzbar`-backed implementation (available, not the default).

    Kept as a second concrete `BarcodeEngine` implementation — for anyone
    who already has a working `zbar` install and prefers it — and to
    demonstrate the engine stays swappable, same as `PaddleOcrEngine`
    alongside the default `TesseractOcrEngine` in `app/ai/ocr.py`.
    Requires the system `zbar` shared library (`brew install zbar` /
    `apt-get install libzbar0`) in addition to `pip install pyzbar`; if
    either half is missing or unreachable, `failure_reason` says so.
    """

    def decode(self, image: Image.Image) -> BarcodeResult:
        try:
            from pyzbar.pyzbar import decode
        except Exception as exc:
            return BarcodeResult(
                decoded=False,
                attempted=False,
                status="not_attempted",
                failure_reason=(
                    f"Barcode library unavailable ({exc}). Requires the system zbar library "
                    "(brew install zbar on macOS, apt-get install libzbar0 on Debian/Ubuntu) "
                    "in addition to `pip install pyzbar`."
                ),
            )

        try:
            results = decode(image)
        except Exception as exc:
            return BarcodeResult(
                decoded=False, attempted=True, status="failed", failure_reason=f"Barcode decoding raised an error ({exc})."
            )

        if not results:
            return BarcodeResult(
                decoded=False, attempted=True, status="not_found", failure_reason="No barcode found in the frame."
            )

        first = results[0]
        symbology = getattr(first, "type", None)
        rect_obj = getattr(first, "rect", None)
        rect: Box | None = None
        if rect_obj is not None:
            try:
                rect = (int(rect_obj.left), int(rect_obj.top), int(rect_obj.width), int(rect_obj.height))
            except Exception:
                rect = None

        try:
            data = first.data.decode("utf-8", errors="replace").strip()
        except Exception:
            data = None

        if not data:
            return BarcodeResult(
                decoded=False,
                attempted=True,
                status="failed",
                symbology=symbology,
                rect=rect,
                failure_reason="Barcode located but its contents could not be decoded as text.",
            )

        return BarcodeResult(decoded=True, data=data, symbology=symbology, attempted=True, status="decoded", rect=rect)


@lru_cache
def get_barcode_engine() -> BarcodeEngine:
    """Factory used by the rest of the app — swap the returned type to change engines."""
    return ZxingBarcodeEngine()


def decode_barcode(image: Image.Image) -> BarcodeResult:
    """Backward-compatible entry point (unchanged signature/behavior
    contract used by `pipeline.py`) — delegates to whichever engine
    `get_barcode_engine()` currently returns."""
    return get_barcode_engine().decode(image)
