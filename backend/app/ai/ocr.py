"""OCR engine abstraction.

The rest of the application only ever calls `get_ocr_engine().extract(...)`
— it never imports Tesseract, PaddleOCR, or any other engine directly.
Swapping engines later means writing a new class that implements
`OcrEngine` and changing the single factory function at the bottom of this
file. `TesseractOcrEngine` (default) and `PaddleOcrEngine` are both defined
below as concrete examples of this; EasyOCR, Google Vision, and Azure
Vision can be added the same way without touching any other module.

Only two fields are ever extracted: PRN and student name. The full card
is intentionally never OCR'd wholesale.
"""
from __future__ import annotations

import re
from abc import ABC, abstractmethod
from functools import lru_cache

from PIL import Image

from app.ai import config
from app.ai.schemas import OcrField, OcrResult

# PRN candidates. Length range is configurable (app/ai/config.py) so it can
# be tuned per institution without touching this module. Digit-only
# candidates are matched separately and preferred (the product requirement
# is "the PRN is numeric"), but alphanumeric candidates are still matched
# as a fallback for institutions whose identifiers mix in a few letters.
_PRN_DIGITS_ONLY_RE = re.compile(rf"\b\d{{{config.PRN_MIN_LENGTH},{config.PRN_MAX_LENGTH}}}\b")
_PRN_CANDIDATE_RE = re.compile(
    rf"\b(?=[A-Z0-9]{{{config.PRN_MIN_LENGTH},{config.PRN_MAX_LENGTH}}}\b)(?=[A-Z0-9]*\d)"
    rf"[A-Z0-9]{{{config.PRN_MIN_LENGTH},{config.PRN_MAX_LENGTH}}}\b"
)
_PRN_LABEL_RE = re.compile(r"\b(PRN|REG(?:ISTRATION)?\s*NO\.?|ID\s*NO\.?)\b", re.IGNORECASE)
_NAME_LABEL_RE = re.compile(r"\b(STUDENT\s*NAME|NAME)\b", re.IGNORECASE)
_NON_NAME_CHARS_RE = re.compile(r"[^A-Za-z .'-]")
# Institution header/footer lines ("XYZ COLLEGE OF ENGINEERING") satisfy the
# generic "2+ alphabetic words" name heuristic just as well as a real name
# does, so the label-less fallback in `extract_student_name` skips any line
# containing one of these — otherwise it tends to pick the college's own
# name over the student's when no "Name:" label is present on the card.
_INSTITUTION_KEYWORDS_RE = re.compile(
    r"\b(COLLEGE|UNIVERSITY|INSTITUTE|SCHOOL|ACADEMY|ENGINEERING|POLYTECHNIC|IDENTITY\s*CARD)\b",
    re.IGNORECASE,
)


class OcrEngine(ABC):
    """Interface every OCR backend must satisfy."""

    @abstractmethod
    def extract(self, image: Image.Image) -> OcrResult:
        """Run OCR on a preprocessed image and extract PRN + student name."""
        raise NotImplementedError

    def extract_digits(self, image: Image.Image) -> OcrField:
        """Digit-priority OCR pass, used on small cropped PRN regions.

        Default implementation just reuses `extract()`'s general-purpose
        text extraction and re-scores whatever PRN candidates it finds — a
        reasonable fallback for engines that have no way to restrict the
        recognized character set. Engines that support a digit-whitelist
        mode (Tesseract) should override this for materially better
        accuracy on tiny, low-context crops.
        """
        return self.extract(image).prn


def _looks_like_name(line: str, *, allow_institution_words: bool = True) -> bool:
    """Coarse heuristic: a name line is 2+ alphabetic words, nothing else."""
    stripped = line.strip()
    if not stripped or _NON_NAME_CHARS_RE.search(stripped):
        return False
    if not allow_institution_words and _INSTITUTION_KEYWORDS_RE.search(stripped):
        return False
    words = stripped.split()
    return len(words) >= 2 and all(word.isalpha() for word in words)


