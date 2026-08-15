import {
  CartesianGrid,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';

/**
 * Historical price curve with a sell/wait overlay (§4.8).
 *
 * The line is colour-coded by trend direction — green rising, red falling,
 * grey flat — and the recommendation is annotated directly on the chart so the
 * advice and the evidence for it are read together.
 */

const LINE_COLOR = {
  upward: '#16a34a',
  downward: '#dc2626',
  stable: '#78716c',
};

const formatRupees = (value) =>
  `₹${new Intl.NumberFormat('en-IN', { maximumFractionDigits: 0 }).format(value)}`;

const shortDate = (iso) => {
  const date = new Date(iso);
  return Number.isNaN(date.getTime())
    ? iso
    : date.toLocaleDateString('en-IN', { day: 'numeric', month: 'short' });
};

function ChartTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null;
  return (
    <div className="glass px-3 py-2 text-xs shadow-lift">
      <p className="font-semibold">{shortDate(label)}</p>
      <p className="opacity-80">{formatRupees(payload[0].value)} per quintal</p>
    </div>
  );
}

export default function TrendChart({ points = [], trend, prediction, crop }) {
  if (!points.length) {
    return (
      <div className="surface p-6 text-center text-sm muted" data-testid="trend-chart-empty">
        No price history available yet for this crop and district.
        <span lang="hi" className="mt-1 block">
          इस फसल का पुराना भाव अभी उपलब्ध नहीं है।
        </span>
      </div>
    );
  }

  const direction = trend?.direction || 'stable';
  const color = LINE_COLOR[direction];
  const prices = points.map((p) => p.modal_price);
  const min = Math.min(...prices);
  const max = Math.max(...prices);
  // Pad the axis so the line never sits flush against the frame.
  const padding = Math.max((max - min) * 0.15, 25);

  return (
    <section className="surface p-4" data-testid="trend-chart">
      <header className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <div>
          <h3 className="text-base font-semibold">{crop ? `${crop} price trend` : 'Price trend'}</h3>
          <p lang="hi" className="muted text-xs">
            पिछले दिनों का भाव
          </p>
        </div>
        {prediction && (
          <span
            className={`chip ${
              prediction.recommendation === 'SELL'
                ? 'bg-mandi-600 text-white'
                : 'bg-amber-500 text-white'
            }`}
          >
            {prediction.recommendation === 'SELL' ? 'Sell now · अभी बेचें' : 'Wait · रुकें'}
          </span>
        )}
      </header>

      <div className="h-64 w-full">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={points} margin={{ top: 8, right: 12, bottom: 4, left: 4 }}>
            <CartesianGrid strokeDasharray="3 3" className="opacity-20" />
            <XAxis
              dataKey="date"
              tickFormatter={shortDate}
              tick={{ fontSize: 11 }}
              minTickGap={24}
            />
            <YAxis
              domain={[Math.floor(min - padding), Math.ceil(max + padding)]}
              tickFormatter={formatRupees}
              tick={{ fontSize: 11 }}
              width={64}
            />
            <Tooltip content={<ChartTooltip />} />
            {trend?.ema_30 > 0 && (
              <ReferenceLine
                y={trend.ema_30}
                stroke={color}
                strokeDasharray="4 4"
                strokeOpacity={0.5}
                label={{ value: '30-day avg', position: 'insideTopLeft', fontSize: 10 }}
              />
            )}
            <Line
              type="monotone"
              dataKey="modal_price"
              stroke={color}
              strokeWidth={2.5}
              dot={false}
              activeDot={{ r: 4 }}
              isAnimationActive={false}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>

      {trend && (
        <footer className="muted mt-2 flex flex-wrap gap-4 text-xs">
          <span>7-day avg {formatRupees(trend.ema_7)}</span>
          <span>14-day avg {formatRupees(trend.ema_14)}</span>
          <span>30-day avg {formatRupees(trend.ema_30)}</span>
          <span className="capitalize" style={{ color }}>
            {direction}
          </span>
        </footer>
      )}
    </section>
  );
}
