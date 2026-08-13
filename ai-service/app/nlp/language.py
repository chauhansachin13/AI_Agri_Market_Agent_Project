"""Stage 1 of the NLP pipeline: language detection (§4.1.1, extended by §6.3).

The implementation now lives in `app.i18n.detect`, which covers all seven
supported languages rather than only Hindi and English. This module stays as
the pipeline's stable entry point so callers are unaffected by that move.
"""

from __future__ import annotations

from ..i18n.detect import (  # noqa: F401
    detect_language,
    is_code_switched,
    response_language as _response_language,
    script_of,
    script_ratio,
)
from ..schemas import Language


def response_language(detected: Language, text: str = "") -> Language:
    """Language used for the primary answer.

    A farmer who wrote in Bhojpuri is answered in Bhojpuri; a code-switched
    query is answered in its Indic language, never in English.
    """
    return _response_language(detected, text)  # type: ignore[return-value]


__all__ = [
    "detect_language",
    "response_language",
    "is_code_switched",
    "script_of",
    "script_ratio",
]
