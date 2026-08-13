"""Stage 3: crop, quantity and variety extraction (§4.1.3)."""

from __future__ import annotations

import re

from ..i18n.registry import LANGUAGES
from .lexicon import (
    CROP_HINDI_LABEL,
    CROP_VOCABULARY,
    UNIT_SYNONYMS,
    UNIT_TO_QUINTAL,
)

# Units are written in every supported script, so the pattern must accept
# Devanagari, Bengali and Tamil letters as well as Latin.
_QUANTITY_PATTERN = re.compile(
    r"(?P<value>\d+(?:[.,]\d+)?)\s*(?P<unit>[A-Za-zऀ-ॿঀ-৿஀-௿]+)",
    re.UNICODE,
)


def _regional_crop_forms() -> list[tuple[str, str]]:
    """Crop surface forms contributed by every regional language.

    A Marathi farmer writes "कांदा", not "प्याज"; without this the crop simply
    would not be recognised and the whole answer would degrade.
    """
    forms: list[tuple[str, str]] = []
    for spec in LANGUAGES.values():
        for commodity, label in spec.crop_names.items():
            forms.append((label, commodity))
        for commodity, extras in spec.extra_crop_forms.items():
            forms.extend((extra, commodity) for extra in extras)
    return forms

# Dependent vowel signs (matras) that carry case and number in Indic scripts.
_MATRAS = "ािीुूृेैोौंँः্ািীুূেৈোৌং" "ாிீுூெேைொோௌ்"


def _indic_stem(form: str) -> str | None:
    """The consonant stem of an Indic word, with trailing vowel signs removed.

    Indic languages inflect by replacing the final vowel sign rather than
    appending: Marathi कांदा (onion) becomes कांद्याचा in the oblique, so the
    citation form is not a prefix of the inflected one and a plain containment
    check misses it entirely. Matching on the stem recovers these.
    """
    stem = form.rstrip(_MATRAS)
    # Keep enough of the word that the stem is still discriminative.
    if len(stem) >= 3 and stem != form:
        return stem
    return None


def _surface_variants(form: str) -> list[str]:
    """Accepted written forms of one vocabulary entry.

    Farmers write "onions" as readily as "onion", and the lexicon stores only
    the singular. Indic scripts do not pluralise that way — they inflect the
    ending — so each script family gets the treatment that fits it.
    """
    variants = [form]

    if not form.isascii():
        stem = _indic_stem(form)
        if stem:
            variants.append(stem)
        return variants

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
        for form_source in (
            [
                (form, commodity)
                for commodity, forms in CROP_VOCABULARY.items()
                for form in forms
            ],
            _regional_crop_forms(),
        )
        for form, commodity in form_source
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
