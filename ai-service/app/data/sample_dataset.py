"""Deterministic offline dataset used when the government APIs are unreachable.

This is a reproducible stand-in, not a claim about real prices.  Every record
it produces is tagged ``source="sample"`` so the fact-check agent downgrades
any claim resting on it, and the API response is flagged ``degraded``.

The generator is seeded from the (commodity, district, day) triple, so the
same query returns the same series on every run — which is what makes the test
suite and the demo reproducible.
"""

from __future__ import annotations

import hashlib
import math
from datetime import date, timedelta

from ..nlp.lexicon import STATE_DISTRICTS
from ..schemas import PriceRecord

# Typical modal price in INR per quintal, and the annual seasonal swing.
CROP_BASELINES: dict[str, tuple[float, float]] = {
    "Tomato": (1850.0, 0.42),
    "Onion": (2100.0, 0.35),
    "Wheat": (2350.0, 0.09),
    "Potato": (1250.0, 0.30),
    "Rice": (2180.0, 0.11),
    "Lentil (Masur)(Whole)": (6100.0, 0.14),
    "Maize": (2050.0, 0.13),
    "Mustard": (5450.0, 0.16),
    "Bengal Gram (Gram)(Whole)": (5300.0, 0.15),
    "Sugarcane": (340.0, 0.06),
    "Cauliflower": (1450.0, 0.38),
    "Brinjal": (1550.0, 0.33),
    "Garlic": (7800.0, 0.45),
    "Green Chilli": (3900.0, 0.40),
    "Soyabean": (4600.0, 0.18),
}

DEFAULT_BASELINE = (2000.0, 0.20)

# A handful of real mandi names per district keeps the demo output plausible.
MARKETS: dict[str, list[str]] = {
    "Patna": ["Patna (Musallahpur)", "Patna City", "Danapur"],
    "Muzaffarpur": ["Muzaffarpur", "Motipur", "Sahebganj"],
    "Gaya": ["Gaya", "Sherghati", "Tekari"],
    "Bhagalpur": ["Bhagalpur", "Naugachia", "Kahalgaon"],
    "Nalanda": ["Biharsharif", "Hilsa", "Rajgir"],
    "Vaishali": ["Hajipur", "Mahua", "Lalganj"],
    "Lucknow": ["Lucknow", "Sitapur Road", "Mohanlalganj"],
    "Kanpur": ["Kanpur (Grain)", "Bilhaur", "Ghatampur"],
    "Varanasi": ["Varanasi", "Pindra", "Chandauli"],
    "Bhopal": ["Bhopal", "Berasia", "Bairagarh"],
    "Indore": ["Indore (F&V)", "Sanwer", "Mhow"],
    "Ludhiana": ["Ludhiana", "Khanna", "Jagraon"],
    "Amritsar": ["Amritsar", "Majitha", "Rayya"],
    "Jaipur": ["Jaipur (Muhana)", "Chomu", "Bassi"],
    "Karnal": ["Karnal", "Gharaunda", "Nilokheri"],
}

DEFAULT_MARKETS = ["Main Mandi", "Sub Yard", "Regulated Market"]


def _seeded_unit(*parts: object) -> float:
    """A stable pseudo-random float in [0, 1) derived from the given parts."""
    digest = hashlib.sha256("|".join(str(p) for p in parts).encode()).hexdigest()
    return int(digest[:12], 16) / float(16**12)


def _markets_for(district: str) -> list[str]:
    return MARKETS.get(district, [f"{district} {name}" for name in DEFAULT_MARKETS])


def _districts_for(state: str | None, district: str | None) -> list[tuple[str, str]]:
    if state and district:
        return [(state, district)]
    if state:
        return [(state, d) for d in STATE_DISTRICTS.get(state, [])[:5]]
    if district:
        for st, districts in STATE_DISTRICTS.items():
            if district in districts:
                return [(st, district)]
        return [("Bihar", district)]
    # No location at all: sample the primary evaluation districts (§5.1).
    return [("Bihar", d) for d in ["Patna", "Muzaffarpur", "Gaya", "Bhagalpur", "Nalanda"]]


def _modal_price(commodity: str, district: str, market: str, day: date) -> float:
    base, swing = CROP_BASELINES.get(commodity, DEFAULT_BASELINE)

    # Seasonal component: one full cycle per year, peaking before the harvest.
    day_of_year = day.timetuple().tm_yday
    seasonal = 1.0 + swing * math.sin(2 * math.pi * (day_of_year - 60) / 365.0)

    # District premium: structural, stable across days.
    district_premium = 0.90 + 0.20 * _seeded_unit(commodity, district)

    # Market-level spread within a district.
    market_offset = 0.96 + 0.08 * _seeded_unit(commodity, district, market)

    # Day-to-day noise, plus a slow drift so trends are detectable.  The drift
    # is a function of the absolute ordinal date, not the day of the month —
    # keying it to `day.day` would reset the trend at every month boundary and
    # inject a sawtooth the EMA model would read as a real reversal.
    noise = 0.97 + 0.06 * _seeded_unit(commodity, market, day.isoformat())
    phase = 2 * math.pi * _seeded_unit(commodity, district)
    drift = 1.0 + 0.03 * math.sin(phase + day.toordinal() / 47.0)

    price = base * seasonal * district_premium * market_offset * noise * drift
    return round(price, 2)


def synthesize_price_series(
    commodity: str | None = None,
    state: str | None = None,
    district: str | None = None,
    days: int = 1,
    reference_date: date | None = None,
) -> list[PriceRecord]:
    """Build a reproducible price series for the requested crop and area."""
    commodities = [commodity] if commodity else ["Tomato", "Onion", "Wheat", "Potato"]
    locations = _districts_for(state, district)
    today = reference_date or date.today()

    records: list[PriceRecord] = []
    for offset in range(days):
        day = today - timedelta(days=offset)
        for crop in commodities:
            for st, dist in locations:
                for market in _markets_for(dist):
                    modal = _modal_price(crop, dist, market, day)
                    spread = modal * (0.04 + 0.05 * _seeded_unit(market, day.isoformat()))
                    records.append(
                        PriceRecord(
                            state=st,
                            district=dist,
                            market=market,
                            commodity=crop,
                            variety="Other",
                            grade="FAQ",
                            arrival_date=day.isoformat(),
                            min_price=round(modal - spread, 2),
                            max_price=round(modal + spread, 2),
                            modal_price=modal,
                            source="sample",
                        )
                    )
    return records


def synthesize_buyers(state: str | None, district: str | None) -> list[dict]:
    """APMC/buyer records in the shape the eNAM scraper returns."""
    locations = _districts_for(state, district)
    buyers: list[dict] = []
    for st, dist in locations:
        for index, market in enumerate(_markets_for(dist)[:3]):
            buyers.append(
                {
                    "apmc_name": f"{market} APMC",
                    "state": st,
                    "district": dist,
                    "address": f"{market} Yard, {dist}, {st}",
                    "contact": f"0{6 + index}{_seeded_unit(market, dist):.8f}".replace(".", "")[:11],
                    "trading_hours": "06:00 - 14:00 IST",
                    "commodities": ["Wheat", "Potato", "Onion", "Tomato"],
                    "source": "sample",
                }
            )
    return buyers
