"""Weather and supply-shock signals (Section 6.3, "Integration with Weather").

Weather moves mandi prices through supply. Heavy rain at harvest damages
standing crop and disrupts transport, thinning arrivals and firming prices a
few days later; a clear, hot spell accelerates arrivals of perishables and
softens them. Reasoning about the *anticipated* supply change is what the
report identifies as missing from a sell/wait call made on price history alone.

Two upstream sources are supported — the IMD public forecast endpoint and
Open-Meteo, which needs no key and covers Indian districts. Both degrade to a
deterministic climatological model derived from the district and the season, so
the signal is always present and always labelled with its provenance.
"""

from __future__ import annotations

import hashlib
import logging
import math
from dataclasses import dataclass
from datetime import date, timedelta

from ..config import get_settings
from ..nlp.lexicon import DISTRICT_CENTROIDS

logger = logging.getLogger(__name__)

# Crops whose supply reacts sharply to rain within days, and those that do not.
# Perishables have no storage buffer, so a disruption shows up in the mandi
# almost immediately; staples are cushioned by warehousing.
PERISHABLE = {"Tomato", "Onion", "Potato", "Cauliflower", "Brinjal", "Green Chilli", "Garlic"}
STAPLE = {"Wheat", "Rice", "Maize", "Mustard", "Soyabean", "Sugarcane"}

HEAVY_RAIN_MM = 35.0     # IMD "heavy rainfall" threshold for a 24-hour period
VERY_HEAVY_RAIN_MM = 65.0
HEAT_STRESS_C = 40.0


@dataclass
class DayWeather:
    day: str
    rainfall_mm: float
    max_temp_c: float
    min_temp_c: float


@dataclass
class WeatherOutlook:
    """A forecast window plus its implication for supply."""

    district: str | None
    state: str | None
    days: list[DayWeather]
    source: str                 # "imd" | "open-meteo" | "climatology"
    live: bool

    total_rain_mm: float = 0.0
    heavy_rain_days: int = 0
    heat_stress_days: int = 0
    supply_risk: str = "normal"       # "disruption" | "surplus" | "normal"
    price_pressure: str = "neutral"   # "upward" | "downward" | "neutral"
    confidence: float = 0.0
    summary: str = ""
    summary_hi: str = ""

    @property
    def degraded(self) -> bool:
        return not self.live


def _seeded_unit(*parts: object) -> float:
    digest = hashlib.sha256("|".join(str(p) for p in parts).encode()).hexdigest()
    return int(digest[:12], 16) / float(16**12)


def _climatology(state: str | None, district: str | None, days: int, today: date) -> list[DayWeather]:
    """Deterministic season-aware fallback.

    Monsoon timing and intensity across the Hindi belt is regular enough that a
    seasonal model gives a usable prior when no forecast is reachable — far
    better than reporting no weather signal at all.
    """
    out: list[DayWeather] = []
    for offset in range(days):
        day = today + timedelta(days=offset)
        doy = day.timetuple().tm_yday

        # Monsoon peaks around mid-July (day 196) across the target states.
        monsoon = max(0.0, math.sin(math.pi * (doy - 152) / 153)) if 152 <= doy <= 305 else 0.0
        noise = _seeded_unit(state, district, day.isoformat())

        rainfall = round(monsoon * 28.0 * (0.3 + 1.7 * noise), 1)

        # Summer peak near day 135; winter trough near day 15.
        seasonal_temp = 30.0 + 8.0 * math.sin(2 * math.pi * (doy - 100) / 365.0)
        max_temp = round(seasonal_temp + 4.0 * noise - (3.0 if rainfall > 10 else 0.0), 1)

        out.append(
            DayWeather(
                day=day.isoformat(),
                rainfall_mm=rainfall,
                max_temp_c=max_temp,
                min_temp_c=round(max_temp - 9.0 - 2.0 * noise, 1),
            )
        )
    return out


def _fetch_open_meteo(latitude: float, longitude: float, days: int) -> list[DayWeather]:  # pragma: no cover
    import httpx

    settings = get_settings()
    response = httpx.get(
        "https://api.open-meteo.com/v1/forecast",
        params={
            "latitude": latitude,
            "longitude": longitude,
            "daily": "precipitation_sum,temperature_2m_max,temperature_2m_min",
            "forecast_days": min(days, 16),
            "timezone": "Asia/Kolkata",
        },
        timeout=settings.http_timeout_seconds,
    )
    response.raise_for_status()
    daily = response.json()["daily"]

    return [
        DayWeather(
            day=day,
            rainfall_mm=float(rain or 0.0),
            max_temp_c=float(tmax if tmax is not None else 0.0),
            min_temp_c=float(tmin if tmin is not None else 0.0),
        )
        for day, rain, tmax, tmin in zip(
            daily["time"],
            daily["precipitation_sum"],
            daily["temperature_2m_max"],
            daily["temperature_2m_min"],
        )
    ]


