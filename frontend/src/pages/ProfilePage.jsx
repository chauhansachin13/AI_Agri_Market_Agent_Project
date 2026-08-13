import { useEffect, useState } from 'react';

import * as api from '../services/api.js';
import { useAuth } from '../context/AuthContext.jsx';

export default function ProfilePage() {
  const { user, updateProfile } = useAuth();
  const [form, setForm] = useState({
    name: user?.name || '',
    preferredLanguage: user?.preferredLanguage || 'hi',
    state: user?.location?.state || '',
    district: user?.location?.district || '',
    pincode: user?.location?.pincode || '',
    crops: (user?.crops || []).join(', '),
  });
  const [history, setHistory] = useState([]);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    let cancelled = false;
    api
      .queryHistory(10)
      .then((rows) => {
        if (!cancelled) setHistory(rows);
      })
      .catch(() => {
        /* history is a convenience; its absence should not block the page */
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const update = (field) => (event) => {
    setForm({ ...form, [field]: event.target.value });
    setSaved(false);
  };

  const submit = async (event) => {
    event.preventDefault();
    setError(null);
    try {
      await updateProfile({
        name: form.name,
        preferredLanguage: form.preferredLanguage,
        location: {
          state: form.state || undefined,
          district: form.district || undefined,
          pincode: form.pincode || undefined,
        },
        crops: form.crops
          .split(',')
          .map((crop) => crop.trim())
          .filter(Boolean),
      });
      setSaved(true);
    } catch (caught) {
      setError(caught.message);
    }
  };

  if (!user) {
    return (
      <div className="mx-auto max-w-md px-4 py-12">
        <p className="glass p-6 text-center text-sm">Sign in to view your profile.</p>
      </div>
    );
  }

  return (
    <div className="mx-auto grid max-w-4xl gap-6 px-4 py-8 md:grid-cols-2">
      <form onSubmit={submit} className="glass p-6">
        <h1 className="text-xl font-bold">Your profile</h1>
        <p lang="hi" className="text-sm opacity-70">
          आपकी जानकारी
        </p>

        <div className="mt-5 space-y-4">
          <label className="block text-sm">
            <span className="mb-1 block opacity-70">Name · नाम</span>
            <input className="field" value={form.name} onChange={update('name')} />
          </label>

          <label className="block text-sm">
            <span className="mb-1 block opacity-70">Answer language · जवाब की भाषा</span>
            <select
              className="field"
              value={form.preferredLanguage}
              onChange={update('preferredLanguage')}
            >
              <option value="hi">हिंदी</option>
              <option value="en">English</option>
            </select>
          </label>

          <div className="grid grid-cols-2 gap-3">
            <label className="block text-sm">
              <span className="mb-1 block opacity-70">State</span>
              <input className="field" value={form.state} onChange={update('state')} />
            </label>
            <label className="block text-sm">
              <span className="mb-1 block opacity-70">District</span>
              <input className="field" value={form.district} onChange={update('district')} />
            </label>
          </div>

          <label className="block text-sm">
            <span className="mb-1 block opacity-70">Pincode · पिन कोड</span>
            <input
              className="field"
              value={form.pincode}
              onChange={update('pincode')}
              maxLength={6}
              inputMode="numeric"
            />
          </label>

          <label className="block text-sm">
            <span className="mb-1 block opacity-70">Your crops · आपकी फसलें</span>
            <input
              className="field"
              value={form.crops}
              onChange={update('crops')}
              placeholder="Wheat, Potato"
            />
          </label>
        </div>

        {error && (
          <p className="mt-3 rounded-lg bg-red-100 px-3 py-2 text-sm text-red-800 dark:bg-red-900/30 dark:text-red-200">
            {error}
          </p>
        )}
        {saved && <p className="mt-3 text-sm text-mandi-700 dark:text-mandi-300">Saved.</p>}

        <button type="submit" className="btn-primary mt-5 w-full">
          Save
        </button>
      </form>

      <section className="glass p-6">
        <h2 className="text-xl font-bold">Recent questions</h2>
        <p lang="hi" className="text-sm opacity-70">
          आपके पिछले सवाल
        </p>

        {history.length === 0 ? (
          <p className="mt-4 text-sm opacity-60">No questions yet.</p>
        ) : (
          <ul className="mt-4 space-y-3">
            {history.map((row) => (
              <li key={row._id} className="border-b border-black/5 pb-2 last:border-0 dark:border-white/10">
                <p className="text-sm">{row.text}</p>
                <p className="mt-0.5 text-xs opacity-60">
                  {row.intent}
                  {row.recommendation ? ` · ${row.recommendation}` : ''}
                  {typeof row.confidenceScore === 'number'
                    ? ` · ${Math.round(row.confidenceScore * 100)}% confidence`
                    : ''}
                </p>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
