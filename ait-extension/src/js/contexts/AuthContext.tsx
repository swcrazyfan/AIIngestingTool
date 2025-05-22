import React, { createContext, useContext, useState, useEffect, ReactNode } from 'react';
import { authApi } from '../api/client';
import { AuthStatus } from '../types/api';

interface AuthContextType {
  authStatus: AuthStatus | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  checkAuth: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};

export const AuthProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  const [authStatus, setAuthStatus] = useState<AuthStatus | null>(null);
  const [loading, setLoading] = useState(true);

  const checkAuth = async () => {
    try {
      const status = await authApi.getStatus();
      setAuthStatus(status);
    } catch (error) {
      setAuthStatus({ authenticated: false });
    } finally {
      setLoading(false);
    }
  };

  const login = async (email: string, password: string) => {
    const response = await authApi.login(email, password);
    if (response.success) {
      await checkAuth();
    } else {
      throw new Error(response.error || 'Login failed');
    }
  };

  const logout = async () => {
    await authApi.logout();
    setAuthStatus({ authenticated: false });
  };

  useEffect(() => {
    checkAuth();
  }, []);

  return (
    <AuthContext.Provider value={{ authStatus, loading, login, logout, checkAuth }}>
      {children}
    </AuthContext.Provider>
  );
};
