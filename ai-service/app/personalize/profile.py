"""Farmer profiles for personalised advice (Section 6.3, "Federated Learning").

The report's goal is to adapt recommendations to the individual — crop
portfolio, typical selling patterns, risk tolerance — *without centralising
sensitive personal data*. This module holds the local half of that: a profile
derived from a farmer's own history, which never leaves their record.

What personalisation actually changes is the sell/wait threshold. Two farmers
looking at identical prices should not always get identical advice:

  * a farmer who cannot store produce has to sell into a falling market, so
    telling them to wait is useless advice;
  * a farmer with storage and no immediate cash need can hold for a better
    price, so the bar for "sell now" should be higher;
  * a farmer whose last three "wait" calls lost them money has earned a more
    conservative recommendation.

Nothing here invents data. A profile with no history returns a neutral
adjustment, and the reason string always states what was applied, so the
farmer can see why their advice differs.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

RiskTolerance = Literal["cautious", "balanced", "patient"]

# How far each disposition moves the sell threshold. A cautious farmer needs
# less evidence to be told to sell; a patient one needs more.
RISK_SHIFT: dict[str, float] = {
    "cautious": -0.8,   # leans towards selling sooner
    "balanced": 0.0,
    "patient": 0.8,     # leans towards holding out
}

# Perishables cannot be held regardless of disposition, so storage capability
# only matters for crops that survive storage.
STORABLE = {
    "Wheat", "Rice", "Maize", "Mustard", "Soyabean",
    "Bengal Gram (Gram)(Whole)", "Lentil (Masur)(Whole)",
}


@dataclass
class FarmerProfile:
    """Everything personalisation is allowed to use. All of it stays local."""

    farmer_id: str = "anonymous"
    risk_tolerance: RiskTolerance = "balanced"
    has_storage: bool = False
    crops: tuple[str, ...] = ()
    # Outcomes of past recommendations the farmer acted on, newest first:
    # True when following the advice turned out well.
    outcomes: tuple[bool, ...] = ()
    typical_quantity_quintal: float | None = None

    @property
    def observations(self) -> int:
        return len(self.outcomes)

    @property
    def success_rate(self) -> float | None:
        """How often past advice served this farmer well."""
        if not self.outcomes:
            return None
        return sum(self.outcomes) / len(self.outcomes)


@dataclass
class Personalisation:
    """The adjustment applied, and why."""

    threshold_shift: float = 0.0
    confidence_scale: float = 1.0
    reasons: list[str] = field(default_factory=list)
    applied: bool = False

    def describe(self) -> str:
        return "; ".join(self.reasons)


def personalise(profile: FarmerProfile | None, crop: str | None) -> Personalisation:
    """Compute the sell-threshold adjustment for one farmer and crop.

    A positive shift makes the system more willing to say WAIT; a negative one
    makes it more willing to say SELL.
    """
    result = Personalisation()
    if profile is None:
        return result

    # 1. Stated risk tolerance.
    shift = RISK_SHIFT.get(profile.risk_tolerance, 0.0)
    if shift:
        result.threshold_shift += shift
        result.reasons.append(
            "you have told us you prefer to hold out for a better price"
            if shift > 0
            else "you have told us you prefer to sell sooner rather than wait"
        )

    # 2. Storage. Advising a farmer to wait is only actionable if they can
    #    actually store the crop until then.
    if crop and crop in STORABLE and profile.has_storage:
        result.threshold_shift += 0.5
        result.reasons.append("you have storage for this crop, so waiting is an option")
    elif crop and crop not in STORABLE:
        result.threshold_shift -= 0.4
        result.reasons.append("this crop does not keep, so holding it carries real risk")

    # 3. Outcome history. Only applied once there is enough of it to mean
    #    anything — three observations is thin, but it is the point at which a
    #    pattern is better than nothing.
    rate = profile.success_rate
    if rate is not None and profile.observations >= 3:
        if rate < 0.4:
            result.threshold_shift -= 0.5
            result.reasons.append(
                "waiting has not worked out for you recently, so we lean towards selling"
            )
        elif rate > 0.75:
            result.confidence_scale = 1.05
            result.reasons.append("our advice has served you well before")

    result.applied = bool(result.reasons)
    return result
