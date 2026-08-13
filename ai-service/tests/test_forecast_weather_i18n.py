"""Tests for the Section 6.3 additions: trained forecasting, weather signals
and the regional language expansion."""

from __future__ import annotations

import math

import pytest

from app.data import weather
from app.forecast.features import build_supervised
from app.forecast.linalg import cholesky, ridge_solve, solve_cholesky
from app.forecast.models import (
    LSTMForecaster,
    RidgeARForecaster,
    SeasonalNaiveForecaster,
    _confidence_from_backtest,
)
from app.i18n import translate
from app.i18n.detect import detect_language, is_code_switched, script_of
from app.i18n.registry import LANGUAGES, SUPPORTED_CODES, crop_label, get_language, template
from app.schemas import QueryRequest
from app.tools import forecast_tool, weather_tool


# --------------------------------------------------------------------------- #
# Linear algebra
# --------------------------------------------------------------------------- #
def test_cholesky_reconstructs_the_matrix():
    matrix = [[4.0, 2.0], [2.0, 3.0]]
    lower = cholesky(matrix)
    product = [
        [sum(lower[i][k] * lower[j][k] for k in range(2)) for j in range(2)] for i in range(2)
    ]
    for i in range(2):
        for j in range(2):
            assert abs(product[i][j] - matrix[i][j]) < 1e-9


def test_cholesky_rejects_a_non_positive_definite_matrix():
    with pytest.raises(ValueError):
        cholesky([[1.0, 2.0], [2.0, 1.0]])


def test_cholesky_solve_recovers_the_solution():
    matrix = [[4.0, 1.0], [1.0, 3.0]]
    expected = [2.0, -1.0]
    rhs = [
        sum(matrix[i][j] * expected[j] for j in range(2)) for i in range(2)
    ]
    solution = solve_cholesky(matrix, rhs)
    assert all(abs(a - b) < 1e-9 for a, b in zip(solution, expected))


def test_ridge_recovers_a_linear_relationship():
    design = [[1.0, float(x)] for x in range(20)]
    target = [3.0 + 2.0 * x for x in range(20)]
    intercept, slope = ridge_solve(design, target, penalty=1e-6)
    assert abs(slope - 2.0) < 0.05
    assert abs(intercept - 3.0) < 0.5


def test_ridge_survives_perfectly_collinear_features():
    """A flat price series makes lag features collinear; this must not raise."""
    design = [[1.0, 2.0, 4.0] for _ in range(10)]
    target = [1.0] * 10
    coefficients = ridge_solve(design, target, penalty=1.0)
    assert len(coefficients) == 3
    assert all(math.isfinite(c) for c in coefficients)


# --------------------------------------------------------------------------- #
# Feature construction
# --------------------------------------------------------------------------- #
def test_supervised_data_has_matching_rows_and_targets():
    data = build_supervised([100.0 + i for i in range(40)])
    assert len(data.design) == len(data.target)
    assert len(data.design[0]) == len(data.feature_names)


def test_supervised_data_is_empty_for_a_short_series():
    assert len(build_supervised([1.0, 2.0])) == 0


def test_features_are_scale_invariant():
    """Two series differing only in scale must produce the same design matrix.

    Prices range from ~340 (sugarcane) to ~7800 (garlic); without this the
    ridge penalty would mean something different for every crop.
    """
    small = [100.0 + i for i in range(40)]
    large = [10000.0 + 100.0 * i for i in range(40)]
    a = build_supervised(small)
    b = build_supervised(large)
    for row_a, row_b in zip(a.design, b.design):
        assert all(abs(x - y) < 1e-9 for x, y in zip(row_a, row_b))


# --------------------------------------------------------------------------- #
# Forecasters
# --------------------------------------------------------------------------- #
def test_ridge_extrapolates_a_linear_ramp():
    series = [1000.0 + 5.0 * i for i in range(60)]
    forecast = RidgeARForecaster().fit_predict(series, horizon=5)
    assert forecast.model == "ridge-ar"
    # Each step should continue upward, close to the true slope of 5/day.
    assert forecast.points[0].value > series[-1]
    assert forecast.points[-1].value > forecast.points[0].value


def test_ridge_beats_the_naive_baseline_on_a_trending_series():
    series = [1000.0 + 5.0 * i for i in range(60)]
    forecast = RidgeARForecaster().fit_predict(series, horizon=7)
    assert forecast.mape is not None
    assert forecast.baseline_mape is not None
    assert forecast.mape < forecast.baseline_mape


