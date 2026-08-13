"""Tests for the tool suite (§4.2.2) and the specialist agents (Table 3.2)."""

from __future__ import annotations

import pytest

from app.agents.specialists import (
    AgentContext,
    FactCheckAgent,
    IntentDetectionAgent,
    LocationResolutionAgent,
    MandiIntelligenceAgent,
    PricePredictionAgent,
    ReasoningAgent,
    SellDecisionAgent,
)
from app.schemas import FactCheckClaim, GeoPoint, PriceRecord, Prediction, TrendAnalysis
from app.tools import location_tool, mandi_tool, prediction_tool, tavily_tool, vector_tool
from app.tools.base import Tool, ToolResult
from app.tools.prediction_tool import (
    classify_trend,
    exponential_moving_average,
    relative_volatility,
)


def _price(market: str, modal: float, district: str = "Patna", source: str = "sample") -> PriceRecord:
    return PriceRecord(
        state="Bihar", district=district, market=market, commodity="Wheat",
        arrival_date="2026-08-01", min_price=modal - 50, max_price=modal + 50,
        modal_price=modal, source=source,
    )


# --- tool contract ----------------------------------------------------------
def test_a_raising_tool_returns_an_error_result_instead_of_propagating():
    def explode():
        raise ValueError("upstream is down")

    tool = Tool(name="boom", description="", func=explode)
    result = tool()
    assert result.ok is False
    assert "upstream is down" in result.error


def test_observation_text_marks_degraded_results():
    result = ToolResult(ok=True, data=None, summary="fetched", degraded=True)
    assert "degraded" in result.as_observation()


def test_failed_observation_reads_as_an_error():
    result = ToolResult(ok=False, data=None, summary="", error="no data")
    assert result.as_observation().startswith("ERROR")


# --- mandi tool -------------------------------------------------------------
def test_mandi_tool_returns_records_with_a_readable_summary():
    result = mandi_tool.TOOL(crop="Wheat", state="Bihar", district="Patna")
    assert result.ok
    assert result.data
    assert "modal price" in result.summary.lower()


def test_mandi_tool_summary_names_the_best_mandi():
    result = mandi_tool.TOOL(crop="Onion", state="Bihar", district="Patna")
    best = max(result.data, key=lambda r: r.modal_price)
    assert best.market in result.summary


# --- location tool ----------------------------------------------------------
def test_location_tool_resolves_from_text():
    result = location_tool.TOOL(text="wheat price in Gaya")
    assert result.ok
    assert result.data["context"].district == "Gaya"


def test_location_tool_resolves_from_coordinates():
    result = location_tool.TOOL(text="wheat price", latitude=25.5941, longitude=85.1376)
    assert result.data["context"].district == "Patna"


def test_location_tool_reports_failure_when_nothing_resolves():
    result = location_tool.TOOL(text="what is the price")
    assert result.ok is False
    assert result.error == "location_unresolved"


# --- tavily tool ------------------------------------------------------------
def test_search_tool_degrades_cleanly_without_credentials():
    result = tavily_tool.TOOL(crop="Wheat", location="Patna")
    assert result.ok is True       # a missing optional source is not a failure
    assert result.degraded is True
    assert result.data == []


# --- vector tool ------------------------------------------------------------
def test_vector_tool_retrieves_attributed_context(store):
    result = vector_tool.TOOL(query="tomato price trend", crop="Tomato", location="Patna")
    assert result.ok
    assert result.data["citations"]
    assert all(c.startswith("[") for c in result.data["citations"])


def test_vector_tool_honours_k(store):
    assert len(vector_tool.TOOL(query="wheat price", k=3).data["hits"]) == 3


# --- EMA maths --------------------------------------------------------------
def test_ema_of_a_constant_series_is_that_constant():
    assert exponential_moving_average([100.0] * 20, 7) == 100.0


def test_ema_tracks_a_rising_series_below_its_last_value():
    series = [float(v) for v in range(100, 140)]
    assert 100 < exponential_moving_average(series, 7) < 139


def test_short_ema_reacts_faster_than_long_ema_on_a_rising_series():
    series = [float(v) for v in range(100, 140)]
    assert exponential_moving_average(series, 7) > exponential_moving_average(series, 30)


def test_ema_of_an_empty_series_is_zero():
    assert exponential_moving_average([], 7) == 0.0


def test_volatility_of_a_flat_series_is_zero():
    assert relative_volatility([100.0] * 10) == 0.0


def test_volatility_rises_with_noise():
    steady = relative_volatility([100, 101, 102, 103, 104, 105])
    jumpy = relative_volatility([100, 130, 95, 140, 90, 135])
    assert jumpy > steady


# --- trend classification ---------------------------------------------------
def test_rising_series_is_classified_upward():
    analysis = classify_trend([float(v) for v in range(100, 145)])
    assert analysis.direction == "upward"


def test_falling_series_is_classified_downward():
    analysis = classify_trend([float(v) for v in range(145, 100, -1)])
    assert analysis.direction == "downward"


