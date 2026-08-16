import { useCallback, useEffect, useState } from 'react';

import * as api from '../services/api.js';
import { useAuth } from '../context/AuthContext.jsx';

const CROPS = ['Tomato', 'Onion', 'Wheat', 'Potato', 'Rice', 'Maize', 'Mustard', 'Garlic'];

const STATUS_CHIP = {
  active: 'chip-mandi',
  triggered: 'chip-harvest',
  paused: 'chip-neutral',
};

const rupees = (value) =>
  typeof value === 'number'
    ? `₹${new Intl.NumberFormat('en-IN', { maximumFractionDigits: 0 }).format(value)}`
    : '—';

export default function AlertsPage() {
  const { isAuthenticated, user } = useAuth();
  const [alerts, setAlerts] = useState([]);
  const [form, setForm] = useState({ crop: 'Wheat', targetPrice: '', direction: 'above' });
  const [status, setStatus] = useState('idle');
  const [error, setError] = useState(null);
  const [checkResult, setCheckResult] = useState(null);

  const load = useCallback(async () => {
    if (!isAuthenticated) return;
    setStatus('loading');
    try {
      const data = await api.listAlerts();
      setAlerts(data.alerts || []);
      setStatus('ready');
    } catch (caught) {
      setError(caught.message);
      setStatus('error');
    }
  }, [isAuthenticated]);

  useEffect(() => {
    load();
  }, [load]);

  const submit = async (event) => {
    event.preventDefault();
    setError(null);
    const target = Number(form.targetPrice);
    if (!Number.isFinite(target) || target <= 0) {
      setError('Enter the price you are waiting for.');
      return;
    }
    try {
      await api.createAlert({ ...form, targetPrice: target });
      setForm({ ...form, targetPrice: '' });
      await load();
    } catch (caught) {
      setError(caught.message);
    }
  };

  const check = async () => {
    setError(null);
    try {
      setCheckResult(await api.checkAlerts());
      await load();
    } catch (caught) {
      setError(caught.message);
    }
  };

  const act = async (alert, action) => {
    try {
      if (action === 'delete') await api.deleteAlert(alert.id);
      else await api.updateAlert(alert.id, { status: action });
      await load();
    } catch (caught) {
      setError(caught.message);
    }
  };

  if (!isAuthenticated) {
    return (
      <div className="container-page py-16">
        <div className="surface mx-auto max-w-md p-8 text-center">
          <h1 className="text-xl">Price alerts</h1>
          <p lang="hi" className="muted mt-1 text-sm">
            भाव पहुँचते ही खबर पाइए
          </p>
          <p className="muted mt-4 text-sm">
            Sign in to tell us the price you are waiting for. We will watch the mandi feed
            so you do not have to check every morning.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="container-page py-8">
      <header className="mb-6">
        <h1 className="text-2xl">Price alerts</h1>
        <p lang="hi" className="muted">
          भाव पहुँचते ही खबर — रोज़ देखने की ज़रूरत नहीं
        </p>
      </header>

      <div className="grid gap-6 lg:grid-cols-[340px_minmax(0,1fr)]">
        <form onSubmit={submit} className="surface h-fit p-5">
          <h2 className="text-base">Watch a price</h2>
          <p lang="hi" className="muted text-xs">
            कौन सा भाव देखना है
          </p>

          <label className="mt-4 block">
            <span className="label">Crop · फसल</span>
            <select
              className="field"
              value={form.crop}
              onChange={(e) => setForm({ ...form, crop: e.target.value })}
            >
              {CROPS.map((crop) => (
                <option key={crop} value={crop}>
                  {crop}
                </option>
              ))}
            </select>
          </label>

          <label className="mt-3 block">
            <span className="label">Tell me when it is · मुझे बताएँ जब भाव</span>
            <select
              className="field"
              value={form.direction}
              onChange={(e) => setForm({ ...form, direction: e.target.value })}
            >
              <option value="above">at or above · इससे ऊपर हो</option>
              <option value="below">at or below · इससे नीचे हो</option>
            </select>
          </label>

          <label className="mt-3 block">
            <span className="label">Price per quintal · रुपये प्रति क्विंटल</span>
            <input
              className="field"
              inputMode="numeric"
              value={form.targetPrice}
              onChange={(e) => setForm({ ...form, targetPrice: e.target.value })}
              placeholder="2600"
            />
          </label>

          <p className="muted mt-2 text-2xs">
            Watching {user?.location?.district || 'your district'} and nearby mandis.
          </p>

          {error && (
            <p className="mt-3 rounded-lg bg-red-100 px-3 py-2 text-sm text-red-800 dark:bg-red-500/15 dark:text-red-300">
              {error}
            </p>
          )}

          <button type="submit" className="btn-primary mt-4 w-full">
            Add alert · जोड़ें
          </button>
        </form>

        <section>
          <div className="mb-3 flex items-center justify-between gap-3">
            <p className="muted text-sm">
              {alerts.length} alert{alerts.length === 1 ? '' : 's'}
            </p>
            <button type="button" onClick={check} className="btn-ghost text-sm">
              Check now · अभी जाँचें
            </button>
          </div>

          {checkResult && (
            <p
              className={`mb-3 rounded-xl px-4 py-3 text-sm ${
                checkResult.triggered.length
                  ? 'bg-mandi-100 text-mandi-900 dark:bg-mandi-500/15 dark:text-mandi-200'
                  : 'muted border'
              }`}
              data-testid="check-result"
            >
              {checkResult.triggered.length
                ? `${checkResult.triggered.length} alert(s) reached their price.`
                : `Checked ${checkResult.checked} alert(s) — none have reached their price yet.`}
            </p>
          )}

          {status === 'ready' && alerts.length === 0 && (
            <p className="surface p-8 text-center text-sm muted">
              No alerts yet. Add the price you are waiting for and we will watch it.
              <span lang="hi" className="mt-1 block">
                अभी कोई अलर्ट नहीं। जिस भाव का इंतज़ार है, वह जोड़ दीजिए।
              </span>
            </p>
          )}

          <ul className="space-y-3">
            {alerts.map((alert) => (
              <li key={alert.id} className="surface p-4" data-testid="alert-row">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <p className="font-semibold">
                      {alert.crop}{' '}
                      <span className="muted font-normal">
                        {alert.direction === 'below' ? 'at or below' : 'at or above'}{' '}
                        {rupees(alert.targetPrice)}
                      </span>
                    </p>
                    <p className="muted text-xs">
                      {[alert.district, alert.state].filter(Boolean).join(', ') || 'Any district'}
                      {alert.lastSeenPrice ? ` · last seen ${rupees(alert.lastSeenPrice)}` : ''}
                    </p>
                  </div>
                  <span className={STATUS_CHIP[alert.status] || 'chip-neutral'}>
                    {alert.status}
                  </span>
                </div>

                <div className="mt-3 flex flex-wrap gap-2">
                  {alert.status !== 'paused' && (
                    <button type="button" onClick={() => act(alert, 'paused')} className="btn-ghost text-xs">
                      Pause
                    </button>
                  )}
                  {alert.status !== 'active' && (
                    <button type="button" onClick={() => act(alert, 'active')} className="btn-ghost text-xs">
                      Resume
                    </button>
                  )}
                  <button type="button" onClick={() => act(alert, 'delete')} className="btn-ghost text-xs">
                    Remove
                  </button>
                </div>
              </li>
            ))}
          </ul>
        </section>
      </div>
    </div>
  );
}
