import { AnimatePresence, motion } from 'framer-motion';
import { useEffect, useRef, useState } from 'react';

import { useAuth } from '../context/AuthContext.jsx';
import { useLocation } from '../hooks/useLocation.js';
import { useQuery } from '../context/QueryContext.jsx';
import { useVoice } from '../hooks/useVoice.js';
import ConfidenceBar from './ConfidenceBar.jsx';

// Recognition tags per language. Bhojpuri and Maithili have no dedicated
// recogniser, so they borrow Hindi — imperfect, and better than nothing.
const SPEECH_TAGS = {
  en: 'en-IN', hi: 'hi-IN', bho: 'hi-IN', mai: 'hi-IN',
  mr: 'mr-IN', bn: 'bn-IN', ta: 'ta-IN',
};

const SUGGESTIONS = [
  { hi: 'बिहार में टमाटर का क्या रेट है?', en: 'What is the tomato price in Bihar?' },
  { hi: 'आसपास गेहूं कौन खरीद रहा है?', en: 'Who is buying wheat nearby?' },
  { hi: 'क्या मुझे अभी प्याज बेच देना चाहिए?', en: 'Should I sell onions now?' },
  { hi: 'पिछले हफ्ते से आलू का भाव बढ़ा है?', en: 'Has potato price risen from last week?' },
];

function AgentBubble({ response, language, onSpeak }) {
  // Prefer the answer the agent actually produced for this language; fall back
  // to the schema's Hindi/English pair when the language has no dedicated text.
  const answer =
    response.answers?.[language] ||
    response.answer ||
    (language === 'en' ? response.english_answer : response.hindi_answer);
  const alternate = language === 'en' ? response.hindi_answer : response.english_answer;
  const [showAlternate, setShowAlternate] = useState(false);

  return (
    <div className="glass max-w-[85%] p-4">
      <p lang={language} className="whitespace-pre-wrap text-sm leading-relaxed">
        {answer}
      </p>

      {alternate && (
        <>
          <button
            type="button"
            onClick={() => setShowAlternate((value) => !value)}
            className="mt-2 text-xs font-medium text-mandi-700 underline-offset-2 hover:underline dark:text-mandi-300"
          >
            {showAlternate
              ? 'Hide translation'
              : language === 'en'
                ? 'हिंदी में देखें'
                : 'Show in English'}
          </button>
          <AnimatePresence>
            {showAlternate && (
              <motion.p
                lang={language === 'en' ? 'hi' : 'en'}
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: 'auto' }}
                exit={{ opacity: 0, height: 0 }}
                className="mt-2 border-t border-black/10 pt-2 text-sm opacity-80 dark:border-white/10"
              >
                {alternate}
              </motion.p>
            )}
          </AnimatePresence>
        </>
      )}

      <footer className="mt-3 flex flex-wrap items-center gap-3">
        <ConfidenceBar score={response.confidence_score} compact />
        {response.prediction && (
          <span
            className={`chip ${
              response.prediction.recommendation === 'SELL'
                ? 'bg-mandi-600 text-white'
                : 'bg-amber-500 text-white'
            }`}
          >
            {response.prediction.recommendation === 'SELL' ? 'बेचें · SELL' : 'रुकें · WAIT'}
          </span>
        )}
        <button
          type="button"
          onClick={() => onSpeak(answer, SPEECH_TAGS[language] || 'hi-IN')}
          className="ml-auto text-xs opacity-70 hover:opacity-100"
          aria-label="Listen to this answer"
        >
          🔊 सुनें
        </button>
      </footer>
    </div>
  );
}

