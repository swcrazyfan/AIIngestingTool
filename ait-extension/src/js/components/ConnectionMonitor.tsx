import React, { useEffect, useState } from 'react';
import { connectionApi } from '../api/client';

interface ConnectionMonitorProps {
  isConnected: boolean;
}

/**
 * ConnectionMonitor component that monitors connection status and handles reconnection.
 */
const ConnectionMonitor: React.FC<ConnectionMonitorProps> = ({ isConnected }) => {
  const [showReconnectAlert, setShowReconnectAlert] = useState(false);
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
        connectionApi.checkConnection();
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

  // Handle manual reconnect attempt
  const handleManualReconnect = () => {
    connectionApi.checkConnection();
  };

  return (
    <>
      {/* Connection Lost Alert */}
      {showReconnectAlert && (
        <div className="connection-alert error">
          <div className="alert-content">
            <h4>Connection Lost</h4>
            <p>Lost connection to the server. Attempting to reconnect... (Attempt {reconnectAttempts})</p>
          </div>
          <div className="alert-actions">
            <button className="btn btn-primary" onClick={handleManualReconnect}>
              Reconnect Now
            </button>
          </div>
        </div>
      )}
    </>
  );
};

export default ConnectionMonitor;
