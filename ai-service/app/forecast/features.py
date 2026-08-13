"""Supervised feature construction for price forecasting.

Section 6.2 of the report names the limitation this addresses: the EMA model
smooths, it does not learn, so it cannot capture the harvest cycles and
policy-driven shocks that actually move mandi prices.

A raw daily price series is converted into a supervised matrix of lagged and
seasonal features, which the ridge and neural forecasters both consume. The
transformation is the same for both so their errors are directly comparable.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

# Lags chosen to span the horizons that matter in a mandi: yesterday, the last
# few days, one week (weekly arrival rhythm) and two weeks.
DEFAULT_LAGS = (1, 2, 3, 5, 7, 14)
SEASONAL_PERIOD = 365.25


@dataclass
class SupervisedData:
    """Design matrix, targets, and the metadata needed to invert the scaling."""

    design: list[list[float]]
    target: list[float]
    feature_names: list[str]
    mean: float
    scale: float

    def __len__(self) -> int:
        return len(self.target)


def _normalise(values: list[float]) -> tuple[list[float], float, float]:
    """Centre and scale a series.

    Prices differ by an order of magnitude across crops (sugarcane ~340, garlic
    ~7800). Fitting on raw levels would make the ridge penalty mean something
    different for every crop, so the series is standardised first and the
    prediction is mapped back afterwards.
    """
    if not values:
        return [], 0.0, 1.0

    mu = sum(values) / len(values)
    if len(values) < 2:
        return [0.0 for _ in values], mu, 1.0

    variance = sum((v - mu) ** 2 for v in values) / (len(values) - 1)
    sigma = math.sqrt(variance) if variance > 1e-12 else 1.0
    return [(v - mu) / sigma for v in values], mu, sigma


def _row(
    scaled: list[float],
    index: int,
    lags: tuple[int, ...],
    day_index: int,
) -> list[float]:
    """One feature row predicting `scaled[index]` from what precedes it."""
    features = [1.0]  # intercept
    features += [scaled[index - lag] for lag in lags]

    window = scaled[max(0, index - 7) : index]
    features.append(sum(window) / len(window) if window else 0.0)

    # First difference: the immediate direction of travel.
    features.append(scaled[index - 1] - scaled[index - 2] if index >= 2 else 0.0)

    # Annual seasonality as a smooth pair, so the model can place the harvest
    # cycle without a discontinuity at the year boundary.
    angle = 2 * math.pi * (day_index % SEASONAL_PERIOD) / SEASONAL_PERIOD
    features.append(math.sin(angle))
    features.append(math.cos(angle))

    return features


def build_supervised(
    series: list[float],
    lags: tuple[int, ...] = DEFAULT_LAGS,
    start_day_index: int = 0,
) -> SupervisedData:
    """Turn a daily price series (oldest first) into supervised training data."""
    usable_lags = tuple(lag for lag in lags if lag < len(series))
    if not usable_lags or len(series) <= max(usable_lags, default=0) + 1:
        return SupervisedData([], [], [], 0.0, 1.0)

    scaled, mu, sigma = _normalise(series)
    first = max(usable_lags)

    design: list[list[float]] = []
    target: list[float] = []
    for index in range(first, len(scaled)):
        design.append(_row(scaled, index, usable_lags, start_day_index + index))
        target.append(scaled[index])

    names = (
        ["intercept"]
        + [f"lag_{lag}" for lag in usable_lags]
        + ["rolling_mean_7", "first_difference", "season_sin", "season_cos"]
    )
    return SupervisedData(design, target, names, mu, sigma)


def next_row(
    scaled_history: list[float],
    lags: tuple[int, ...],
    day_index: int,
) -> list[float]:
    """Feature row for the step immediately after `scaled_history`."""
    usable = tuple(lag for lag in lags if lag <= len(scaled_history))
    return _row(scaled_history + [0.0], len(scaled_history), usable, day_index)
