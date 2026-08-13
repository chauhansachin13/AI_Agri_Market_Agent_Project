"""Prediction Tool — exponential moving-average trend analysis (§4.6.1).

Three EMAs (7, 14 and 30 day) are computed over recent modal prices for a
crop-location pair.  The trend is classified *upward* when EMA-7 > EMA-14 >
EMA-30, *downward* when the converse holds, and *stable* otherwise.

Confidence is a function of the EMA spread relative to price volatility: a
high score requires both a clear directional signal and low recent volatility,
so a strong-looking spread in a violently noisy series is correctly reported as
weak evidence.
"""

from __future__ import annotations

import math

from ..config import get_settings
from ..data import agmarknet_gov
from ..schemas import PriceRecord, TrendAnalysis
from .base import Tool, ToolResult


def exponential_moving_average(values: list[float], window: int) -> float:
    """EMA over ``values`` (oldest first) with smoothing factor 2/(window+1)."""
    if not values:
        return 0.0
    window = max(1, min(window, len(values)))
    alpha = 2.0 / (window + 1.0)
    ema = values[0]
    for value in values[1:]:
        ema = alpha * value + (1 - alpha) * ema
    return round(ema, 2)


def relative_volatility(values: list[float]) -> float:
    """Coefficient of variation of day-over-day returns."""
    if len(values) < 3:
        return 0.0
    returns = [
        (b - a) / a for a, b in zip(values, values[1:]) if a > 0
    ]
    if not returns:
        return 0.0
    mean = sum(returns) / len(returns)
    variance = sum((r - mean) ** 2 for r in returns) / len(returns)
    return round(math.sqrt(variance), 5)


def _daily_modal_series(records: list[PriceRecord]) -> list[float]:
    """Collapse multi-market records into one modal price per day, oldest first."""
    by_date: dict[str, list[float]] = {}
    for record in records:
        by_date.setdefault(record.arrival_date, []).append(record.modal_price)
    return [
        round(sum(prices) / len(prices), 2)
        for _, prices in sorted(by_date.items())
    ]


def classify_trend(series: list[float]) -> TrendAnalysis:
    """Compute the three EMAs and classify the direction with a confidence."""
    settings = get_settings()
    short, medium, long = settings.ema_windows

    ema_short = exponential_moving_average(series, short)
    ema_medium = exponential_moving_average(series, medium)
    ema_long = exponential_moving_average(series, long)
    volatility = relative_volatility(series)

    if ema_short > ema_medium > ema_long:
        direction = "upward"
    elif ema_short < ema_medium < ema_long:
        direction = "downward"
    else:
        direction = "stable"

    # Spread is the directional signal, expressed as a fraction of price level.
    reference = ema_long or 1.0
    spread = abs(ema_short - ema_long) / reference

    if direction == "stable":
        confidence = round(max(0.25, 0.6 - spread * 4), 3)
    else:
        signal = min(spread / 0.06, 1.0)          # 6% spread saturates the signal
        steadiness = 1.0 / (1.0 + volatility * 25)  # heavy noise erodes confidence
        sample_weight = min(len(series) / long, 1.0) if long else 1.0
        confidence = round(min(0.97, 0.35 + 0.5 * signal * steadiness * sample_weight), 3)

    return TrendAnalysis(
        direction=direction,  # type: ignore[arg-type]
        ema_7=ema_short,
        ema_14=ema_medium,
        ema_30=ema_long,
        volatility=volatility,
        confidence=confidence,
        samples=len(series),
    )


def predict_trend(
    crop: str,
    state: str | None = None,
    district: str | None = None,
    days: int = 45,
) -> ToolResult:
    """Analyse the recent price trend for a crop-location pair."""
    history = agmarknet_gov.fetch_price_history(
        commodity=crop, state=state, district=district, days=days
    )
    series = _daily_modal_series(history)

    if len(series) < 3:
        return ToolResult(
            ok=False,
            data=None,
            summary=f"Not enough price history for {crop} to compute a trend.",
            source="prediction",
            error="insufficient_history",
        )

    analysis = classify_trend(series)
    change = ((series[-1] - series[0]) / series[0] * 100) if series[0] else 0.0

    summary = (
        f"{crop} price trend is {analysis.direction} "
        f"(EMA-7 Rs {analysis.ema_7:.0f}, EMA-14 Rs {analysis.ema_14:.0f}, "
        f"EMA-30 Rs {analysis.ema_30:.0f}) over {analysis.samples} days. "
        f"Net change {change:+.1f}%, volatility {analysis.volatility:.4f}, "
        f"confidence {analysis.confidence:.2f}."
    )

    return ToolResult(
        ok=True,
        data={"analysis": analysis, "series": series, "change_pct": round(change, 2)},
        summary=summary,
        source="prediction",
    )


TOOL = Tool(
    name="price_trend",
    description=(
        "Analyse the recent price trend for a crop in a location using 7, 14 and "
        "30 day exponential moving averages over historical modal prices. Returns "
        "the trend direction (upward, downward or stable) with a confidence score "
        "that accounts for price volatility."
    ),
    func=predict_trend,
    args_schema={
        "crop": "Agmarknet commodity name",
        "state": "State name",
        "district": "District name",
        "days": "History window in days (integer, default 45)",
    },
)
