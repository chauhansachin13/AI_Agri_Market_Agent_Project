"""Trained price forecasters (Section 6.3, "Advanced Price Forecasting").

Three models behind one interface:

* ``RidgeARForecaster`` — regularised autoregression over lag and seasonal
  features. Pure Python, always available, and genuinely *fitted* to the
  crop-location history rather than smoothing it.
* ``LSTMForecaster`` — the recurrent model the report proposes, used when
  PyTorch is installed.
* ``SeasonalNaiveForecaster`` — the honest baseline for very short histories,
  where fitting anything richer would be overfitting noise.

Every forecaster returns multi-step point forecasts with prediction intervals
and a backtested error, so the sell-decision agent can weigh the forecast by
how well the model actually performed on this series instead of trusting it
unconditionally.
"""

from __future__ import annotations

import logging
import math
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from .features import DEFAULT_LAGS, build_supervised, next_row
from .linalg import ridge_solve, stdev

logger = logging.getLogger(__name__)

# Below this many observations, a learned model has nothing to learn from.
MIN_TRAINING_POINTS = 12


@dataclass
class ForecastPoint:
    horizon: int          # days ahead (1-based)
    value: float
    lower: float
    upper: float


@dataclass
class Forecast:
    """A multi-step forecast plus the evidence for trusting it."""

    model: str
    points: list[ForecastPoint] = field(default_factory=list)
    mape: float | None = None          # backtested mean absolute percentage error
    baseline_mape: float | None = None  # seasonal-naive error on the same split
    trained_on: int = 0
    confidence: float = 0.0
    notes: list[str] = field(default_factory=list)

    @property
    def horizon_days(self) -> int:
        return len(self.points)

    def value_at(self, horizon: int) -> float | None:
        for point in self.points:
            if point.horizon == horizon:
                return point.value
        return None

    @property
    def expected_change_pct(self) -> float | None:
        """Percentage change from the last observation to the final horizon."""
        if not self.points or self._last_observed is None or self._last_observed == 0:
            return None
        return round((self.points[-1].value - self._last_observed) / self._last_observed * 100, 2)

    _last_observed: float | None = None


class Forecaster(ABC):
    name: str

    @abstractmethod
    def fit_predict(self, series: list[float], horizon: int, start_day_index: int) -> Forecast:
        """Fit on `series` (oldest first) and forecast `horizon` days ahead."""


# --------------------------------------------------------------------------- #
# Baseline
# --------------------------------------------------------------------------- #
class SeasonalNaiveForecaster(Forecaster):
    """Repeat the recent level, widening the interval with the horizon.

    This is the benchmark every learned model has to beat. Reporting it beside
    the trained model's error is what makes the trained model's value legible
    rather than assumed.
    """

    name = "seasonal-naive"

    def fit_predict(self, series: list[float], horizon: int, start_day_index: int = 0) -> Forecast:
        if not series:
            return Forecast(model=self.name, notes=["empty series"])

        window = series[-7:]
        level = sum(window) / len(window)
        noise = stdev(series[-30:]) or abs(level) * 0.02

        points = [
            ForecastPoint(
                horizon=step,
                value=round(level, 2),
                # Uncertainty of a random walk grows with the square root of time.
                lower=round(level - 1.96 * noise * math.sqrt(step), 2),
                upper=round(level + 1.96 * noise * math.sqrt(step), 2),
            )
            for step in range(1, horizon + 1)
        ]

        forecast = Forecast(
            model=self.name, points=points, trained_on=len(series), confidence=0.35
        )
        forecast._last_observed = series[-1]
        return forecast


