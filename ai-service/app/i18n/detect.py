"""Multilingual detection across the seven supported languages.

Two stages, in order:

1. **Script.** Bengali and Tamil have their own Unicode blocks, so a query in
   either is settled immediately. Latin text is English unless romanised
   Indic markers say otherwise.
2. **Markers.** Hindi, Bhojpuri, Maithili and Marathi all use Devanagari, so
   script cannot separate them. Diagnostic function words decide — "बा" is
   Bhojpuri, "अछि" is Maithili, "आहे" is Marathi, and none appears in standard
   Hindi. Hindi is the default when nothing is diagnostic, since it is both the
   most common input and the safest fallback for the Devanagari group.

`langdetect` is consulted last and only for Latin text; the target queries are
short code-switched fragments, which is exactly what it handles worst.
"""

from __future__ import annotations

import re

from .registry import DEVANAGARI_LANGUAGES, LANGUAGES, SCRIPT_RANGES

_DEVANAGARI = re.compile(r"[ऀ-ॿ]")
_BENGALI = re.compile(r"[ঀ-৿]")
_TAMIL = re.compile(r"[஀-௿]")
_LATIN = re.compile(r"[A-Za-z]")

# Romanised Indic that carries no native script but is clearly not English.
ROMANISED_MARKERS: dict[str, tuple[str, ...]] = {
    "hi": (
        "kya", "kitna", "bhav", "bhaav", "kaun", "kharid", "bech", "chahiye",
        "hai", "mera", "mere",
        # Postpositions and common nouns. Without these, "Bhagalpur mein onion
        # ka rate" and "phool gobhi ka daam" were both classified as English.
        "mein", "me", "ka", "ki", "ke", "daam", "mandi", "kisan", "aaj",
        "phool", "gobhi", "mirch", "sarson", "makka",
    ),
    "bho": ("ba", "bate", "ketna", "kawan", "raua", "hamni"),
    "mai": ("achi", "achhi", "katek", "ahaan", "hamar"),
    "mr": ("aahe", "ahe", "kiti", "kasa", "mala", "pahije", "kanda", "cha bhav", "sanga"),
    "bn": ("koto", "dam", "ache", "amar", "kinche"),
    "ta": ("evvalavu", "vilai", "enna", "yaar"),
}


def script_of(text: str) -> str:
    """Dominant script in the text."""
    counts = {
        "devanagari": len(_DEVANAGARI.findall(text)),
        "bengali": len(_BENGALI.findall(text)),
        "tamil": len(_TAMIL.findall(text)),
        "latin": len(_LATIN.findall(text)),
    }
    best = max(counts, key=lambda key: counts[key])
    return best if counts[best] > 0 else "unknown"


def script_ratio(text: str, script: str) -> float:
    pattern = {
        "devanagari": _DEVANAGARI, "bengali": _BENGALI,
        "tamil": _TAMIL, "latin": _LATIN,
    }.get(script)
    if pattern is None:
        return 0.0
    total = sum(
        len(p.findall(text)) for p in (_DEVANAGARI, _BENGALI, _TAMIL, _LATIN)
    )
    return len(pattern.findall(text)) / total if total else 0.0


def _marker_scores(text: str, codes: tuple[str, ...]) -> dict[str, int]:
    """Count diagnostic markers per candidate language."""
    padded = f" {text.lower()} "
    scores: dict[str, int] = {}
    for code in codes:
        spec = LANGUAGES[code]
        hits = 0
        for marker in spec.markers:
            needle = marker.lower()
            # Devanagari has no ASCII word boundary, so containment is checked
            # with explicit spacing for short markers to avoid false positives
            # ("बा" inside "बाजार" must not count as Bhojpuri).
            if len(needle) <= 2 and not needle.isascii():
                if f" {needle} " in padded or padded.endswith(f" {needle} "):
                    hits += 2
            elif needle in padded:
                hits += 2 if len(needle) > 3 else 1

        # Morphological signals count as strongly as a diagnostic word: an
        # inflection is at least as reliable an indicator as a lexical item.
        for pattern in spec.marker_patterns:
            if re.search(pattern, text):
                hits += 2

        scores[code] = hits
    return scores


def detect_language(text: str) -> str:
    """Return the language code for a query."""
    if not text or not text.strip():
        return "en"

    # Presence of an Indic script decides the language, even when Latin
    # characters outnumber it. Romanised place names and English loanwords are
    # long ("Patna", "tomato", "rate"), so a raw character count makes a
    # genuinely Hindi query look English — and answering it in English is
    # exactly the exclusion this system exists to remove.
    for candidate, code in (("bengali", "bn"), ("tamil", "ta")):
        if script_ratio(text, candidate) >= 0.15:
            return code

    script = "devanagari" if script_ratio(text, "devanagari") >= 0.15 else script_of(text)

    if script == "bengali":
        return "bn"
    if script == "tamil":
        return "ta"

    if script == "devanagari":
        scores = _marker_scores(text, DEVANAGARI_LANGUAGES)
        # Hindi is the fallback, so a non-Hindi language must actually out-score
        # it to win; ties go to Hindi.
        best = max(scores, key=lambda code: (scores[code], code != "hi"))
        if scores[best] > scores.get("hi", 0):
            return best
        return "hi"

    # Latin script from here.
    lowered = f" {text.lower()} "
    romanised = {
        code: sum(1 for marker in markers if f" {marker} " in lowered)
        for code, markers in ROMANISED_MARKERS.items()
    }
    best_romanised = max(romanised, key=lambda code: romanised[code])
    if romanised[best_romanised] >= 2:
        return best_romanised

    try:  # pragma: no cover - optional dependency
        from langdetect import DetectorFactory, detect

        DetectorFactory.seed = 0
        code = detect(text)
        if code in LANGUAGES:
            return code
    except Exception:
        pass

    return "en"


def is_code_switched(text: str) -> bool:
    """True when the query mixes an Indic script with Latin.

    Code-switching is the norm in semi-urban speech, and the report specifies
    that such queries are answered in the Indic language rather than English.
    """
    if not text:
        return False
    latin = script_ratio(text, "latin")
    indic = max(
        script_ratio(text, "devanagari"),
        script_ratio(text, "bengali"),
        script_ratio(text, "tamil"),
    )
    return latin > 0.1 and indic > 0.1


def response_language(detected: str, text: str = "") -> str:
    """Language the primary answer is written in.

    A code-switched query is answered in its Indic language, never in English —
    the farmer reached for their own language for the part that mattered.
    """
    if detected in LANGUAGES and detected != "en":
        return detected
    if text and is_code_switched(text):
        script = script_of(text)
        return {"bengali": "bn", "tamil": "ta", "devanagari": "hi"}.get(script, "hi")
    return "en"


__all__ = [
    "detect_language",
    "response_language",
    "is_code_switched",
    "script_of",
    "script_ratio",
    "SCRIPT_RANGES",
]
