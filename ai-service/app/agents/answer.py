"""Answer Generation Agent — bilingual, farmer-friendly output (§4.7).

Two generation paths produce the same schema:

  * **LLM path** — Gemini is prompted with the grounding contract plus the
    assembled context, and asked for Hindi and English answers.
  * **Template path** — deterministic natural-language templates built directly
    from the verified data.

The template path is not a stub. It is the guaranteed-grounded generator: every
number it emits is copied from a fetched record, so it cannot hallucinate by
construction. It runs whenever no LLM is configured, and it is also the safety
net when the LLM's output fails fact-checking.
"""

from __future__ import annotations

import logging

from ..nlp.lexicon import to_devanagari_place
from ..schemas import FactCheckStatus
from .llm import GROUNDING_RULES, get_llm
from .specialists import AgentContext, FactCheckAgent, hindi_crop_label

logger = logging.getLogger(__name__)


# --------------------------------------------------------------------------- #
# Deterministic bilingual templates
# --------------------------------------------------------------------------- #
def _english_answer(context: AgentContext) -> str:
    crop = context.nlp.crop or "your crop"
    where = context.location_label
    sentences: list[str] = []

    if context.prices:
        best = context.prices[0]
        sentences.append(
            f"{crop} is selling at about Rs {best.modal_price:.0f} per quintal at "
            f"{best.market} mandi in {best.district}, the best rate near {where} "
            f"on {best.arrival_date}."
        )
        if len(context.prices) > 1:
            others = context.prices[1:4]
            listed = "; ".join(
                f"{r.market} Rs {r.modal_price:.0f}" for r in others
            )
            sentences.append(f"Other nearby mandis: {listed}.")
    else:
        sentences.append(
            f"No mandi price was reported for {crop} near {where} for the latest arrival day."
        )

    if context.prediction:
        verb = "sell now" if context.prediction.recommendation == "SELL" else "wait"
        reason = context.prediction.reason.rstrip(". ")
        sentences.append(
            f"Our advice is to {verb} — {reason} "
            f"(confidence {context.prediction.confidence * 100:.0f} percent)."
        )

    if context.trend:
        direction = {
            "upward": "rising", "downward": "falling", "stable": "steady"
        }[context.trend.direction]
        sentences.append(
            f"The price has been {direction} over the past few weeks "
            f"(7-day average Rs {context.trend.ema_7:.0f} against "
            f"30-day average Rs {context.trend.ema_30:.0f})."
        )

    if context.buyers:
        names = ", ".join(b.apmc_name for b in context.buyers[:3])
        sentences.append(f"Buyers you can contact near {where}: {names}.")

    if context.degraded:
        sentences.append(
            "Note: the live government feed was not reachable, so these figures come "
            "from the offline reference dataset and should be confirmed at the mandi."
        )

    return " ".join(sentences)


def _hindi_location(context: AgentContext) -> str:
    """Render the location in Devanagari where a known form exists.

    Mandi names themselves stay as Agmarknet publishes them — a farmer looks
    for the name that is painted on the yard gate, not a transliteration.
    """
    location = context.nlp.location
    parts = [to_devanagari_place(location.district), to_devanagari_place(location.state)]
    label = ", ".join(p for p in parts if p)
    if label:
        return label

    # Unresolved location: translate the district set the prices actually came from.
    districts = list(dict.fromkeys(r.district for r in context.prices if r.district))
    if districts:
        translated = [to_devanagari_place(d) or d for d in districts[:3]]
        return ", ".join(translated) + (" और आसपास" if len(districts) > 3 else "")
    return "आपके क्षेत्र"


def _hindi_answer(context: AgentContext) -> str:
    crop = hindi_crop_label(context.nlp.crop)
    where = _hindi_location(context)
    sentences: list[str] = []

    if context.prices:
        best = context.prices[0]
        sentences.append(
            f"{where} के पास {best.market} मंडी में {crop} का भाव लगभग "
            f"{best.modal_price:.0f} रुपये प्रति क्विंटल है। यह {best.arrival_date} का "
            f"सबसे अच्छा रेट है।"
        )
        if len(context.prices) > 1:
            listed = "; ".join(
                f"{r.market} में {r.modal_price:.0f} रुपये" for r in context.prices[1:4]
            )
            sentences.append(f"आसपास की दूसरी मंडियाँ: {listed}।")
    else:
        sentences.append(f"{where} के पास {crop} का कोई ताज़ा मंडी भाव नहीं मिला।")

    if context.prediction:
        if context.prediction.recommendation == "SELL":
            sentences.append(
                f"हमारी सलाह है कि अभी बेच दें। भरोसा "
                f"{context.prediction.confidence * 100:.0f} प्रतिशत।"
            )
        else:
            sentences.append(
                f"हमारी सलाह है कि अभी रुक जाएँ। भरोसा "
                f"{context.prediction.confidence * 100:.0f} प्रतिशत।"
            )

    if context.trend:
        direction = {
            "upward": "बढ़ रहा है", "downward": "घट रहा है", "stable": "एक जैसा है"
        }[context.trend.direction]
        sentences.append(
            f"पिछले कुछ हफ़्तों में भाव {direction} "
            f"(7 दिन का औसत {context.trend.ema_7:.0f} रुपये, "
            f"30 दिन का औसत {context.trend.ema_30:.0f} रुपये)।"
        )

    if context.buyers:
        names = ", ".join(b.apmc_name for b in context.buyers[:3])
        sentences.append(f"{where} के पास खरीदार: {names}।")

    if context.degraded:
        sentences.append(
            "ध्यान दें: सरकारी लाइव आँकड़े अभी नहीं मिल पाए, इसलिए ये भाव संदर्भ डेटा से हैं। "
            "मंडी जाकर एक बार पक्का कर लें।"
        )

    return " ".join(sentences)


