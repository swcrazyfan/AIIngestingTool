import React, { createContext, useContext, useState, useEffect, ReactNode, useCallback } from 'react';
import { authApi, connectionManager } from '../api/client';
import { AuthStatus } from '../types/api'; 
import { clearCache } from '../components/shared/ThumbnailCache';

interface AuthContextType {
  authStatus: AuthStatus | null;
  loading: boolean;
  isConnected: boolean;
  requiresReLogin: boolean;
  isGuestMode: boolean;
  login: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  checkAuth: () => Promise<void>;
  handleAuthError: () => void;
  setGuestMode: (guest: boolean) => void;
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
  // Since authentication is disabled, start in local authenticated mode
  const [authStatus, setAuthStatus] = useState<AuthStatus | null>({
    authenticated: true,
    user: {
      id: 'local-user',
      email: 'local@localhost',
      profile_type: 'local'
    }
  });
  const [loading, setLoading] = useState(false); // No loading since we start authenticated
  const [isConnected, setIsConnected] = useState(true);
  const [requiresReLogin, setRequiresReLogin] = useState(false);
  const [isGuestMode, setIsGuestMode] = useState(false); // Not guest mode, but local mode

  const handleAuthError = useCallback(() => {
    // Since auth is disabled, this shouldn't really happen, but keep for compatibility
    console.warn('Authentication error detected, but auth is disabled - continuing in local mode.');
    setRequiresReLogin(false); // Don't require re-login since auth is disabled
  }, []);

  const checkAuth = useCallback(async () => {
    try {
      setLoading(true);
      const status = await authApi.getStatus(); // This will return fake success
      // Always set to authenticated since auth is disabled
      setAuthStatus({
        authenticated: true,
        user: {
          id: 'local-user',
          email: 'local@localhost',
          profile_type: 'local'
        }
      });
      setRequiresReLogin(false);
    } catch (error) {
      console.error('checkAuth failed:', error);
      // Even if check fails, keep authenticated since auth is disabled
      setAuthStatus({
        authenticated: true,
        user: {
          id: 'local-user',
          email: 'local@localhost',
          profile_type: 'local'
        }
      });
    } finally {
      setLoading(false);
    }
  }, []);

  const login = async (email: string, password: string) => {
    // Since auth is disabled, always succeed
    const response = await authApi.login(email, password); // Returns fake success
    setAuthStatus({
      authenticated: true,
      user: {
        id: 'local-user',
        email: email || 'local@localhost',
        profile_type: 'local'
      }
    });
    setRequiresReLogin(false);
  };

  const logout = async () => {
    setLoading(true);
    try {
      await authApi.logout(); // Returns fake success
      // For local mode, don't actually log out - just refresh the status
      setAuthStatus({
        authenticated: true,
        user: {
          id: 'local-user',
          email: 'local@localhost',
          profile_type: 'local'
        }
      });
      setIsGuestMode(false);
      // Clear the thumbnail cache when logging out
      clearCache();
      localStorage.removeItem('reconnectAfterAuth');
    } catch (error) {
      console.error('Logout failed:', error);
    } finally {
      setLoading(false);
    }
  };

  const setGuestMode = (guest: boolean) => {
    if (guest) {
      // Create mock auth status for guest mode
      setAuthStatus({
        authenticated: true,
        user: {
          id: 'guest',
          email: 'guest@example.com',
          profile_type: 'guest'
        }
      });
      setIsGuestMode(true);
      setLoading(false);
    } else {
      // Return to local mode
      setAuthStatus({
        authenticated: true,
        user: {
          id: 'local-user',
          email: 'local@localhost',
          profile_type: 'local'
        }
      });
      setIsGuestMode(false);
    }
  };

  useEffect(() => {
    const handleConnectionChange = async (connected: boolean) => {
      setIsConnected(connected);
      
      if (connected) {
        console.log('Reconnected to server, checking status.');
        await checkAuth();
      }
    };
    
    connectionManager.addConnectionListener(handleConnectionChange);
    
    // Initial check - but since auth is disabled, this will just confirm local mode
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
    <AuthContext.Provider value={{ authStatus, loading, isConnected, login, logout, checkAuth, requiresReLogin, handleAuthError, isGuestMode, setGuestMode }}>
      {children}
    </AuthContext.Provider>
  );
};
