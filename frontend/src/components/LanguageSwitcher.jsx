import { useEffect, useState } from 'react';

import * as api from '../services/api.js';
import { useAuth } from '../context/AuthContext.jsx';

/**
 * Language picker (§6.3).
 *
 * Each language is listed in its own script — a Bhojpuri speaker looks for
 * "भोजपुरी", not "Bhojpuri". The list comes from the service so adding a
 * language server-side needs no frontend change.
 */

const FALLBACK = [
  { code: 'hi', name: 'हिंदी', english_name: 'Hindi' },
  { code: 'en', name: 'English', english_name: 'English' },
  { code: 'bho', name: 'भोजपुरी', english_name: 'Bhojpuri' },
  { code: 'mai', name: 'मैथिली', english_name: 'Maithili' },
  { code: 'mr', name: 'मराठी', english_name: 'Marathi' },
  { code: 'bn', name: 'বাংলা', english_name: 'Bengali' },
  { code: 'ta', name: 'தமிழ்', english_name: 'Tamil' },
];

export default function LanguageSwitcher({ compact = false }) {
  const { language, setLanguage } = useAuth();
  const [languages, setLanguages] = useState(FALLBACK);

  useEffect(() => {
    let cancelled = false;
    api
      .supportedLanguages()
      .then((payload) => {
        if (!cancelled && payload?.languages?.length) setLanguages(payload.languages);
      })
      .catch(() => {
        /* the bundled list is a fine fallback */
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <label className={compact ? 'text-xs' : 'block text-sm'} data-testid="language-switcher">
      <span className="sr-only">Answer language</span>
      <select
        className={compact ? 'field px-2 py-1 text-xs' : 'field'}
        value={language}
        onChange={(event) => setLanguage(event.target.value)}
        aria-label="Answer language"
      >
        {languages.map((option) => (
          <option key={option.code} value={option.code}>
            {option.name}
            {option.english_name && option.english_name !== option.name
              ? ` · ${option.english_name}`
              : ''}
          </option>
        ))}
      </select>
    </label>
  );
}
