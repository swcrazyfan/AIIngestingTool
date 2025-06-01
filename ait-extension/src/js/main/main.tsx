import React, { useState, useEffect } from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { WebSocketProvider } from '../contexts/WebSocketContext';
import Header from '../components/Header';
import VideoLibrary from '../components/VideoLibrary';
import IngestPanel from '../components/IngestPanel';
import Dashboard from '../components/Dashboard';
import ConnectionMonitor from '../components/ConnectionMonitor';
import { connectionApi } from '../api/client';
import '../styles/App.scss';

const queryClient = new QueryClient();

const AppContent: React.FC = () => {
  const [activeTab, setActiveTab] = useState<'dashboard' | 'library' | 'ingest'>('dashboard');
  const [isConnected, setIsConnected] = useState(true);
  const [loading, setLoading] = useState(true);

  // Handle connection status changes
  useEffect(() => {
    const handleConnectionChange = (connected: boolean) => {
      setIsConnected(connected);
    };

    // Add connection listener
    connectionApi.addConnectionListener(handleConnectionChange);

    // Initial setup
    const initializeApp = async () => {
      console.log('🔄 App loading - refreshing port configuration...');
      connectionApi.refreshPortConfiguration();
      
      // Log current config for debugging
      const config = connectionApi.getCurrentConfig();
      console.log('📊 Current API configuration:', config);
      
      // Check initial connection
      const connected = await connectionApi.checkConnection();
      setIsConnected(connected);
      setLoading(false);
    };

    initializeApp();

    return () => {
      connectionApi.removeConnectionListener(handleConnectionChange);
    };
  }, []);

  if (loading) {
    return (
      <div className="app-loading">
        <div className="spinner" />
        <p>Loading...</p>
      </div>
    );
  }

  return (
    <div className="app">
      {/* Connection status monitor */}
      <ConnectionMonitor isConnected={isConnected} />
      
      <Header isConnected={isConnected} />
      
      <div className="app-content">
        <div className="tab-navigation">
          <button
            className={`tab-button ${activeTab === 'dashboard' ? 'active' : ''}`}
            onClick={() => setActiveTab('dashboard')}
            disabled={!isConnected}
          >
            Dashboard
          </button>
          <button
            className={`tab-button ${activeTab === 'library' ? 'active' : ''}`}
            onClick={() => setActiveTab('library')}
            disabled={!isConnected}
          >
            Library
          </button>
          <button
            className={`tab-button ${activeTab === 'ingest' ? 'active' : ''}`}
            onClick={() => setActiveTab('ingest')}
            disabled={!isConnected}
          >
            Ingest
          </button>
        </div>

        <div className="tab-content">
          {!isConnected ? (
            <div className="connection-lost-message">
              <p>Connection to the server has been lost. Attempting to reconnect...</p>
            </div>
          ) : (
            <>
              {activeTab === 'dashboard' && <Dashboard />}
              {activeTab === 'library' && <VideoLibrary />}
              {activeTab === 'ingest' && <IngestPanel />}
            </>
          )}
        </div>
      </div>
    </div>
  );
};

const Main: React.FC = () => {
  return (
    <QueryClientProvider client={queryClient}>
      <WebSocketProvider>
        <AppContent />
      </WebSocketProvider>
    </QueryClientProvider>
  );
};

export default Main;
