"""Registration intelligence pipeline.

This package is intentionally self-contained: nothing outside `app.ai`
should be imported here, and nothing in here should import from
`app.api`, `app.models`, or `app.schemas`. The only supported entry
point for the rest of the application is `analyze_registration_photo`
from `app.ai.pipeline` — callers never need to know which OCR engine,
detector, or quality heuristics are used underneath.

Modules:
    schemas.py     Pydantic contracts shared across the pipeline.
    config.py       Institution-agnostic, env-overridable tuning constants.
    quality.py      Pre-OCR image quality gate (resolution/blur/brightness/glare/coverage).
    preprocess.py   Whole-card normalize/resize chain + a separate PRN-region enhancement chain.
    detector.py     Lightweight heuristic ID-card presence check + card bounding box estimate.
    roi.py           Locates likely PRN crop regions (barcode-relative, then configurable fallback bands).
    ocr.py           Replaceable OCR engine interface (Tesseract by default; PaddleOCR available).
    barcode.py       Best-effort barcode/QR decoding, attempted before OCR (never blocks registration).
    pipeline.py      Orchestrates the above into a RegistrationAnalysis.
"""
from app.ai.pipeline import analyze_registration_photo
from app.ai.schemas import RegistrationAnalysis

__all__ = ["analyze_registration_photo", "RegistrationAnalysis"]
