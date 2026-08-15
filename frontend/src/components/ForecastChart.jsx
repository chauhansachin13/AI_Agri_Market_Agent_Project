import {
  Area,
  CartesianGrid,
  ComposedChart,
  Line,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';

/**
 * Observed history plus the trained forecast and its 95% interval (§6.3).
 *
 * The interval is drawn, not just stated. A point forecast on its own reads as
 * a promise; showing how wide the band is — and that it widens with the
 * horizon — is what stops a farmer treating a 14-day projection as fact.
 */

const formatRupees = (value) =>
  `₹${new Intl.NumberFormat('en-IN', { maximumFractionDigits: 0 }).format(value)}`;

const shortDate = (iso) => {
  const date = new Date(iso);
  return Number.isNaN(date.getTime())
    ? iso
    : date.toLocaleDateString('en-IN', { day: 'numeric', month: 'short' });
};

function ForecastTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null;
  const row = payload[0]?.payload || {};
  return (
    <div className="glass px-3 py-2 text-xs shadow-lift">
      <p className="font-semibold">{shortDate(label)}</p>
      {row.observed != null && <p className="opacity-80">Actual {formatRupees(row.observed)}</p>}
      {row.predicted != null && (
        <>
          <p className="opacity-80">Forecast {formatRupees(row.predicted)}</p>
          <p className="opacity-60">
            Range {formatRupees(row.lower)} – {formatRupees(row.upper)}
          </p>
        </>
      )}
    </div>
  );
}

function skillLabel(forecast) {
  if (forecast?.mape == null) return null;
  if (forecast.baseline_mape == null) return `${forecast.mape.toFixed(1)}% backtested error`;
  return forecast.beats_baseline
    ? `${forecast.mape.toFixed(1)}% error, better than the ${forecast.baseline_mape.toFixed(1)}% naive baseline`
    : `${forecast.mape.toFixed(1)}% error — no better than a naive guess, so treat this as weak`;
}

export default function ForecastChart({ history = [], forecast, crop }) {
  if (!forecast?.points?.length) {
    return (
      <div className="surface p-6 text-center text-sm muted" data-testid="forecast-empty">
        No forecast available for this crop and district yet.
        <span lang="hi" className="mt-1 block">
          इस फसल का अनुमान अभी उपलब्ध नहीं है।
        </span>
      </div>
    );
  }

  const lastDate = history.length ? new Date(history[history.length - 1].date) : new Date();

  const observedRows = history.map((point) => ({
    date: point.date,
    observed: point.modal_price,
  }));

  const forecastRows = forecast.points.map((point) => {
    const date = new Date(lastDate);
    date.setDate(date.getDate() + point.horizon);
    return {
      date: date.toISOString().slice(0, 10),
      predicted: point.value,
      lower: point.lower,
      // Recharts stacks an Area from its own baseline, so the band is drawn as
      // the lower bound plus the span rather than two absolute bounds.
      band: point.upper - point.lower,
      upper: point.upper,
    };
  });

  const rows = [...observedRows, ...forecastRows];
  const rising = (forecast.expected_change_pct ?? 0) > 0;
  const colour = rising ? '#16a34a' : '#dc2626';
  const skill = skillLabel(forecast);

  // The interval band is drawn as a stacked Area, and a stack is measured from
  // zero — so an automatic domain drags the axis down to ₹0 and squashes the
  // whole price range into a sliver at the top. The domain is therefore set
  // explicitly from the values actually plotted.
  const plotted = [
    ...observedRows.map((row) => row.observed),
    ...forecastRows.flatMap((row) => [row.lower, row.upper]),
  ].filter((value) => Number.isFinite(value));

  const low = Math.min(...plotted);
  const high = Math.max(...plotted);
  const pad = Math.max((high - low) * 0.12, 20);
  const domain = [Math.floor(low - pad), Math.ceil(high + pad)];

  return (
    <section className="surface p-4" data-testid="forecast-chart">
      <header className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <div>
          <h3 className="text-base font-semibold">
            {crop ? `${crop} forecast` : 'Price forecast'}
          </h3>
          <p lang="hi" className="muted text-xs">
            आगे भाव क्या रहेगा — अनुमान
          </p>
        </div>
        <span
          className="chip"
          style={{ backgroundColor: `${colour}22`, color: colour }}
          data-testid="forecast-change"
        >
          {rising ? '▲' : '▼'} {Math.abs(forecast.expected_change_pct ?? 0).toFixed(1)}% in{' '}
          {forecast.horizon_days} days
        </span>
      </header>

      <div className="h-64 w-full">
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart data={rows} margin={{ top: 8, right: 12, bottom: 4, left: 4 }}>
            <CartesianGrid strokeDasharray="3 3" className="opacity-20" />
            <XAxis dataKey="date" tickFormatter={shortDate} tick={{ fontSize: 11 }} minTickGap={28} />
            <YAxis
              tickFormatter={formatRupees}
              tick={{ fontSize: 11 }}
              width={64}
              domain={domain}
              allowDataOverflow
            />
            <Tooltip content={<ForecastTooltip />} />

            <Area
              dataKey="lower"
              stackId="band"
              stroke="none"
              fill="transparent"
              isAnimationActive={false}
            />
            <Area
              dataKey="band"
              stackId="band"
              stroke="none"
              fill={colour}
              fillOpacity={0.15}
              isAnimationActive={false}
            />

            <Line
              type="monotone"
              dataKey="observed"
              stroke="#78716c"
              strokeWidth={2}
              dot={false}
              isAnimationActive={false}
            />
            <Line
              type="monotone"
              dataKey="predicted"
              stroke={colour}
              strokeWidth={2.5}
              strokeDasharray="5 4"
              dot={false}
              isAnimationActive={false}
            />
            {observedRows.length > 0 && (
              <ReferenceLine
                x={observedRows[observedRows.length - 1].date}
                stroke="currentColor"
                strokeOpacity={0.35}
                label={{ value: 'today', position: 'top', fontSize: 10 }}
              />
            )}
          </ComposedChart>
        </ResponsiveContainer>
      </div>

      <footer className="muted mt-2 space-y-1 text-xs">
        <p>
          {forecast.model_name} model, trained on {forecast.trained_on} days
          {skill ? ` · ${skill}` : ''}
        </p>
        <p className="opacity-80">
          The shaded band is the 95% range. It widens further out because the further ahead
          the forecast, the less certain it is.
        </p>
        {forecast.notes?.map((note) => (
          <p key={note} className="opacity-60">
            Note: {note}
          </p>
        ))}
      </footer>
    </section>
  );
}
