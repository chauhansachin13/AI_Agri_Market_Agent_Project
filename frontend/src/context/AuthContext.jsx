import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';

import * as api from '../services/api.js';

const AuthContext = createContext(null);

const LANGUAGE_KEY = 'agri.language';

function storedLanguage() {
  try {
    return localStorage.getItem(LANGUAGE_KEY);
  } catch {
    return null;
  }
}

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  // Language is chosen before sign-in and must survive a reload, so it lives in
  // storage rather than only on the profile. §6.3 expands this well past hi/en.
  // 'auto' means: let the service detect the language of the question. A fixed
  // default would answer a Marathi speaker in Hindi just because they never
  // opened the picker.
  const [language, setLanguageState] = useState(() => storedLanguage() || 'auto');

  // Restore the session on first mount. A stored token may have expired while
  // the tab was closed, so it is validated against the server, not trusted.
  useEffect(() => {
    let cancelled = false;

    async function restore() {
      if (!api.tokenStore.get()) {
        setLoading(false);
        return;
      }
      try {
        const { user: profile } = await api.me();
        if (!cancelled) setUser(profile);
      } catch {
        api.tokenStore.set(null);
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    restore();
    return () => {
      cancelled = true;
    };
  }, []);

  const setLanguage = useCallback((code) => {
    setLanguageState(code);
    try {
      localStorage.setItem(LANGUAGE_KEY, code);
    } catch {
      /* non-fatal: the choice simply will not survive a reload */
    }
  }, []);

  const signIn = useCallback(async (credentials) => {
    const { user: profile, token } = await api.login(credentials);
    api.tokenStore.set(token);
    setUser(profile);
    return profile;
  }, []);

  const signUp = useCallback(async (payload) => {
    const { user: profile, token } = await api.register(payload);
    api.tokenStore.set(token);
    setUser(profile);
    return profile;
  }, []);

  const signOut = useCallback(() => {
    api.tokenStore.set(null);
    setUser(null);
  }, []);

  const updateProfile = useCallback(async (updates) => {
    const { user: profile } = await api.updateProfile(updates);
    setUser(profile);
    return profile;
  }, []);

  const value = useMemo(
    () => ({
      user,
      loading,
      isAuthenticated: Boolean(user),
      // An explicit pick always wins over the saved profile preference.
      language: storedLanguage() || user?.preferredLanguage || language,
      setLanguage,
      signIn,
      signUp,
      signOut,
      updateProfile,
    }),
    [user, loading, language, setLanguage, signIn, signUp, signOut, updateProfile],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) throw new Error('useAuth must be used inside an AuthProvider');
  return context;
}
