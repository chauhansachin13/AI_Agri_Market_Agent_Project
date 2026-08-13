"""Location Tool — resolve a farmer's location and map it to nearby mandis."""

from __future__ import annotations

from ..nlp import location as location_nlp
from ..schemas import GeoPoint
from .base import Tool, ToolResult


def resolve_location(
    text: str = "",
    pincode: str | None = None,
    ip_address: str | None = None,
    latitude: float | None = None,
    longitude: float | None = None,
) -> ToolResult:
    """Resolve location through the text -> pincode -> IP -> GPS hierarchy."""
    coordinates = None
    if latitude is not None and longitude is not None:
        coordinates = GeoPoint(latitude=latitude, longitude=longitude)

    context = location_nlp.resolve(
        text, pincode=pincode, ip_address=ip_address, coordinates=coordinates
    )

    if context.state is None and context.district is None:
        return ToolResult(
            ok=False,
            data=context,
            summary="Could not determine the farmer's location from the available signals.",
            error="location_unresolved",
        )

    where = ", ".join(p for p in (context.district, context.state) if p)
    neighbours: list[tuple[str, str]] = []
    if context.state and context.district:
        neighbours = location_nlp.nearest_districts(context.state, context.district)

    summary = (
        f"Location resolved to {where} via {context.resolved_by} "
        f"(confidence {context.confidence:.2f})."
    )
    if neighbours:
        listed = ", ".join(f"{d} ({s})" for s, d in neighbours)
        summary += f" Nearby districts for price comparison: {listed}."

    return ToolResult(
        ok=True,
        data={"context": context, "nearby_districts": neighbours},
        summary=summary,
        source=context.resolved_by,
    )


TOOL = Tool(
    name="resolve_location",
    description=(
        "Resolve the farmer's location from the query text, a pincode, an IP "
        "address or GPS coordinates, and return the state, district and the "
        "nearby districts whose mandis are worth comparing prices against."
    ),
    func=resolve_location,
    args_schema={
        "text": "The farmer's query text",
        "pincode": "Six-digit Indian pincode",
        "ip_address": "Client IP address",
        "latitude": "GPS latitude (float)",
        "longitude": "GPS longitude (float)",
    },
)
