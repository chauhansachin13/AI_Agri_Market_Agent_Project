# Price forecasting

Section 6.2 of the report names the limitation plainly: the EMA model smooths,
it does not learn, so it cannot capture the harvest cycles and policy shocks
that actually move mandi prices. Section 6.3 asks for a trained time-series
model. This is that model.

The EMA triple is **not** removed. It still classifies the trend, because the
response schema exposes it and because three moving averages explain themselves
to a farmer in a way a fitted model does not. What it could never do is say
where prices are going. That is the forecaster's job, and the two answer
different questions.

## Models

| Model | When it runs | Notes |
|---|---|---|
| `ridge-ar` | default | Ridge-regularised autoregression, pure Python |
| `lstm` | when PyTorch is installed | Single-layer LSTM, trained per request |
| `seasonal-naive` | fewer than 12 observations | The honest baseline |

### Ridge autoregression

Features per day, built from the standardised series:

- lags at 1, 2, 3, 5, 7 and 14 days — yesterday, the last few days, the weekly
  arrival rhythm, and a fortnight
- a 7-day rolling mean
- the first difference, giving the immediate direction of travel
- annual seasonality as a sine/cosine pair, so the harvest cycle can be placed
  without a discontinuity at the year boundary

Coefficients come from the ridge normal equations, `(XᵀX + λI)⁻¹Xᵀy`, solved by
Cholesky decomposition. The penalty is raised progressively if the system is
ill-conditioned, which happens whenever a price series is flat enough to make
the lag features collinear — common, and therefore handled rather than allowed
to raise.

Multi-step forecasts are produced recursively: each prediction is appended to
the history and becomes an input to the next step.

**Why the series is standardised.** Crop prices span sugarcane at ~₹340 and
garlic at ~₹7,800 per quintal. Fitting on raw levels would make a single ridge
penalty mean something completely different for each crop.

**Why pure Python.** It keeps the trained forecaster in the default install.
A model that only runs once someone has installed NumPy and PyTorch is a model
most deployments will never actually run.

### LSTM

A single-layer LSTM over a 14-day sliding window, 32 hidden units, trained for
120 epochs per request with Adam. Deliberately small: the goal is to capture
non-linear dynamics the linear model cannot, not to reach research accuracy
inside a web request. The seed is fixed, so the same input gives the same
forecast.

## Honesty about accuracy

Every forecast is backtested on a held-out final 20% of the series and reported
next to a naive baseline on the same split:

```json
{
  "model_name": "ridge-ar",
  "mape": 1.24,
  "baseline_mape": 2.19,
  "beats_baseline": true,
  "confidence": 0.71
}
```

Confidence blends absolute accuracy with *skill* — how much the model improves
on the baseline — and scales both by how much training data existed. A model
that cannot beat guessing is explicitly not trusted more than guessing, and the
UI says so in words: *"no better than a naive guess, so treat this as weak."*

This matters because the Sell Decision agent weighs the forecast. Without the
skill term, a confidently-drawn but useless projection would move real advice.

## Prediction intervals

Interval half-width grows as `1.96 σ √t`, where σ is the residual standard
deviation from the training fit. The √t term is the random-walk result: a
14-day forecast is not as certain as a 1-day forecast, and the chart draws that
widening band rather than only stating a point value.

## Fact-checking a forecast

A forecast figure is a model output, not a government record, so it can never
be `verified`. It is `partially_verified`, with the model, its training window
and its backtested error recorded as the evidence:

> `Forecast value of Rs 2380 per quintal` — *point forecast at day 7 from the
> ridge-ar model trained on 90 days, backtested error 1.2%*

An earlier version had no rule for forecast values at all, so the fact-checker
classified them as unsupported and deleted the very sentence the forecasting
agent had just produced. The regression test
`test_a_forecast_value_is_traceable_not_a_hallucination` exists to keep that
from returning.

## Limitations

- Recursive multi-step forecasting compounds error; beyond about two weeks the
  interval is wide enough that the point value carries little information.
- The model sees only price history. Arrival volumes, MSP announcements and
  export policy all move prices and none of them are inputs.
- The offline dataset is smooth by construction, so backtested errors on it are
  flattering. Real Agmarknet series are noisier, and the reported MAPE on live
  data will be higher.
- The LSTM trains per request rather than from a persisted checkpoint, which
  bounds how large it can usefully be.