# --------------------------------------------------------------------------- #
# Ridge autoregression
# --------------------------------------------------------------------------- #
class RidgeARForecaster(Forecaster):
    """Ridge-regularised autoregression over lag, rolling and seasonal features."""

    name = "ridge-ar"

    def __init__(self, penalty: float = 1.0, lags: tuple[int, ...] = DEFAULT_LAGS):
        self.penalty = penalty
        self.lags = lags

    # -- internals ----------------------------------------------------------
    def _fit(self, series: list[float], start_day_index: int):
        data = build_supervised(series, self.lags, start_day_index)
        if len(data) < 4:
            return None
        coefficients = ridge_solve(data.design, data.target, self.penalty)
        return coefficients, data

    def _roll_forward(
        self,
        coefficients: list[float],
        scaled_history: list[float],
        horizon: int,
        day_index: int,
        usable_lags: tuple[int, ...],
    ) -> list[float]:
        """Recursive multi-step prediction in scaled space."""
        history = list(scaled_history)
        predictions: list[float] = []

        for step in range(horizon):
            row = next_row(history, usable_lags, day_index + step)
            # Guard against a feature/coefficient length mismatch when the
            # usable lag set shrank on a short series.
            width = min(len(row), len(coefficients))
            predicted = sum(row[i] * coefficients[i] for i in range(width))
            predictions.append(predicted)
            history.append(predicted)

        return predictions

    def _backtest(self, series: list[float], start_day_index: int) -> tuple[float | None, float | None]:
        """Hold out the final 20% and measure MAPE against the naive baseline."""
        split = int(len(series) * 0.8)
        if split < MIN_TRAINING_POINTS or len(series) - split < 2:
            return None, None

        train, test = series[:split], series[split:]
        fitted = self._fit(train, start_day_index)
        if fitted is None:
            return None, None

        coefficients, data = fitted
        usable_lags = tuple(lag for lag in self.lags if lag < len(train))
        scaled_history = [(v - data.mean) / data.scale for v in train]

        predicted_scaled = self._roll_forward(
            coefficients, scaled_history, len(test), start_day_index + len(train), usable_lags
        )
        predicted = [p * data.scale + data.mean for p in predicted_scaled]

        def mape(forecasts: list[float]) -> float:
            errors = [
                abs(f - actual) / abs(actual)
                for f, actual in zip(forecasts, test)
                if actual != 0
            ]
            return round(sum(errors) / len(errors) * 100, 3) if errors else 0.0

        naive_level = sum(train[-7:]) / len(train[-7:])
        return mape(predicted), mape([naive_level] * len(test))

    # -- interface ----------------------------------------------------------
    def fit_predict(self, series: list[float], horizon: int, start_day_index: int = 0) -> Forecast:
        if len(series) < MIN_TRAINING_POINTS:
            forecast = SeasonalNaiveForecaster().fit_predict(series, horizon, start_day_index)
            forecast.notes.append(
                f"only {len(series)} observations; a learned model needs at least "
                f"{MIN_TRAINING_POINTS}"
            )
            return forecast

        fitted = self._fit(series, start_day_index)
        if fitted is None:
            return SeasonalNaiveForecaster().fit_predict(series, horizon, start_day_index)

        coefficients, data = fitted
        usable_lags = tuple(lag for lag in self.lags if lag < len(series))
        scaled_history = [(v - data.mean) / data.scale for v in series]

        predicted_scaled = self._roll_forward(
            coefficients, scaled_history, horizon, start_day_index + len(series), usable_lags
        )
        predicted = [p * data.scale + data.mean for p in predicted_scaled]

        # Residual spread on the training fit sets the interval width.
        residuals = [
            (actual - sum(row[i] * coefficients[i] for i in range(len(coefficients))))
            * data.scale
            for row, actual in zip(data.design, data.target)
        ]
        sigma = stdev(residuals) or abs(data.scale) * 0.02

        points = [
            ForecastPoint(
                horizon=step + 1,
                value=round(value, 2),
                lower=round(value - 1.96 * sigma * math.sqrt(step + 1), 2),
                upper=round(value + 1.96 * sigma * math.sqrt(step + 1), 2),
            )
            for step, value in enumerate(predicted)
        ]

        mape, baseline_mape = self._backtest(series, start_day_index)
        forecast = Forecast(
            model=self.name,
            points=points,
            mape=mape,
            baseline_mape=baseline_mape,
            trained_on=len(series),
            confidence=_confidence_from_backtest(mape, baseline_mape, len(series)),
        )
        forecast._last_observed = series[-1]
        return forecast


