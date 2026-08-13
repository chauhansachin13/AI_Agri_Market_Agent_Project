"""Stage 1 of the NLP pipeline: probabilistic language detection (§4.1.1).

`langdetect` is used when it is installed.  Because the target queries are
short, code-switched Hindi-English fragments — exactly the input `langdetect`
is weakest on — the detector is wrapped in a Devanagari script ratio check
that takes precedence.  A query carrying a meaningful proportion of Devanagari
is Hindi; a query mixing both scripts is reported as ``mixed`` and, per the
report, defaults to Hindi for response generation.
"""

from __future__ import annotations

import re

from ..schemas import Language

_DEVANAGARI = re.compile(r"[ऀ-ॿ]")
_LATIN = re.compile(r"[A-Za-z]")

# Romanised Hindi that carries no Devanagari but is unambiguously Hindi.
_ROMANISED_HINDI_MARKERS = {
    "kya", "kitna", "bhav", "rate kya", "kaun", "kharid", "bech", "chahiye",
    "abhi", "aaj", "mera", "mere", "hai", "hain", "nahi", "mandi", "kisan",
    "pyaz", "gehu", "aloo", "tamatar", "sarson", "bhaav",
}


def _script_ratios(text: str) -> tuple[float, float]:
    deva = len(_DEVANAGARI.findall(text))
    latin = len(_LATIN.findall(text))
    total = deva + latin
    if total == 0:
        return 0.0, 0.0
    return deva / total, latin / total


def _romanised_hindi_score(text: str) -> int:
    lowered = text.lower()
    return sum(1 for marker in _ROMANISED_HINDI_MARKERS if marker in lowered)


def detect_language(text: str) -> Language:
    """Classify a query as ``hi``, ``en`` or ``mixed``."""
    if not text or not text.strip():
        return "en"

    deva_ratio, latin_ratio = _script_ratios(text)

    if deva_ratio >= 0.6:
        return "hi"
    if 0.15 <= deva_ratio < 0.6 and latin_ratio > 0.0:
        return "mixed"
    if 0.0 < deva_ratio < 0.15:
        return "mixed"

    # Pure Latin script from here on.
    if _romanised_hindi_score(text) >= 2:
        return "mixed"

    try:  # pragma: no cover - exercised only when the dependency is installed
        from langdetect import DetectorFactory, detect

        DetectorFactory.seed = 0
        code = detect(text)
        if code == "hi":
            return "hi"
    except Exception:
        pass

    return "en"


def response_language(detected: Language) -> Language:
    """Language used for the primary answer.

    Section 4.1.1: mixed-language queries default to Hindi mode for response
    generation while entity extraction stays language-agnostic.
    """
    return "hi" if detected in ("hi", "mixed") else "en"
