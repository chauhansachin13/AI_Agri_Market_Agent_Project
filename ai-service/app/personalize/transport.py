"""Net realisation after transport (Section 4.6.1).

The system's own market notes already say it: transport between districts in
the Hindi belt runs roughly Rs 40-90 per quintal under 150 km, "so a price gap
smaller than that between two mandis is rarely worth travelling for". The
sell-decision agent was quoting gross gaps anyway, which is advice that costs a
farmer money — a Rs 60 gap looks worth a trip and is not.

What a farmer actually earns is the price at the far mandi, minus the cost of
getting the load there. This computes that, so the recommendation names the
mandi with the best *net* return rather than the best sticker price.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..nlp.lexicon import DISTRICT_CENTROIDS
from ..nlp.location import haversine_km

# Rupees per quintal per km, for a shared truck on Hindi-belt district roads.
# Documented as an estimate, and exposed so a deployment can tune it.
RATE_PER_QUINTAL_KM = 0.45

# Loading, unloading and mandi entry, charged per trip regardless of distance.
FIXED_HANDLING_PER_QUINTAL = 18.0

# Below this there is no journey: the farmer is already at their local mandi.
SAME_DISTRICT_KM = 0.0


@dataclass
class NetRealisation:
    market: str
    district: str
    gross_price: float
    distance_km: float
    transport_cost: float
    net_price: float

    @property
    def worth_travelling(self) -> bool:
        return self.net_price > self.gross_price - self.transport_cost + 0.01


def distance_between(origin: tuple[str, str] | None, destination: tuple[str, str] | None) -> float:
    """Kilometres between two (state, district) pairs, 0 when the same or unknown."""
    if not origin or not destination or origin == destination:
        return SAME_DISTRICT_KM
    a = DISTRICT_CENTROIDS.get(origin)
    b = DISTRICT_CENTROIDS.get(destination)
    if a is None or b is None:
        # Unknown geography: assume a local trip rather than inventing a
        # distance that would silently penalise a real option.
        return SAME_DISTRICT_KM
    return round(haversine_km(a, b), 1)


def transport_cost(distance_km: float) -> float:
    """Cost per quintal of moving produce `distance_km`."""
    if distance_km <= 0:
        return 0.0
    return round(distance_km * RATE_PER_QUINTAL_KM + FIXED_HANDLING_PER_QUINTAL, 2)


def net_realisations(records, origin: tuple[str, str] | None) -> list[NetRealisation]:
    """Rank mandi records by what the farmer would actually take home."""
    out: list[NetRealisation] = []
    for record in records:
        distance = distance_between(origin, (record.state, record.district))
        cost = transport_cost(distance)
        out.append(
            NetRealisation(
                market=record.market,
                district=record.district,
                gross_price=record.modal_price,
                distance_km=distance,
                transport_cost=cost,
                net_price=round(record.modal_price - cost, 2),
            )
        )
    return sorted(out, key=lambda r: r.net_price, reverse=True)


def best_net(records, origin: tuple[str, str] | None) -> NetRealisation | None:
    ranked = net_realisations(records, origin)
    return ranked[0] if ranked else None
