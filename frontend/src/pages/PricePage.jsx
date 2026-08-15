import { useCallback, useEffect, useState } from 'react';

import ForecastChart from '../components/ForecastChart.jsx';
import TrendChart from '../components/TrendChart.jsx';
import WeatherCard from '../components/WeatherCard.jsx';
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
  const [forecast, setForecast] = useState(null);
  const [weather, setWeather] = useState(null);
  const [status, setStatus] = useState('idle');
  const [error, setError] = useState(null);

  const load = useCallback(async () => {
    setStatus('loading');
    setError(null);
    try {
      const params = { crop, district: district || undefined, days };
      // The series and trend are the page; the forecast and weather enrich it.
      // Settling them separately means one flaky upstream cannot blank the page.
      const [seriesResult, trendResult] = await Promise.all([
        api.priceSeries(params),
        api.priceTrend(params),
      ]);
      setSeries(seriesResult.points || []);
      setTrend(trendResult);
      setStatus('ready');

      const [forecastResult, weatherResult] = await Promise.allSettled([
        api.priceForecast({ crop, district: district || undefined, horizon: 7 }),
        api.weatherOutlook({ crop, district: district || undefined }),
      ]);
      setForecast(forecastResult.status === 'fulfilled' ? forecastResult.value : null);
      setWeather(weatherResult.status === 'fulfilled' ? weatherResult.value : null);
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
        <p lang="hi" className="muted">
          भाव का रुझान — कब बेचना ठीक रहेगा
        </p>
      </header>

      <form
        className="surface mb-6 grid gap-3 p-4 sm:grid-cols-3"
        onSubmit={(event) => {
          event.preventDefault();
          load();
        }}
      >
        <label className="text-sm">
          <span className="label">Crop · फसल</span>
          <select className="field" value={crop} onChange={(e) => setCrop(e.target.value)}>
            {CROPS.map((option) => (
              <option key={option} value={option}>
                {option}
              </option>
            ))}
          </select>
        </label>

        <label className="text-sm">
          <span className="label">District · जिला</span>
          <input
            className="field"
            value={district}
            onChange={(e) => setDistrict(e.target.value)}
            placeholder="Patna"
          />
        </label>

        <label className="text-sm">
          <span className="label">Window · अवधि</span>
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
        <div className="space-y-4">
          <TrendChart points={series} trend={trend} crop={crop} />
          <ForecastChart history={series} forecast={forecast} crop={crop} />
        </div>

        {/* self-start so the card hugs its content instead of stretching to the
            height of the two stacked charts beside it. */}
        {trend && (
          <aside className="surface flex flex-col items-center justify-center self-start p-5">
            <ConfidenceBar score={trend.confidence} label="Trend confidence" />
            <dl className="muted mt-4 w-full space-y-1 text-xs">
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
            <p className="muted mt-4 text-[11px]">
              Confidence falls when prices are volatile, even if the direction looks clear.
            </p>
          </aside>
        )}
      </div>

      {weather && (
        <div className="mt-4">
          <WeatherCard weather={weather} />
        </div>
      )}
    </div>
  );
}
