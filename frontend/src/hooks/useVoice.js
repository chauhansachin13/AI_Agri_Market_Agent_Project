import { useCallback, useEffect, useMemo, useRef, useState } from 'react';

/**
 * Voice input and output via the browser Web Speech API (§4.8).
 *
 * Recognition runs with lang='hi-IN' by default, matching the report. Section
 * 6.2 records that accuracy degrades on Bhojpuri- and Maithili-accented Hindi
 * and in noisy field conditions, so the hook always exposes `supported` and
 * surfaces errors rather than failing silently — the UI must keep the typed
 * input path available.
 */
export function useVoice({ lang = 'hi-IN' } = {}) {
  const [listening, setListening] = useState(false);
  const [transcript, setTranscript] = useState('');
  const [error, setError] = useState(null);
  const [speaking, setSpeaking] = useState(false);
  const recognitionRef = useRef(null);

  const SpeechRecognition = useMemo(() => {
    if (typeof window === 'undefined') return null;
    return window.SpeechRecognition || window.webkitSpeechRecognition || null;
  }, []);

  const supported = Boolean(SpeechRecognition);
  const speechSupported =
    typeof window !== 'undefined' && typeof window.speechSynthesis !== 'undefined';

  useEffect(() => {
    if (!SpeechRecognition) return undefined;

    const recognition = new SpeechRecognition();
    recognition.lang = lang;
    recognition.continuous = false;
    recognition.interimResults = true;
    recognition.maxAlternatives = 1;

    recognition.onresult = (event) => {
      const text = Array.from(event.results)
        .map((result) => result[0].transcript)
        .join(' ')
        .trim();
      setTranscript(text);
    };
    recognition.onerror = (event) => {
      setError(event.error || 'speech recognition failed');
      setListening(false);
    };
    recognition.onend = () => setListening(false);

    recognitionRef.current = recognition;
    return () => {
      recognition.onresult = null;
      recognition.onerror = null;
      recognition.onend = null;
      try {
        recognition.abort();
      } catch {
        /* already stopped */
      }
    };
  }, [SpeechRecognition, lang]);

  const start = useCallback(() => {
    if (!recognitionRef.current || listening) return;
    setTranscript('');
    setError(null);
    try {
      recognitionRef.current.start();
      setListening(true);
    } catch (caught) {
      setError(caught.message);
    }
  }, [listening]);

  const stop = useCallback(() => {
    if (!recognitionRef.current) return;
    try {
      recognitionRef.current.stop();
    } catch {
      /* already stopped */
    }
    setListening(false);
  }, []);

  const speak = useCallback(
    (text, speakLang = lang) => {
      if (!speechSupported || !text) return;
      window.speechSynthesis.cancel(); // never let two answers talk over each other
      const utterance = new SpeechSynthesisUtterance(text);
      utterance.lang = speakLang;
      utterance.rate = 0.95; // a touch slower reads more clearly in Devanagari
      utterance.onstart = () => setSpeaking(true);
      utterance.onend = () => setSpeaking(false);
      utterance.onerror = () => setSpeaking(false);
      window.speechSynthesis.speak(utterance);
    },
    [lang, speechSupported],
  );

  const stopSpeaking = useCallback(() => {
    if (speechSupported) window.speechSynthesis.cancel();
    setSpeaking(false);
  }, [speechSupported]);

  return {
    supported,
    speechSupported,
    listening,
    transcript,
    error,
    speaking,
    start,
    stop,
    speak,
    stopSpeaking,
    reset: () => setTranscript(''),
  };
}
