import React, { createContext, useContext, useState, useEffect, ReactNode, useCallback } from 'react';
import { authApi, connectionManager } from '../api/client';
import { AuthStatus } from '../types/api'; 
import { clearCache } from '../components/shared/ThumbnailCache';

interface AuthContextType {
  authStatus: AuthStatus | null;
  loading: boolean;
  isConnected: boolean;
  requiresReLogin: boolean;
  login: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  checkAuth: () => Promise<void>;
  handleAuthError: () => void;
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
  const [isConnected, setIsConnected] = useState(true);
  const [requiresReLogin, setRequiresReLogin] = useState(false);

  const handleAuthError = useCallback(() => {
    console.warn('Authentication error detected, forcing re-login.');
    setAuthStatus({ authenticated: false, user: undefined }); 
    setRequiresReLogin(true);
  }, []);

  const checkAuth = useCallback(async () => {
    try {
      setLoading(true);
      const status = await authApi.getStatus();
      setAuthStatus(status);
      if (!status.authenticated) {
        handleAuthError(); 
      } else {
        setRequiresReLogin(false); 
      }
    } catch (error) {
      console.error('checkAuth failed:', error);
      handleAuthError(); 
    } finally {
      setLoading(false);
    }
  }, [handleAuthError]);

  const login = async (email: string, password: string) => {
    const response = await authApi.login(email, password);
    if (response.success) {
      await checkAuth(); 
    } else {
      setRequiresReLogin(true); 
      throw new Error(response.error || 'Login failed');
    }
  };

  const logout = async () => {
    setLoading(true);
    try {
      await authApi.logout();
      setAuthStatus(null);
      // Clear the thumbnail cache when logging out
      clearCache();
      localStorage.removeItem('reconnectAfterAuth');
    } catch (error) {
      console.error('Logout failed:', error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    const handleConnectionChange = async (connected: boolean) => {
      setIsConnected(connected);
      
      if (connected) {
        console.log('Reconnected to server, re-checking authentication.');
        await checkAuth();
      }
    };
    
    connectionManager.addConnectionListener(handleConnectionChange);
    
    checkAuth();
    
    return () => {
      connectionManager.removeConnectionListener(handleConnectionChange);
    };
  }, [checkAuth]); 

  useEffect(() => {
    if (connectionManager.setAuthErrorCallback) {
      connectionManager.setAuthErrorCallback(handleAuthError);
    }
    return () => {
      if (connectionManager.setAuthErrorCallback) {
        connectionManager.setAuthErrorCallback(null);
      }
    };
  }, [handleAuthError]);

  return (
    <AuthContext.Provider value={{ authStatus, loading, isConnected, login, logout, checkAuth, requiresReLogin, handleAuthError }}>
      {children}
    </AuthContext.Provider>
  );
};
