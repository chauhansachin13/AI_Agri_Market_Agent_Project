"""Stage 2: hybrid rule-based intent classification (§4.1.2).

A deterministic scorer was chosen over a neural classifier so that the
system's behaviour stays predictable and auditable — the report's stated
rationale, given that the output is advice farmers act on.  Each intent owns a
weighted trigger vocabulary in both Hindi and English; the highest aggregate
score wins, with `price_query` as the fallback.
"""

from __future__ import annotations

from ..i18n.registry import LANGUAGES
from ..schemas import Intent
from .lexicon import DEFAULT_INTENT, INTENT_TRIGGERS


def _regional_triggers() -> dict[str, dict[str, int]]:
    """Trigger words contributed by the regional language registry.

    The Hindi and English vocabularies in `lexicon` are weighted by hand and
    stay authoritative. Every other language contributes its triggers at a
    uniform weight of 2, which is enough to classify correctly without
    re-tuning seven vocabularies against each other.
    """
    # A word for "price" appears in almost every query, including ones that are
    # really asking whether to sell. The more specific intents therefore carry
    # more weight, so they do not lose a tie to the ubiquitous term.
    weights = {
        "price_query": 2,
        "buyer_search": 3,
        "sell_advice": 3,
        "trend_analysis": 3,
    }

    merged: dict[str, dict[str, int]] = {intent: {} for intent in INTENT_TRIGGERS}
    for spec in LANGUAGES.values():
        for intent, phrases in spec.intent_triggers.items():
            if intent not in merged:
                continue
            for phrase in phrases:
                merged[intent].setdefault(phrase.lower(), weights.get(intent, 2))
    return merged


def score_intents(text: str) -> dict[str, float]:
    """Aggregate trigger weights per intent class, across all languages."""
    lowered = f" {text.lower().strip()} "
    scores: dict[str, float] = {intent: 0.0 for intent in INTENT_TRIGGERS}

    regional = _regional_triggers()

    for intent in INTENT_TRIGGERS:
        # Hand-weighted terms first; regional terms only where they add a
        # phrase the curated vocabulary does not already cover.
        combined = dict(regional.get(intent, {}))
        combined.update(INTENT_TRIGGERS[intent])

        for phrase, weight in combined.items():
            if phrase in lowered:
                # Multi-word phrases are far more discriminative than single
                # tokens, so they carry an additional multiplier.
                multiplier = 1.5 if " " in phrase else 1.0
                scores[intent] += weight * multiplier

    return scores


def classify_intent(text: str) -> tuple[Intent, float]:
    """Return the winning intent and a normalised confidence in [0, 1]."""
    scores = score_intents(text)
    total = sum(scores.values())

    if total == 0:
        return DEFAULT_INTENT, 0.25  # type: ignore[return-value]

    best = max(scores, key=lambda k: scores[k])
    best_score = scores[best]

    # Confidence blends dominance (how far ahead the winner is) with absolute
    # evidence, so a single weak keyword never yields a high-confidence label.
    dominance = best_score / total
    evidence = min(best_score / 6.0, 1.0)
    confidence = round(0.6 * dominance + 0.4 * evidence, 3)

    return best, min(confidence, 1.0)  # type: ignore[return-value]


def is_ambiguous(text: str, margin: float = 0.15) -> bool:
    """True when the top two intents are within ``margin`` of each other.

    Section 6.2 records that sell_advice and trend_analysis are linguistically
    close in colloquial Hindi; callers use this to widen the data they gather.
    """
    scores = score_intents(text)
    total = sum(scores.values())
    if total == 0:
        return True

    ranked = sorted(scores.values(), reverse=True)
    if len(ranked) < 2:
        return False
    return (ranked[0] - ranked[1]) / total < margin
