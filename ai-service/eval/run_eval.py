"""Accuracy evaluation for the NLP pipeline, the forecaster and grounding.

    python -m eval.run_eval            # everything
    python -m eval.run_eval --nlp      # intent / crop / language / location only
    python -m eval.run_eval --forecast # forecaster against a naive baseline
    python -m eval.run_eval --grounding# hallucination audit over the full pipeline

Exits non-zero if any measured figure falls below the target the report states,
so this doubles as a regression gate rather than a report that is read once.
"""

from __future__ import annotations

import argparse
import os
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("OFFLINE_MODE", "1")

from app.config import get_settings  # noqa: E402
from eval.dataset import ALL_CASES, BY_LANGUAGE, summary  # noqa: E402
from eval.metrics import Report, confusion  # noqa: E402

# Targets quoted in Section 5.1 / 5.2 of the report.
TARGETS = {
    "intent_accuracy": 0.90,
    "crop_accuracy": 0.90,
    "language_accuracy": 0.90,
    "location_accuracy": 0.85,
    "grounded_rate": 0.95,
    "forecast_skill": 0.60,  # share of series where the model beats naive
}


def banner(title: str) -> None:
    print(f"\n\033[1m{title}\033[0m")
    print("=" * max(54, len(title)))


# --------------------------------------------------------------------------- #
# NLP
# --------------------------------------------------------------------------- #
def evaluate_nlp(verbose: bool = False) -> dict[str, float]:
    from app.i18n.detect import detect_language
    from app.nlp import pipeline

    intent_report = Report("intent")
    language_report = Report("language")
    crop_report = Report("crop")
    location_report = Report("location")

    hard_intent = Report("intent (ambiguous subset)")
    latencies: list[float] = []

    for case in ALL_CASES:
        started = time.perf_counter()
        result = pipeline.run(case.query)
        latencies.append((time.perf_counter() - started) * 1000)

        detected = detect_language(case.query)
        language_report.add(case.language, detected, case.query)

        intent_report.add(case.intent, result.intent, case.query)
        if case.hard:
            hard_intent.add(case.intent, result.intent, case.query)

        # `crop=None` is a real label: nothing should be detected.
        expected_crop = case.crop or "<none>"
        crop_report.add(expected_crop, result.crop or "<none>", case.query)

        if case.district or case.state:
            expected = case.district or case.state or ""
            got = result.location.district or result.location.state or "<none>"
            location_report.add(expected, got, case.query)

    banner("Intent classification")
    print(intent_report.table())
    print("\nConfusion (rows = expected, columns = predicted):")
    print(confusion(intent_report))
    if hard_intent.total:
        print(
            f"\nOn the {hard_intent.total} deliberately ambiguous cases: "
            f"{hard_intent.accuracy:.3f} accuracy"
        )
        straightforward = (intent_report.correct - hard_intent.correct) / (
            intent_report.total - hard_intent.total
        )
        print(f"On the {intent_report.total - hard_intent.total} straightforward cases: "
              f"{straightforward:.3f}")

    banner("Language detection")
    print(language_report.table())

    banner("Crop extraction")
    print(f"accuracy {crop_report.accuracy:.3f} over {crop_report.total} cases "
          f"({len(crop_report.classes)} distinct labels)")

    banner("Location resolution")
    print(f"accuracy {location_report.accuracy:.3f} over {location_report.total} cases")

    banner("Per-language intent accuracy")
    for language, cases in sorted(BY_LANGUAGE.items()):
        per = Report(language)
        for case in cases:
            per.add(case.intent, pipeline.run(case.query).intent, case.query)
        print(f"  {language:<4} {per.accuracy:>6.3f}  ({per.total} cases)")

    if verbose:
        for report in (intent_report, language_report, crop_report, location_report):
            if report.errors:
                banner(f"{report.name} errors")
                for source, expected, got in report.errors:
                    print(f"  expected {expected:<28} got {got:<28} {source}")

    banner("Pipeline latency")
    print(f"  mean {statistics.mean(latencies):.2f} ms · "
          f"p95 {sorted(latencies)[int(len(latencies) * 0.95)]:.2f} ms")

    return {
        "intent_accuracy": intent_report.accuracy,
        "intent_weighted_f1": intent_report.weighted_f1,
        "language_accuracy": language_report.accuracy,
        "crop_accuracy": crop_report.accuracy,
        "location_accuracy": location_report.accuracy,
    }


