import { motion } from 'framer-motion';

/**
 * Weather outlook and its supply implication (§6.3).
 *
 * The forecast itself is secondary; what a farmer needs is the consequence.
 * The card leads with the supply verdict and keeps the daily numbers below it.
 */

const RISK = {
  disruption: {
    icon: '🌧️',
    en: 'Supply may be disrupted',
    hi: 'आवक घट सकती है',
    className: 'bg-blue-100 text-blue-900 dark:bg-blue-900/30 dark:text-blue-200',
  },
  surplus: {
    icon: '☀️',
    en: 'Arrivals may increase',
    hi: 'आवक बढ़ सकती है',
    className: 'bg-amber-100 text-amber-900 dark:bg-amber-900/30 dark:text-amber-200',
  },
  normal: {
    icon: '🌤️',
    en: 'No weather disruption expected',
    hi: 'मौसम से दिक्कत नहीं',
    className: 'bg-mandi-100 text-mandi-900 dark:bg-mandi-900/30 dark:text-mandi-200',
  },
};

const PRESSURE = {
  upward: { en: 'Prices may firm', hi: 'भाव चढ़ सकते हैं', colour: '#16a34a' },
  downward: { en: 'Prices may soften', hi: 'भाव नरम पड़ सकते हैं', colour: '#dc2626' },
  neutral: { en: 'No clear price effect', hi: 'भाव पर खास असर नहीं', colour: '#78716c' },
};

export default function WeatherCard({ weather, language = 'hi' }) {
  if (!weather) return null;

  const risk = RISK[weather.supply_risk] || RISK.normal;
  const pressure = PRESSURE[weather.price_pressure] || PRESSURE.neutral;
  const summary = language === 'en' ? weather.summary : weather.summary_hi || weather.summary;

  return (
    <motion.section
      className="glass p-4"
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      data-testid="weather-card"
    >
      <header className="flex items-start justify-between gap-3">
        <div>
          <h3 className="text-base font-semibold">
            <span aria-hidden="true" className="mr-1.5">
              {risk.icon}
            </span>
            {risk.en}
          </h3>
          <p lang="hi" className="text-xs opacity-70">
            {risk.hi}
          </p>
        </div>
        <span className={`chip ${risk.className}`}>{weather.district || weather.state || '—'}</span>
      </header>

      <p className="mt-3 text-sm font-medium" style={{ color: pressure.colour }}>
        {pressure.en} · <span lang="hi">{pressure.hi}</span>
      </p>

      <p lang={language} className="mt-2 text-sm opacity-80">
        {summary}
      </p>

      <dl className="mt-3 grid grid-cols-3 gap-2 text-center text-xs">
        <div className="rounded-lg bg-black/5 p-2 dark:bg-white/5">
          <dt className="opacity-60">Rain</dt>
          <dd className="font-semibold">{weather.total_rain_mm.toFixed(0)} mm</dd>
        </div>
        <div className="rounded-lg bg-black/5 p-2 dark:bg-white/5">
          <dt className="opacity-60">Heavy days</dt>
          <dd className="font-semibold">{weather.heavy_rain_days}</dd>
        </div>
        <div className="rounded-lg bg-black/5 p-2 dark:bg-white/5">
          <dt className="opacity-60">Hot days</dt>
          <dd className="font-semibold">{weather.heat_stress_days}</dd>
        </div>
      </dl>

      <footer className="mt-3 flex items-center justify-between text-[11px] opacity-60">
        <span>
          {weather.live ? `Live forecast (${weather.source})` : 'Seasonal model — no live forecast'}
        </span>
        <span>{Math.round(weather.confidence * 100)}% confidence</span>
      </footer>
    </motion.section>
  );
}
