"""Answer Generation Agent — multilingual, farmer-friendly output (§4.7, §6.3).

Two generation paths produce the same schema:

  * **LLM path** — Gemini is prompted with the grounding contract plus the
    assembled context, and asked for the answer in the farmer's language.
  * **Template path** — deterministic templates from the language registry,
    filled directly from the verified data.

The template path is not a stub. It is the guaranteed-grounded generator:
every number it emits is copied from a fetched record, so it cannot
hallucinate by construction, and because only numbers and proper nouns cross
the language boundary, no figure can be corrupted in translation. It runs
whenever no LLM is configured, for every language without exception, and it is
also the safety net when the LLM's output fails fact-checking.
"""

from __future__ import annotations

import logging

from ..i18n.registry import crop_label, get_language, template
from ..nlp.lexicon import localise_place
from ..schemas import FactCheckStatus, Language
from .llm import GROUNDING_RULES, get_llm
from .specialists import AgentContext, FactCheckAgent

logger = logging.getLogger(__name__)

def _format_number(value: float) -> str:
    return f"{value:.0f}"


def _location_label(context: AgentContext, language: str) -> str:
    """Location in the reader's own script.

    Bengali and Tamil were previously left in Latin here, so a Tamil answer
    read "Gaya, Muzaffarpur, Patna அருகே" — half the sentence in the wrong
    script.
    """
    location = context.nlp.location
    parts = [
        localise_place(location.district, language),
        localise_place(location.state, language),
    ]
    label = ", ".join(p for p in parts if p)
    if label:
        return label

    # Unresolved: name the districts the prices actually came from.
    districts = list(dict.fromkeys(r.district for r in context.prices if r.district))
    if districts:
        translated = [localise_place(d, language) or d for d in districts[:3]]
        return ", ".join(translated)

    return context.location_label


