import { useCallback, useEffect, useState } from 'react';

import TrendChart from '../components/TrendChart.jsx';
import ConfidenceBar from '../components/ConfidenceBar.jsx';
import * as api from '../services/api.js';
import { useAuth } from '../context/AuthContext.jsx';

const CROPS = ['Tomato', 'Onion', 'Wheat', 'Potato', 'Rice', 'Maize', 'Mustard'];
const WINDOWS = [
  { days: 30, label: '1 month' },
  { days: 45, label: '6 weeks' },
  { days: 90, label: '3 months' },
];

export default function PricePage() {
  const { user } = useAuth();
  const [crop, setCrop] = useState('Tomato');
  const [district, setDistrict] = useState(user?.location?.district || 'Patna');
  const [days, setDays] = useState(45);
  const [series, setSeries] = useState([]);
  const [trend, setTrend] = useState(null);
  const [status, setStatus] = useState('idle');
  const [error, setError] = useState(null);

  const load = useCallback(async () => {
    setStatus('loading');
    setError(null);
    try {
      const params = { crop, district: district || undefined, days };
      const [seriesResult, trendResult] = await Promise.all([
        api.priceSeries(params),
        api.priceTrend(params),
      ]);
      setSeries(seriesResult.points || []);
      setTrend(trendResult);
      setStatus('ready');
    } catch (caught) {
      setError(caught.message);
      setStatus('error');
    }
  }, [crop, district, days]);

  useEffect(() => {
    load();
  }, [load]);

  return (
    <div className="mx-auto max-w-5xl px-4 py-8">
      <header className="mb-6">
        <h1 className="text-2xl font-bold">Price Trends</h1>
        <p lang="hi" className="opacity-70">
          भाव का रुझान — कब बेचना ठीक रहेगा
        </p>
      </header>

      <form
        className="glass mb-6 grid gap-3 p-4 sm:grid-cols-3"
        onSubmit={(event) => {
          event.preventDefault();
          load();
        }}
      >
        <label className="text-sm">
          <span className="mb-1 block opacity-70">Crop · फसल</span>
          <select className="field" value={crop} onChange={(e) => setCrop(e.target.value)}>
            {CROPS.map((option) => (
              <option key={option} value={option}>
                {option}
              </option>
            ))}
          </select>
        </label>

        <label className="text-sm">
          <span className="mb-1 block opacity-70">District · जिला</span>
          <input
            className="field"
            value={district}
            onChange={(e) => setDistrict(e.target.value)}
            placeholder="Patna"
          />
        </label>

        <label className="text-sm">
          <span className="mb-1 block opacity-70">Window · अवधि</span>
          <select
            className="field"
            value={days}
            onChange={(e) => setDays(Number(e.target.value))}
          >
            {WINDOWS.map((option) => (
              <option key={option.days} value={option.days}>
                {option.label}
              </option>
            ))}
          </select>
        </label>
      </form>

      {status === 'error' && (
        <p className="glass p-4 text-sm text-red-700 dark:text-red-300">
          Could not load the trend: {error}
        </p>
      )}

      <div className="grid gap-4 md:grid-cols-[minmax(0,1fr)_220px]">
        <TrendChart points={series} trend={trend} crop={crop} />

        {trend && (
          <aside className="glass flex flex-col items-center justify-center p-5">
            <ConfidenceBar score={trend.confidence} label="Trend confidence" />
            <dl className="mt-4 w-full space-y-1 text-xs opacity-75">
              <div className="flex justify-between">
                <dt>Direction</dt>
                <dd className="font-medium capitalize">{trend.direction}</dd>
              </div>
              <div className="flex justify-between">
                <dt>Volatility</dt>
                <dd className="font-medium">{trend.volatility?.toFixed(4)}</dd>
              </div>
              <div className="flex justify-between">
                <dt>Days analysed</dt>
                <dd className="font-medium">{trend.samples}</dd>
              </div>
            </dl>
            <p className="mt-4 text-[11px] opacity-60">
              Confidence falls when prices are volatile, even if the direction looks clear.
            </p>
          </aside>
        )}
      </div>
    </div>
  );
}
