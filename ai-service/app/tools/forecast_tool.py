"""Forecast Tool — trained multi-step price forecasting (Section 6.3).

This supersedes the EMA model for *forecasting*. The EMA triple is retained
for trend classification, because the report's response schema exposes it and
it remains a clear, explainable summary of where prices have been. What it was
never able to do is say where they are going; that is this tool's job.
"""

from __future__ import annotations

from ..data import agmarknet_gov
from ..forecast.models import select_forecaster
from ..tools.prediction_tool import _daily_modal_series
from .base import Tool, ToolResult


def forecast_price(
    crop: str,
    state: str | None = None,
    district: str | None = None,
    horizon: int = 7,
    history_days: int = 90,
    prefer_neural: bool = True,
) -> ToolResult:
    """Fit a forecaster on the crop-location history and project it forward."""
    horizon = max(1, min(int(horizon), 30))

    history = agmarknet_gov.fetch_price_history(
        commodity=crop, state=state, district=district, days=history_days
    )
    series = _daily_modal_series(history)

    if len(series) < 4:
        return ToolResult(
            ok=False,
            data=None,
            summary=f"Not enough price history for {crop} to fit a forecast.",
            source="forecast",
            error="insufficient_history",
        )

    forecaster = select_forecaster(prefer_neural=prefer_neural)
    forecast = forecaster.fit_predict(series, horizon=horizon)

    last = series[-1]
    final = forecast.points[-1]
    change = ((final.value - last) / last * 100) if last else 0.0

    lines = [
        f"{crop} forecast from the {forecast.model} model trained on "
        f"{forecast.trained_on} days of history: "
        f"Rs {last:.0f} today to Rs {final.value:.0f} in {horizon} days "
        f"({change:+.1f}%), 95% interval Rs {final.lower:.0f}–{final.upper:.0f}."
    ]
    if forecast.mape is not None:
        comparison = (
            f" against a naive baseline of {forecast.baseline_mape:.1f}%"
            if forecast.baseline_mape is not None
            else ""
        )
        lines.append(
            f"  Backtested error {forecast.mape:.1f}%{comparison}; "
            f"forecast confidence {forecast.confidence:.2f}."
        )
    for note in forecast.notes:
        lines.append(f"  Note: {note}")

    return ToolResult(
        ok=True,
        data={
            "forecast": forecast,
            "series": series,
            "last_observed": last,
            "change_pct": round(change, 2),
        },
        summary="\n".join(lines),
        source="forecast",
        # A model that could not beat the naive baseline is reported as degraded
        # evidence, so downstream agents weigh it accordingly.
        degraded=(
            forecast.mape is not None
            and forecast.baseline_mape is not None
            and forecast.mape >= forecast.baseline_mape
        ),
    )


TOOL = Tool(
    name="price_forecast",
    description=(
        "Forecast future mandi prices for a crop and location using a model "
        "trained on historical price data, returning point forecasts with 95% "
        "prediction intervals, a backtested error rate, and a comparison "
        "against a naive baseline. Use this to answer questions about where "
        "prices are heading, rather than where they have been."
    ),
    func=forecast_price,
    args_schema={
        "crop": "Agmarknet commodity name",
        "state": "State name",
        "district": "District name",
        "horizon": "Days ahead to forecast (integer, 1-30, default 7)",
        "history_days": "Days of history to train on (integer, default 90)",
    },
)
