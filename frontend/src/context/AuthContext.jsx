import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';

import * as api from '../services/api.js';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

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
      language: user?.preferredLanguage || 'hi',
      signIn,
      signUp,
      signOut,
      updateProfile,
    }),
    [user, loading, signIn, signUp, signOut, updateProfile],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) throw new Error('useAuth must be used inside an AuthProvider');
  return context;
}
