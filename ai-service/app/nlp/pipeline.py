"""The four-stage NLP pipeline that fronts every farmer query (§4.1).

    language detection -> intent classification -> entity extraction
                       -> location normalisation
"""

from __future__ import annotations

from ..schemas import GeoPoint, NLPResult
from .entities import extract_all_crops, extract_crop, extract_quantity
from .intents import classify_intent, is_ambiguous
from .language import detect_language
from .location import resolve


def run(
    query: str,
    pincode: str | None = None,
    ip_address: str | None = None,
    coordinates: GeoPoint | None = None,
    language_override: str | None = None,
) -> NLPResult:
    """Convert a raw farmer query into the structured representation agents consume."""
    language = language_override or detect_language(query)
    intent, confidence = classify_intent(query)
    crop, crop_hindi = extract_crop(query)
    quantity, unit = extract_quantity(query)
    location = resolve(query, pincode=pincode, ip_address=ip_address, coordinates=coordinates)

    return NLPResult(
        language=language,  # type: ignore[arg-type]
        intent=intent,
        intent_confidence=confidence,
        crop=crop,
        crop_hindi=crop_hindi,
        quantity_value=quantity,
        quantity_unit=unit,
        location=location,
    )


__all__ = ["run", "extract_all_crops", "is_ambiguous"]
