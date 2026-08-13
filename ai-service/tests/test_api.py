"""End-to-end tests for the orchestrator (§4.3) and the FastAPI surface (§3.4)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.schemas import GeoPoint, QueryRequest

client = TestClient(app)


REPORT_QUERIES = [
    ("बिहार में टमाटर का क्या रेट है?", "price_query", "Tomato"),
    ("What is the tomato price in Bihar?", "price_query", "Tomato"),
    ("आसपास गेहूं कौन खरीद रहा है?", "buyer_search", "Wheat"),
    ("Who is buying wheat nearby?", "buyer_search", "Wheat"),
    ("क्या मुझे अभी प्याज बेच देना चाहिए?", "sell_advice", "Onion"),
    ("Should I sell onions now?", "sell_advice", "Onion"),
    ("पिछले हफ्ते से आलू का भाव बढ़ा है?", "trend_analysis", "Potato"),
    ("Has potato price risen from last week?", "trend_analysis", "Potato"),
]


# --- orchestrator -----------------------------------------------------------
@pytest.mark.parametrize("query,intent,crop", REPORT_QUERIES)
def test_the_report_example_queries_run_end_to_end(orchestrator, query, intent, crop):
    response = orchestrator.run(QueryRequest(query=query))
    assert response.intent == intent
    assert response.crop == crop
    assert response.english_answer
    assert response.hindi_answer
    assert response.reasoning_steps


def test_response_carries_both_languages(orchestrator):
    response = orchestrator.run(QueryRequest(query="What is the wheat price in Patna?"))
    # The Hindi answer must actually be in Devanagari, not a transliteration.
    assert any("ऀ" <= ch <= "ॿ" for ch in response.hindi_answer)
    assert not any("ऀ" <= ch <= "ॿ" for ch in response.english_answer)


def test_price_query_returns_live_records_and_a_best_mandi(orchestrator):
    response = orchestrator.run(QueryRequest(query="wheat price in Patna"))
    assert response.live_mandi_prices
    assert response.best_mandi
    top = max(r.modal_price for r in response.live_mandi_prices)
    assert response.live_mandi_prices[0].modal_price == top


def test_buyer_query_returns_buyer_contacts(orchestrator):
    response = orchestrator.run(QueryRequest(query="Who is buying wheat nearby in Patna?"))
    assert response.buyers


def test_sell_advice_returns_a_recommendation_with_a_reason(orchestrator):
    response = orchestrator.run(QueryRequest(query="Should I sell onions in Patna now?"))
    assert response.prediction is not None
    assert response.prediction.recommendation in ("SELL", "WAIT")
    assert response.prediction.reason


def test_trend_query_returns_the_full_ema_triple(orchestrator):
    response = orchestrator.run(QueryRequest(query="Has potato price risen in Patna?"))
    assert response.trend_analysis is not None
    assert response.trend_analysis.direction in ("upward", "downward", "stable")
    assert response.trend_analysis.ema_7 > 0


def test_reasoning_steps_name_the_agents_that_ran(orchestrator):
    response = orchestrator.run(QueryRequest(query="wheat price in Patna"))
    joined = " ".join(response.reasoning_steps)
    for agent in ("Intent Detection", "Location Resolution", "Mandi Intelligence"):
        assert agent in joined


def test_offline_responses_are_flagged_degraded(orchestrator):
    response = orchestrator.run(QueryRequest(query="wheat price in Patna"))
    assert response.degraded is True


def test_confidence_is_a_probability(orchestrator):
    for query, _, _ in REPORT_QUERIES:
        response = orchestrator.run(QueryRequest(query=query))
        assert 0.0 <= response.confidence_score <= 1.0


def test_degraded_data_never_reports_full_confidence(orchestrator):
    response = orchestrator.run(QueryRequest(query="wheat price in Patna"))
    assert response.confidence_score < 1.0


def test_no_answer_contains_an_unsupported_price(orchestrator):
    """The hallucination-prevention guarantee, checked end to end.

    Every rupee figure in the answer must trace back to a fetched record, a
    moving average, or arithmetic over those records.
    """
    import re

    for query, _, _ in REPORT_QUERIES:
        response = orchestrator.run(QueryRequest(query=query))
        for claim in response.fact_check_claims:
            if claim.claim.startswith(("Price of Rs", "Derived figure")):
                assert claim.status != "insufficient_evidence", (query, claim)
        assert re.search(r"Rs\s*\d", response.english_answer) or not response.live_mandi_prices


def test_gps_coordinates_drive_location_resolution(orchestrator):
    response = orchestrator.run(
        QueryRequest(query="tomato price", coordinates=GeoPoint(latitude=26.12, longitude=85.36))
    )
    assert "Muzaffarpur" in response.location


def test_pincode_drives_location_resolution(orchestrator):
    response = orchestrator.run(QueryRequest(query="tomato price", pincode="823001"))
    assert "Gaya" in response.location


def test_query_without_a_crop_still_answers(orchestrator):
    response = orchestrator.run(QueryRequest(query="what are the rates in Patna?"))
    assert response.english_answer
    assert response.crop is None


def test_location_label_names_real_districts_when_unresolved(orchestrator):
    response = orchestrator.run(QueryRequest(query="tomato ka bhav"))
    assert response.location != "your area"


# --- HTTP API ---------------------------------------------------------------
def test_health_endpoint_reports_integration_state():
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["llm_enabled"] is False
    assert body["vector_documents"] > 0


def test_agent_query_endpoint_returns_the_section_4_7_schema():
    response = client.post("/agent/query", json={"query": "wheat price in Patna"})
    assert response.status_code == 200
    body = response.json()
    for field in (
        "intent", "crop", "location", "live_mandi_prices", "trend_analysis",
        "prediction", "confidence_score", "fact_check_status",
        "english_answer", "hindi_answer", "reasoning_steps",
    ):
        assert field in body


def test_agent_query_rejects_an_empty_query():
    assert client.post("/agent/query", json={"query": "   "}).status_code == 422


def test_agent_query_rejects_a_missing_query():
    assert client.post("/agent/query", json={}).status_code == 422


def test_nlp_parse_endpoint_exposes_the_pipeline():
    response = client.post("/nlp/parse", json={"query": "पटना में गेहूं का भाव"})
    body = response.json()
    assert body["intent"] == "price_query"
    assert body["crop"] == "Wheat"
    assert body["location"]["district"] == "Patna"


def test_mandi_prices_endpoint_filters_by_crop():
    response = client.get("/mandi/prices", params={"crop": "Onion", "state": "Bihar", "limit": 5})
    assert response.status_code == 200
    body = response.json()
    assert body
    assert all(record["commodity"] == "Onion" for record in body)


def test_buyers_endpoint_returns_contacts():
    response = client.get("/mandi/buyers", params={"state": "Bihar", "district": "Patna"})
    assert response.status_code == 200
    assert response.json()


def test_trend_endpoint_returns_an_analysis():
    response = client.get("/mandi/trend", params={"crop": "Wheat", "district": "Patna"})
    assert response.status_code == 200
    assert response.json()["direction"] in ("upward", "downward", "stable")


def test_series_endpoint_returns_ordered_points():
    response = client.get(
        "/mandi/series", params={"crop": "Wheat", "district": "Patna", "days": 20}
    )
    points = response.json()["points"]
    assert len(points) == 20
    assert [p["date"] for p in points] == sorted(p["date"] for p in points)


def test_cors_preflight_is_allowed_for_the_frontend_origin():
    response = client.options(
        "/agent/query",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "POST",
        },
    )
    assert response.status_code in (200, 204)