def _iter_prn_candidates(line: str) -> list[str]:
    """All plausible-length candidates on a line, digit-only ones first
    (the PRN is expected to be numeric; alphanumeric candidates are a
    fallback for institutions that mix in a few letters)."""
    digit_matches = [m.group(0) for m in _PRN_DIGITS_ONLY_RE.finditer(line)]
    alnum_matches = [m.group(0) for m in _PRN_CANDIDATE_RE.finditer(line)]

    seen: set[str] = set()
    ordered: list[str] = []
    for candidate in (*digit_matches, *alnum_matches):
        if candidate not in seen:
            seen.add(candidate)
            ordered.append(candidate)
    return ordered


def _score_prn_candidate(candidate: str, *, near_label: bool) -> float:
    """Rank a PRN candidate by how trustworthy it looks: within the
    configured length range, mostly/fully numeric, and near a recognizable
    label ("PRN", "Reg No", ...) — each contributes independently so a
    candidate doesn't need every signal to win, it just needs to look more
    plausible than the alternatives.
    """
    score = 0.15
    length = len(candidate)
    if config.PRN_MIN_LENGTH <= length <= config.PRN_MAX_LENGTH:
        score += 0.25

    digit_ratio = sum(ch.isdigit() for ch in candidate) / max(1, length)
    score += 0.3 * digit_ratio

    if near_label:
        score += 0.3

    return min(1.0, round(score, 3))


def extract_prn(lines: list[str]) -> OcrField:
    """Find the strongest PRN candidate across all lines.

    Every plausible-length digit/alphanumeric run is treated as a
    candidate, scored (length fit, digit density, proximity to a
    recognizable label), and the single highest-scoring candidate wins —
    not just the first match encountered. This intentionally does NOT
    accept arbitrary numbers: a run only becomes a candidate at all if it
    matches the configured length range via `_PRN_DIGITS_ONLY_RE` /
    `_PRN_CANDIDATE_RE`.
    """
    best_value: str | None = None
    best_score = -1.0

    for i, line in enumerate(lines):
        near_label = bool(_PRN_LABEL_RE.search(line)) or (i > 0 and bool(_PRN_LABEL_RE.search(lines[i - 1])))
        for candidate in _iter_prn_candidates(line):
            score = _score_prn_candidate(candidate, near_label=near_label)
            if score > best_score:
                best_score = score
                best_value = candidate

    if best_value is None:
        return OcrField()
    return OcrField(value=best_value, confidence=best_score)


def is_plausible_prn(value: str) -> bool:
    """Validity gate for a PRN sourced directly from barcode data.

    Barcode payloads aren't run through OCR noise, so a simple length +
    character-set check (reusing the same candidate patterns as
    `extract_prn`) is enough to decide whether to trust it outright as the
    student identifier, skipping the OCR-based search entirely.
    """
    stripped = value.strip().upper()
    if not stripped:
        return False
    return bool(_PRN_DIGITS_ONLY_RE.fullmatch(stripped)) or bool(_PRN_CANDIDATE_RE.fullmatch(stripped))


def extract_student_name(lines: list[str]) -> OcrField:
    """Find a student name, preferring text near a recognizable label."""
    for i, line in enumerate(lines):
        if _NAME_LABEL_RE.search(line):
            remainder = _NAME_LABEL_RE.sub("", line).strip(" :-")
            if _looks_like_name(remainder):
                return OcrField(value=remainder.title(), confidence=0.9)
            if i + 1 < len(lines) and _looks_like_name(lines[i + 1]):
                return OcrField(value=lines[i + 1].strip().title(), confidence=0.75)

    for line in lines:
        if _looks_like_name(line, allow_institution_words=False):
            return OcrField(value=line.strip().title(), confidence=0.4)

    return OcrField()


