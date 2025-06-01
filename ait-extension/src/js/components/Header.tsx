import React from 'react';
import { connectionApi } from '../api/client';
import { FiWifi, FiWifiOff, FiRefreshCw } from 'react-icons/fi';
import '../styles/Header.scss';

interface HeaderProps {
  isConnected: boolean;
}

const Header: React.FC<HeaderProps> = ({ isConnected }) => {
  // Debug function to refresh port config
  const handleRefreshConfig = () => {
    console.log('🔄 Manual port configuration refresh...');
    connectionApi.refreshPortConfiguration();
    const config = connectionApi.getCurrentConfig();
    console.log('📊 Updated configuration:', config);
    alert(`Port Config:\nPort: ${config.port}\nBase URL: ${config.baseUrl}\nLoaded: ${config.loaded}`);
  };

  return (
    <header className="app-header">
      <div className="header-content">
        <div className="header-left">
          <h1>AI Video Ingest Tool</h1>
        </div>
        
        <div className="header-actions">
          <div className={`connection-status ${isConnected ? 'connected' : 'disconnected'}`}>
            {isConnected ? <FiWifi /> : <FiWifiOff />}
            <span>{isConnected ? 'Connected' : 'Disconnected'}</span>
          </div>

          {/* Debug button for port configuration */}
          <button 
            onClick={handleRefreshConfig} 
            className="debug-button" 
            title="Refresh Port Configuration"
            aria-label="Refresh Port Configuration"
            style={{ 
              background: 'none', 
              border: '1px solid #666', 
              color: '#fff', 
              padding: '4px 8px', 
              borderRadius: '4px',
              cursor: 'pointer',
              marginRight: '8px',
              display: 'flex',
              alignItems: 'center',
              gap: '4px'
            }}
          >
            <FiRefreshCw size={14} />
            <span style={{ fontSize: '12px' }}>Port</span>
          </button>
        </div>
      </div>
    </header>
  );
};

export default Header;
