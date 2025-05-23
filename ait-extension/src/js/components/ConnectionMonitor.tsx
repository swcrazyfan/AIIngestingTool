import React, { useEffect, useState } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { connectionManager } from '../api/client';

/**
 * ConnectionMonitor component that monitors connection status and handles reconnection
 * authentication verification. Shows a login prompt when connection is restored but
 * authentication has expired.
 */
const ConnectionMonitor: React.FC = () => {
  const { authStatus, isConnected, checkAuth } = useAuth();
  const [showReconnectAlert, setShowReconnectAlert] = useState(false);
  const [showLoginPrompt, setShowLoginPrompt] = useState(false);
  const [reconnectAttempts, setReconnectAttempts] = useState(0);

  // Monitor connection status
  useEffect(() => {
    let reconnectTimer: NodeJS.Timeout | null = null;

    // When disconnected, show alert and attempt to reconnect
    if (!isConnected) {
      setShowReconnectAlert(true);
      
      // Attempt to reconnect every 5 seconds
      reconnectTimer = setInterval(() => {
        setReconnectAttempts(prev => prev + 1);
        connectionManager.checkConnection();
      }, 5000);
    } else {
      // When reconnected, hide alert and clear timer
      setShowReconnectAlert(false);
      setReconnectAttempts(0);
      
      if (reconnectTimer) {
        clearInterval(reconnectTimer);
      }
    }

    return () => {
      if (reconnectTimer) {
        clearInterval(reconnectTimer);
      }
    };
  }, [isConnected]);

  // Show login prompt when connected but not authenticated
  useEffect(() => {
    if (isConnected && authStatus && !authStatus.authenticated) {
      setShowLoginPrompt(true);
    } else {
      setShowLoginPrompt(false);
    }
  }, [isConnected, authStatus]);

  // Handle manual reconnect attempt
  const handleManualReconnect = () => {
    connectionManager.checkConnection();
  };

  return (
    <>
      {/* Connection Lost Alert */}
      {showReconnectAlert && (
        <div className="connection-alert error">
          <div className="alert-content">
            <h4>Connection Lost</h4>
            <p>Lost connection to the API server. Attempting to reconnect... (Attempt {reconnectAttempts})</p>
          </div>
          <div className="alert-actions">
            <button className="btn btn-primary" onClick={handleManualReconnect}>
              Reconnect Now
            </button>
          </div>
        </div>
      )}

      {/* Login Prompt Modal */}
      {showLoginPrompt && (
        <div className="modal-overlay">
          <div className="modal-content">
            <div className="modal-header">
              <h2>Session Expired</h2>
            </div>
            <div className="modal-body">
              <div className="login-prompt-content">
                <p>Your session has expired or is no longer valid. Please log in again to continue.</p>
                <div className="login-prompt-actions">
                  <button 
                    className="btn btn-primary"
                    onClick={() => window.location.reload()} 
                  >
                    Go to Login
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </>
  );
};

export default ConnectionMonitor;
