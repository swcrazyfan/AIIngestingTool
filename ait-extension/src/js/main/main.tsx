import React, { useState } from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { AuthProvider, useAuth } from '../contexts/AuthContext';
import { WebSocketProvider } from '../contexts/WebSocketContext';
import Header from '../components/Header';
import Login from '../components/Login';
import VideoLibrary from '../components/VideoLibrary';
import IngestPanel from '../components/IngestPanel';
import Dashboard from '../components/Dashboard';
import ConnectionMonitor from '../components/ConnectionMonitor';
import '../styles/App.scss';

const queryClient = new QueryClient();

const AppContent: React.FC = () => {
  const { authStatus, loading, isConnected, isGuestMode } = useAuth();
  const [activeTab, setActiveTab] = useState<'dashboard' | 'library' | 'ingest'>('dashboard');

  if (loading) {
    return (
      <div className="app-loading">
        <div className="spinner" />
        <p>Loading...</p>
      </div>
    );
  }

  // Since authentication is disabled, always show the main app
  const isLocalMode = authStatus?.user?.profile_type === 'local';

  return (
    <div className="app">
      {/* Connection status monitor */}
      <ConnectionMonitor />
      
      {/* Local mode banner */}
      {isLocalMode && !isGuestMode && (
        <div className="guest-mode-banner local-mode-banner">
          <span>🏠 Local Mode - Using local DuckDB database</span>
        </div>
      )}
      
      {/* Guest mode banner */}
      {isGuestMode && (
        <div className="guest-mode-banner">
          <span>👁️ Guest Mode - Read-only preview (some features disabled)</span>
          <button onClick={() => window.location.reload()}>Exit Guest Mode</button>
        </div>
      )}
      
      <Header />
      
      <div className="app-content">
        <div className="tab-navigation">
          <button
            className={`tab-button ${activeTab === 'dashboard' ? 'active' : ''}`}
            onClick={() => setActiveTab('dashboard')}
            disabled={!isConnected && !isGuestMode}
          >
            Dashboard
          </button>
          <button
            className={`tab-button ${activeTab === 'library' ? 'active' : ''}`}
            onClick={() => setActiveTab('library')}
            disabled={!isConnected && !isGuestMode}
          >
            Library
          </button>
          <button
            className={`tab-button ${activeTab === 'ingest' ? 'active' : ''} ${isGuestMode ? 'disabled-guest' : ''}`}
            onClick={() => !isGuestMode && setActiveTab('ingest')}
            disabled={(!isConnected && !isGuestMode) || isGuestMode}
            title={isGuestMode ? 'Not available in guest mode' : ''}
          >
            Ingest
          </button>
        </div>

        <div className="tab-content">
          {!isConnected && !isGuestMode ? (
            <div className="connection-lost-message">
              <p>Connection to the server has been lost. Attempting to reconnect...</p>
            </div>
          ) : (
            <>
              {activeTab === 'dashboard' && <Dashboard />}
              {activeTab === 'library' && <VideoLibrary />}
              {activeTab === 'ingest' && !isGuestMode && <IngestPanel />}
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
      <AuthProvider>
        <WebSocketProvider>
          <AppContent />
        </WebSocketProvider>
      </AuthProvider>
    </QueryClientProvider>
  );
};

export default Main;
