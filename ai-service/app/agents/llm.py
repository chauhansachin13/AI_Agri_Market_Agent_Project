"""Gemini client wrapper (§4.2.1).

Configuration follows the report: temperature 0.3 — deliberately low to
suppress hallucination while keeping the fluency farmer-facing text needs —
and a 1024-token output ceiling, enough for a full bilingual response.

Two loading paths are attempted, ``langchain-google-genai`` first (needed for
the ``AgentExecutor`` tool-calling loop) and the bare ``google-generativeai``
SDK second (enough for plain completion).  If neither is present the caller
falls back to the deterministic template generator, so answer quality degrades
rather than the service failing.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from ..config import get_settings

logger = logging.getLogger(__name__)


@dataclass
class LLMHandle:
    """A loaded model plus a note on which integration produced it."""

    client: object
    flavour: str  # "langchain" | "genai"

    def complete(self, prompt: str) -> str:
        """Single-turn completion."""
        if self.flavour == "langchain":
            return str(self.client.invoke(prompt).content)  # type: ignore[attr-defined]
        response = self.client.generate_content(prompt)  # type: ignore[attr-defined]
        return str(getattr(response, "text", "") or "")


_handle: LLMHandle | None = None
_load_attempted = False


def get_llm() -> LLMHandle | None:
    """Return a loaded Gemini handle, or ``None`` when unavailable."""
    global _handle, _load_attempted

    if _handle is not None:
        return _handle
    if _load_attempted:
        return None

    _load_attempted = True
    settings = get_settings()
    if not settings.llm_enabled:
        logger.info("LLM disabled: no GEMINI_API_KEY configured (running deterministic pipeline)")
        return None

    try:  # pragma: no cover - requires credentials
        from langchain_google_genai import ChatGoogleGenerativeAI

        client = ChatGoogleGenerativeAI(
            model=settings.gemini_model,
            google_api_key=settings.gemini_api_key,
            temperature=settings.llm_temperature,
            max_output_tokens=settings.llm_max_output_tokens,
        )
        _handle = LLMHandle(client=client, flavour="langchain")
        logger.info("LLM loaded via langchain-google-genai: %s", settings.gemini_model)
        return _handle
    except Exception as exc:
        logger.info("langchain-google-genai unavailable (%s); trying google-generativeai", exc)

    try:  # pragma: no cover - requires credentials
        import google.generativeai as genai

        genai.configure(api_key=settings.gemini_api_key)
        client = genai.GenerativeModel(
            settings.gemini_model,
            generation_config={
                "temperature": settings.llm_temperature,
                "max_output_tokens": settings.llm_max_output_tokens,
            },
        )
        _handle = LLMHandle(client=client, flavour="genai")
        logger.info("LLM loaded via google-generativeai: %s", settings.gemini_model)
        return _handle
    except Exception as exc:
        logger.warning("Gemini unavailable (%s); falling back to deterministic generation", exc)
        return None


def reset_llm() -> None:
    """Drop the cached handle — used by the test suite."""
    global _handle, _load_attempted
    _handle = None
    _load_attempted = False


# The grounding contract every generation prompt inherits.  Section 4.5 makes
# this constraint explicit: the model must never state a price that is not in
# the supplied context, and the fact-check agent verifies compliance.
GROUNDING_RULES = """You are an agricultural market assistant for Indian farmers.

Absolute rules:
1. Never state a price, date or market name that does not appear in the CONTEXT below.
2. If the context does not contain the information needed, say so plainly.
3. Prices are in Indian rupees per quintal (1 quintal = 100 kg).
4. Write for a farmer with limited formal education: short sentences, concrete
   advice, no technical jargon, no English loanwords when a common Hindi word exists.
5. Put the most important price and recommendation in the first two sentences.
"""
