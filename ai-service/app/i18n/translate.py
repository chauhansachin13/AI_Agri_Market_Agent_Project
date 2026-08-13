"""Translation layer (Section 6.3, NLLB-200 / IndicBERT).

Three strategies, tried in order:

1. **Templates** — the default. Answers are assembled from per-language
   templates whose slots hold numbers and proper nouns only. Nothing is
   machine-translated, so no figure can be corrupted in translation and the
   phrasing stays natural to each language.
2. **NLLB-200** — used for free text that has no template, notably an
   LLM-written answer. Loaded only if `transformers` is installed.
3. **Passthrough** — return the source text, marked untranslated, rather than
   emit a mistranslated price.

The ordering is deliberate. Machine translation of a sentence containing "Rs
2,714 per quintal" is a real risk to a farmer if the number is mangled; the
template path removes that risk entirely for the answers that matter most.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from ..config import get_settings
from .registry import LANGUAGES, get_language

logger = logging.getLogger(__name__)

# NLLB-200 uses FLORES-200 language codes.
NLLB_CODES: dict[str, str] = {
    "en": "eng_Latn",
    "hi": "hin_Deva",
    "bho": "bho_Deva",
    "mai": "mai_Deva",
    "mr": "mar_Deva",
    "bn": "ben_Beng",
    "ta": "tam_Taml",
}


@dataclass
class Translation:
    text: str
    source: str          # "template" | "nllb" | "passthrough"
    translated: bool


_pipeline_cache: dict[tuple[str, str], object] = {}
_load_failed = False


def _nllb_translate(text: str, source: str, target: str) -> str | None:  # pragma: no cover
    """Translate with NLLB-200 if transformers is available."""
    global _load_failed
    if _load_failed:
        return None

    source_code = NLLB_CODES.get(source)
    target_code = NLLB_CODES.get(target)
    if not source_code or not target_code:
        return None

    key = (source_code, target_code)
    try:
        pipe = _pipeline_cache.get(key)
        if pipe is None:
            from transformers import pipeline

            pipe = pipeline(
                "translation",
                model="facebook/nllb-200-distilled-600M",
                src_lang=source_code,
                tgt_lang=target_code,
                max_length=512,
            )
            _pipeline_cache[key] = pipe

        result = pipe(text)
        return str(result[0]["translation_text"]) if result else None
    except Exception as exc:
        logger.info("NLLB-200 unavailable (%s); using template output only", exc)
        _load_failed = True
        return None


def translate(text: str, source: str, target: str) -> Translation:
    """Translate free text between supported languages."""
    if not text or source == target:
        return Translation(text=text, source="passthrough", translated=False)

    if target not in LANGUAGES or source not in LANGUAGES:
        return Translation(text=text, source="passthrough", translated=False)

    settings = get_settings()
    if not settings.offline_mode:
        rendered = _nllb_translate(text, source, target)
        if rendered:
            return Translation(text=rendered, source="nllb", translated=True)

    return Translation(text=text, source="passthrough", translated=False)


def available() -> bool:
    """Whether neural translation can be used in this environment."""
    if get_settings().offline_mode or _load_failed:
        return False
    try:  # pragma: no cover - optional dependency
        import transformers  # noqa: F401

        return True
    except Exception:
        return False


def reset() -> None:
    """Drop cached pipelines — used by the test suite."""
    global _load_failed
    _pipeline_cache.clear()
    _load_failed = False


def language_options() -> list[dict[str, str]]:
    """The language picker payload for the frontend."""
    return [
        {
            "code": spec.code,
            "name": spec.name,
            "english_name": spec.english_name,
            "script": spec.script,
            "speech_tag": spec.speech_tag,
            "has_templates": bool(spec.templates),
        }
        for spec in (get_language(code) for code in LANGUAGES)
    ]