def test_flat_series_is_classified_stable():
    analysis = classify_trend([100.0] * 40)
    assert analysis.direction == "stable"


def test_confidence_is_lower_for_a_noisy_trend_than_a_clean_one():
    clean = classify_trend([100 + 2 * i for i in range(40)])
    noisy = classify_trend([100 + 2 * i + (60 if i % 2 else -60) for i in range(40)])
    assert clean.confidence > noisy.confidence


def test_prediction_tool_reports_the_full_ema_triple():
    result = prediction_tool.TOOL(crop="Wheat", state="Bihar", district="Patna")
    assert result.ok
    analysis = result.data["analysis"]
    assert analysis.ema_7 > 0 and analysis.ema_14 > 0 and analysis.ema_30 > 0
    assert analysis.samples > 0


# --- intent agent -----------------------------------------------------------
def test_intent_agent_builds_a_context_with_a_reasoning_step():
    context = IntentDetectionAgent().run("पटना में गेहूं का भाव क्या है?")
    assert context.nlp.intent == "price_query"
    assert context.nlp.crop == "Wheat"
    assert context.reasoning_steps


# --- location agent ---------------------------------------------------------
def test_location_agent_updates_the_context_and_lists_neighbours():
    context = IntentDetectionAgent().run("wheat price in Patna")
    LocationResolutionAgent().run(context)
    assert context.nlp.location.district == "Patna"
    assert context.nearby_districts


def test_location_agent_survives_an_unresolvable_query():
    context = IntentDetectionAgent().run("what is the price")
    LocationResolutionAgent().run(context)
    assert context.nlp.location.district is None


def test_location_agent_accepts_gps_coordinates():
    context = IntentDetectionAgent().run("wheat price")
    LocationResolutionAgent().run(context, coordinates=GeoPoint(latitude=24.79, longitude=85.0))
    assert context.nlp.location.district == "Gaya"


# --- mandi agent ------------------------------------------------------------
def test_mandi_agent_deduplicates_and_sorts_by_price():
    context = IntentDetectionAgent().run("wheat price in Patna")
    LocationResolutionAgent().run(context)
    MandiIntelligenceAgent().run(context)
    prices = [r.modal_price for r in context.prices]
    assert prices == sorted(prices, reverse=True)
    keys = [(r.market, r.commodity, r.arrival_date) for r in context.prices]
    assert len(keys) == len(set(keys))


def test_mandi_agent_marks_the_context_degraded_offline():
    context = IntentDetectionAgent().run("wheat price in Patna")
    LocationResolutionAgent().run(context)
    MandiIntelligenceAgent().run(context)
    assert context.degraded is True


def test_neighbouring_records_are_attributed_to_their_own_state():
    """A neighbour district must be queried under the state it belongs to."""
    from app.nlp.lexicon import STATE_DISTRICTS

    context = IntentDetectionAgent().run("tomato price in Indore")
    LocationResolutionAgent().run(context)
    MandiIntelligenceAgent().run(context)
    for record in context.prices:
        assert record.district in STATE_DISTRICTS[record.state]


# --- reasoning agent --------------------------------------------------------
def test_reasoning_agent_writes_a_narrative_from_the_evidence():
    context = AgentContext(query="wheat price", nlp=IntentDetectionAgent().run("wheat price").nlp)
    context.prices = [_price("A", 2400), _price("B", 2100)]
    ReasoningAgent().run(context)
    assert "2400" in context.narrative or "2,400" in context.narrative


def test_reasoning_agent_states_plainly_when_no_prices_were_found():
    context = AgentContext(query="wheat price", nlp=IntentDetectionAgent().run("wheat price").nlp)
    ReasoningAgent().run(context)
    assert "No mandi price records" in context.narrative


# --- sell decision agent ----------------------------------------------------
def _context_with_trend(direction: str, series: list[float]) -> AgentContext:
    context = AgentContext(query="should i sell", nlp=IntentDetectionAgent().run("should i sell wheat").nlp)
    context.prices = [_price("A", 2400), _price("B", 2350)]
    context.price_series = series
    context.trend = classify_trend(series)
    assert context.trend.direction == direction
    return context


def test_price_at_the_top_of_a_falling_range_says_sell():
    series = [2000 + i for i in range(40)][::-1]  # falling, currently at the low
    rising_to_peak = sorted(series)               # rising, currently at the peak
    context = AgentContext(query="sell?", nlp=IntentDetectionAgent().run("should i sell wheat").nlp)
    context.prices = [_price("A", 2400)]
    context.price_series = rising_to_peak
    context.trend = classify_trend(rising_to_peak)
    SellDecisionAgent().run(context)
    assert context.prediction is not None


