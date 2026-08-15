import { Link } from 'react-router-dom';

const STATS = [
  { value: '3,500+', en: 'Mandis covered', hi: 'मंडियाँ' },
  { value: '7', en: 'Languages', hi: 'भाषाएँ' },
  { value: '12', en: 'AI agents', hi: 'एआई एजेंट' },
  { value: '0', en: 'Invented prices', hi: 'मनगढ़ंत भाव' },
];

const FEATURES = [
  {
    icon: '📊',
    en: 'Government data, or nothing',
    hi: 'सरकारी आँकड़े, वरना कुछ नहीं',
    body: 'Every price comes from Agmarknet and eNAM. The model reasons and explains; it is never allowed to produce a number.',
  },
  {
    icon: '🗣️',
    en: 'Seven languages, your script',
    hi: 'सात भाषाएँ, आपकी लिपि',
    body: 'Hindi, Bhojpuri, Maithili, Marathi, Bengali, Tamil or English — typed or spoken. The answer returns in the language you asked in.',
  },
  {
    icon: '🧭',
    en: 'Sell or wait, and why',
    hi: 'बेचें या रुकें — और क्यों',
    body: 'Trend, forecast, weather and the spread between nearby mandis combine into one clear call, citing only the reasons that support it.',
  },
  {
    icon: '📈',
    en: 'A forecast that admits its error',
    hi: 'अनुमान, अपनी ग़लती के साथ',
    body: 'A trained model projects the week ahead, backtested against a naive baseline. If it cannot beat guessing, the page says so.',
  },
  {
    icon: '🔍',
    en: 'Every step is visible',
    hi: 'हर कदम दिखता है',
    body: 'The reasoning panel shows what was checked, what was verified, and what was thrown away for lack of evidence.',
  },
  {
    icon: '🤝',
    en: 'Sell directly to buyers',
    hi: 'सीधे खरीदार को बेचें',
    body: 'List your produce, receive offers, and see each one measured against the mandi rate at the moment you listed.',
  },
];

const STEPS = [
  {
    n: '01',
    en: 'Ask in your own words',
    hi: 'अपनी भाषा में पूछें',
    body: 'Typed or spoken, in any of the seven supported languages.',
  },
  {
    n: '02',
    en: 'Agents gather the evidence',
    hi: 'एजेंट सबूत जुटाते हैं',
    body: 'Location, live mandi prices, historical context, a trained forecast, the weather outlook and current market news.',
  },
  {
    n: '03',
    en: 'Every claim is checked',
    hi: 'हर दावे की जाँच',
    body: 'Each figure is traced to a government record, the trend model, the forecast, or arithmetic over those. Anything else is removed.',
  },
  {
    n: '04',
    en: 'You get an answer you can audit',
    hi: 'जवाब, जिसे आप परख सकें',
    body: 'A plain recommendation with its confidence, the prices behind it, and the full reasoning trail.',
  },
];

// Entrance motion is a CSS enhancement, never a visibility gate. The keyframes
// run without a fill mode, so an element's resting state is fully visible: if
// the animation never runs -- a backgrounded tab throttling rAF, a reduced-
// motion setting, a crawler -- the content is simply there.

