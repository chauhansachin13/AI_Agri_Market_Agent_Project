"""Tests for the four-stage NLP pipeline (§4.1)."""

from __future__ import annotations

import pytest

from app.nlp import pipeline
from app.nlp.entities import extract_all_crops, extract_crop, extract_quantity, to_quintals
from app.nlp.intents import classify_intent, is_ambiguous
from app.nlp.language import detect_language, response_language
from app.nlp.location import (
    from_coordinates,
    from_pincode,
    from_text,
    haversine_km,
    nearest_districts,
    resolve,
)
from app.schemas import GeoPoint


# --- language detection -----------------------------------------------------
@pytest.mark.parametrize(
    "text,expected",
    [
        ("बिहार में टमाटर का क्या रेट है?", "hi"),
        ("What is the tomato price in Bihar?", "en"),
        ("आसपास गेहूं कौन खरीद रहा है?", "hi"),
        ("Who is buying wheat nearby?", "en"),
    ],
)
def test_detects_pure_language(text, expected):
    assert detect_language(text) == expected


def test_code_switched_query_is_mixed():
    assert detect_language("Patna में tomato का rate क्या है") == "mixed"


def test_romanised_hindi_is_treated_as_mixed():
    assert detect_language("Patna me tamatar ka bhav kya hai") == "mixed"


def test_mixed_queries_answer_in_hindi():
    # Section 4.1.1: mixed input defaults to Hindi for response generation.
    assert response_language("mixed") == "hi"
    assert response_language("hi") == "hi"
    assert response_language("en") == "en"


def test_empty_query_does_not_crash():
    assert detect_language("") == "en"


# --- intent classification --------------------------------------------------
@pytest.mark.parametrize(
    "text,expected",
    [
        ("बिहार में टमाटर का क्या रेट है?", "price_query"),
        ("What is the tomato price in Bihar?", "price_query"),
        ("आसपास गेहूं कौन खरीद रहा है?", "buyer_search"),
        ("Who is buying wheat nearby?", "buyer_search"),
        ("क्या मुझे अभी प्याज बेच देना चाहिए?", "sell_advice"),
        ("Should I sell onions now?", "sell_advice"),
        ("पिछले हफ्ते से आलू का भाव बढ़ा है?", "trend_analysis"),
        ("Has potato price risen from last week?", "trend_analysis"),
    ],
)
def test_classifies_the_four_report_intents(text, expected):
    intent, confidence = classify_intent(text)
    assert intent == expected
    assert 0.0 < confidence <= 1.0


def test_unknown_query_falls_back_to_price_query_with_low_confidence():
    intent, confidence = classify_intent("zzzz qqqq")
    assert intent == "price_query"
    assert confidence < 0.4


def test_ambiguity_detection_flags_a_bare_query():
    assert is_ambiguous("zzzz") is True


# --- entity extraction ------------------------------------------------------
@pytest.mark.parametrize(
    "text,expected",
    [
        ("टमाटर का भाव", "Tomato"),
        ("prices for pyaz", "Onion"),
        ("गेहूं कौन खरीद रहा है", "Wheat"),
        ("aloo rate", "Potato"),
        ("मसूर का दाम", "Lentil (Masur)(Whole)"),
        ("sarson price today", "Mustard"),
    ],
)
def test_extracts_crop_across_scripts(text, expected):
    crop, _ = extract_crop(text)
    assert crop == expected


def test_returns_no_crop_when_none_named():
    assert extract_crop("what is the weather today") == (None, None)


def test_longer_crop_name_wins_over_substring():
    crop, _ = extract_crop("phool gobhi ka rate")
    assert crop == "Cauliflower"


def test_extracts_multiple_crops_in_order():
    assert extract_all_crops("tomato and onion prices") == ["Tomato", "Onion"]


@pytest.mark.parametrize(
    "text,value,unit",
    [
        ("I have 20 quintal wheat", 20.0, "quintal"),
        ("500 kg potato", 500.0, "kg"),
        ("2 ton onion", 2.0, "ton"),
        ("10 मन गेहूं", 10.0, "maund"),
    ],
)
def test_extracts_quantity_with_unit(text, value, unit):
    assert extract_quantity(text) == (value, unit)


