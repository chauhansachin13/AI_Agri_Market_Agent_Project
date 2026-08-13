import { motion } from 'framer-motion';
import { Link } from 'react-router-dom';

const STATS = [
  { value: '3,500+', en: 'Mandis covered', hi: 'मंडियाँ' },
  { value: '15', en: 'Crops supported', hi: 'फसलें' },
  { value: '7', en: 'Languages', hi: 'भाषाएँ' },
  { value: '12', en: 'AI agents', hi: 'एआई एजेंट' },
];

const FEATURES = [
  {
    icon: '📊',
    en: 'Live government prices',
    hi: 'सरकारी ताज़ा भाव',
    body: 'Every price comes from Agmarknet and eNAM. The assistant is never allowed to invent a number.',
    bodyHi: 'हर भाव सरकारी स्रोत से। सहायक अपने मन से कोई रेट नहीं बताता।',
  },
  {
    icon: '🗣️',
    en: 'Ask in your own words',
    hi: 'अपनी भाषा में पूछें',
    body: 'Hindi, Bhojpuri, Maithili, Marathi, Bengali, Tamil or English — typed or spoken. The answer comes back in the language you asked in.',
    bodyHi: 'हिंदी, भोजपुरी, मैथिली, मराठी, बांग्ला, तमिल या अंग्रेज़ी — बोलकर या लिखकर पूछें। जवाब उसी भाषा में मिलेगा।',
  },
  {
    icon: '🧭',
    en: 'Sell or wait, with reasons',
    hi: 'बेचें या रुकें — कारण के साथ',
    body: 'Trend analysis across nearby mandis gives a clear recommendation and shows the working.',
    bodyHi: 'आसपास की मंडियों का रुझान देखकर साफ़ सलाह, और वजह भी दिखती है।',
  },
  {
    icon: '🔍',
    en: 'Every step is visible',
    hi: 'हर कदम दिखता है',
    body: 'The reasoning panel shows what the assistant checked and what it could verify.',
    bodyHi: 'सहायक ने क्या देखा और क्या पक्का किया — सब पैनल में दिखता है।',
  },
  {
    icon: '📈',
    en: 'A forecast, with its error rate',
    hi: 'आगे का अनुमान, सच्चाई के साथ',
    body: 'A trained model projects the week ahead and reports how well it actually scored.',
    bodyHi: 'आगे हफ़्ते भर का अनुमान, और यह भी कि अनुमान कितना सही बैठता रहा है।',
  },
  {
    icon: '🤝',
    en: 'Sell directly to buyers',
    hi: 'सीधे खरीदार को बेचें',
    body: 'List your produce, receive offers, and compare each one against the mandi rate.',
    bodyHi: 'अपनी फसल डालें, ऑफर पाएँ, और हर ऑफर को मंडी भाव से मिलाकर देखें।',
  },
];

export default function HomePage() {
  return (
    <div className="mx-auto max-w-7xl px-4">
      <section className="grid items-center gap-10 py-14 md:grid-cols-2 md:py-20">
        <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.5 }}>
          <span className="chip bg-mandi-100 text-mandi-800 dark:bg-white/10 dark:text-mandi-200">
            Grounded in Government of India data
          </span>
          <h1 className="mt-4 text-4xl font-bold leading-tight md:text-5xl">
            आपकी मंडी का सही भाव,
            <span className="block text-mandi-700 dark:text-mandi-300">आपकी अपनी भाषा में</span>
          </h1>
          <p className="mt-4 max-w-xl opacity-80">
            Ask what your crop is fetching at nearby mandis, who is buying, and whether this is
            the week to sell. Every answer is traced back to official price records.
          </p>
          <div className="mt-6 flex flex-wrap gap-3">
            <Link to="/chat" className="btn-primary">
              सवाल पूछें · Ask the assistant
            </Link>
            <Link to="/dashboard" className="btn-ghost">
              मंडी भाव देखें · View prices
            </Link>
          </div>
        </motion.div>

        <motion.div
          initial={{ opacity: 0, scale: 0.96 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ duration: 0.5, delay: 0.15 }}
          className="glass p-6"
        >
          <p className="text-xs uppercase tracking-wide opacity-60">Example</p>
          <p lang="hi" className="mt-2 rounded-xl bg-mandi-600 px-4 py-2.5 text-sm text-white">
            बिहार में टमाटर का क्या रेट है?
          </p>
          <p lang="hi" className="mt-3 rounded-xl bg-white/70 px-4 py-3 text-sm dark:bg-white/10">
            पटना सिटी मंडी में टमाटर का भाव लगभग 1,850 रुपये प्रति क्विंटल है — आसपास में सबसे
            अच्छा रेट। पिछले हफ़्ते से भाव थोड़ा बढ़ा है, इसलिए अभी बेचना ठीक रहेगा।
          </p>
          <p className="mt-3 text-xs opacity-60">
            ✓ Verified against Agmarknet · reasoning shown in the AI panel
          </p>
        </motion.div>
      </section>

      <section className="grid grid-cols-2 gap-4 md:grid-cols-4">
        {STATS.map((stat, index) => (
          <motion.div
            key={stat.en}
            initial={{ opacity: 0, y: 12 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ delay: index * 0.08 }}
            className="glass p-5 text-center"
          >
            <p className="text-3xl font-bold text-mandi-700 dark:text-mandi-300">{stat.value}</p>
            <p className="mt-1 text-sm opacity-80">{stat.en}</p>
            <p lang="hi" className="text-xs opacity-60">
              {stat.hi}
            </p>
          </motion.div>
        ))}
      </section>

      <section className="mt-16">
        <h2 className="text-2xl font-bold">यह सहायक क्या करता है</h2>
        <p className="mt-1 opacity-70">What this assistant does</p>
        <div className="mt-6 grid gap-4 md:grid-cols-2">
          {FEATURES.map((feature, index) => (
            <motion.article
              key={feature.en}
              initial={{ opacity: 0, y: 12 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ delay: index * 0.06 }}
              className="glass p-5"
            >
              <p className="text-2xl" aria-hidden="true">
                {feature.icon}
              </p>
              <h3 className="mt-2 font-semibold">{feature.en}</h3>
              <p lang="hi" className="text-sm text-mandi-700 dark:text-mandi-300">
                {feature.hi}
              </p>
              <p className="mt-2 text-sm opacity-75">{feature.body}</p>
              <p lang="hi" className="mt-1 text-sm opacity-60">
                {feature.bodyHi}
              </p>
            </motion.article>
          ))}
        </div>
      </section>
    </div>
  );
}