export default function ChatBot() {
  const { ask, messages, pending, reset } = useQuery();
  const { language } = useAuth();
  const voice = useVoice({ lang: SPEECH_TAGS[language] || 'hi-IN' });
  const geo = useLocation();
  const [draft, setDraft] = useState('');
  const endRef = useRef(null);

  // Voice transcription feeds the same input box the keyboard does, so the
  // farmer can correct a misheard word before sending.
  useEffect(() => {
    if (voice.transcript) setDraft(voice.transcript);
  }, [voice.transcript]);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' });
  }, [messages.length, pending]);

  const submit = async (event) => {
    event?.preventDefault();
    const text = draft.trim();
    if (!text || pending) return;
    setDraft('');
    voice.reset();
    await ask(text, {
      ...(geo.coordinates ? { coordinates: geo.coordinates } : {}),
      languageOverride: language,
    });
  };

  return (
    <section className="flex h-full flex-col" data-testid="chatbot">
      <div className="flex-1 space-y-4 overflow-y-auto p-1" role="log" aria-live="polite">
        {messages.length === 0 && (
          <div className="glass p-5">
            <h2 className="text-lg font-semibold">नमस्ते! मैं आपका मंडी सहायक हूँ।</h2>
            <p className="mt-1 text-sm opacity-70">
              Ask about mandi prices, buyers, or whether to sell — in Hindi or English.
            </p>
            <ul className="mt-4 grid gap-2 sm:grid-cols-2">
              {SUGGESTIONS.map((suggestion) => (
                <li key={suggestion.en}>
                  <button
                    type="button"
                    onClick={() => setDraft(language === 'en' ? suggestion.en : suggestion.hi)}
                    className="w-full rounded-xl border border-mandi-600/20 px-3 py-2 text-left text-sm hover:bg-mandi-50 dark:hover:bg-white/5"
                  >
                    {language === 'en' ? suggestion.en : suggestion.hi}
                  </button>
                </li>
              ))}
            </ul>
          </div>
        )}

        {messages.map((message, index) => {
          if (message.role === 'farmer') {
            return (
              <div key={index} className="flex justify-end">
                <p className="max-w-[80%] rounded-2xl bg-mandi-600 px-4 py-2.5 text-sm text-white">
                  {message.text}
                </p>
              </div>
            );
          }
          if (message.role === 'error') {
            return (
              <div key={index} className="flex justify-start">
                <p className="max-w-[85%] rounded-2xl bg-red-100 px-4 py-2.5 text-sm text-red-900 dark:bg-red-900/30 dark:text-red-200">
                  {message.text}
                </p>
              </div>
            );
          }
          return (
            <div key={index} className="flex justify-start">
              <AgentBubble response={message.response} language={language} onSpeak={voice.speak} />
            </div>
          );
        })}

        {pending && (
          <div className="flex items-center gap-2 px-2 text-sm opacity-70" data-testid="thinking">
            {[0, 1, 2].map((dot) => (
              <motion.span
                key={dot}
                className="h-2 w-2 rounded-full bg-mandi-600"
                animate={{ opacity: [0.3, 1, 0.3] }}
                transition={{ duration: 1.2, repeat: Infinity, delay: dot * 0.2 }}
              />
            ))}
            <span>सोच रहा हूँ…</span>
          </div>
        )}
        <div ref={endRef} />
      </div>

      <form onSubmit={submit} className="mt-3 flex items-end gap-2">
        <label className="sr-only" htmlFor="chat-input">
          Ask a question about mandi prices
        </label>
        <input
          id="chat-input"
          className="field"
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          placeholder={language === 'en' ? 'Ask about mandi prices…' : 'मंडी भाव पूछिए…'}
          autoComplete="off"
          disabled={pending}
        />

        {voice.supported && (
          <button
            type="button"
            onClick={voice.listening ? voice.stop : voice.start}
            className={`btn ${voice.listening ? 'bg-red-600 text-white' : 'btn-ghost'}`}
            aria-pressed={voice.listening}
            aria-label={voice.listening ? 'Stop listening' : 'Speak your question'}
            title={voice.listening ? 'Stop' : 'Speak'}
          >
            {voice.listening ? '⏹' : '🎤'}
          </button>
        )}

        <button type="submit" className="btn-primary" disabled={pending || !draft.trim()}>
          {pending ? '…' : 'भेजें'}
        </button>
      </form>

      <div className="mt-2 flex flex-wrap items-center gap-3 text-xs opacity-60">
        {geo.supported && (
          <button type="button" onClick={geo.request} className="hover:opacity-100">
            📍{' '}
            {geo.status === 'ready'
              ? 'Location shared'
              : geo.status === 'locating'
                ? 'Locating…'
                : 'Use my location'}
          </button>
        )}
        {geo.status === 'denied' && (
          <span>Location declined — name your district in the question instead.</span>
        )}
        {voice.error && <span>Voice input failed: {voice.error}</span>}
        {messages.length > 0 && (
          <button type="button" onClick={reset} className="ml-auto hover:opacity-100">
            Clear chat
          </button>
        )}
      </div>
    </section>
  );
}
