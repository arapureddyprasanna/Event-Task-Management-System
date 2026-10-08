import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import { getProfile, login as loginRequest, logout as logoutRequest } from '../api/auth';
import { clearSessionTokens, sessionKeys } from '../api/client';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [isLoading, setIsLoading] = useState(true);

  const clearAuth = useCallback(() => {
    clearSessionTokens();
    setUser(null);
  }, []);

  useEffect(() => {
    let active = true;
    const access = window.sessionStorage.getItem(sessionKeys.access);
    const refresh = window.sessionStorage.getItem(sessionKeys.refresh);
    const onExpired = () => clearAuth();
    window.addEventListener('gather:session-expired', onExpired);

    if (!access || !refresh) {
      clearAuth();
      setIsLoading(false);
    } else {
      getProfile()
        .then(({ data }) => { if (active) setUser(data); })
        .catch(() => { if (active) clearAuth(); })
        .finally(() => { if (active) setIsLoading(false); });
    }
    return () => {
      active = false;
      window.removeEventListener('gather:session-expired', onExpired);
    };
  }, [clearAuth]);

  const signIn = useCallback(async (credentials) => {
    const { data } = await loginRequest(credentials);
    window.sessionStorage.setItem(sessionKeys.access, data.access);
    window.sessionStorage.setItem(sessionKeys.refresh, data.refresh);
    const profile = await getProfile();
    setUser(profile.data);
    return profile.data;
  }, []);

  const signOut = useCallback(async () => {
    const refresh = window.sessionStorage.getItem(sessionKeys.refresh);
    try {
      if (refresh) await logoutRequest(refresh);
    } catch (error) {
      // Local sign-out must still complete when the server cannot be reached.
    } finally {
      clearAuth();
    }
  }, [clearAuth]);

  const refreshProfile = useCallback(async () => {
    const { data } = await getProfile();
    setUser(data);
    return data;
  }, []);

  const value = useMemo(() => ({
    user,
    isLoading,
    isAuthenticated: Boolean(user),
    isStaff: Boolean(user?.is_staff),
    isSuperuser: Boolean(user?.is_superuser),
    signIn,
    signOut,
    refreshProfile,
    clearAuth,
  }), [user, isLoading, signIn, signOut, refreshProfile, clearAuth]);

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) throw new Error('useAuth must be used inside AuthProvider');
  return context;
}