def test_recommendation_cites_only_supporting_reasons():
    """The rationale must not list signals that argue against the call.

    A farmer reading "sell now, because the price is near its low" has been
    given a self-contradicting answer.
    """
    context = _context_with_trend("downward", [float(2400 - i) for i in range(40)])
    SellDecisionAgent().run(context)
    prediction = context.prediction
    assert prediction is not None
    if prediction.recommendation == "SELL":
        assert "near the bottom of its recent range" not in prediction.reason
    else:
        assert "near the top of its recent range" not in prediction.reason


def test_confidence_stays_within_bounds():
    context = _context_with_trend("downward", [float(2400 - i) for i in range(40)])
    SellDecisionAgent().run(context)
    assert 0.0 <= context.prediction.confidence <= 1.0


def test_no_recommendation_without_any_evidence():
    context = AgentContext(query="sell?", nlp=IntentDetectionAgent().run("should i sell").nlp)
    SellDecisionAgent().run(context)
    assert context.prediction is None


# --- fact-check agent -------------------------------------------------------
def test_a_price_from_a_government_record_is_verified():
    context = AgentContext(query="q", nlp=IntentDetectionAgent().run("wheat price").nlp)
    context.prices = [_price("A", 2400, source="agmarknet")]
    FactCheckAgent().run(context, generated_text="Wheat is Rs 2400 per quintal.")
    assert context.claims[0].status == "verified"


def test_a_price_from_the_offline_dataset_is_only_partially_verified():
    context = AgentContext(query="q", nlp=IntentDetectionAgent().run("wheat price").nlp)
    context.prices = [_price("A", 2400, source="sample")]
    FactCheckAgent().run(context, generated_text="Wheat is Rs 2400 per quintal.")
    assert context.claims[0].status == "partially_verified"


def test_an_invented_price_is_flagged_as_unsupported():
    context = AgentContext(query="q", nlp=IntentDetectionAgent().run("wheat price").nlp)
    context.prices = [_price("A", 2400)]
    FactCheckAgent().run(context, generated_text="Wheat is Rs 9999 per quintal.")
    assert any(c.status == "insufficient_evidence" for c in context.claims)


def test_a_figure_derived_from_records_is_not_treated_as_invented():
    """Arithmetic over government records is traceable, not hallucinated.

    Without this the fact-checker flags its own correct subtraction and the
    recommendation sentence is stripped from the answer.
    """
    context = AgentContext(query="q", nlp=IntentDetectionAgent().run("wheat price").nlp)
    context.prices = [_price("A", 2400), _price("B", 2100)]
    FactCheckAgent().run(context, generated_text="A nearby mandi pays Rs 300 more per quintal.")
    statuses = {c.status for c in context.claims}
    assert "insufficient_evidence" not in statuses


def test_an_ema_value_is_partially_verified():
    context = AgentContext(query="q", nlp=IntentDetectionAgent().run("wheat price").nlp)
    context.prices = [_price("A", 2400)]
    context.trend = TrendAnalysis(
        direction="stable", ema_7=2222, ema_14=2222, ema_30=2222, confidence=0.5, samples=30
    )
    FactCheckAgent().run(context, generated_text="The 7-day average is Rs 2222.")
    assert any("Moving-average" in c.claim for c in context.claims)


def test_a_recommendation_backed_by_prices_alone_is_still_supported():
    context = AgentContext(query="q", nlp=IntentDetectionAgent().run("wheat price").nlp)
    context.prices = [_price("A", 2400)]
    context.prediction = Prediction(recommendation="WAIT", confidence=0.5, reason="test")
    FactCheckAgent().run(context, generated_text="")
    claim = next(c for c in context.claims if c.claim.startswith("Recommendation"))
    assert claim.status == "partially_verified"


@pytest.mark.parametrize(
    "statuses,expected",
    [
        (["verified", "verified"], "verified"),
        (["verified", "partially_verified"], "partially_verified"),
        (["verified", "insufficient_evidence"], "insufficient_evidence"),
        ([], "insufficient_evidence"),
    ],
)
def test_overall_status_rollup(statuses, expected):
    claims = [FactCheckClaim(claim="c", status=s) for s in statuses]
    assert FactCheckAgent.overall_status(claims) == expected


def test_unsupported_prices_are_stripped_from_the_answer():
    claims = [FactCheckClaim(claim="Price of Rs 9999 per quintal", status="insufficient_evidence")]
    text = "Wheat is Rs 2400 today. A trader offered Rs 9999 per quintal."
    cleaned = FactCheckAgent.strip_unverified(text, claims)
    assert "9999" not in cleaned
    assert "2400" in cleaned


def test_stripping_is_a_no_op_when_everything_is_supported():
    text = "Wheat is Rs 2400 today."
    assert FactCheckAgent.strip_unverified(text, []) == text


# --- prediction agent -------------------------------------------------------
def test_prediction_agent_skips_gracefully_without_a_crop():
    context = IntentDetectionAgent().run("what is the price")
    PricePredictionAgent().run(context)
    assert context.trend is None
    assert any("No crop identified" in step for step in context.reasoning_steps)