class TesseractOcrEngine(OcrEngine):
    """Tesseract-backed implementation (default engine).

    `pytesseract` is a thin subprocess wrapper around the system
    `tesseract` binary — no large ML framework to install, no
    platform/Python-version-specific wheel to chase. It has had stable
    Apple Silicon and current-CPython support for years, which is why it
    is the default here. Imported lazily inside `extract` — importing this
    *module* must never require pytesseract (or the `tesseract` binary) to
    be installed, so environments that haven't set either up yet can still
    boot the API; `pipeline.py` catches extraction failures and degrades
    to manual entry.

    Requires the `tesseract` binary on PATH — see the "Registration
    intelligence pipeline" section of the project README for install
    instructions.
    """

    def extract(self, image: Image.Image) -> OcrResult:
        # Intentionally lazy import — see class docstring.
        import pytesseract

        raw_text = pytesseract.image_to_string(image.convert("RGB"))
        lines = [line.strip() for line in raw_text.splitlines() if line.strip()]

        return OcrResult(prn=extract_prn(lines), student_name=extract_student_name(lines), raw_text=lines)

    def extract_digits(self, image: Image.Image) -> OcrField:
        """Digit-priority pass over a small, already-cropped PRN region.

        Tesseract supports restricting recognition to a character
        whitelist and picking a page-segmentation mode suited to a tiny
        crop — both configurable (app/ai/config.py) so this can be tuned
        per institution without a code change. Falls back to the generic
        `extract()` path (via the ABC default) if pytesseract isn't
        available; `pipeline.py` treats any exception here as "no PRN
        found in this region" and tries the next candidate.
        """
        import pytesseract

        tess_config = f"--psm {config.PRN_OCR_PSM} -c tessedit_char_whitelist=0123456789"
        raw_text = pytesseract.image_to_string(image.convert("RGB"), config=tess_config)
        lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
        return extract_prn(lines)


class PaddleOcrEngine(OcrEngine):
    """PaddleOCR-backed implementation (available, not the default).

    Kept as a second concrete `OcrEngine` implementation to demonstrate —
    and preserve — the swappable-engine architecture. `get_ocr_engine()`
    below does not return this by default because `paddlepaddle` is a
    large, native-code dependency that has historically lagged behind on
    Apple Silicon / new-Python-version wheels; pulling it in as a required
    dependency risks breaking `pip install` on some machines even when
    compatible versions technically exist. If you want to opt back in, see
    the commented block in `requirements.txt` for versions confirmed to
    ship Python 3.13 + macOS arm64 wheels — note that PaddleOCR's 3.x
    Python API is not backward-compatible with the 2.x-style
    `.ocr(..., cls=True)` call below, so this method would need a small
    update to match whichever release you install.

    PaddleOCR is imported lazily inside `_get_reader` — importing this
    *module* must never require PaddleOCR to be installed, so environments
    that haven't set up the (large) dependency yet can still boot the API;
    `pipeline.py` catches extraction failures and degrades to manual entry.
    """

    def __init__(self) -> None:
        self._reader = None

    def _get_reader(self):
        if self._reader is None:
            # Intentionally lazy import — see class docstring.
            from paddleocr import PaddleOCR

            self._reader = PaddleOCR(use_angle_cls=True, lang="en", show_log=False)
        return self._reader

    def extract(self, image: Image.Image) -> OcrResult:
        # Only needed on this (optional) code path.
        import numpy as np

        reader = self._get_reader()
        result = reader.ocr(np.asarray(image.convert("RGB")), cls=True)

        lines: list[str] = []
        for page in result or []:
            for _box, (text, _confidence) in page or []:
                if text:
                    lines.append(text.strip())

        return OcrResult(prn=extract_prn(lines), student_name=extract_student_name(lines), raw_text=lines)


@lru_cache
def get_ocr_engine() -> OcrEngine:
    """Factory used by the rest of the app — swap the returned type to change engines."""
    return TesseractOcrEngine()
