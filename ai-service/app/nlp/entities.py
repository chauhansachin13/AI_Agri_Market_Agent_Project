"""Stage 3: crop, quantity and variety extraction (§4.1.3)."""

from __future__ import annotations

import re

from .lexicon import (
    CROP_HINDI_LABEL,
    CROP_VOCABULARY,
    UNIT_SYNONYMS,
    UNIT_TO_QUINTAL,
)

_QUANTITY_PATTERN = re.compile(
    r"(?P<value>\d+(?:[.,]\d+)?)\s*(?P<unit>[A-Za-zऀ-ॿ]+)",
    re.UNICODE,
)

def _surface_variants(form: str) -> list[str]:
    """Accepted written forms of one vocabulary entry.

    Farmers write "onions" as readily as "onion", and the lexicon stores only
    the singular. Devanagari does not pluralise this way, so variants are
    generated for ASCII forms only.
    """
    variants = [form]
    if form.isascii() and len(form) > 2:
        if form.endswith(("s", "sh", "ch", "x", "z", "o")):
            # tomato -> tomatoes, potato -> potatoes
            variants.append(form + "es")
        elif form.endswith("y"):
            variants.append(form[:-1] + "ies")
        else:
            variants.append(form + "s")
    return variants


# Longest surface forms first so that "phool gobhi" wins over "gobhi".
_CROP_FORMS: list[tuple[str, str]] = sorted(
    (
        (variant, commodity)
        for commodity, forms in CROP_VOCABULARY.items()
        for form in forms
        for variant in _surface_variants(form)
    ),
    key=lambda pair: len(pair[0]),
    reverse=True,
)

_UNIT_FORMS: dict[str, str] = {
    form: unit for unit, forms in UNIT_SYNONYMS.items() for form in forms
}


def _boundary_match(haystack: str, needle: str) -> bool:
    """Word-boundary containment that also works for Devanagari.

    Python's ``\\b`` is unreliable across script boundaries, so adjacency is
    checked explicitly against Latin letters and digits only.
    """
    start = 0
    while True:
        idx = haystack.find(needle, start)
        if idx == -1:
            return False
        before = haystack[idx - 1] if idx > 0 else " "
        after_idx = idx + len(needle)
        after = haystack[after_idx] if after_idx < len(haystack) else " "
        if not (before.isalnum() and before.isascii()) and not (
            after.isalnum() and after.isascii()
        ):
            return True
        start = idx + 1


def extract_crop(text: str) -> tuple[str | None, str | None]:
    """Return ``(agmarknet_commodity, hindi_label)`` for the first crop found."""
    lowered = text.lower()
    for form, commodity in _CROP_FORMS:
        if _boundary_match(lowered, form.lower()):
            return commodity, CROP_HINDI_LABEL.get(commodity)
    return None, None


def extract_all_crops(text: str) -> list[str]:
    """Every distinct crop mentioned, in order of appearance."""
    lowered = text.lower()
    found: list[tuple[int, str]] = []
    for form, commodity in _CROP_FORMS:
        idx = lowered.find(form.lower())
        if idx != -1 and _boundary_match(lowered, form.lower()):
            if commodity not in {c for _, c in found}:
                found.append((idx, commodity))
    return [commodity for _, commodity in sorted(found)]


def extract_quantity(text: str) -> tuple[float | None, str | None]:
    """Extract a numeric quantity with a normalised agricultural unit."""
    for match in _QUANTITY_PATTERN.finditer(text.lower()):
        unit_token = match.group("unit")
        unit = _UNIT_FORMS.get(unit_token)
        if unit is None:
            continue
        raw = match.group("value").replace(",", ".")
        try:
            value = float(raw)
        except ValueError:
            continue
        return value, unit
    return None, None


def to_quintals(value: float, unit: str) -> float:
    """Convert a quantity to quintals, the unit Agmarknet prices are quoted in."""
    return round(value * UNIT_TO_QUINTAL.get(unit, 1.0), 4)
