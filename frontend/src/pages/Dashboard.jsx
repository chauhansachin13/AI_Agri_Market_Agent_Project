import { useCallback, useEffect, useState } from 'react';

import MandiCard from '../components/MandiCard.jsx';
import * as api from '../services/api.js';
import { useAuth } from '../context/AuthContext.jsx';

const CROPS = ['Tomato', 'Onion', 'Wheat', 'Potato', 'Rice', 'Maize', 'Mustard'];
const STATES = ['Bihar', 'Uttar Pradesh', 'Madhya Pradesh', 'Punjab', 'Haryana', 'Rajasthan'];

export default function Dashboard() {
  const { user } = useAuth();
  const [crop, setCrop] = useState('Tomato');
  const [state, setState] = useState(user?.location?.state || 'Bihar');
  const [district, setDistrict] = useState(user?.location?.district || '');
  const [records, setRecords] = useState([]);
  const [trend, setTrend] = useState(null);
  const [status, setStatus] = useState('idle');
  const [error, setError] = useState(null);
  const [cached, setCached] = useState(false);

  const load = useCallback(async () => {
    setStatus('loading');
    setError(null);
    try {
      // The trend is supplementary — a price board is still useful without it,
      // so its failure must not blank out the records.
      const [priceResult, trendResult] = await Promise.allSettled([
        api.mandiPrices({ crop, state, district: district || undefined, limit: 24 }),
        api.priceTrend({ crop, state, district: district || undefined }),
      ]);

      if (priceResult.status === 'rejected') throw priceResult.reason;

      setRecords(priceResult.value.records || []);
      setCached(Boolean(priceResult.value.cached));
      setTrend(trendResult.status === 'fulfilled' ? trendResult.value : null);
      setStatus('ready');
    } catch (caught) {
      setError(caught.message);
      setStatus('error');
    }
  }, [crop, state, district]);

  useEffect(() => {
    load();
  }, [load]);

  const sorted = [...records].sort((a, b) => b.modal_price - a.modal_price);

  return (
    <div className="mx-auto max-w-7xl px-4 py-8">
      <header className="mb-6">
        <h1 className="text-2xl font-bold">Live Mandi Board</h1>
        <p lang="hi" className="opacity-70">
          आसपास की मंडियों के ताज़ा भाव
        </p>
      </header>

      <form
        className="glass mb-6 grid gap-3 p-4 sm:grid-cols-2 lg:grid-cols-4"
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
          <span className="mb-1 block opacity-70">State · राज्य</span>
          <select className="field" value={state} onChange={(e) => setState(e.target.value)}>
            {STATES.map((option) => (
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
            placeholder="All districts"
          />
        </label>

        <div className="flex items-end">
          <button type="submit" className="btn-primary w-full" disabled={status === 'loading'}>
            {status === 'loading' ? 'Loading…' : 'Refresh'}
          </button>
        </div>
      </form>

      {status === 'error' && (
        <p className="glass p-4 text-sm text-red-700 dark:text-red-300">
          Could not load prices: {error}
        </p>
      )}

      {status === 'ready' && sorted.length === 0 && (
        <p className="glass p-6 text-center text-sm opacity-70">
          No mandi records reported for this crop and district on the latest arrival day.
        </p>
      )}

      {sorted.length > 0 && (
        <>
          <div className="mb-3 flex flex-wrap items-center gap-3 text-xs opacity-60">
            <span>{sorted.length} markets</span>
            {trend && <span className="capitalize">Trend: {trend.direction}</span>}
            {cached && <span>Served from cache</span>}
          </div>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
            {sorted.map((record, index) => (
              <MandiCard
                key={`${record.market}-${record.arrival_date}-${index}`}
                record={record}
                trend={trend?.direction}
                best={index === 0}
                index={index}
              />
            ))}
          </div>
        </>
      )}
    </div>
  );
}
