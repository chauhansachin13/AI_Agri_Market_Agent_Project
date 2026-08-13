"""eNAM buyer and APMC contact integration (§4.4.2).

eNAM publishes APMC names, addresses, contact numbers, trading hours and
traded commodities per state and district.  This module performs the
state-wise extraction with district filtering that the ``buyer_search`` intent
depends on, and degrades to the bundled dataset when the platform is
unreachable.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from ..config import get_settings
from ..schemas import BuyerRecord
from .sample_dataset import synthesize_buyers

logger = logging.getLogger(__name__)


@dataclass
class BuyerFetchResult:
    buyers: list[BuyerRecord]
    live: bool
    error: str | None = None

    @property
    def degraded(self) -> bool:
        return not self.live


def _normalise(raw: dict) -> BuyerRecord | None:
    name = str(raw.get("apmc_name") or raw.get("apmcName") or "").strip()
    if not name:
        return None
    commodities = raw.get("commodities") or []
    if isinstance(commodities, str):
        commodities = [c.strip() for c in commodities.split(",") if c.strip()]
    return BuyerRecord(
        apmc_name=name,
        state=str(raw.get("state") or raw.get("stateName") or "").strip(),
        district=str(raw.get("district") or raw.get("districtName") or "").strip(),
        address=str(raw.get("address") or "").strip(),
        contact=str(raw.get("contact") or raw.get("phone") or "").strip(),
        trading_hours=str(raw.get("trading_hours") or "").strip(),
        commodities=list(commodities),
        source=str(raw.get("source") or "enam"),
    )


def _request_live(state: str | None, district: str | None) -> list[dict]:
    import httpx

    settings = get_settings()
    params: dict[str, object] = {}
    if state:
        params["stateName"] = state
    if district:
        params["districtName"] = district

    response = httpx.get(
        f"{settings.enam_base_url}/trade_data_list",
        params=params,
        timeout=settings.http_timeout_seconds,
        headers={"Accept": "application/json"},
    )
    response.raise_for_status()
    payload = response.json()
    if isinstance(payload, dict):
        return list(payload.get("data", []))
    return list(payload)


def fetch_buyers(
    state: str | None = None,
    district: str | None = None,
    commodity: str | None = None,
    limit: int = 12,
) -> BuyerFetchResult:
    """Return APMC/buyer contacts for a location, optionally filtered by crop."""
    settings = get_settings()

    if not settings.offline_mode:
        try:
            raw = _request_live(state, district)
            buyers = [b for b in (_normalise(item) for item in raw) if b is not None]
            if buyers:
                buyers = _apply_commodity_filter(buyers, commodity)
                return BuyerFetchResult(buyers=buyers[:limit], live=True)
        except Exception as exc:
            logger.warning("eNAM unavailable (%s); using bundled dataset", exc)

    fallback = [BuyerRecord(**item) for item in synthesize_buyers(state, district)]
    fallback = _apply_commodity_filter(fallback, commodity)
    return BuyerFetchResult(
        buyers=fallback[:limit],
        live=False,
        error=None if settings.offline_mode else "eNAM data unavailable",
    )


def _apply_commodity_filter(
    buyers: list[BuyerRecord], commodity: str | None
) -> list[BuyerRecord]:
    """Prefer APMCs that trade the queried crop, but never return an empty list.

    A farmer asking who buys wheat is better served by the full mandi list than
    by nothing at all when commodity metadata is missing upstream.
    """
    if not commodity:
        return buyers
    matching = [
        b for b in buyers
        if any(commodity.lower() in c.lower() for c in b.commodities)
    ]
    return matching or buyers
