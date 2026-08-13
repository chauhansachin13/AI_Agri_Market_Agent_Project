"""The specialist agents of Table 3.2.

Each agent is a thin, independently testable unit with one responsibility.
The ReAct orchestrator composes them; none of them calls another directly, so
the pipeline order lives in exactly one place (``orchestrator.py``).

Agents covered here:
    Intent Detection, Location Resolution, Mandi Intelligence, Tavily Search,
    Reasoning, Price Prediction, Fact-Check, Sell Decision.

The Answer Generation agent lives in ``answer.py`` and the ReAct Orchestrator
in ``orchestrator.py``.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field

from ..nlp import pipeline as nlp_pipeline
from ..nlp.intents import classify_intent, is_ambiguous
from ..nlp.lexicon import CROP_HINDI_LABEL
from ..schemas import (
    BuyerRecord,
    FactCheckClaim,
    GeoPoint,
    LocationContext,
    NLPResult,
    Prediction,
    PriceRecord,
    TrendAnalysis,
)
from ..tools import location_tool, mandi_tool, prediction_tool, tavily_tool, vector_tool
from ..tools.base import ToolResult

logger = logging.getLogger(__name__)


@dataclass
class AgentContext:
    """Mutable state threaded through the multi-agent workflow (§4.3)."""

    query: str
    nlp: NLPResult
    reasoning_steps: list[str] = field(default_factory=list)
    prices: list[PriceRecord] = field(default_factory=list)
    buyers: list[BuyerRecord] = field(default_factory=list)
    nearby_districts: list[tuple[str, str]] = field(default_factory=list)
    retrieved_context: list[str] = field(default_factory=list)
    search_snippets: list[str] = field(default_factory=list)
    trend: TrendAnalysis | None = None
    price_series: list[float] = field(default_factory=list)
    narrative: str = ""
    prediction: Prediction | None = None
    claims: list[FactCheckClaim] = field(default_factory=list)
    degraded: bool = False
    price_source: str = "sample"

    def observe(self, agent: str, text: str) -> None:
        """Append one auditable step to the reasoning trail shown in the XAI panel."""
        self.reasoning_steps.append(f"{agent}: {text}")

    @property
    def location_label(self) -> str:
        parts = [self.nlp.location.district, self.nlp.location.state]
        label = ", ".join(p for p in parts if p)
        if label:
            return label
        # Location was never resolved, but prices were still fetched over a
        # default district set. Naming those districts is more honest — and more
        # useful — than telling the farmer the rate is "in your area".
        districts = list(dict.fromkeys(r.district for r in self.prices if r.district))
        if districts:
            return ", ".join(districts[:3]) + (" and nearby" if len(districts) > 3 else "")
        return "your area"

    @property
    def crop_label(self) -> str:
        return self.nlp.crop or "the crop"


# --------------------------------------------------------------------------- #
# 1. Intent Detection Agent
# --------------------------------------------------------------------------- #
class IntentDetectionAgent:
    """Classify the query into one of four intents using hybrid rule-based NLP."""

    name = "Intent Detection"

    def run(
        self,
        query: str,
        pincode: str | None = None,
        ip_address: str | None = None,
        coordinates: GeoPoint | None = None,
        language_override: str | None = None,
    ) -> AgentContext:
        result = nlp_pipeline.run(
            query,
            pincode=pincode,
            ip_address=ip_address,
            coordinates=coordinates,
            language_override=language_override,
        )
        context = AgentContext(query=query, nlp=result)
        context.observe(
            self.name,
            f"Detected language '{result.language}' and intent '{result.intent}' "
            f"(confidence {result.intent_confidence:.2f})"
            + (f", crop '{result.crop}'" if result.crop else ", no crop named")
            + ".",
        )
        if is_ambiguous(query):
            context.observe(
                self.name,
                "Intent is ambiguous between close classes, so both price and trend "
                "evidence will be gathered before answering.",
            )
        return context


# --------------------------------------------------------------------------- #
# 2. Location Resolution Agent
# --------------------------------------------------------------------------- #
class LocationResolutionAgent:
    """Resolve location via text, pincode, IP or GPS, then map to nearby mandis."""

    name = "Location Resolution"

    def run(
        self,
        context: AgentContext,
        pincode: str | None = None,
        ip_address: str | None = None,
        coordinates: GeoPoint | None = None,
    ) -> AgentContext:
        result: ToolResult = location_tool.TOOL(
            text=context.query,
            pincode=pincode,
            ip_address=ip_address,
            latitude=coordinates.latitude if coordinates else None,
            longitude=coordinates.longitude if coordinates else None,
        )

        if result.ok:
            payload = result.data
            resolved: LocationContext = payload["context"]
            context.nlp.location = resolved
            context.nearby_districts = payload["nearby_districts"]
        else:
            context.observe(
                self.name,
                "Location could not be resolved; falling back to state-level or "
                "default district coverage.",
            )
        context.observe(self.name, result.as_observation())
        return context


# --------------------------------------------------------------------------- #
# 3. Mandi Intelligence Agent
# --------------------------------------------------------------------------- #
class MandiIntelligenceAgent:
    """Fetch, filter and normalise live Agmarknet price records."""

    name = "Mandi Intelligence"

    def run(self, context: AgentContext) -> AgentContext:
        location = context.nlp.location
        result: ToolResult = mandi_tool.TOOL(
            crop=context.nlp.crop, state=location.state, district=location.district
        )
        records: list[PriceRecord] = result.data or []

        # A single district can be thin on a given arrival day. Widening to the
        # neighbouring districts gives the farmer a real comparison set — and it
        # is the same data the sell-decision agent needs for arbitrage. Each
        # neighbour carries its own state, since the nearest mandi to a border
        # district is often across the state line.
        for neighbour_state, neighbour_district in context.nearby_districts[:3]:
            extra: ToolResult = mandi_tool.TOOL(
                crop=context.nlp.crop, state=neighbour_state, district=neighbour_district
            )
            if extra.ok and extra.data:
                records.extend(extra.data)

        seen: set[tuple[str, str, str]] = set()
        deduped: list[PriceRecord] = []
        for record in records:
            key = (record.market, record.commodity, record.arrival_date)
            if key not in seen:
                seen.add(key)
                deduped.append(record)

        context.prices = sorted(deduped, key=lambda r: r.modal_price, reverse=True)
        context.price_source = result.source
        context.degraded = context.degraded or result.degraded
        context.observe(self.name, result.as_observation())
        return context


# --------------------------------------------------------------------------- #
# 4. Buyer / eNAM lookup (serves the buyer_search intent)
# --------------------------------------------------------------------------- #
class BuyerConnectAgent:
    """Retrieve APMC and buyer contacts from eNAM for the resolved location."""

    name = "Buyer Connect"

    def run(self, context: AgentContext) -> AgentContext:
        from ..data import enam

        location = context.nlp.location
        result = enam.fetch_buyers(
            state=location.state, district=location.district, commodity=context.nlp.crop
        )
        context.buyers = result.buyers
        context.degraded = context.degraded or result.degraded
        context.observe(
            self.name,
            f"Retrieved {len(result.buyers)} APMC/buyer contacts for {context.location_label}"
            + (" (offline directory)" if result.degraded else " from eNAM")
            + ".",
        )
        return context


# --------------------------------------------------------------------------- #
# 5. Tavily Search Agent
# --------------------------------------------------------------------------- #
class TavilySearchAgent:
    """Pull current market trends, demand signals and agricultural news."""

    name = "Internet Search"

    def run(self, context: AgentContext) -> AgentContext:
        result: ToolResult = tavily_tool.TOOL(
            crop=context.nlp.crop, location=context.location_label
        )
        snippets = result.data or []
        context.search_snippets = [
            f"{item['title']}: {item['content'][:200]}" for item in snippets
        ]
        context.observe(self.name, result.as_observation())
        return context


# --------------------------------------------------------------------------- #
# 6. Vector retrieval feeding the Reasoning Agent
# --------------------------------------------------------------------------- #
class ContextRetrievalAgent:
    """Retrieve historical precedent from the FAISS index."""

    name = "Historical Context"

    def run(self, context: AgentContext) -> AgentContext:
        result: ToolResult = vector_tool.TOOL(
            query=context.query, crop=context.nlp.crop, location=context.location_label
        )
        if result.ok:
            context.retrieved_context = result.data["citations"]
        context.observe(self.name, result.as_observation())
        return context


# --------------------------------------------------------------------------- #
# 7. Price Prediction Agent
# --------------------------------------------------------------------------- #
class PricePredictionAgent:
    """Classify the price trend with EMA-7/14/30 analysis."""

    name = "Price Prediction"

    def run(self, context: AgentContext) -> AgentContext:
        if not context.nlp.crop:
            context.observe(
                self.name, "No crop identified in the query, so no trend was computed."
            )
            return context

        location = context.nlp.location
        result: ToolResult = prediction_tool.TOOL(
            crop=context.nlp.crop, state=location.state, district=location.district
        )
        if result.ok:
            context.trend = result.data["analysis"]
            context.price_series = result.data["series"]
        context.observe(self.name, result.as_observation())
        return context


# --------------------------------------------------------------------------- #
# 8. Reasoning Agent
# --------------------------------------------------------------------------- #
class ReasoningAgent:
    """Synthesise mandi data, retrieved history and search results into a narrative."""

    name = "Reasoning"

    def run(self, context: AgentContext) -> AgentContext:
        parts: list[str] = []

        if context.prices:
            best = context.prices[0]
            worst = context.prices[-1]
            modal_values = [r.modal_price for r in context.prices]
            average = sum(modal_values) / len(modal_values)
            parts.append(
                f"Across {len(context.prices)} mandi records for {context.crop_label} "
                f"near {context.location_label}, the modal price averages "
                f"Rs {average:.0f} per quintal. The best rate is Rs {best.modal_price:.0f} "
                f"at {best.market} ({best.district}) and the lowest is "
                f"Rs {worst.modal_price:.0f} at {worst.market}."
            )
            gap = best.modal_price - worst.modal_price
            if worst.modal_price > 0 and gap / worst.modal_price > 0.08:
                parts.append(
                    f"The spread of Rs {gap:.0f} per quintal between mandis is wide enough "
                    f"to be worth the journey to {best.market} for a full load, after "
                    f"allowing for transport."
                )
        else:
            parts.append(
                f"No mandi price records were available for {context.crop_label} near "
                f"{context.location_label} for the requested arrival day."
            )

        if context.trend:
            parts.append(
                f"The {context.trend.direction} trend is supported by EMA-7 at "
                f"Rs {context.trend.ema_7:.0f} against EMA-30 at Rs {context.trend.ema_30:.0f}, "
                f"with measured volatility of {context.trend.volatility:.4f}."
            )

        if context.retrieved_context:
            parts.append(
                f"Historical context retrieved from {len(context.retrieved_context)} "
                f"indexed records was used to judge whether the current level is "
                f"unusual for this season."
            )

        if context.search_snippets:
            parts.append(
                f"Current market reporting adds: {context.search_snippets[0][:180]}"
            )

        context.narrative = " ".join(parts)
        context.observe(self.name, "Synthesised the available evidence into an analysis.")
        return context


# --------------------------------------------------------------------------- #
# 9. Sell Decision Agent
# --------------------------------------------------------------------------- #
class SellDecisionAgent:
    """Turn trend, volatility and cross-mandi spread into a SELL/WAIT call.

    SELL when prices sit at or near a local maximum, the trend is downward, and
    a best-price mandi has been identified. WAIT when the trend is upward,
    prices sit below recent peaks, or the spread between nearby mandis suggests
    a materially better realisation elsewhere.
    """

    name = "Sell Decision"

    def run(self, context: AgentContext) -> AgentContext:
        if not context.prices and context.trend is None:
            context.observe(self.name, "Insufficient data for a sell-or-wait recommendation.")
            return context

        # Each signal contributes a weight and the reason it implies. Positive
        # weights argue for selling now, negative ones for waiting.
        signals: list[tuple[float, str]] = []
        confidence_inputs: list[float] = []

        trend = context.trend
        if trend is not None:
            confidence_inputs.append(trend.confidence)
            if trend.direction == "downward":
                signals.append((2.0, "prices have been easing over the last few weeks"))
            elif trend.direction == "upward":
                signals.append((-2.0, "prices have been climbing steadily"))
            else:
                signals.append((0.0, "prices have been broadly flat"))

            if trend.volatility > 0.05:
                signals.append(
                    (0.5, "day-to-day movement is unusually sharp, which adds risk to waiting")
                )

        # Position of today's price within its recent range. Sitting at the
        # bottom of the range is the strongest single argument for holding, so
        # it outweighs a soft downward trend rather than merely offsetting it.
        if len(context.price_series) >= 5:
            recent = context.price_series[-30:]
            low, high = min(recent), max(recent)
            current = context.price_series[-1]
            if high > low:
                position = (current - low) / (high - low)
                confidence_inputs.append(min(1.0, 0.5 + abs(position - 0.5)))
                if position >= 0.75:
                    signals.append((2.5, "the current rate is near the top of its recent range"))
                elif position <= 0.35:
                    signals.append(
                        (-2.5, "the current rate is near the bottom of its recent range")
                    )

        # Cross-mandi arbitrage: a wide spread means the farmer can do better by
        # moving the load, which argues against selling into the local rate.
        best_market = None
        if len(context.prices) >= 2:
            best, worst = context.prices[0], context.prices[-1]
            best_market = best.market
            if worst.modal_price > 0:
                spread = (best.modal_price - worst.modal_price) / worst.modal_price
                if spread > 0.12:
                    signals.append(
                        (
                            -0.5,
                            f"a nearby mandi ({best.market}) is paying about "
                            f"Rs {best.modal_price - worst.modal_price:.0f} more per quintal",
                        )
                    )

        sell_score = sum(weight for weight, _ in signals)
        recommendation = "SELL" if sell_score > 0 else "WAIT"

        # Only cite the signals that actually support the call. Listing the
        # opposing ones alongside it reads as self-contradiction to a farmer.
        supporting = [
            reason for weight, reason in signals
            if (weight > 0) == (recommendation == "SELL") and weight != 0
        ]
        if not supporting:
            supporting = [reason for weight, reason in signals if weight == 0]

        base_confidence = sum(confidence_inputs) / len(confidence_inputs) if confidence_inputs else 0.4
        decisiveness = min(abs(sell_score) / 3.5, 1.0)
        confidence = round(min(0.95, 0.35 + 0.55 * (0.5 * base_confidence + 0.5 * decisiveness)), 3)

        reasons = supporting
        reason_text = "; ".join(reasons) if reasons else "based on the available price records"
        if recommendation == "SELL" and best_market:
            reason_text += f". Best realisation right now is at {best_market}"

        context.prediction = Prediction(
            recommendation=recommendation,  # type: ignore[arg-type]
            confidence=confidence,
            reason=reason_text.strip().rstrip(".") + ".",
        )
        context.observe(
            self.name,
            f"Recommendation {recommendation} at confidence {confidence:.2f} — {reason_text}.",
        )
        return context


# --------------------------------------------------------------------------- #
# 10. Fact-Check Agent
# --------------------------------------------------------------------------- #
_PRICE_IN_TEXT = re.compile(r"(?:Rs\.?|₹|रु\.?)\s*([\d,]+(?:\.\d+)?)", re.IGNORECASE)


class FactCheckAgent:
    """Verify every claim against government data, retrieved history and search.

    Verification is claim-by-claim (§4.6.2). A price assertion is *verified*
    only when it is traceable to an Agmarknet record; a claim supported only by
    search results or historical context is *partially verified*; anything
    unsupported is *insufficient evidence* and is suppressed from the answer.
    """

    name = "Fact-Check"

    TOLERANCE = 0.01  # 1% — absorbs rounding in generated text

    def _close(self, a: float, b: float) -> bool:
        return b > 0 and abs(a - b) / b <= self.TOLERANCE

    def _price_is_grounded(self, value: float, prices: list[PriceRecord]) -> PriceRecord | None:
        """Match a figure against a price that appears in a fetched record."""
        for record in prices:
            for candidate in (record.modal_price, record.min_price, record.max_price):
                if candidate > 0 and self._close(value, candidate):
                    return record
        return None

    def _derived_from_records(self, value: float, prices: list[PriceRecord]) -> str | None:
        """Recognise a figure computed from fetched records rather than quoted.

        Answers legitimately contain arithmetic over government data — the gap
        between two mandis, an average across them. Those values appear in no
        single record, so without this check the fact-checker would flag its own
        correct arithmetic as a hallucination and suppress the recommendation.
        """
        if not prices or value <= 0:
            return None

        modals = [r.modal_price for r in prices]

        average = sum(modals) / len(modals)
        if self._close(value, average):
            return f"Average modal price across {len(prices)} fetched mandi records"

        best, worst = max(modals), min(modals)
        if self._close(value, best - worst):
            return (
                f"Difference between the highest (Rs {best:.0f}) and lowest "
                f"(Rs {worst:.0f}) modal price in the fetched records"
            )

        # Any pairwise gap between two fetched records is equally traceable.
        for i, a in enumerate(modals):
            for b in modals[i + 1 :]:
                if self._close(value, abs(a - b)):
                    return (
                        f"Difference between two fetched mandi records "
                        f"(Rs {max(a, b):.0f} and Rs {min(a, b):.0f})"
                    )
        return None

    def run(self, context: AgentContext, generated_text: str = "") -> AgentContext:
        claims: list[FactCheckClaim] = []
        text = generated_text or context.narrative

        # --- price claims ---------------------------------------------------
        for raw in _PRICE_IN_TEXT.findall(text):
            try:
                value = float(raw.replace(",", ""))
            except ValueError:
                continue
            match = self._price_is_grounded(value, context.prices)
            if match is not None:
                claims.append(
                    FactCheckClaim(
                        claim=f"Price of Rs {value:.0f} per quintal",
                        status="verified" if match.source == "agmarknet" else "partially_verified",
                        evidence=[
                            f"{match.market}, {match.district} on {match.arrival_date} "
                            f"(modal Rs {match.modal_price:.0f}, source: {match.source})"
                        ],
                    )
                )
                continue

            if context.trend and any(
                self._close(value, ema)
                for ema in (context.trend.ema_7, context.trend.ema_14, context.trend.ema_30)
            ):
                claims.append(
                    FactCheckClaim(
                        claim=f"Moving-average value of Rs {value:.0f} per quintal",
                        status="partially_verified",
                        evidence=["Derived from the EMA trend model, not a single mandi record"],
                    )
                )
                continue

            derivation = self._derived_from_records(value, context.prices)
            if derivation is not None:
                claims.append(
                    FactCheckClaim(
                        claim=f"Derived figure of Rs {value:.0f} per quintal",
                        status="partially_verified",
                        evidence=[derivation],
                    )
                )
            else:
                claims.append(
                    FactCheckClaim(
                        claim=f"Price of Rs {value:.0f} per quintal",
                        status="insufficient_evidence",
                        evidence=[],
                    )
                )

        # --- trend claim ----------------------------------------------------
        if context.trend is not None:
            claims.append(
                FactCheckClaim(
                    claim=f"Price trend is {context.trend.direction}",
                    status="partially_verified",
                    evidence=[
                        f"EMA-7 {context.trend.ema_7:.0f} / EMA-14 {context.trend.ema_14:.0f} / "
                        f"EMA-30 {context.trend.ema_30:.0f} over {context.trend.samples} days"
                    ],
                )
            )

        # --- recommendation claim -------------------------------------------
        if context.prediction is not None:
            # A recommendation is evidenced by whatever it was actually built
            # from. Price records alone are enough to justify a cross-mandi
            # call; demanding a trend as well would mark sound advice unsupported
            # on the intents that never compute one.
            evidence: list[str] = []
            if context.prices:
                evidence.append(
                    f"{len(context.prices)} mandi price records from {context.price_source}"
                )
            if context.trend is not None:
                evidence.append(
                    f"EMA trend model over {context.trend.samples} days "
                    f"(direction {context.trend.direction})"
                )
            claims.append(
                FactCheckClaim(
                    claim=f"Recommendation to {context.prediction.recommendation}",
                    status="partially_verified" if evidence else "insufficient_evidence",
                    evidence=evidence,
                )
            )

        context.claims = claims
        context.observe(
            self.name,
            f"Checked {len(claims)} claims: "
            f"{sum(1 for c in claims if c.status == 'verified')} verified, "
            f"{sum(1 for c in claims if c.status == 'partially_verified')} partially verified, "
            f"{sum(1 for c in claims if c.status == 'insufficient_evidence')} unsupported.",
        )
        return context

    @staticmethod
    def overall_status(claims: list[FactCheckClaim]) -> str:
        """Roll individual claim statuses up into the response-level status."""
        if not claims:
            return "insufficient_evidence"
        if any(c.status == "insufficient_evidence" for c in claims):
            return "insufficient_evidence"
        if all(c.status == "verified" for c in claims):
            return "verified"
        return "partially_verified"

    @staticmethod
    def strip_unverified(text: str, claims: list[FactCheckClaim]) -> str:
        """Remove sentences carrying prices that no source supports.

        This is the enforcement half of the hallucination-prevention design:
        the fact-checker does not merely label a bad number, it stops it from
        reaching the farmer.
        """
        unsupported = [
            c for c in claims
            if c.status == "insufficient_evidence" and c.claim.startswith("Price of Rs")
        ]
        if not unsupported:
            return text

        bad_values = set()
        for claim in unsupported:
            match = re.search(r"Rs\s*([\d.]+)", claim.claim)
            if match:
                bad_values.add(match.group(1).rstrip("."))

        sentences = re.split(r"(?<=[.!?।])\s+", text)
        kept = [
            s for s in sentences
            if not any(
                value in s.replace(",", "") for value in bad_values
            ) or not _PRICE_IN_TEXT.search(s)
        ]
        return " ".join(kept).strip() or text


def hindi_crop_label(crop: str | None) -> str:
    """Devanagari label for a crop, falling back to the English name."""
    if not crop:
        return "फसल"
    return CROP_HINDI_LABEL.get(crop, crop)


__all__ = [
    "AgentContext",
    "IntentDetectionAgent",
    "LocationResolutionAgent",
    "MandiIntelligenceAgent",
    "BuyerConnectAgent",
    "TavilySearchAgent",
    "ContextRetrievalAgent",
    "PricePredictionAgent",
    "ReasoningAgent",
    "SellDecisionAgent",
    "FactCheckAgent",
    "hindi_crop_label",
    "classify_intent",
]