# --------------------------------------------------------------------------- #
# LLM-backed generation
# --------------------------------------------------------------------------- #
def _build_context_block(context: AgentContext) -> str:
    lines: list[str] = []

    if context.prices:
        lines.append("LIVE GOVERNMENT MANDI PRICES (the only valid source of price values):")
        for record in context.prices[:10]:
            lines.append(
                f"  - {record.commodity} at {record.market}, {record.district}, "
                f"{record.state} on {record.arrival_date}: modal Rs {record.modal_price:.0f}, "
                f"min Rs {record.min_price:.0f}, max Rs {record.max_price:.0f} per quintal "
                f"[source: {record.source}]"
            )
    else:
        lines.append("LIVE GOVERNMENT MANDI PRICES: none available for this query.")

    if context.trend:
        lines.append(
            f"TREND MODEL: direction {context.trend.direction}, "
            f"EMA-7 Rs {context.trend.ema_7:.0f}, EMA-14 Rs {context.trend.ema_14:.0f}, "
            f"EMA-30 Rs {context.trend.ema_30:.0f}, volatility {context.trend.volatility:.4f}."
        )

    if context.prediction:
        lines.append(
            f"SELL DECISION: {context.prediction.recommendation} at confidence "
            f"{context.prediction.confidence:.2f}. Reason: {context.prediction.reason}"
        )

    if context.buyers:
        lines.append("BUYER CONTACTS:")
        for buyer in context.buyers[:5]:
            lines.append(
                f"  - {buyer.apmc_name}, {buyer.district}: {buyer.address} "
                f"({buyer.trading_hours})"
            )

    if context.retrieved_context:
        lines.append("HISTORICAL CONTEXT:")
        lines += [f"  - {c}" for c in context.retrieved_context[:5]]

    if context.search_snippets:
        lines.append("CURRENT MARKET REPORTING:")
        lines += [f"  - {s}" for s in context.search_snippets[:3]]

    return "\n".join(lines)


_SEPARATOR = "-----HINDI-----"


def _llm_answers(context: AgentContext) -> tuple[str, str] | None:
    handle = get_llm()
    if handle is None:
        return None

    prompt = f"""{GROUNDING_RULES}

FARMER'S QUESTION: {context.query}
DETECTED INTENT: {context.nlp.intent}
LOCATION: {context.location_label}

CONTEXT:
{_build_context_block(context)}

ANALYSIS PREPARED BY THE REASONING AGENT:
{context.narrative}

Write two answers to the farmer's question, separated by a line containing
exactly {_SEPARATOR}. Write the English answer first, then the Hindi answer in
Devanagari script. Each answer should be three to five short sentences.
"""

    try:  # pragma: no cover - requires credentials
        raw = handle.complete(prompt)
        if _SEPARATOR not in raw:
            return None
        english, hindi = raw.split(_SEPARATOR, 1)
        english, hindi = english.strip(), hindi.strip()
        if not english or not hindi:
            return None
        return english, hindi
    except Exception as exc:
        logger.warning("LLM generation failed (%s); using template generator", exc)
        return None


# --------------------------------------------------------------------------- #
# Agent
# --------------------------------------------------------------------------- #
class AnswerGenerationAgent:
    """Produce the bilingual farmer-facing answer, fact-checked before release."""

    name = "Answer Generation"

    def run(self, context: AgentContext) -> tuple[str, str, FactCheckStatus]:
        fact_checker = FactCheckAgent()

        generated = _llm_answers(context)
        if generated is not None:
            english, hindi = generated
            # Anything the model wrote is verified before it is shown.
            fact_checker.run(context, generated_text=f"{english}\n{hindi}")
            status = fact_checker.overall_status(context.claims)
            if status == "insufficient_evidence":
                context.observe(
                    self.name,
                    "Generated text contained an unsupported figure; falling back to the "
                    "grounded template answer.",
                )
                english, hindi = _english_answer(context), _hindi_answer(context)
                fact_checker.run(context, generated_text=english)
                status = fact_checker.overall_status(context.claims)
            else:
                context.observe(self.name, "Produced a bilingual answer from the language model.")
        else:
            english, hindi = _english_answer(context), _hindi_answer(context)
            fact_checker.run(context, generated_text=english)
            status = fact_checker.overall_status(context.claims)
            context.observe(
                self.name, "Produced a bilingual answer from the grounded response templates."
            )

        english = fact_checker.strip_unverified(english, context.claims)
        hindi = fact_checker.strip_unverified(hindi, context.claims)
        return english, hindi, status  # type: ignore[return-value]
