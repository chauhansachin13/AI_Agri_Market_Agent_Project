"""Stage 2: hybrid rule-based intent classification (§4.1.2).

A deterministic scorer was chosen over a neural classifier so that the
system's behaviour stays predictable and auditable — the report's stated
rationale, given that the output is advice farmers act on.  Each intent owns a
weighted trigger vocabulary in both Hindi and English; the highest aggregate
score wins, with `price_query` as the fallback.
"""

from __future__ import annotations

from ..schemas import Intent
from .lexicon import DEFAULT_INTENT, INTENT_TRIGGERS


def score_intents(text: str) -> dict[str, float]:
    """Aggregate trigger weights per intent class."""
    lowered = f" {text.lower().strip()} "
    scores: dict[str, float] = {intent: 0.0 for intent in INTENT_TRIGGERS}

    for intent, triggers in INTENT_TRIGGERS.items():
        for phrase, weight in triggers.items():
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