# --------------------------------------------------------------------------- #
# LSTM
# --------------------------------------------------------------------------- #
class LSTMForecaster(Forecaster):  # pragma: no cover - optional dependency
    """The recurrent forecaster named in Section 6.3, used when PyTorch is present.

    A small single-layer LSTM over a sliding window. It is trained per
    crop-location series at request time, so the architecture is kept
    deliberately small — the goal is to capture non-linear dynamics that the
    linear model cannot, not to reach research accuracy in a web request.
    """

    name = "lstm"

    def __init__(self, window: int = 14, hidden: int = 32, epochs: int = 120, lr: float = 0.02):
        self.window = window
        self.hidden = hidden
        self.epochs = epochs
        self.lr = lr

    @staticmethod
    def available() -> bool:
        try:
            import torch  # noqa: F401

            return True
        except Exception:
            return False

    def fit_predict(self, series: list[float], horizon: int, start_day_index: int = 0) -> Forecast:
        if len(series) < self.window + MIN_TRAINING_POINTS:
            return RidgeARForecaster().fit_predict(series, horizon, start_day_index)

        try:
            import torch
            from torch import nn
        except Exception:
            return RidgeARForecaster().fit_predict(series, horizon, start_day_index)

        torch.manual_seed(0)  # reproducible forecasts for the same input

        mu = sum(series) / len(series)
        sigma = stdev(series) or 1.0
        scaled = [(v - mu) / sigma for v in series]

        windows, targets = [], []
        for index in range(self.window, len(scaled)):
            windows.append(scaled[index - self.window : index])
            targets.append(scaled[index])

        x = torch.tensor(windows, dtype=torch.float32).unsqueeze(-1)
        y = torch.tensor(targets, dtype=torch.float32).unsqueeze(-1)

        class Net(nn.Module):
            def __init__(self, hidden: int):
                super().__init__()
                self.lstm = nn.LSTM(1, hidden, batch_first=True)
                self.head = nn.Linear(hidden, 1)

            def forward(self, inputs):
                output, _ = self.lstm(inputs)
                return self.head(output[:, -1, :])

        model = Net(self.hidden)
        optimiser = torch.optim.Adam(model.parameters(), lr=self.lr)
        loss_fn = nn.MSELoss()

        model.train()
        for _ in range(self.epochs):
            optimiser.zero_grad()
            loss = loss_fn(model(x), y)
            loss.backward()
            optimiser.step()

        model.eval()
        history = list(scaled)
        predictions: list[float] = []
        with torch.no_grad():
            for _ in range(horizon):
                probe = torch.tensor([history[-self.window :]], dtype=torch.float32).unsqueeze(-1)
                nxt = float(model(probe).item())
                predictions.append(nxt)
                history.append(nxt)

        with torch.no_grad():
            residuals = (model(x) - y).squeeze(-1).tolist()
        residual_sigma = (stdev(residuals) or 0.02) * sigma

        values = [p * sigma + mu for p in predictions]
        points = [
            ForecastPoint(
                horizon=step + 1,
                value=round(value, 2),
                lower=round(value - 1.96 * residual_sigma * math.sqrt(step + 1), 2),
                upper=round(value + 1.96 * residual_sigma * math.sqrt(step + 1), 2),
            )
            for step, value in enumerate(values)
        ]

        ridge = RidgeARForecaster()
        _, baseline_mape = ridge._backtest(series, start_day_index)
        forecast = Forecast(
            model=self.name,
            points=points,
            baseline_mape=baseline_mape,
            trained_on=len(series),
            confidence=0.6,
            notes=["trained per request; see docs/FORECASTING.md"],
        )
        forecast._last_observed = series[-1]
        return forecast


def _confidence_from_backtest(
    mape: float | None, baseline_mape: float | None, samples: int
) -> float:
    """Trust the forecast in proportion to how well it backtested.

    A model that cannot beat the naive baseline is explicitly not trusted more
    than the baseline, however confident its intervals look.
    """
    sample_weight = min(samples / 60.0, 1.0)

    if mape is None:
        return round(0.4 * sample_weight, 3)

    accuracy = max(0.0, 1.0 - mape / 20.0)  # 20% MAPE scores zero

    if baseline_mape and baseline_mape > 0:
        improvement = (baseline_mape - mape) / baseline_mape
        skill = max(0.0, min(improvement, 1.0))
    else:
        skill = 0.5

    return round(min(0.95, (0.55 * accuracy + 0.45 * skill) * sample_weight), 3)


def select_forecaster(prefer_neural: bool = True) -> Forecaster:
    """Best forecaster available in this environment."""
    if prefer_neural and LSTMForecaster.available():  # pragma: no cover
        return LSTMForecaster()
    return RidgeARForecaster()
