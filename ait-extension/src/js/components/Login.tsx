import React, { useState } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { FiUser, FiLock, FiLogIn, FiEye } from 'react-icons/fi';
import '../styles/Login.scss';

const Login: React.FC = () => {
  const { login, setGuestMode } = useAuth();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      await login(email, password);
    } catch (err: any) {
      setError(err.message || 'Login failed');
    } finally {
      setLoading(false);
    }
  };

  const handleGuestMode = () => {
    setError('');
    setGuestMode(true);
  };

  return (
    <div className="login-container">
      <div className="login-card">
        <h2>AI Video Ingest Tool</h2>
        <p className="login-subtitle">Sign in to access your video library</p>
        
        {/* Guest Mode Button */}
        <div className="session-check">
          <button 
            type="button" 
            className="session-button guest-button" 
            onClick={handleGuestMode}
            disabled={loading}
          >
            <FiEye /> Explore in Guest Mode
          </button>
          <p className="session-help">View the interface without authentication (read-only)</p>
        </div>

        <div className="login-divider">
          <span>or sign in for full access</span>
        </div>
        
        <form onSubmit={handleSubmit} className="login-form">
          <div className="input-group">
            <FiUser className="input-icon" />
            <input
              type="email"
              placeholder="Email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              disabled={loading}
            />
          </div>

          <div className="input-group">
            <FiLock className="input-icon" />
            <input
              type="password"
              placeholder="Password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              disabled={loading}
            />
          </div>

          {error && <div className="error-message">{error}</div>}

          <button type="submit" className="login-button" disabled={loading}>
            {loading ? (
              <span>Signing in...</span>
            ) : (
              <>
                <FiLogIn /> Sign In
              </>
            )}
          </button>
        </form>
      </div>
    </div>
  );
};

export default Login;
