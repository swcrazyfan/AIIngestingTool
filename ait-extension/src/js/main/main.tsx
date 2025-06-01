import React, { useState, useEffect, ErrorInfo, Component } from 'react';
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

// Error Boundary to catch React errors
class ErrorBoundary extends Component<{children: React.ReactNode}, {hasError: boolean, error?: Error}> {
  constructor(props: {children: React.ReactNode}) {
    super(props);
    this.state = { hasError: false };
  }

  static getDerivedStateFromError(error: Error) {
    console.error('🚨 React Error Boundary caught error:', error);
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error('🚨 Error Boundary componentDidCatch:', error, errorInfo);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div style={{ padding: '20px', color: 'white', backgroundColor: '#2a2a2a' }}>
          <h2>Something went wrong</h2>
          <p>The extension encountered an error:</p>
          <pre style={{ color: '#ff6b6b', marginTop: '10px' }}>
            {this.state.error?.message || 'Unknown error'}
          </pre>
          <p style={{ marginTop: '10px', fontSize: '12px' }}>
            Check the browser console for more details.
          </p>
          <button 
            onClick={() => this.setState({ hasError: false, error: undefined })} 
            style={{ marginTop: '10px', padding: '8px 16px' }}
          >
            Try Again
          </button>
        </div>
      );
    }

    return this.props.children;
  }
}

const AppContent: React.FC = () => {
  console.log('📱 AppContent component rendering...');
  
  const [activeTab, setActiveTab] = useState<'dashboard' | 'library' | 'ingest'>('dashboard');
  const [isConnected, setIsConnected] = useState(true);
  const [loading, setLoading] = useState(true);

  // Handle connection status changes
  useEffect(() => {
    console.log('🔄 AppContent useEffect starting...');
    
    const handleConnectionChange = (connected: boolean) => {
      console.log('🔌 Connection status changed:', connected);
      setIsConnected(connected);
    };

    // Add connection listener
    connectionApi.addConnectionListener(handleConnectionChange);

    // Initial setup
    const initializeApp = async () => {
      try {
        console.log('🔄 App loading - refreshing port configuration...');
        connectionApi.refreshPortConfiguration();
        
        // Log current config for debugging
        const config = connectionApi.getCurrentConfig();
        console.log('📊 Current API configuration:', config);
        
        // Check initial connection
        const connected = await connectionApi.checkConnection();
        console.log('✅ Initial connection check result:', connected);
        setIsConnected(connected);
        setLoading(false);
      } catch (error) {
        console.error('❌ Error during app initialization:', error);
        setLoading(false);
      }
    };

    initializeApp();

    return () => {
      connectionApi.removeConnectionListener(handleConnectionChange);
    };
  }, []);

  console.log('📊 AppContent state:', { loading, isConnected, activeTab });

  if (loading) {
    console.log('⏳ Showing loading state...');
    return (
      <div className="app-loading">
        <div className="spinner" />
        <p>Loading...</p>
      </div>
    );
  }

  console.log('🎯 Rendering main app content...');
  
  try {
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
  } catch (error) {
    console.error('❌ Error in AppContent render:', error);
    return (
      <div style={{ padding: '20px', color: 'white', backgroundColor: '#2a2a2a' }}>
        <h2>Debug: Render Error</h2>
        <p>Error in AppContent: {String(error)}</p>
      </div>
    );
  }
};

const Main: React.FC = () => {
  console.log('🚀 Main component rendering...');
  
  return (
    <QueryClientProvider client={queryClient}>
      <WebSocketProvider>
        <ErrorBoundary>
          <AppContent />
        </ErrorBoundary>
      </WebSocketProvider>
    </QueryClientProvider>
  );
};

export default Main;
