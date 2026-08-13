import { createContext, useCallback, useContext, useMemo, useRef, useState } from 'react';

import * as api from '../services/api.js';

const QueryContext = createContext(null);

const newSessionId = () =>
  `s_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 8)}`;

export function QueryProvider({ children }) {
  const [messages, setMessages] = useState([]);
  const [latest, setLatest] = useState(null);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState(null);
  const sessionId = useRef(newSessionId());

  const ask = useCallback(async (text, options = {}) => {
    const trimmed = String(text || '').trim();
    if (!trimmed) return null;

    const askedAt = new Date().toISOString();
    setMessages((current) => [...current, { role: 'farmer', text: trimmed, at: askedAt }]);
    setPending(true);
    setError(null);

    try {
      const response = await api.askAgent({
        query: trimmed,
        sessionId: sessionId.current,
        ...options,
      });
      setLatest(response);
      setMessages((current) => [
        ...current,
        { role: 'agent', response, at: new Date().toISOString() },
      ]);
      return response;
    } catch (caught) {
      setError(caught.message);
      setMessages((current) => [
        ...current,
        { role: 'error', text: caught.message, at: new Date().toISOString() },
      ]);
      return null;
    } finally {
      setPending(false);
    }
  }, []);

  const reset = useCallback(() => {
    setMessages([]);
    setLatest(null);
    setError(null);
    sessionId.current = newSessionId();
  }, []);

  const value = useMemo(
    () => ({ messages, latest, pending, error, ask, reset, sessionId: sessionId.current }),
    [messages, latest, pending, error, ask, reset],
  );

  return <QueryContext.Provider value={value}>{children}</QueryContext.Provider>;
}

export function useQuery() {
  const context = useContext(QueryContext);
  if (!context) throw new Error('useQuery must be used inside a QueryProvider');
  return context;
}