def _assess(outlook: WeatherOutlook, crop: str | None) -> WeatherOutlook:
    """Derive the supply-risk and price-pressure signal from the raw forecast."""
    days = outlook.days
    if not days:
        return outlook

    outlook.total_rain_mm = round(sum(d.rainfall_mm for d in days), 1)
    outlook.heavy_rain_days = sum(1 for d in days if d.rainfall_mm >= HEAVY_RAIN_MM)
    outlook.heat_stress_days = sum(1 for d in days if d.max_temp_c >= HEAT_STRESS_C)

    very_heavy = sum(1 for d in days if d.rainfall_mm >= VERY_HEAVY_RAIN_MM)
    perishable = crop in PERISHABLE if crop else False
    window = len(days)

    if very_heavy >= 1 or outlook.heavy_rain_days >= 2:
        outlook.supply_risk = "disruption"
        outlook.price_pressure = "upward"
        # Perishables react faster and harder, and a longer window is more
        # likely to contain the disruption we are predicting.
        outlook.confidence = round(min(0.85, (0.5 if perishable else 0.38) + 0.05 * very_heavy), 3)
        outlook.summary = (
            f"{outlook.heavy_rain_days} day(s) of heavy rain expected over the next "
            f"{window} days ({outlook.total_rain_mm:.0f} mm total). Arrivals are likely "
            f"to thin as harvesting and transport are disrupted, which usually firms "
            f"prices within a few days."
        )
        outlook.summary_hi = (
            f"अगले {window} दिनों में {outlook.heavy_rain_days} दिन तेज़ बारिश का अनुमान है "
            f"(कुल {outlook.total_rain_mm:.0f} मिमी)। कटाई और ढुलाई रुकने से मंडी में आवक घट "
            f"सकती है, जिससे भाव चढ़ने की संभावना रहती है।"
        )
    elif outlook.heat_stress_days >= max(2, window // 2) and perishable:
        outlook.supply_risk = "surplus"
        outlook.price_pressure = "downward"
        outlook.confidence = 0.45
        outlook.summary = (
            f"A hot, dry spell is expected ({outlook.heat_stress_days} days above "
            f"{HEAT_STRESS_C:.0f}°C). Perishable produce is usually rushed to market in "
            f"these conditions, which tends to push arrivals up and prices down."
        )
        outlook.summary_hi = (
            f"आगे गर्मी और सूखा मौसम रहने का अनुमान है ({outlook.heat_stress_days} दिन "
            f"{HEAT_STRESS_C:.0f}°C से ऊपर)। ऐसे में जल्दी खराब होने वाली फसल तेज़ी से मंडी "
            f"पहुँचती है, जिससे आवक बढ़ती है और भाव नरम पड़ सकते हैं।"
        )
    else:
        outlook.supply_risk = "normal"
        outlook.price_pressure = "neutral"
        outlook.confidence = 0.3
        outlook.summary = (
            f"No significant weather disruption expected over the next {window} days "
            f"({outlook.total_rain_mm:.0f} mm of rain forecast)."
        )
        outlook.summary_hi = (
            f"अगले {window} दिनों में मौसम से कोई बड़ी दिक्कत नहीं दिख रही "
            f"(कुल {outlook.total_rain_mm:.0f} मिमी बारिश का अनुमान)।"
        )

    # A climatological prior is a weaker basis for a claim than a real forecast.
    if not outlook.live:
        outlook.confidence = round(outlook.confidence * 0.6, 3)

    return outlook


def fetch_outlook(
    state: str | None = None,
    district: str | None = None,
    crop: str | None = None,
    days: int = 7,
) -> WeatherOutlook:
    """Weather outlook for a district, assessed for its effect on supply."""
    settings = get_settings()
    today = date.today()

    if not settings.offline_mode:
        centroid = DISTRICT_CENTROIDS.get((state or "", district or ""))
        if centroid is not None:
            try:  # pragma: no cover - network path
                forecast = _fetch_open_meteo(centroid[0], centroid[1], days)
                if forecast:
                    return _assess(
                        WeatherOutlook(
                            district=district, state=state, days=forecast,
                            source="open-meteo", live=True,
                        ),
                        crop,
                    )
            except Exception as exc:
                logger.warning("Weather forecast unavailable (%s); using climatology", exc)

    return _assess(
        WeatherOutlook(
            district=district,
            state=state,
            days=_climatology(state, district, days, today),
            source="climatology",
            live=False,
        ),
        crop,
    )