def test_ridge_beats_the_baseline_on_a_seasonal_series():
    series = [1000 + 200 * math.sin(i / 12) for i in range(90)]
    forecast = RidgeARForecaster().fit_predict(series, horizon=7)
    assert forecast.mape < forecast.baseline_mape


def test_prediction_intervals_widen_with_the_horizon():
    series = [1000.0 + 5.0 * i for i in range(60)]
    forecast = RidgeARForecaster().fit_predict(series, horizon=10)
    widths = [p.upper - p.lower for p in forecast.points]
    assert widths == sorted(widths)
    assert widths[-1] > widths[0]


def test_point_forecast_lies_inside_its_own_interval():
    series = [1000 + 200 * math.sin(i / 9) for i in range(80)]
    forecast = RidgeARForecaster().fit_predict(series, horizon=7)
    assert all(p.lower <= p.value <= p.upper for p in forecast.points)


def test_a_short_series_degrades_to_the_baseline_instead_of_pretending():
    forecast = RidgeARForecaster().fit_predict([100.0, 101.0, 99.0, 102.0], horizon=3)
    assert forecast.model == "seasonal-naive"
    assert any("observations" in note for note in forecast.notes)


def test_seasonal_naive_holds_the_recent_level():
    series = [100.0] * 30
    forecast = SeasonalNaiveForecaster().fit_predict(series, horizon=5)
    assert all(abs(p.value - 100.0) < 1e-6 for p in forecast.points)


def test_forecast_horizon_is_respected():
    series = [1000.0 + i for i in range(50)]
    assert len(RidgeARForecaster().fit_predict(series, horizon=12).points) == 12


def test_expected_change_is_reported_against_the_last_observation():
    series = [1000.0 + 5.0 * i for i in range(60)]
    forecast = RidgeARForecaster().fit_predict(series, horizon=7)
    assert forecast.expected_change_pct is not None
    assert forecast.expected_change_pct > 0


def test_confidence_is_zero_weighted_when_the_model_loses_to_the_baseline():
    """A model no better than guessing must not be trusted more than guessing."""
    worse = _confidence_from_backtest(mape=10.0, baseline_mape=5.0, samples=60)
    better = _confidence_from_backtest(mape=2.0, baseline_mape=10.0, samples=60)
    assert better > worse


def test_confidence_grows_with_more_training_data():
    few = _confidence_from_backtest(mape=2.0, baseline_mape=10.0, samples=10)
    many = _confidence_from_backtest(mape=2.0, baseline_mape=10.0, samples=90)
    assert many > few


def test_lstm_availability_is_reported_honestly():
    assert isinstance(LSTMForecaster.available(), bool)


def test_forecast_tool_returns_a_usable_result():
    result = forecast_tool.TOOL(crop="Wheat", state="Bihar", district="Patna", horizon=5)
    assert result.ok
    assert len(result.data["forecast"].points) == 5
    assert "forecast" in result.summary.lower()


def test_forecast_tool_clamps_an_absurd_horizon():
    result = forecast_tool.TOOL(crop="Wheat", district="Patna", horizon=500)
    assert len(result.data["forecast"].points) == 30


# --------------------------------------------------------------------------- #
# Weather
# --------------------------------------------------------------------------- #
def test_offline_outlook_uses_climatology_and_says_so():
    outlook = weather.fetch_outlook(state="Bihar", district="Patna", crop="Tomato")
    assert outlook.source == "climatology"
    assert outlook.live is False
    assert outlook.degraded is True


def test_outlook_returns_the_requested_number_of_days():
    assert len(weather.fetch_outlook(district="Patna", days=10).days) == 10


def test_climatology_is_reproducible():
    first = weather.fetch_outlook(district="Patna", crop="Onion")
    second = weather.fetch_outlook(district="Patna", crop="Onion")
    assert [d.rainfall_mm for d in first.days] == [d.rainfall_mm for d in second.days]


def test_heavy_rain_is_read_as_a_supply_disruption():
    outlook = weather.WeatherOutlook(
        district="Patna", state="Bihar", source="test", live=True,
        days=[
            weather.DayWeather(day="2026-08-01", rainfall_mm=80.0, max_temp_c=29, min_temp_c=24),
            weather.DayWeather(day="2026-08-02", rainfall_mm=70.0, max_temp_c=28, min_temp_c=24),
        ],
    )
    assessed = weather._assess(outlook, "Tomato")
    assert assessed.supply_risk == "disruption"
    assert assessed.price_pressure == "upward"


