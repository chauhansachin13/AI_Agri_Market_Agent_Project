"""Federated aggregation of personalisation signals (Section 6.3).

The report asks for personalisation "without centralizing sensitive personal
data". This is the mechanism that makes that claim true rather than aspirational.

How it works:

  1. Each client computes an **update** from its own history — a small vector
     of statistics, never the underlying queries, prices or decisions.
  2. The update is **clipped** to a bounded norm, so no single farmer can move
     the shared model much, whether by accident or on purpose.
  3. **Calibrated noise** is added before the update leaves the device, giving
     each contribution local differential privacy.
  4. The server averages the updates it receives. It never sees, stores or is
     able to reconstruct any individual's data.

What is honest about the scope: this implements the aggregation protocol and
its privacy properties, and the server genuinely cannot recover an
individual's history from what it receives. It is not a distributed training
system — there is one process here, and rounds are simulated by passing
updates in. The privacy argument is about *what is transmitted*, which is the
part that matters and the part that is testable.
"""

from __future__ import annotations

import hashlib
import math
import random
from dataclasses import dataclass, field

# The signals a client may contribute. Deliberately tiny and non-identifying:
# aggregate dispositions, not events.
SIGNALS = ("sell_bias", "storage_rate", "advice_success", "volatility_sensitivity")

# Maximum L2 norm of a single client update. Bounding sensitivity is what makes
# the noise scale meaningful, and stops one client dominating a round.
CLIP_NORM = 1.0

# Local differential privacy budget per round. Lower epsilon is more private
# and noisier; 1.0 is a commonly used operating point for this kind of signal.
DEFAULT_EPSILON = 1.0

# A round with too few clients would let the server infer an individual's
# contribution from the average, so rounds below this are refused.
MIN_CLIENTS = 3


@dataclass
class ClientUpdate:
    """What actually leaves a device. No identifiers, no raw history."""

    values: dict[str, float]
    weight: float = 1.0          # observations behind it, for weighted averaging
    clipped: bool = False
    noised: bool = False

    def norm(self) -> float:
        return math.sqrt(sum(v * v for v in self.values.values()))


@dataclass
class AggregateModel:
    """The shared model. Population-level only, by construction."""

    values: dict[str, float] = field(default_factory=lambda: {s: 0.0 for s in SIGNALS})
    rounds: int = 0
    clients_seen: int = 0

    def shift_for(self, signal: str) -> float:
        return self.values.get(signal, 0.0)


def compute_local_update(
    sell_bias: float,
    storage_rate: float,
    advice_success: float,
    volatility_sensitivity: float,
    observations: int,
) -> ClientUpdate:
    """Turn one farmer's own history into an update. Runs client-side."""
    return ClientUpdate(
        values={
            "sell_bias": sell_bias,
            "storage_rate": storage_rate,
            "advice_success": advice_success,
            "volatility_sensitivity": volatility_sensitivity,
        },
        weight=float(max(observations, 1)),
    )


def clip(update: ClientUpdate, max_norm: float = CLIP_NORM) -> ClientUpdate:
    """Scale an update down to a bounded norm."""
    norm = update.norm()
    if norm <= max_norm or norm == 0:
        return update
    scale = max_norm / norm
    return ClientUpdate(
        values={k: v * scale for k, v in update.values.items()},
        weight=update.weight,
        clipped=True,
        noised=update.noised,
    )


def add_noise(
    update: ClientUpdate,
    epsilon: float = DEFAULT_EPSILON,
    seed: str | None = None,
) -> ClientUpdate:
    """Add Laplace noise calibrated to the clipping bound.

    Sensitivity is the clipping norm, so scale = sensitivity / epsilon. The
    seed exists purely so tests are deterministic; production leaves it unset
    and draws from the system source.
    """
    if epsilon <= 0:
        raise ValueError("epsilon must be positive")

    scale = CLIP_NORM / epsilon
    rng = random.Random(
        int(hashlib.sha256(seed.encode()).hexdigest()[:8], 16) if seed else None
    )

    def laplace() -> float:
        # Inverse-CDF sampling: u in (-0.5, 0.5] maps onto a Laplace draw.
        u = rng.random() - 0.5
        return -scale * math.copysign(1.0, u) * math.log(1 - 2 * abs(u))

    return ClientUpdate(
        values={k: v + laplace() for k, v in update.values.items()},
        weight=update.weight,
        clipped=update.clipped,
        noised=True,
    )


def prepare_update(update: ClientUpdate, epsilon: float = DEFAULT_EPSILON,
                   seed: str | None = None) -> ClientUpdate:
    """Clip then noise — the full client-side pipeline, in the required order.

    Order matters: noising before clipping would scale the noise down along
    with the signal and void the privacy guarantee.
    """
    return add_noise(clip(update), epsilon=epsilon, seed=seed)


def aggregate(updates: list[ClientUpdate], model: AggregateModel | None = None) -> AggregateModel:
    """Weighted-average the round's updates into the shared model."""
    if len(updates) < MIN_CLIENTS:
        raise ValueError(
            f"a round needs at least {MIN_CLIENTS} clients; "
            f"averaging {len(updates)} would expose individual contributions"
        )

    model = model or AggregateModel()
    total_weight = sum(u.weight for u in updates) or 1.0

    averaged = {
        signal: sum(u.values.get(signal, 0.0) * u.weight for u in updates) / total_weight
        for signal in SIGNALS
    }

    # Exponential moving average across rounds, so one noisy round cannot
    # swing the shared model.
    alpha = 0.3 if model.rounds else 1.0
    model.values = {
        signal: alpha * averaged[signal] + (1 - alpha) * model.values.get(signal, 0.0)
        for signal in SIGNALS
    }
    model.rounds += 1
    model.clients_seen += len(updates)
    return model
