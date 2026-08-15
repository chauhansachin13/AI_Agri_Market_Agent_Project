"""Accuracy floors, enforced as tests.

`eval/run_eval.py` prints the full report; this file pins the same metrics so a
change that quietly degrades classification fails the normal test run rather
than waiting to be noticed in a report nobody re-runs.

The thresholds are set a little below the measured figures. They are a floor
against regression, not a target to tune towards — tightening them to the
current numbers would make every harmless lexicon addition a test failure.
"""

from __future__ import annotations

import pytest

from eval.dataset import ALL_CASES, BY_LANGUAGE
from eval.metrics import Report

from app.i18n.detect import detect_language
from app.nlp import pipeline


@pytest.fixture(scope="module")
def reports():
    intent = Report("intent")
    language = Report("language")
    crop = Report("crop")
    location = Report("location")

    for case in ALL_CASES:
        result = pipeline.run(case.query)
        intent.add(case.intent, result.intent, case.query)
        language.add(case.language, detect_language(case.query), case.query)
        crop.add(case.crop or "<none>", result.crop or "<none>", case.query)
        if case.district or case.state:
            location.add(
                case.district or case.state or "",
                result.location.district or result.location.state or "<none>",
                case.query,
            )

    return {"intent": intent, "language": language, "crop": crop, "location": location}


def test_the_evaluation_set_is_substantial():
    # A floor that passes on three examples is not a floor.
    assert len(ALL_CASES) >= 100
    assert len(BY_LANGUAGE) == 7


def test_intent_accuracy_meets_the_reported_target(reports):
    assert reports["intent"].accuracy >= 0.90


def test_no_intent_class_collapses(reports):
    """Overall accuracy can hide a class that never fires.

    A classifier that answered `price_query` to everything would score well on
    this set, since price questions dominate it. Per-class recall is what
    catches that.
    """
    for label, metrics in reports["intent"].classes.items():
        if metrics.support:
            assert metrics.recall >= 0.75, f"{label} recall collapsed"


def test_language_detection_accuracy(reports):
    assert reports["language"].accuracy >= 0.90


def test_every_language_is_detected_at_least_sometimes(reports):
    for code in BY_LANGUAGE:
        metrics = reports["language"].classes.get(code)
        assert metrics and metrics.recall >= 0.70, f"{code} detection collapsed"


def test_crop_extraction_accuracy(reports):
    assert reports["crop"].accuracy >= 0.90


def test_location_resolution_accuracy(reports):
    assert reports["location"].accuracy >= 0.85


def test_no_crop_is_detected_when_none_is_named():
    """A false positive here sends the farmer prices for a crop they never asked about."""
    for case in ALL_CASES:
        if case.crop is None and "no-crop" in case.tags:
            assert pipeline.run(case.query).crop is None, case.query


# --------------------------------------------------------------------------- #
# Grounding
# --------------------------------------------------------------------------- #
@pytest.fixture(scope="module")
def grounding():
    from app.agents.orchestrator import ReActOrchestrator
    from app.schemas import QueryRequest

    orchestrator = ReActOrchestrator()
    total = 0
    grounded = 0
    unsupported: list[str] = []

    # A subset keeps the test fast; run_eval covers the whole set.
    for case in ALL_CASES[::3]:
        response = orchestrator.run(QueryRequest(query=case.query))
        for claim in response.fact_check_claims:
            total += 1
            if claim.status == "insufficient_evidence":
                unsupported.append(f"{case.query} -> {claim.claim}")
            else:
                grounded += 1

    return {"total": total, "grounded": grounded, "unsupported": unsupported}


def test_every_price_claim_is_traceable(grounding):
    """The core guarantee: no figure reaches a farmer without a source."""
    assert grounding["total"] > 0
    assert not grounding["unsupported"], grounding["unsupported"][:5]


def test_grounded_rate_meets_the_reported_target(grounding):
    rate = grounding["grounded"] / grounding["total"]
    assert rate >= 0.95


# --------------------------------------------------------------------------- #
# Forecasting
# --------------------------------------------------------------------------- #
def test_the_forecaster_beats_the_naive_baseline_on_most_series():
    """A trained model that cannot beat repeating the last value is not worth shipping."""
    from app.data import agmarknet_gov
    from app.forecast.models import RidgeARForecaster, SeasonalNaiveForecaster
    from app.tools.prediction_tool import _daily_modal_series

    horizon = 7
    ridge, naive = RidgeARForecaster(), SeasonalNaiveForecaster()
    wins = attempts = 0

    for crop in ("Tomato", "Onion", "Wheat", "Potato"):
        for state, district in (("Bihar", "Patna"), ("Madhya Pradesh", "Indore")):
            series = _daily_modal_series(
                agmarknet_gov.fetch_price_history(
                    commodity=crop, state=state, district=district, days=120
                )
            )
            if len(series) < 40:
                continue
            train, test = series[:-horizon], series[-horizon:]

            def mape(predictions):
                errors = [abs(p - a) / a for p, a in zip(predictions, test) if a]
                return sum(errors) / len(errors) if errors else 0.0

            attempts += 1
            if mape([p.value for p in ridge.fit_predict(train, horizon).points]) < mape(
                [p.value for p in naive.fit_predict(train, horizon).points]
            ):
                wins += 1

    assert attempts > 0
    assert wins / attempts >= 0.6, f"beat the baseline on only {wins}/{attempts} series"
