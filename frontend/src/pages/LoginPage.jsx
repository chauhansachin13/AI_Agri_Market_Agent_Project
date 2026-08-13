import { useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';

import { useAuth } from '../context/AuthContext.jsx';

export default function LoginPage() {
  const { signIn, signUp } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [mode, setMode] = useState('login');
  const [form, setForm] = useState({
    name: '',
    phone: '',
    password: '',
    state: 'Bihar',
    district: '',
    preferredLanguage: 'hi',
  });
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);

  const update = (field) => (event) => setForm({ ...form, [field]: event.target.value });

  const submit = async (event) => {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      if (mode === 'login') {
        await signIn({ phone: form.phone, password: form.password });
      } else {
        await signUp({
          name: form.name,
          phone: form.phone,
          password: form.password,
          preferredLanguage: form.preferredLanguage,
          location: { state: form.state, district: form.district },
        });
      }
      navigate(location.state?.from || '/chat', { replace: true });
    } catch (caught) {
      setError(caught.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="mx-auto max-w-md px-4 py-12">
      <div className="glass p-6">
        <h1 className="text-2xl font-bold">
          {mode === 'login' ? 'Sign in' : 'Create an account'}
        </h1>
        <p lang="hi" className="mt-1 text-sm opacity-70">
          {mode === 'login'
            ? 'अपने मोबाइल नंबर से लॉगिन करें'
            : 'अपना खाता बनाइए — भाव आपके जिले के हिसाब से मिलेंगे'}
        </p>

        <form onSubmit={submit} className="mt-6 space-y-4">
          {mode === 'register' && (
            <label className="block text-sm">
              <span className="mb-1 block opacity-70">Name · नाम</span>
              <input className="field" value={form.name} onChange={update('name')} required />
            </label>
          )}

          <label className="block text-sm">
            <span className="mb-1 block opacity-70">Mobile number · मोबाइल नंबर</span>
            <input
              className="field"
              type="tel"
              inputMode="numeric"
              pattern="[6-9][0-9]{9}"
              maxLength={10}
              value={form.phone}
              onChange={update('phone')}
              placeholder="9876543210"
              required
            />
          </label>

          <label className="block text-sm">
            <span className="mb-1 block opacity-70">Password · पासवर्ड</span>
            <input
              className="field"
              type="password"
              minLength={6}
              value={form.password}
              onChange={update('password')}
              required
            />
          </label>

          {mode === 'register' && (
            <div className="grid grid-cols-2 gap-3">
              <label className="block text-sm">
                <span className="mb-1 block opacity-70">State · राज्य</span>
                <input className="field" value={form.state} onChange={update('state')} />
              </label>
              <label className="block text-sm">
                <span className="mb-1 block opacity-70">District · जिला</span>
                <input className="field" value={form.district} onChange={update('district')} />
              </label>
            </div>
          )}

          {error && (
            <p className="rounded-lg bg-red-100 px-3 py-2 text-sm text-red-800 dark:bg-red-900/30 dark:text-red-200">
              {error}
            </p>
          )}

          <button type="submit" className="btn-primary w-full" disabled={busy}>
            {busy ? 'Please wait…' : mode === 'login' ? 'Sign in' : 'Create account'}
          </button>
        </form>

        <p className="mt-4 text-center text-sm opacity-70">
          {mode === 'login' ? 'New here?' : 'Already registered?'}{' '}
          <button
            type="button"
            className="font-medium text-mandi-700 underline-offset-2 hover:underline dark:text-mandi-300"
            onClick={() => {
              setMode(mode === 'login' ? 'register' : 'login');
              setError(null);
            }}
          >
            {mode === 'login' ? 'Create an account' : 'Sign in'}
          </button>
        </p>

        <p className="mt-4 text-center text-xs opacity-60">
          You can ask questions without an account. Signing in saves your district and history.
        </p>
      </div>
    </div>
  );
}
