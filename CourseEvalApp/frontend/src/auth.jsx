import { createContext, useCallback, useContext, useEffect, useState } from 'react';
import PropTypes from 'prop-types';
import { api, getToken, setToken, setUnauthorizedHandler } from './api';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(Boolean(getToken()));

  const signOut = useCallback(() => {
    setToken(null);
    setUser(null);
  }, []);

  const refresh = useCallback(async () => {
    if (!getToken()) { setUser(null); setLoading(false); return; }
    try {
      setUser(await api('/auth/me'));
    } catch {
      signOut();
    } finally {
      setLoading(false);
    }
  }, [signOut]);

  useEffect(() => {
    setUnauthorizedHandler(signOut);
    refresh();
  }, [refresh, signOut]);

  const signIn = async (email, password) => {
    const result = await api('/auth/login', { method: 'POST', body: { email, password } });
    setToken(result.access_token);
    setUser(result.user);
    return result.user;
  };

  return (
    <AuthContext.Provider value={{ user, loading, signIn, signOut, refresh, isAdmin: user?.role === 'admin' }}>
      {children}
    </AuthContext.Provider>
  );
}

AuthProvider.propTypes = { children: PropTypes.node };

// eslint-disable-next-line react-refresh/only-export-components
export const useAuth = () => useContext(AuthContext);