# --------------------------------------------------------------------------- #
# Forecasting
# --------------------------------------------------------------------------- #
def evaluate_forecast() -> dict[str, float]:
    """Backtest the trained forecaster against the naive baseline it must beat."""
    from app.data import agmarknet_gov
    from app.forecast.models import RidgeARForecaster, SeasonalNaiveForecaster
    from app.tools.prediction_tool import _daily_modal_series

    crops = ["Tomato", "Onion", "Wheat", "Potato", "Rice", "Maize", "Mustard"]
    districts = [("Bihar", "Patna"), ("Bihar", "Gaya"), ("Uttar Pradesh", "Lucknow"),
                 ("Madhya Pradesh", "Indore"), ("Punjab", "Ludhiana")]
    horizon = 7

    ridge = RidgeARForecaster()
    naive = SeasonalNaiveForecaster()

    rows: list[tuple[str, str, float, float]] = []
    for crop in crops:
        for state, district in districts:
            history = agmarknet_gov.fetch_price_history(
                commodity=crop, state=state, district=district, days=120
            )
            series = _daily_modal_series(history)
            if len(series) < 40:
                continue

            # Hold out the last `horizon` days and forecast them.
            train, test = series[:-horizon], series[-horizon:]

            def mape(predictions: list[float]) -> float:
                errors = [
                    abs(p - a) / abs(a) for p, a in zip(predictions, test) if a
                ]
                return sum(errors) / len(errors) * 100 if errors else 0.0

            model_pred = [p.value for p in ridge.fit_predict(train, horizon).points]
            naive_pred = [p.value for p in naive.fit_predict(train, horizon).points]
            rows.append((crop, district, mape(model_pred), mape(naive_pred)))

    banner("Forecast accuracy (7-day horizon, held out)")
    if get_settings().offline_mode or not get_settings().agmarknet_live:
        print(
            "\033[33mNOTE:\033[0m measured on the bundled reference series, which is\n"
            "generated from smooth seasonal curves. A linear autoregressor fits that\n"
            "far more easily than real mandi prices, so treat the absolute MAPE as a\n"
            "sanity check on the implementation, not as a real-world accuracy claim.\n"
            "The skill score — how often the model beats the naive baseline on the\n"
            "same series — is the meaningful number here.\n"
        )
    print(f"{'crop':<14} {'district':<12} {'model':>8} {'naive':>8} {'better':>8}")
    print("-" * 54)
    wins = 0
    for crop, district, model_mape, naive_mape in rows:
        better = model_mape < naive_mape
        wins += better
        print(f"{crop[:13]:<14} {district[:11]:<12} {model_mape:>7.2f}% {naive_mape:>7.2f}% "
              f"{'yes' if better else 'no':>8}")

    model_mean = statistics.mean(r[2] for r in rows)
    naive_mean = statistics.mean(r[3] for r in rows)
    skill = wins / len(rows)

    print("-" * 54)
    print(f"{'MEAN':<27} {model_mean:>7.2f}% {naive_mean:>7.2f}%")
    print(f"\nBeats the naive baseline on {wins}/{len(rows)} series ({skill:.1%})")
    print(f"Mean error reduction: {(naive_mean - model_mean) / naive_mean:.1%}")

    return {
        "forecast_mape": model_mean,
        "forecast_baseline_mape": naive_mean,
        "forecast_skill": skill,
    }


