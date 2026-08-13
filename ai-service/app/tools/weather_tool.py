"""Weather Tool — supply-shock outlook for a crop and district (Section 6.3)."""

from __future__ import annotations

from ..data import weather
from .base import Tool, ToolResult


def weather_outlook(
    state: str | None = None,
    district: str | None = None,
    crop: str | None = None,
    days: int = 7,
) -> ToolResult:
    """Fetch the weather outlook and its implication for mandi supply."""
    days = max(1, min(int(days), 16))
    outlook = weather.fetch_outlook(state=state, district=district, crop=crop, days=days)

    where = district or state or "the region"
    summary = (
        f"Weather outlook for {where} ({outlook.source}): {outlook.summary} "
        f"Supply risk: {outlook.supply_risk}; price pressure: {outlook.price_pressure} "
        f"(confidence {outlook.confidence:.2f})."
    )

    return ToolResult(
        ok=True,
        data=outlook,
        summary=summary,
        source=outlook.source,
        degraded=outlook.degraded,
    )


TOOL = Tool(
    name="weather_outlook",
    description=(
        "Get the weather forecast for a district and what it implies for crop "
        "supply: heavy rain disrupts harvesting and transport and tends to firm "
        "prices, while a hot dry spell accelerates arrivals of perishables and "
        "tends to soften them. Use this when advising whether to sell now or "
        "wait, since anticipated supply changes are not visible in price "
        "history alone."
    ),
    func=weather_outlook,
    args_schema={
        "state": "State name",
        "district": "District name",
        "crop": "Crop name, so perishability is taken into account",
        "days": "Forecast window in days (integer, 1-16, default 7)",
    },
)
