import { motion } from 'framer-motion';

const formatPrice = (value) =>
  new Intl.NumberFormat('en-IN', { maximumFractionDigits: 0 }).format(Number(value) || 0);

const TREND_MARK = {
  upward: { glyph: '▲', className: 'text-mandi-600', en: 'Rising', hi: 'बढ़ रहा' },
  downward: { glyph: '▼', className: 'text-red-600', en: 'Falling', hi: 'घट रहा' },
  stable: { glyph: '▬', className: 'text-amber-600', en: 'Steady', hi: 'एक जैसा' },
};

/** Freshness matters: Agmarknet can lag 24-48 hours in some states (§6.2). */
function freshness(arrivalDate) {
  if (!arrivalDate) return null;
  const reported = new Date(arrivalDate);
  if (Number.isNaN(reported.getTime())) return null;
  const days = Math.floor((Date.now() - reported.getTime()) / 86400000);
  if (days <= 0) return { en: 'Today', hi: 'आज', stale: false };
  if (days === 1) return { en: 'Yesterday', hi: 'कल', stale: false };
  return { en: `${days} days old`, hi: `${days} दिन पुराना`, stale: days > 2 };
}

export default function MandiCard({ record, trend, best = false, index = 0 }) {
  if (!record) return null;

  const mark = TREND_MARK[trend] || null;
  const age = freshness(record.arrival_date);

  return (
    <motion.article
      data-testid="mandi-card"
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: Math.min(index * 0.05, 0.4), duration: 0.35 }}
      className={`glass relative p-4 ${best ? 'ring-2 ring-mandi-500' : ''}`}
    >
      {best && (
        <span className="chip absolute -top-2.5 right-3 bg-mandi-600 text-white">
          Best price · सबसे अच्छा भाव
        </span>
      )}

      <header>
        <h3 className="truncate text-base font-semibold" title={record.market}>
          {record.market}
        </h3>
        <p className="text-xs opacity-60">
          {record.district}, {record.state}
        </p>
      </header>

      <div className="mt-3 flex items-baseline gap-2">
        <span className="text-2xl font-bold text-mandi-700 dark:text-mandi-300">
          ₹{formatPrice(record.modal_price)}
        </span>
        <span className="text-xs opacity-60">/ quintal</span>
        {mark && (
          <span className={`ml-auto text-sm font-semibold ${mark.className}`} title={mark.en}>
            {mark.glyph} {mark.en}
          </span>
        )}
      </div>

      <dl className="mt-2 flex gap-4 text-xs opacity-70">
        <div>
          <dt className="inline">Min </dt>
          <dd className="inline font-medium">₹{formatPrice(record.min_price)}</dd>
        </div>
        <div>
          <dt className="inline">Max </dt>
          <dd className="inline font-medium">₹{formatPrice(record.max_price)}</dd>
        </div>
      </dl>

      <footer className="mt-3 flex items-center justify-between text-[11px]">
        <span className="opacity-60">{record.commodity}</span>
        {age && (
          <span
            className={
              age.stale
                ? 'chip bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-200'
                : 'opacity-60'
            }
            title={record.arrival_date}
          >
            {age.en}
          </span>
        )}
      </footer>
    </motion.article>
  );
}