def test_a_heat_spell_is_read_as_a_surplus_for_perishables():
    days = [
        weather.DayWeather(day=f"2026-05-0{i}", rainfall_mm=0.0, max_temp_c=43.0, min_temp_c=30.0)
        for i in range(1, 6)
    ]
    assessed = weather._assess(
        weather.WeatherOutlook(district="Patna", state="Bihar", source="test", live=True, days=days),
        "Tomato",
    )
    assert assessed.supply_risk == "surplus"
    assert assessed.price_pressure == "downward"


def test_a_heat_spell_does_not_move_a_storable_staple():
    days = [
        weather.DayWeather(day=f"2026-05-0{i}", rainfall_mm=0.0, max_temp_c=43.0, min_temp_c=30.0)
        for i in range(1, 6)
    ]
    assessed = weather._assess(
        weather.WeatherOutlook(district="Patna", state="Bihar", source="test", live=True, days=days),
        "Wheat",
    )
    assert assessed.supply_risk == "normal"


def test_climatological_confidence_is_discounted():
    days = [
        weather.DayWeather(day="2026-08-01", rainfall_mm=80.0, max_temp_c=29, min_temp_c=24),
        weather.DayWeather(day="2026-08-02", rainfall_mm=70.0, max_temp_c=28, min_temp_c=24),
    ]
    live = weather._assess(
        weather.WeatherOutlook(district="Patna", state="Bihar", source="imd", live=True, days=days),
        "Tomato",
    )
    modelled = weather._assess(
        weather.WeatherOutlook(
            district="Patna", state="Bihar", source="climatology", live=False, days=list(days)
        ),
        "Tomato",
    )
    assert modelled.confidence < live.confidence


def test_weather_tool_summarises_the_signal():
    result = weather_tool.TOOL(district="Patna", crop="Onion")
    assert result.ok
    assert "supply risk" in result.summary.lower()


# --------------------------------------------------------------------------- #
# Language registry
# --------------------------------------------------------------------------- #
def test_all_seven_languages_are_registered():
    assert set(SUPPORTED_CODES) == {"en", "hi", "bho", "mai", "mr", "bn", "ta"}


@pytest.mark.parametrize("code", SUPPORTED_CODES)
def test_every_language_can_render_every_template_slot(code):
    """A missing template would silently produce an empty sentence."""
    for key in ("price", "others", "sell", "wait", "trend", "forecast", "weather",
                "buyers", "none", "degraded", "rising", "falling", "steady"):
        assert template(code, key), f"{code} is missing the '{key}' template"


@pytest.mark.parametrize("code", [c for c in SUPPORTED_CODES if c != "en"])
def test_every_indic_language_names_the_core_crops(code):
    spec = get_language(code)
    for commodity in ("Tomato", "Onion", "Wheat", "Potato", "Rice"):
        assert commodity in spec.crop_names


def test_crop_label_falls_back_to_the_english_name():
    assert crop_label("ta", "Dragonfruit") == "Dragonfruit"


def test_unknown_language_code_falls_back_to_hindi():
    assert get_language("xx").code == "hi"


@pytest.mark.parametrize(
    "text,expected",
    [
        ("बिहार में टमाटर का क्या रेट है?", "hi"),
        ("रउआ बताईं कि पियाज के भाव केतना बा?", "bho"),
        ("पियाज बेचीं कि रुकीं?", "bho"),
        ("गहूम के भाव कतेक अछि?", "mai"),
        ("कांद्याचा भाव किती आहे?", "mr"),
        ("আজ পেঁয়াজের দাম কত?", "bn"),
        ("இன்று வெங்காயம் விலை எவ்வளவு?", "ta"),
        ("What is the tomato price in Bihar?", "en"),
    ],
)
def test_detects_each_supported_language(text, expected):
    assert detect_language(text) == expected


@pytest.mark.parametrize(
    "text",
    ["मंडी में भाव नहीं बढ़ा है क्या?", "कहीं टमाटर सस्ता मिलेगा क्या?"],
)
def test_common_hindi_words_do_not_trigger_a_regional_language(text):
    """नहीं and कहीं end in -ईं, which is the Bhojpuri imperative marker."""
    assert detect_language(text) == "hi"


