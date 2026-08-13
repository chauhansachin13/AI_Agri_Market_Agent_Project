"""Mandi Tool — live crop prices from Agmarknet, filtered by crop and location."""

from __future__ import annotations

from ..data import agmarknet_gov
from ..schemas import PriceRecord
from .base import Tool, ToolResult


def _summarise(records: list[PriceRecord], crop: str | None, where: str) -> str:
    if not records:
        return f"No mandi price records found for {crop or 'the requested crop'} in {where}."

    best = agmarknet_gov.best_price_mandi(records)
    prices = [r.modal_price for r in records]
    average = sum(prices) / len(prices)
    lines = [
        f"{len(records)} mandi records for {crop or 'multiple crops'} in {where}. "
        f"Average modal price Rs {average:.0f}/quintal; "
        f"best price Rs {best.modal_price:.0f} at {best.market} ({best.district})."
    ]
    for record in sorted(records, key=lambda r: r.modal_price, reverse=True)[:5]:
        lines.append(
            f"  - {record.market}, {record.district}: modal Rs {record.modal_price:.0f} "
            f"(min {record.min_price:.0f} / max {record.max_price:.0f}) on {record.arrival_date}"
        )
    dispersion = agmarknet_gov.price_dispersion_index(records)
    if dispersion > 0:
        lines.append(f"  Price dispersion index across these mandis: {dispersion:.3f}")
    return "\n".join(lines)


def fetch_mandi_prices(
    crop: str | None = None,
    state: str | None = None,
    district: str | None = None,
    limit: int | None = None,
) -> ToolResult:
    """Fetch and normalise current mandi prices for a crop and location."""
    result = agmarknet_gov.fetch_prices(
        commodity=crop, state=state, district=district, limit=limit
    )
    where = ", ".join(p for p in (district, state) if p) or "the default districts"

    return ToolResult(
        ok=bool(result.records),
        data=result.records,
        summary=_summarise(result.records, crop, where),
        source="agmarknet" if result.live else "sample",
        degraded=result.degraded,
        error=result.error if not result.records else None,
    )


TOOL = Tool(
    name="mandi_prices",
    description=(
        "Fetch live wholesale mandi prices from the Government of India Agmarknet "
        "dataset for a specific crop, state and district. Returns modal, minimum "
        "and maximum price per quintal for each market. This is the only "
        "authoritative source for price values — never state a price that did not "
        "come from this tool."
    ),
    func=fetch_mandi_prices,
    args_schema={
        "crop": "Agmarknet commodity name, e.g. 'Tomato', 'Wheat'",
        "state": "Indian state name, e.g. 'Bihar'",
        "district": "District name, e.g. 'Patna'",
        "limit": "Maximum number of records to return (integer)",
    },
)