# --------------------------------------------------------------------------- #
# Template generation
# --------------------------------------------------------------------------- #
def render_answer(context: AgentContext, language: str) -> str:
    """Assemble the answer for one language from the registry templates."""
    crop = crop_label(language, context.nlp.crop)
    where = _location_label(context, language)
    sentences: list[str] = []

    if context.prices:
        best = context.prices[0]
        sentences.append(
            template(language, "price").format(
                crop=crop,
                price=_format_number(best.modal_price),
                market=best.market,
                district=best.district,
                where=where,
                date=best.arrival_date,
            )
        )
        if len(context.prices) > 1:
            listed = "; ".join(
                f"{r.market} {_format_number(r.modal_price)}" for r in context.prices[1:4]
            )
            sentences.append(template(language, "others").format(listed=listed))
    else:
        sentences.append(template(language, "none").format(crop=crop, where=where))

    if context.prediction:
        key = "sell" if context.prediction.recommendation == "SELL" else "wait"
        sentences.append(
            template(language, key).format(
                reason=context.prediction.reason.rstrip(". "),
                confidence=f"{context.prediction.confidence * 100:.0f}",
            )
        )

    if context.trend:
        direction = template(
            language,
            {"upward": "rising", "downward": "falling", "stable": "steady"}[
                context.trend.direction
            ],
        )
        sentences.append(
            template(language, "trend").format(
                direction=direction,
                ema7=_format_number(context.trend.ema_7),
                ema30=_format_number(context.trend.ema_30),
            )
        )

    if context.forecast and context.forecast.points:
        final = context.forecast.points[-1]
        change = context.forecast.expected_change_pct
        sentences.append(
            template(language, "forecast").format(
                value=_format_number(final.value),
                horizon=final.horizon,
                change=f"{change:+.1f}" if change is not None else "0.0",
                lower=_format_number(final.lower),
                upper=_format_number(final.upper),
            )
        )

    # Weather is only worth a sentence when it actually implies something.
    if context.weather and context.weather.supply_risk != "normal":
        note = context.weather.summary_hi if language != "en" else context.weather.summary
        sentences.append(template(language, "weather").format(weather=note))

    if context.buyers:
        names = ", ".join(b.apmc_name for b in context.buyers[:3])
        sentences.append(template(language, "buyers").format(where=where, names=names))

    if context.degraded:
        sentences.append(template(language, "degraded"))

    return " ".join(s for s in sentences if s)


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

    if context.forecast and context.forecast.points:
        final = context.forecast.points[-1]
        lines.append(
            f"TRAINED FORECAST ({context.forecast.model}): Rs {final.value:.0f} per quintal "
            f"in {final.horizon} days, 95% interval Rs {final.lower:.0f}-{final.upper:.0f}, "
            f"backtested error {context.forecast.mape}%."
        )

    if context.weather:
        lines.append(
            f"WEATHER ({context.weather.source}): {context.weather.summary} "
            f"Supply risk {context.weather.supply_risk}, price pressure "
            f"{context.weather.price_pressure}."
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


_SEPARATOR = "-----NEXT-----"


def _llm_answers(context: AgentContext, languages: list[str]) -> dict[str, str] | None:
    """Ask the model for the answer in each requested language."""
    handle = get_llm()
    if handle is None:
        return None

    named = [get_language(code) for code in languages]
    instructions = "\n".join(
        f"{index + 1}. {spec.english_name} ({spec.name}), written in its own script"
        for index, spec in enumerate(named)
    )

    prompt = f"""{GROUNDING_RULES}

FARMER'S QUESTION: {context.query}
DETECTED INTENT: {context.nlp.intent}
LOCATION: {context.location_label}

CONTEXT:
{_build_context_block(context)}

ANALYSIS PREPARED BY THE REASONING AGENT:
{context.narrative}

Write the answer to the farmer's question in each of these languages, in this
order, separated by a line containing exactly {_SEPARATOR}:

{instructions}

Each answer should be three to five short sentences. Do not label them.
"""

    try:  # pragma: no cover - requires credentials
        raw = handle.complete(prompt)
        parts = [part.strip() for part in raw.split(_SEPARATOR)]
        if len(parts) < len(languages) or not all(parts[: len(languages)]):
            return None
        return dict(zip(languages, parts))
    except Exception as exc:
        logger.warning("LLM generation failed (%s); using template generator", exc)
        return None


# --------------------------------------------------------------------------- #
# Agent
# --------------------------------------------------------------------------- #
class AnswerGenerationAgent:
    """Produce the farmer-facing answers, fact-checked before release."""

    name = "Answer Generation"

    def _target_languages(self, context: AgentContext) -> list[str]:
        """The farmer's own language, plus the two the report's schema requires.

        English and Hindi are always produced so `english_answer` and
        `hindi_answer` stay populated for clients written against Section 4.7,
        even when the farmer wrote in Tamil.
        """
        primary = context.response_language
        ordered = [primary]
        for code in ("en", "hi"):
            if code not in ordered:
                ordered.append(code)
        return ordered

    def run(self, context: AgentContext) -> tuple[dict[str, str], Language, FactCheckStatus]:
        fact_checker = FactCheckAgent()
        languages = self._target_languages(context)
        primary = languages[0]

        generated = _llm_answers(context, languages)
        if generated is not None:
            fact_checker.run(context, generated_text="\n".join(generated.values()))
            status = fact_checker.overall_status(context.claims)
            if status == "insufficient_evidence":
                context.observe(
                    self.name,
                    "Generated text contained an unsupported figure; falling back to the "
                    "grounded template answer.",
                )
                generated = None
            else:
                context.observe(
                    self.name,
                    f"Produced answers in {', '.join(languages)} from the language model.",
                )

        if generated is None:
            generated = {code: render_answer(context, code) for code in languages}
            fact_checker.run(context, generated_text=generated[primary])
            status = fact_checker.overall_status(context.claims)
            context.observe(
                self.name,
                f"Produced answers in {', '.join(languages)} from the grounded "
                f"response templates.",
            )

        cleaned = {
            code: fact_checker.strip_unverified(text, context.claims)
            for code, text in generated.items()
        }
        return cleaned, primary, status  # type: ignore[return-value]
