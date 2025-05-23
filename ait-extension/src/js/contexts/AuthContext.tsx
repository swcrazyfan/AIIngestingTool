import React, { createContext, useContext, useState, useEffect, ReactNode, useCallback } from 'react';
import { authApi, connectionManager } from '../api/client';
import { AuthStatus } from '../types/api';

interface AuthContextType {
  authStatus: AuthStatus | null;
  loading: boolean;
  isConnected: boolean;
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
  const [isConnected, setIsConnected] = useState(true);

  const checkAuth = useCallback(async () => {
    try {
      setLoading(true);
      const status = await authApi.getStatus();
      setAuthStatus(status);
    } catch (error) {
      setAuthStatus({ authenticated: false });
    } finally {
      setLoading(false);
    }
  }, []);

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

  // Handle connection status changes
  useEffect(() => {
    const handleConnectionChange = async (connected: boolean) => {
      setIsConnected(connected);
      
      // If we're reconnecting, verify authentication status
      if (connected && authStatus?.authenticated) {
        // Check if the authentication is still valid
        try {
          const status = await authApi.getStatus();
          setAuthStatus(status);
          
          // If no longer authenticated, sign out
          if (!status.authenticated) {
            console.log('Session expired, logging out');
            // No need to call the API since we're already logged out on the server
            setAuthStatus({ authenticated: false });
          }
        } catch (error) {
          console.error('Failed to verify authentication on reconnect:', error);
          setAuthStatus({ authenticated: false });
        }
      }
    };
    
    // Add connection listener
    connectionManager.addConnectionListener(handleConnectionChange);
    
    // Initial auth check
    checkAuth();
    
    // Clean up
    return () => {
      connectionManager.removeConnectionListener(handleConnectionChange);
    };
  }, [checkAuth]);

  return (
    <AuthContext.Provider value={{ authStatus, loading, isConnected, login, logout, checkAuth }}>
      {children}
    </AuthContext.Provider>
  );
};