# --------------------------------------------------------------------------- #
# Grounding
# --------------------------------------------------------------------------- #
def evaluate_grounding() -> dict[str, float]:
    """Audit every rupee figure the pipeline emits for traceability.

    This is the claim that matters most: a price a farmer acts on must come
    from a record, not from the model. The audit runs the whole pipeline and
    inspects the fact-check verdicts it produced.
    """
    import re

    from app.agents.orchestrator import get_orchestrator
    from app.schemas import QueryRequest

    orchestrator = get_orchestrator()
    total_claims = 0
    grounded_claims = 0
    unsupported: list[tuple[str, str]] = []
    leaked: list[tuple[str, str]] = []
    latencies: list[float] = []

    price_pattern = re.compile(r"(?:Rs\.?|₹|रुपये|रुपिया|टाका|ரூபாய்)\s*([\d,]+)")

    for case in ALL_CASES:
        started = time.perf_counter()
        response = orchestrator.run(QueryRequest(query=case.query))
        latencies.append((time.perf_counter() - started) * 1000)

        for claim in response.fact_check_claims:
            total_claims += 1
            if claim.status == "insufficient_evidence":
                unsupported.append((case.query, claim.claim))
            else:
                grounded_claims += 1

        # Independent check: no figure may survive in the answer that the
        # fact-checker rejected.
        rejected = {
            match.group(1).replace(",", "")
            for claim in response.fact_check_claims
            if claim.status == "insufficient_evidence"
            for match in [re.search(r"Rs\s*([\d,.]+)", claim.claim)]
            if match
        }
        for text in (response.answer, response.english_answer, response.hindi_answer):
            for found in price_pattern.findall(text or ""):
                if found.replace(",", "") in rejected:
                    leaked.append((case.query, found))

    rate = grounded_claims / total_claims if total_claims else 1.0

    banner("Grounding audit")
    print(f"  queries run            {len(ALL_CASES)}")
    print(f"  price/derived claims   {total_claims}")
    print(f"  traceable to a source  {grounded_claims}  ({rate:.1%})")
    print(f"  unsupported claims     {len(unsupported)}")
    print(f"  unsupported figures that reached the answer: {len(leaked)}")

    if unsupported[:5]:
        print("\n  Sample unsupported claims:")
        for query, claim in unsupported[:5]:
            print(f"    {claim}  ←  {query[:48]}")
    if leaked:
        print("\n  \033[31mLEAKED into the answer:\033[0m")
        for query, value in leaked[:10]:
            print(f"    {value}  ←  {query[:48]}")

    banner("End-to-end latency (offline, no network)")
    ordered = sorted(latencies)
    print(f"  mean {statistics.mean(latencies):.0f} ms · "
          f"p50 {ordered[len(ordered) // 2]:.0f} ms · "
          f"p95 {ordered[int(len(ordered) * 0.95)]:.0f} ms · "
          f"max {ordered[-1]:.0f} ms")

    return {"grounded_rate": rate, "leaked": float(len(leaked))}


# --------------------------------------------------------------------------- #
def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--nlp", action="store_true")
    parser.add_argument("--forecast", action="store_true")
    parser.add_argument("--grounding", action="store_true")
    parser.add_argument("-v", "--verbose", action="store_true", help="list every error")
    args = parser.parse_args()

    run_all = not (args.nlp or args.forecast or args.grounding)
    results: dict[str, float] = {}

    banner("Evaluation set")
    for key, value in summary().items():
        print(f"  {key:<20} {value}")

    if run_all or args.nlp:
        results.update(evaluate_nlp(verbose=args.verbose))
    if run_all or args.forecast:
        results.update(evaluate_forecast())
    if run_all or args.grounding:
        results.update(evaluate_grounding())

    banner("Against the report's targets")
    failures = []
    for metric, target in TARGETS.items():
        if metric not in results:
            continue
        value = results[metric]
        ok = value >= target
        mark = "\033[32mPASS\033[0m" if ok else "\033[31mFAIL\033[0m"
        print(f"  {metric:<22} {value:>7.3f}  target ≥ {target:<6}  {mark}")
        if not ok:
            failures.append(metric)

    if results.get("leaked", 0) > 0:
        print(f"  {'no leaked figures':<22} {'':>7}  target = 0       \033[31mFAIL\033[0m")
        failures.append("leaked")

    print()
    if failures:
        print(f"\033[31m{len(failures)} metric(s) below target: {', '.join(failures)}\033[0m")
        return 1
    print("\033[32mAll measured metrics meet their targets.\033[0m")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
