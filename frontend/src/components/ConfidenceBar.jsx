import { motion } from 'framer-motion';

/**
 * Confidence indicator (§4.8) — a speedometer-style arc.
 *
 * The colour band is deliberately coarse. A farmer needs to know whether to
 * act on the answer, not to read a decimal, so the arc is paired with a plain
 * verdict word in both languages.
 */

const band = (score) => {
  if (score >= 0.75) return { key: 'high', color: '#16a34a', en: 'High', hi: 'ज्यादा भरोसा' };
  if (score >= 0.5) return { key: 'medium', color: '#ca8a04', en: 'Moderate', hi: 'ठीक-ठाक भरोसा' };
  return { key: 'low', color: '#dc2626', en: 'Low', hi: 'कम भरोसा' };
};

export default function ConfidenceBar({ score = 0, label = 'Confidence', compact = false }) {
  const clamped = Math.min(Math.max(Number(score) || 0, 0), 1);
  const { color, en, hi } = band(clamped);
  const percent = Math.round(clamped * 100);

  // Semi-circular arc: 180 degrees of a circle of radius 52.
  const radius = 52;
  const circumference = Math.PI * radius;
  const filled = circumference * clamped;

  if (compact) {
    return (
      <div className="flex items-center gap-2" data-testid="confidence-compact">
        <div className="h-2 w-24 overflow-hidden rounded-full bg-black/10 dark:bg-white/10">
          <motion.div
            className="h-full rounded-full"
            style={{ backgroundColor: color }}
            initial={{ width: 0 }}
            animate={{ width: `${percent}%` }}
            transition={{ duration: 0.6, ease: 'easeOut' }}
          />
        </div>
        <span className="text-xs font-semibold" style={{ color }}>
          {percent}%
        </span>
      </div>
    );
  }

  return (
    <figure className="flex flex-col items-center" data-testid="confidence-gauge">
      <svg width="140" height="86" viewBox="0 0 140 86" role="img" aria-label={`${label}: ${percent}%`}>
        <path
          d="M 18 74 A 52 52 0 0 1 122 74"
          fill="none"
          stroke="currentColor"
          strokeWidth="12"
          strokeLinecap="round"
          className="text-black/10 dark:text-white/10"
        />
        <motion.path
          d="M 18 74 A 52 52 0 0 1 122 74"
          fill="none"
          stroke={color}
          strokeWidth="12"
          strokeLinecap="round"
          strokeDasharray={circumference}
          initial={{ strokeDashoffset: circumference }}
          animate={{ strokeDashoffset: circumference - filled }}
          transition={{ duration: 0.8, ease: 'easeOut' }}
        />
        <text
          x="70"
          y="66"
          textAnchor="middle"
          className="fill-current text-2xl font-bold"
          style={{ fill: color }}
        >
          {percent}%
        </text>
      </svg>
      <figcaption className="-mt-1 text-center">
        <p className="text-sm font-semibold" style={{ color }}>
          {en}
        </p>
        <p lang="hi" className="muted text-xs">
          {hi}
        </p>
      </figcaption>
    </figure>
  );
}