function Hero() {
  return (
    <section className="relative overflow-hidden">
      <div className="aurora pointer-events-none absolute inset-0 -z-10" />
      <div className="grid-lines pointer-events-none absolute inset-0 -z-10" />

      <div className="container-page grid items-center gap-12 py-16 lg:grid-cols-[1.05fr_0.95fr] lg:py-24">
        <div>
          <div>
            <span className="chip-mandi">
              <span className="relative flex h-1.5 w-1.5">
                <span className="absolute inline-flex h-full w-full animate-pulse-ring rounded-full bg-mandi-500" />
                <span className="relative inline-flex h-1.5 w-1.5 rounded-full bg-mandi-600" />
              </span>
              Grounded in Government of India data
            </span>
          </div>

          <h1 className="mt-6 text-4xl leading-[1.08] sm:text-5xl lg:text-6xl"
          >
            आपकी मंडी का सही भाव,
            <span className="text-gradient mt-1 block">आपकी अपनी भाषा में</span>
          </h1>

          <p className="muted mt-6 max-w-xl text-base sm:text-lg">
            Ask what your crop is fetching at nearby mandis, who is buying, and whether this is
            the week to sell. Every answer is traced back to official price records — and shows
            you the working.
          </p>

          <div className="mt-8 flex flex-wrap gap-3">
            <Link to="/chat" className="btn-primary px-5 py-3 text-base">
              सवाल पूछें · Ask the assistant
              <span aria-hidden="true">→</span>
            </Link>
            <Link to="/dashboard" className="btn-ghost px-5 py-3 text-base">
              मंडी भाव देखें · Live prices
            </Link>
          </div>

          <p className="muted mt-6 text-xs">
            No account needed to ask. Runs without any API key.
          </p>
        </div>

        {/* A worked example rather than a screenshot: it shows the real shape of
            an answer, including the confidence and the provenance line. */}
        <div className="relative"
        >
          <div className="glass relative overflow-hidden p-5 sm:p-6">
            <div className="mb-4 flex items-center gap-2">
              <span className="h-2.5 w-2.5 rounded-full bg-red-400/70" />
              <span className="h-2.5 w-2.5 rounded-full bg-harvest-300" />
              <span className="h-2.5 w-2.5 rounded-full bg-mandi-400" />
              <span className="muted ml-2 text-2xs uppercase tracking-wider">Example</span>
            </div>

            <div className="flex justify-end">
              <p
                lang="hi"
                className="max-w-[85%] rounded-2xl rounded-br-md bg-mandi-600 px-4 py-2.5 text-sm text-white shadow-sm"
              >
                क्या मुझे अभी प्याज बेच देना चाहिए?
              </p>
            </div>

            <div className="mt-3 rounded-2xl rounded-bl-md border bg-[rgb(var(--surface))] p-4">
              <p lang="hi" className="text-sm leading-relaxed">
                सहेबगंज मंडी में प्याज का भाव लगभग{' '}
                <strong className="text-mandi-700 dark:text-mandi-300">2,286 रुपये</strong> प्रति
                क्विंटल है — आसपास सबसे अच्छा रेट। भाव घट रहा है और तेज़ बारिश से आवक रुक सकती है,
                इसलिए अभी बेच देना ठीक रहेगा।
              </p>

              <div className="mt-4 flex flex-wrap items-center gap-2">
                <span className="chip-mandi">बेचें · SELL</span>
                <span className="chip-neutral">68% confidence</span>
                <span className="chip-harvest">Partly verified</span>
              </div>
            </div>

            <p className="muted mt-4 flex items-center gap-1.5 text-2xs">
              <span className="text-mandi-600" aria-hidden="true">✓</span>
              Traced to Agmarknet · full reasoning shown in the AI panel
            </p>
          </div>

          <div
            aria-hidden="true"
            className="absolute -right-6 -top-6 -z-10 h-32 w-32 rounded-full bg-mandi-400/20 blur-2xl"
          />
        </div>
      </div>
    </section>
  );
}

function Stats() {
  return (
    <section className="container-page pb-4">
      <dl className="grid grid-cols-2 gap-3 sm:gap-4 lg:grid-cols-4"
      >
        {STATS.map((stat, index) => (
          <div key={stat.en} className="surface card-hover p-5 text-center animate-fade-up" style={{ animationDelay: `${index * 60}ms` }}>
            <dt className="sr-only">{stat.en}</dt>
            <dd>
              <p className="text-gradient text-3xl font-bold sm:text-4xl">{stat.value}</p>
              <p className="mt-1.5 text-sm font-medium">{stat.en}</p>
              <p lang="hi" className="muted text-xs">
                {stat.hi}
              </p>
            </dd>
          </div>
        ))}
      </dl>
    </section>
  );
}

function Features() {
  return (
    <section className="container-page py-20">
      <div>
        <p className="eyebrow">
          What it does
        </p>
        <h2 className="mt-2 text-3xl sm:text-4xl">
          यह सहायक क्या करता है
        </h2>
        <p className="muted mt-3 max-w-2xl">
          Built around one rule: the assistant may reason, explain and recommend, but it may
          never invent a number.
        </p>

        <div className="mt-10 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {FEATURES.map((feature, index) => (
            <article key={feature.en} className="surface card-hover group p-6 animate-fade-up" style={{ animationDelay: `${index * 60}ms` }}>
              <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-mandi-50 text-xl transition-transform duration-300 ease-smooth group-hover:scale-110 dark:bg-mandi-500/10">
                <span aria-hidden="true">{feature.icon}</span>
              </div>
              <h3 className="mt-4 text-base">{feature.en}</h3>
              <p lang="hi" className="text-sm text-mandi-700 dark:text-mandi-400">
                {feature.hi}
              </p>
              <p className="muted mt-3 text-sm leading-relaxed">{feature.body}</p>
            </article>
          ))}
        </div>
      </div>
    </section>
  );
}