def test_quantity_absent_returns_none():
    assert extract_quantity("wheat price in Patna") == (None, None)


def test_unit_conversion_to_quintals():
    assert to_quintals(500, "kg") == 5.0
    assert to_quintals(2, "ton") == 20.0
    assert to_quintals(3, "quintal") == 3.0


# --- location resolution ----------------------------------------------------
def test_district_in_text_beats_state():
    context = from_text("wheat price in Patna Bihar")
    assert context.district == "Patna"
    assert context.state == "Bihar"


def test_devanagari_place_name_is_resolved():
    context = from_text("मुजफ्फरपुर में गेहूं का भाव")
    assert context.district == "Muzaffarpur"
    assert context.state == "Bihar"


def test_state_only_query_resolves_to_state():
    context = from_text("tomato price in Punjab")
    assert context.state == "Punjab"
    assert context.district is None


def test_pincode_maps_to_district():
    context = from_pincode("800001")
    assert (context.state, context.district) == ("Bihar", "Patna")
    assert context.confidence > 0.8


def test_unknown_pincode_yields_low_confidence():
    context = from_pincode("999999")
    assert context.district is None
    assert context.confidence < 0.5


def test_gps_snaps_to_nearest_district():
    context = from_coordinates(GeoPoint(latitude=25.60, longitude=85.14))
    assert context.district == "Patna"
    assert context.resolved_by == "gps"


def test_gps_far_from_any_known_district_is_rejected():
    assert from_coordinates(GeoPoint(latitude=-33.87, longitude=151.21)) is None


def test_resolution_hierarchy_prefers_explicit_text_over_gps():
    context = resolve(
        "wheat price in Ludhiana",
        coordinates=GeoPoint(latitude=25.60, longitude=85.14),
    )
    assert context.district == "Ludhiana"
    assert context.resolved_by == "text"


def test_resolution_falls_through_to_gps_when_text_is_silent():
    context = resolve("wheat price", coordinates=GeoPoint(latitude=26.12, longitude=85.36))
    assert context.district == "Muzaffarpur"


def test_unresolvable_query_reports_zero_confidence():
    context = resolve("what is the price")
    assert context.resolved_by == "unresolved"
    assert context.confidence == 0.0


def test_haversine_matches_known_distance():
    # Patna to Muzaffarpur is roughly 60 km.
    distance = haversine_km((25.5941, 85.1376), (26.1209, 85.3647))
    assert 50 < distance < 75


def test_nearest_districts_carry_their_own_state():
    neighbours = nearest_districts("Madhya Pradesh", "Indore")
    assert all(isinstance(pair, tuple) and len(pair) == 2 for pair in neighbours)
    # The nearest district to Indore may lie outside Madhya Pradesh; whichever
    # it is, it must be paired with the state it actually belongs to.
    from app.nlp.lexicon import STATE_DISTRICTS

    for state, district in neighbours:
        assert district in STATE_DISTRICTS[state]


# --- full pipeline ----------------------------------------------------------
def test_pipeline_produces_a_complete_structured_result():
    result = pipeline.run("पटना में 20 क्विंटल गेहूं का भाव क्या है?")
    assert result.intent == "price_query"
    assert result.crop == "Wheat"
    assert result.crop_hindi == "गेहूं"
    assert result.quantity_value == 20.0
    assert result.quantity_unit == "quintal"
    assert result.location.district == "Patna"
    assert result.language == "hi"


def test_pipeline_accepts_a_language_override():
    result = pipeline.run("tomato price", language_override="hi")
    assert result.language == "hi"


@pytest.mark.parametrize(
    "text,expected",
    [
        ("Should I sell onions now?", "Onion"),
        ("tomatoes price today", "Tomato"),
        ("potatoes rate in Patna", "Potato"),
        ("who buys lentils", "Lentil (Masur)(Whole)"),
    ],
)
def test_extracts_crop_from_plural_forms(text, expected):
    """Farmers write plurals; the lexicon stores singulars."""
    crop, _ = extract_crop(text)
    assert crop == expected
