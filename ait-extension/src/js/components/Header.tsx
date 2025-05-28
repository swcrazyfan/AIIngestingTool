import React, { useEffect, useState } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { healthApi } from '../api/client';
import { FiWifi, FiWifiOff, FiLogOut, FiUser, FiFolder } from 'react-icons/fi';
import '../styles/Header.scss';

const Header: React.FC = () => {
  const { authStatus, logout } = useAuth();
  const [isConnected, setIsConnected] = useState(false);
  const [currentProject, setCurrentProject] = useState('All Projects');

  useEffect(() => {
    const checkConnection = async () => {
      const result = await healthApi.check();
      setIsConnected(result.connected);
    };

    checkConnection();
    const interval = setInterval(checkConnection, 10000); // Check every 10 seconds

    return () => clearInterval(interval);
  }, []);

  return (
    <header className="app-header">
      <div className="header-content">
        <div className="header-left">
          <h1>AI Video Ingest Tool</h1>
          <div className="project-selector">
            <FiFolder />
            <select 
              value={currentProject} 
              onChange={(e) => setCurrentProject(e.target.value)}
            >
              <option value="All Projects">All Projects</option>
              <option value="Wedding 2024">Wedding 2024</option>
              <option value="Corporate Videos">Corporate Videos</option>
            </select>
          </div>
        </div>
        
        <div className="header-actions">
          <div className={`connection-status ${isConnected ? 'connected' : 'disconnected'}`}>
            {isConnected ? <FiWifi /> : <FiWifiOff />}
            <span>{isConnected ? 'Connected' : 'Disconnected'}</span>
          </div>

          {authStatus?.authenticated && (
            <>
              <div className="user-info">
                <FiUser />
                <span>{authStatus.user?.email}</span>
              </div>
              
              <button onClick={logout} className="logout-button">
                <FiLogOut />
              </button>
            </>
          )}
        </div>
      </div>
    </header>
  );
};

export default Header;
