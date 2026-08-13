"""Stage 4: location normalisation (§4.3).

The resolution hierarchy from the report is applied strictly in order:

    explicit text extraction -> pincode mapping -> IP geolocation -> GPS

Each strategy reports the confidence it earned, so downstream agents can tell
a district named outright by the farmer from one inferred off an IP block.
"""

from __future__ import annotations

import math
import re

from ..schemas import GeoPoint, LocationContext
from .lexicon import (
    DISTRICT_CENTROIDS,
    PINCODE_PREFIXES,
    PLACE_ALIASES,
    STATE_DISTRICTS,
    all_districts,
)

_PINCODE_PATTERN = re.compile(r"\b([1-9]\d{5})\b")
_EARTH_RADIUS_KM = 6371.0


def _boundary_contains(haystack: str, needle: str) -> bool:
    idx = haystack.find(needle)
    if idx == -1:
        return False
    before = haystack[idx - 1] if idx > 0 else " "
    after_idx = idx + len(needle)
    after = haystack[after_idx] if after_idx < len(haystack) else " "
    return not (before.isalnum() and before.isascii()) and not (
        after.isalnum() and after.isascii()
    )


def from_text(text: str) -> LocationContext | None:
    """Extract a state and/or district named directly in the query."""
    lowered = text.lower()

    # Devanagari aliases first — they are unambiguous when present.
    for alias, canonical in PLACE_ALIASES.items():
        if alias in text:
            if canonical in STATE_DISTRICTS:
                return LocationContext(
                    state=canonical, resolved_by="text", confidence=0.85
                )
            for state, districts in STATE_DISTRICTS.items():
                if canonical in districts:
                    return LocationContext(
                        state=state, district=canonical, resolved_by="text", confidence=0.95
                    )

    # Districts before states: a district pins the location more tightly.
    for state, district in all_districts():
        if _boundary_contains(lowered, district.lower()):
            return LocationContext(
                state=state, district=district, resolved_by="text", confidence=0.95
            )

    for state in STATE_DISTRICTS:
        if _boundary_contains(lowered, state.lower()):
            return LocationContext(state=state, resolved_by="text", confidence=0.85)

    return None


def from_pincode(pincode: str | None) -> LocationContext | None:
    """Map a six-digit pincode onto its postal region."""
    if not pincode:
        return None
    match = _PINCODE_PATTERN.search(str(pincode))
    if not match:
        return None
    code = match.group(1)
    region = PINCODE_PREFIXES.get(code[:3])
    if region is None:
        return LocationContext(pincode=code, resolved_by="pincode", confidence=0.3)
    state, district = region
    return LocationContext(
        state=state, district=district, pincode=code, resolved_by="pincode", confidence=0.9
    )


def pincode_in_text(text: str) -> str | None:
    match = _PINCODE_PATTERN.search(text)
    return match.group(1) if match else None


def haversine_km(a: tuple[float, float], b: tuple[float, float]) -> float:
    """Great-circle distance in kilometres between two lat/lon pairs."""
    lat1, lon1 = math.radians(a[0]), math.radians(a[1])
    lat2, lon2 = math.radians(b[0]), math.radians(b[1])
    dlat, dlon = lat2 - lat1, lon2 - lon1
    h = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 2 * _EARTH_RADIUS_KM * math.asin(math.sqrt(h))


def from_coordinates(point: GeoPoint | None, max_km: float = 250.0) -> LocationContext | None:
    """Snap GPS coordinates to the nearest known district centroid."""
    if point is None:
        return None

    origin = (point.latitude, point.longitude)
    nearest: tuple[float, tuple[str, str]] | None = None
    for key, centroid in DISTRICT_CENTROIDS.items():
        distance = haversine_km(origin, centroid)
        if nearest is None or distance < nearest[0]:
            nearest = (distance, key)

    if nearest is None or nearest[0] > max_km:
        return None

    distance, (state, district) = nearest
    # Confidence decays linearly with distance from the centroid.
    confidence = round(max(0.4, 1.0 - distance / max_km), 3)
    return LocationContext(
        state=state, district=district, resolved_by="gps", confidence=confidence
    )


def from_ip(ip_address: str | None) -> LocationContext | None:
    """Coarse IP-based geolocation.

    Public geo-IP lookups are a paid network dependency, so the offline path
    resolves only the private/loopback case and otherwise declines to guess —
    reporting a low confidence is more useful than fabricating a district.
    """
    if not ip_address:
        return None
    if ip_address.startswith(("10.", "192.168.", "127.", "172.16.")):
        return None
    try:  # pragma: no cover - optional network dependency
        import httpx

        response = httpx.get(f"https://ipapi.co/{ip_address}/json/", timeout=3.0)
        payload = response.json()
        state = payload.get("region")
        district = payload.get("city")
        if state in STATE_DISTRICTS:
            valid = district if district in STATE_DISTRICTS[state] else None
            return LocationContext(
                state=state, district=valid, resolved_by="ip", confidence=0.6
            )
    except Exception:
        return None
    return None


def resolve(
    text: str,
    pincode: str | None = None,
    ip_address: str | None = None,
    coordinates: GeoPoint | None = None,
) -> LocationContext:
    """Apply the full resolution hierarchy and return the best context found."""
    explicit = from_text(text)
    if explicit is not None and explicit.district:
        return explicit

    by_pincode = from_pincode(pincode or pincode_in_text(text))
    if by_pincode is not None and by_pincode.district:
        return by_pincode

    by_gps = from_coordinates(coordinates)
    if by_gps is not None:
        return by_gps

    by_ip = from_ip(ip_address)
    if by_ip is not None:
        return by_ip

    # A state without a district still narrows the mandi search usefully.
    for candidate in (explicit, by_pincode):
        if candidate is not None:
            return candidate

    return LocationContext(resolved_by="unresolved", confidence=0.0)


def nearest_districts(state: str, district: str, limit: int = 4) -> list[tuple[str, str]]:
    """Districts closest to the given one, for cross-mandi price comparison.

    Returns ``(state, district)`` pairs rather than bare names: the nearest
    district to Indore may well sit in another state, and a caller that kept
    only the name would go on to query it under the original state.
    """
    origin = DISTRICT_CENTROIDS.get((state, district))
    if origin is None:
        return [(state, d) for d in STATE_DISTRICTS.get(state, []) if d != district][:limit]

    ranked = sorted(
        (
            (haversine_km(origin, centroid), key)
            for key, centroid in DISTRICT_CENTROIDS.items()
            if key != (state, district)
        ),
        key=lambda pair: pair[0],
    )
    return [key for _, key in ranked[:limit]]