function HowItWorks() {
  return (
    <section className="border-y bg-[rgb(var(--surface-muted))] py-20">
      <div className="container-page">
        <div>
          <p className="eyebrow">
            How it works
          </p>
          <h2 className="mt-2 text-3xl sm:text-4xl">
            सवाल से जवाब तक
          </h2>

          <div className="mt-10 grid gap-6 md:grid-cols-2 lg:grid-cols-4">
            {STEPS.map((step, index) => (
              <div key={step.n} className="animate-fade-up" style={{ animationDelay: `${index * 60}ms` }}>
                <span className="text-4xl font-bold text-mandi-600/20 dark:text-mandi-400/25">
                  {step.n}
                </span>
                <h3 className="mt-1 text-base">{step.en}</h3>
                <p lang="hi" className="text-sm text-mandi-700 dark:text-mandi-400">
                  {step.hi}
                </p>
                <p className="muted mt-2 text-sm leading-relaxed">{step.body}</p>
              </div>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}

function Trust() {
  return (
    <section className="container-page py-20">
      <div className="surface overflow-hidden"
      >
        <div className="grid gap-8 p-8 md:grid-cols-2 md:p-12">
          <div>
            <p className="eyebrow">Why you can act on it</p>
            <h2 className="mt-2 text-2xl sm:text-3xl">Nothing here is a confident guess</h2>
            <p className="muted mt-4 text-sm leading-relaxed">
              A wrong mandi price is not a harmless error — a farmer travels on it. So every
              figure in an answer must resolve to a government record, the trend model, the
              forecast, or arithmetic over those. A number that resolves to nothing is deleted
              from the answer before you ever see it.
            </p>
            <p className="muted mt-3 text-sm leading-relaxed">
              When the live government feed cannot be reached, the system says so plainly rather
              than passing reference data off as today&apos;s rate.
            </p>
          </div>

          <ul className="space-y-3">
            {[
              ['Verified', 'Traced to a live Agmarknet record', 'chip-mandi'],
              [
                'Partly verified',
                'From the trend model, the forecast, or arithmetic over records',
                'chip-harvest',
              ],
              ['Not enough evidence', 'Removed from the answer entirely', 'chip-danger'],
            ].map(([label, detail, tone]) => (
              <li key={label} className="flex items-start gap-3 rounded-xl border p-4">
                <span className={`${tone} shrink-0`}>{label}</span>
                <span className="muted text-sm">{detail}</span>
              </li>
            ))}
          </ul>
        </div>
      </div>
    </section>
  );
}

function CallToAction() {
  return (
    <section className="container-page pb-24">
      <div className="relative overflow-hidden rounded-4xl bg-gradient-to-br from-mandi-600 to-mandi-800 px-8 py-14 text-center text-white sm:px-12"
      >
        <div
          aria-hidden="true"
          className="pointer-events-none absolute inset-0 opacity-25"
          style={{
            backgroundImage:
              'radial-gradient(28rem 14rem at 20% 0%, #fff, transparent 60%), radial-gradient(24rem 12rem at 85% 100%, #fff, transparent 60%)',
          }}
        />
        <div className="relative">
          <h2 className="text-3xl sm:text-4xl">आज का भाव पूछकर देखिए</h2>
          <p className="mx-auto mt-3 max-w-xl text-sm text-mandi-50/90">
            Ask a question in any of seven languages and watch every step the assistant takes.
          </p>
          <Link
            to="/chat"
            className="btn mt-8 bg-white px-6 py-3 text-base text-mandi-800 hover:bg-mandi-50 active:scale-[0.98]"
          >
            शुरू करें · Start asking
            <span aria-hidden="true">→</span>
          </Link>
        </div>
      </div>
    </section>
  );
}

export default function HomePage() {
  return (
    <>
      <Hero />
      <Stats />
      <Features />
      <HowItWorks />
      <Trust />
      <CallToAction />
    </>
  );
}
