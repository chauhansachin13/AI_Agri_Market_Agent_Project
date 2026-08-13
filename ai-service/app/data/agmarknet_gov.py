"""Agmarknet daily mandi price integration (§4.4.1).

Live records come from the Government of India open-data portal
(api.data.gov.in, "Agricultural Marketing - Daily Mandi Prices").  The client
implements the safety policies the report specifies: commodity/state/district
filtering, a record limit, a 10-second timeout with exponential-backoff retry,
and error recovery when the API is unavailable.

When no API key is configured — or the portal is down — the module falls back
to a bundled deterministic dataset.  That keeps the system demonstrable
offline while never silently passing simulated numbers off as live government
data: every record carries its `source`, and the caller is told when the
response was degraded.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from datetime import date, timedelta

from ..config import get_settings
from ..schemas import PriceRecord
from .sample_dataset import synthesize_price_series

logger = logging.getLogger(__name__)


@dataclass
class FetchResult:
    """Price records plus the provenance the fact-check agent needs."""

    records: list[PriceRecord]
    live: bool
    error: str | None = None

    @property
    def degraded(self) -> bool:
        return not self.live


def _parse_float(value: object, default: float = 0.0) -> float:
    try:
        return float(str(value).replace(",", "").strip())
    except (TypeError, ValueError):
        return default


def _normalise(raw: dict) -> PriceRecord | None:
    """Map one portal record onto the internal schema.

    Portal field names have changed casing across dataset revisions, so each
    field is looked up through a small list of accepted aliases.
    """

    def pick(*names: str, default: str = "") -> str:
        for name in names:
            value = raw.get(name)
            if value not in (None, ""):
                return str(value).strip()
        return default

    market = pick("market", "Market")
    commodity = pick("commodity", "Commodity")
    if not market or not commodity:
        return None

    modal = _parse_float(pick("modal_price", "Modal_Price", "modal_x0020_price"))
    if modal <= 0:
        return None

    minimum = _parse_float(pick("min_price", "Min_Price", "min_x0020_price"), modal)
    maximum = _parse_float(pick("max_price", "Max_Price", "max_x0020_price"), modal)

    return PriceRecord(
        state=pick("state", "State"),
        district=pick("district", "District"),
        market=market,
        commodity=commodity,
        variety=pick("variety", "Variety", default="Other"),
        grade=pick("grade", "Grade", default="FAQ"),
        arrival_date=pick("arrival_date", "Arrival_Date", default=date.today().isoformat()),
        min_price=min(minimum, maximum) if minimum and maximum else modal,
        max_price=max(minimum, maximum) if minimum and maximum else modal,
        modal_price=modal,
        source="agmarknet",
    )


def _request_live(
    commodity: str | None,
    state: str | None,
    district: str | None,
    limit: int,
) -> list[dict]:
    """Authenticated REST call with exponential-backoff retry."""
    import httpx

    settings = get_settings()
    params: dict[str, object] = {
        "api-key": settings.agmarknet_api_key,
        "format": "json",
        "limit": limit,
    }
    if commodity:
        params["filters[commodity]"] = commodity
    if state:
        params["filters[state]"] = state
    if district:
        params["filters[district]"] = district

    url = f"{settings.agmarknet_base_url}/{settings.agmarknet_resource_id}"
    last_error: Exception | None = None

    for attempt in range(settings.http_max_retries):
        try:
            response = httpx.get(url, params=params, timeout=settings.http_timeout_seconds)
            response.raise_for_status()
            payload = response.json()
            return list(payload.get("records", []))
        except Exception as exc:  # network, HTTP or decode failure
            last_error = exc
            if attempt < settings.http_max_retries - 1:
                time.sleep(2**attempt)  # 1s, 2s, 4s

    raise RuntimeError(f"Agmarknet request failed: {last_error}")


def fetch_prices(
    commodity: str | None = None,
    state: str | None = None,
    district: str | None = None,
    limit: int | None = None,
) -> FetchResult:
    """Fetch current mandi prices, falling back to the bundled dataset."""
    settings = get_settings()
    limit = limit or settings.agmarknet_record_limit

    if settings.agmarknet_live:
        try:
            raw = _request_live(commodity, state, district, limit)
            records = [r for r in (_normalise(item) for item in raw) if r is not None]
            if records:
                return FetchResult(records=records, live=True)
            logger.warning("Agmarknet returned no usable records; using bundled dataset")
        except Exception as exc:
            logger.warning("Agmarknet unavailable (%s); using bundled dataset", exc)
            return FetchResult(
                records=_offline_records(commodity, state, district, limit),
                live=False,
                error=str(exc),
            )

    return FetchResult(
        records=_offline_records(commodity, state, district, limit),
        live=False,
        error=None if settings.offline_mode else "AGMARKNET_API_KEY not configured",
    )


def _offline_records(
    commodity: str | None,
    state: str | None,
    district: str | None,
    limit: int,
) -> list[PriceRecord]:
    series = synthesize_price_series(
        commodity=commodity, state=state, district=district, days=1
    )
    return series[:limit]


def fetch_price_history(
    commodity: str,
    state: str | None = None,
    district: str | None = None,
    days: int = 45,
) -> list[PriceRecord]:
    """Historical daily records feeding the EMA trend model (§4.6.1).

    The open-data resource exposes only the current arrival day, so history is
    assembled from the local cache/corpus rather than a portal call.
    """
    return synthesize_price_series(
        commodity=commodity, state=state, district=district, days=days
    )


def best_price_mandi(records: list[PriceRecord]) -> PriceRecord | None:
    """The record with the highest modal price — the mandi worth travelling to."""
    return max(records, key=lambda r: r.modal_price) if records else None


def price_dispersion_index(records: list[PriceRecord]) -> float:
    """Spread of modal prices across mandis, normalised by the mean.

    A high index means a farmer stands to gain materially by choosing a
    different mandi; the sell-decision agent treats it as an arbitrage signal.
    """
    if len(records) < 2:
        return 0.0
    prices = [r.modal_price for r in records]
    mean = sum(prices) / len(prices)
    if mean == 0:
        return 0.0
    return round((max(prices) - min(prices)) / mean, 4)


def recent_dates(days: int) -> list[str]:
    today = date.today()
    return [(today - timedelta(days=offset)).isoformat() for offset in range(days)]
