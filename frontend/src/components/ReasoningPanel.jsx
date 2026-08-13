import { AnimatePresence, motion } from 'framer-motion';

/**
 * Explainable AI panel (§4.8).
 *
 * Renders the agent's `reasoning_steps` verbatim, plus the claim-level
 * fact-check verdicts. Section 5.3 found this to be the most valued feature in
 * the farmer study: seeing the steps taken is what made participants willing to
 * act on the recommendation, so nothing here is summarised away.
 */

const STATUS_STYLE = {
  verified: {
    className: 'bg-mandi-100 text-mandi-800 dark:bg-mandi-900/40 dark:text-mandi-200',
    en: 'Verified against government data',
    hi: 'सरकारी आँकड़ों से पुष्टि',
  },
  partially_verified: {
    className: 'bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-200',
    en: 'Partly verified',
    hi: 'आंशिक पुष्टि',
  },
  insufficient_evidence: {
    className: 'bg-red-100 text-red-800 dark:bg-red-900/40 dark:text-red-200',
    en: 'Not enough evidence',
    hi: 'पर्याप्त प्रमाण नहीं',
  },
};

function stepParts(step) {
  const separator = step.indexOf(':');
  if (separator === -1) return { actor: 'Agent', detail: step };
  return { actor: step.slice(0, separator), detail: step.slice(separator + 1).trim() };
}

export default function ReasoningPanel({ response, open = true }) {
  if (!response) {
    return (
      <aside className="glass p-5" data-testid="reasoning-panel-empty">
        <h2 className="text-sm font-semibold uppercase tracking-wide opacity-60">
          AI Reasoning · सोचने का तरीका
        </h2>
        <p className="mt-3 text-sm opacity-70">
          Ask a question and every step the assistant takes will appear here.
        </p>
        <p lang="hi" className="mt-1 text-sm opacity-60">
          सवाल पूछिए — सहायक ने कैसे जवाब निकाला, हर कदम यहाँ दिखेगा।
        </p>
      </aside>
    );
  }

  const steps = response.reasoning_steps || [];
  const claims = response.fact_check_claims || [];
  const status = STATUS_STYLE[response.fact_check_status] || STATUS_STYLE.insufficient_evidence;

  return (
    <aside className="glass p-5" data-testid="reasoning-panel">
      <header className="flex items-center justify-between gap-3">
        <h2 className="text-sm font-semibold uppercase tracking-wide opacity-60">
          AI Reasoning · सोचने का तरीका
        </h2>
        <span className={`chip ${status.className}`}>{status.en}</span>
      </header>

      {response.degraded && (
        <p className="mt-3 rounded-lg bg-amber-50 p-3 text-xs text-amber-900 dark:bg-amber-900/20 dark:text-amber-200">
          The live government feed was unreachable. These figures come from the offline
          reference dataset — confirm at the mandi before acting.
          <span lang="hi" className="mt-1 block">
            सरकारी लाइव आँकड़े नहीं मिले। मंडी जाकर भाव पक्का कर लें।
          </span>
        </p>
      )}

      <AnimatePresence initial={false}>
        {open && (
          <motion.ol
            className="mt-4 space-y-2"
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            data-testid="reasoning-steps"
          >
            {steps.map((step, index) => {
              const { actor, detail } = stepParts(step);
              return (
                <motion.li
                  key={`${actor}-${index}`}
                  initial={{ opacity: 0, x: -8 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: Math.min(index * 0.04, 0.4) }}
                  className="rounded-lg border-l-2 border-mandi-500/60 bg-white/40 p-2.5 dark:bg-white/5"
                >
                  <p className="text-[11px] font-semibold uppercase tracking-wide text-mandi-700 dark:text-mandi-300">
                    {actor}
                  </p>
                  <p className="mt-0.5 whitespace-pre-wrap text-sm opacity-90">{detail}</p>
                </motion.li>
              );
            })}
          </motion.ol>
        )}
      </AnimatePresence>

      {claims.length > 0 && (
        <section className="mt-5">
          <h3 className="text-xs font-semibold uppercase tracking-wide opacity-60">
            Fact check · तथ्य जाँच
          </h3>
          <ul className="mt-2 space-y-1.5" data-testid="fact-check-claims">
            {claims.map((claim, index) => {
              const claimStatus = STATUS_STYLE[claim.status] || STATUS_STYLE.insufficient_evidence;
              return (
                <li key={`${claim.claim}-${index}`} className="text-sm">
                  <span className={`chip mr-2 ${claimStatus.className}`}>{claimStatus.en}</span>
                  <span className="opacity-90">{claim.claim}</span>
                  {claim.evidence?.length > 0 && (
                    <p className="mt-0.5 pl-1 text-xs opacity-60">{claim.evidence[0]}</p>
                  )}
                </li>
              );
            })}
          </ul>
        </section>
      )}

      {response.retrieved_context?.length > 0 && (
        <section className="mt-5">
          <h3 className="text-xs font-semibold uppercase tracking-wide opacity-60">
            Historical context retrieved
          </h3>
          <ul className="mt-2 space-y-1 text-xs opacity-70">
            {response.retrieved_context.slice(0, 5).map((citation, index) => (
              <li key={index} className="truncate" title={citation}>
                {citation}
              </li>
            ))}
          </ul>
        </section>
      )}
    </aside>
  );
}