def test_latin_heavy_code_switching_still_resolves_to_the_indic_language():
    """Romanised place names are long; a character count alone would say English."""
    assert detect_language("Patna में tomato का rate क्या है") == "hi"
    assert is_code_switched("Patna में tomato का rate क्या है") is True


def test_script_detection():
    assert script_of("टमाटर") == "devanagari"
    assert script_of("পেঁয়াজ") == "bengali"
    assert script_of("வெங்காயம்") == "tamil"
    assert script_of("tomato") == "latin"
    assert script_of("12345") == "unknown"


# --------------------------------------------------------------------------- #
# Translation layer
# --------------------------------------------------------------------------- #
def test_translation_is_a_passthrough_when_the_languages_match():
    result = translate.translate("hello", "en", "en")
    assert result.translated is False
    assert result.text == "hello"


def test_translation_declines_rather_than_guessing_offline():
    result = translate.translate("hello", "en", "ta")
    assert result.source == "passthrough"
    assert result.translated is False


def test_language_options_describe_every_language():
    options = translate.language_options()
    assert len(options) == len(LANGUAGES)
    assert all(option["name"] and option["speech_tag"] for option in options)


# --------------------------------------------------------------------------- #
# End-to-end, through the orchestrator
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "query,language",
    [
        ("पियाज बेचीं कि रुकीं?", "bho"),
        ("कांद्याचा भाव किती आहे?", "mr"),
        ("আজ পেঁয়াজের দাম কত?", "bn"),
        ("இன்று வெங்காயம் விலை எவ்வளவு?", "ta"),
        ("गहूम के भाव कतेक अछि?", "mai"),
    ],
)
def test_a_farmer_is_answered_in_their_own_language(orchestrator, query, language):
    response = orchestrator.run(QueryRequest(query=query))
    assert response.answer_language == language
    assert response.answer
    assert response.answers[language] == response.answer


def test_hindi_and_english_are_always_populated_for_schema_compatibility(orchestrator):
    """Clients written against Section 4.7 must keep working for any language."""
    response = orchestrator.run(QueryRequest(query="இன்று வெங்காயம் விலை எவ்வளவு?"))
    assert response.english_answer
    assert response.hindi_answer
    assert response.answer_language == "ta"


def test_sell_advice_runs_the_forecast_and_weather_agents(orchestrator):
    response = orchestrator.run(QueryRequest(query="Should I sell wheat in Patna now?"))
    assert response.forecast is not None
    assert response.weather is not None
    assert response.forecast.horizon_days > 0


def test_a_plain_price_query_skips_the_expensive_forward_looking_agents(orchestrator):
    response = orchestrator.run(QueryRequest(query="What is the wheat price in Patna?"))
    assert response.forecast is None
    assert response.weather is None


def test_reasoning_trail_names_the_new_agents(orchestrator):
    response = orchestrator.run(QueryRequest(query="Should I sell wheat in Patna now?"))
    joined = " ".join(response.reasoning_steps)
    assert "Price Forecasting" in joined
    assert "Weather Impact" in joined


# --------------------------------------------------------------------------- #
# Weather: thresholds and climatological calibration
# --------------------------------------------------------------------------- #
def test_thresholds_follow_imd_rainfall_categories():
    """The bands are IMD's published 24-hour categories, not invented numbers."""
    assert weather.HEAVY_RAIN_MM == 64.5
    assert weather.VERY_HEAVY_RAIN_MM == 115.6
    assert weather.WET_DAY_MM == 15.6


def test_sustained_moderate_rain_is_a_disruption_even_without_a_peak_day():
    """A week of steady rain waterlogs fields as surely as one extreme day.

    A peak-only rule scored such a week as untroubled, which is precisely the
    case a farmer most needs warning about.
    """
    days = [
        weather.DayWeather(day=f"2026-08-{i:02d}", rainfall_mm=35.0, max_temp_c=30, min_temp_c=25)
        for i in range(1, 5)
    ]
    assessed = weather._assess(
        weather.WeatherOutlook(district="Patna", state="Bihar", source="test", live=True, days=days),
        "Tomato",
    )
    assert assessed.heavy_rain_days == 0        # no single day reaches 64.5 mm
    assert assessed.total_rain_mm == 140.0
    assert assessed.supply_risk == "disruption"


