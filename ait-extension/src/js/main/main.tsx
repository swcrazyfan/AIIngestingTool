import React, { useState } from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { AuthProvider, useAuth } from '../contexts/AuthContext';
import { WebSocketProvider } from '../contexts/WebSocketContext';
import Header from '../components/Header';
import Login from '../components/Login';
import VideoLibrary from '../components/VideoLibrary';
import IngestPanel from '../components/IngestPanel';
import ConnectionMonitor from '../components/ConnectionMonitor';
import '../styles/App.scss';

const queryClient = new QueryClient();

const AppContent: React.FC = () => {
  const { authStatus, loading, isConnected } = useAuth();
  const [activeTab, setActiveTab] = useState<'library' | 'ingest'>('library');

  if (loading) {
    return (
      <div className="app-loading">
        <div className="spinner" />
        <p>Loading...</p>
      </div>
    );
  }

  if (!authStatus?.authenticated) {
    return <Login />;
  }

  return (
    <div className="app">
      {/* Connection status monitor */}
      <ConnectionMonitor />
      
      <Header />
      
      <div className="app-content">
        <div className="tab-navigation">
          <button
            className={`tab-button ${activeTab === 'library' ? 'active' : ''}`}
            onClick={() => setActiveTab('library')}
            disabled={!isConnected}
          >
            Video Library
          </button>
          <button
            className={`tab-button ${activeTab === 'ingest' ? 'active' : ''}`}
            onClick={() => setActiveTab('ingest')}
            disabled={!isConnected}
          >
            Process Videos
          </button>
        </div>

        <div className="tab-content">
          {!isConnected ? (
            <div className="connection-lost-message">
              <p>Connection to the server has been lost. Attempting to reconnect...</p>
            </div>
          ) : (
            activeTab === 'library' ? <VideoLibrary /> : <IngestPanel />
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