def test_a_single_imd_heavy_day_is_enough():
    days = [
        weather.DayWeather(day="2026-08-01", rainfall_mm=70.0, max_temp_c=29, min_temp_c=24),
        weather.DayWeather(day="2026-08-02", rainfall_mm=0.0, max_temp_c=33, min_temp_c=26),
    ]
    assessed = weather._assess(
        weather.WeatherOutlook(district="Patna", state="Bihar", source="test", live=True, days=days),
        "Tomato",
    )
    assert assessed.heavy_rain_days == 1
    assert assessed.supply_risk == "disruption"


def test_a_light_week_stays_normal():
    days = [
        weather.DayWeather(day=f"2026-08-{i:02d}", rainfall_mm=4.0, max_temp_c=32, min_temp_c=26)
        for i in range(1, 8)
    ]
    assessed = weather._assess(
        weather.WeatherOutlook(district="Patna", state="Bihar", source="test", live=True, days=days),
        "Tomato",
    )
    assert assessed.supply_risk == "normal"


def test_rainfall_is_modelled_as_wet_and_dry_days_not_a_flat_average():
    """Monsoon rain falls in bursts; a smoothed series makes peaks meaningless."""
    from datetime import date

    days = weather._climatology("Bihar", "Patna", 60, date(2026, 7, 1))
    amounts = [d.rainfall_mm for d in days]
    assert any(a == 0.0 for a in amounts), "expected some dry days in the monsoon"
    assert max(amounts) > 3 * (sum(amounts) / len(amounts)), "expected bursty rainfall"


@pytest.mark.parametrize(
    "state,district,seasonal_normal_mm",
    [
        ("Bihar", "Patna", 1000),
        ("Uttar Pradesh", "Lucknow", 850),
        ("Madhya Pradesh", "Indore", 870),
        ("Punjab", "Ludhiana", 500),
        ("Rajasthan", "Jaipur", 500),
        ("Haryana", "Karnal", 450),
    ],
)
def test_climatology_matches_published_seasonal_normals(state, district, seasonal_normal_mm):
    """June-September totals should land near the published normal.

    Averaged over several years, because the wet-day model is heavy-tailed and
    any single season varies widely — as real monsoons do.
    """
    from datetime import date

    totals = [
        sum(d.rainfall_mm for d in weather._climatology(state, district, 122, date(year, 6, 1)))
        for year in range(2020, 2028)
    ]
    modelled = sum(totals) / len(totals)
    error = abs(modelled - seasonal_normal_mm) / seasonal_normal_mm
    assert error < 0.20, f"{district}: modelled {modelled:.0f} mm vs normal {seasonal_normal_mm} mm"


def test_the_dry_season_is_dry():
    from datetime import date

    total = sum(
        d.rainfall_mm for d in weather._climatology("Bihar", "Patna", 90, date(2026, 11, 15))
    )
    assert total < 60


def test_wetter_regions_receive_more_rain_than_drier_ones():
    """Bihar must out-rain Punjab in the same week, as it does in reality."""
    from datetime import date

    def season(state, district):
        return sum(
            d.rainfall_mm for d in weather._climatology(state, district, 122, date(2026, 6, 1))
        )

    assert season("Bihar", "Patna") > season("Punjab", "Ludhiana")
    assert season("Uttar Pradesh", "Lucknow") > season("Haryana", "Karnal")


@pytest.mark.parametrize(
    "text",
    [
        "गहूम बेचब कि रुकब?",
        "हमर गाम मे आलू कतेक अछि?",
        "आलू करब कि नहि?",
    ],
)
def test_maithili_verb_forms_are_detected(text):
    """The -ब verbal form is Maithili's most common diagnostic in real queries."""
    assert detect_language(text) == "mai"


@pytest.mark.parametrize(
    "text",
    [
        "फसल खराब हो गई है क्या भाव मिलेगा?",   # खराब ends in -ब but is Hindi
        "इसका मतलब क्या है?",                    # so does मतलब
        "मुझे जवाब चाहिए भाव का",                 # and जवाब
        "अब सब जब तब कब",                        # and every common Hindi adverb
    ],
)
def test_hindi_words_ending_in_ba_are_not_read_as_maithili(text):
    """A `-ब$` regex would have misclassified all of these."""
    assert detect_language(text) == "hi"
