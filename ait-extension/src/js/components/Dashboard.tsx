import React, { useState, useEffect } from 'react';
import { searchApi, statsApi } from '../api/client';
import { VideoFile, CatalogStats } from '../types/api';
import VideoCard from './VideoCard';
import { formatDuration } from '../utils/format';
import { 
  FiFilm, 
  FiClock, 
  FiHardDrive, 
  FiTrendingUp, 
  FiCalendar, 
  FiFolder,
  FiPlay,
  FiGrid,
  FiSettings,
  FiRefreshCw,
  FiChevronRight
} from 'react-icons/fi';
import '../styles/Dashboard.scss';

interface QuickAction {
  id: string;
  label: string;
  icon: React.ReactNode;
  description: string;
  onClick: () => void;
  disabled?: boolean;
}

const Dashboard: React.FC = () => {
  const [recentVideos, setRecentVideos] = useState<VideoFile[]>([]);
  const [stats, setStats] = useState<CatalogStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadDashboardData = async () => {
    try {
      setLoading(true);
      setError(null);

      // Load recent videos
      const recentResponse = await searchApi.search('', 'hybrid', 6);
      setRecentVideos(recentResponse.results);

      // Load catalog stats
      try {
        const statsResponse = await statsApi.getCatalogStats();
        setStats(statsResponse);
      } catch (statsError) {
        console.warn('Failed to load stats:', statsError);
        // Continue without stats if they fail to load
      }

    } catch (err: any) {
      console.error('Failed to load dashboard data:', err);
      setError(err.message || 'Failed to load dashboard data');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadDashboardData();
  }, []);

  const quickActions: QuickAction[] = [
    {
      id: 'ingest',
      label: 'Start Ingest',
      icon: <FiFolder />,
      description: 'Process new videos',
      onClick: () => {
        // This would trigger a tab change to ingest - implement based on your app structure
        console.log('Navigate to ingest');
      }
    },
    {
      id: 'library',
      label: 'Browse Library',
      icon: <FiGrid />,
      description: 'Explore your videos',
      onClick: () => {
        // Navigate to library
        console.log('Navigate to library');
      }
    },
    {
      id: 'search',
      label: 'Advanced Search',
      icon: <FiTrendingUp />,
      description: 'Find specific content',
      onClick: () => {
        // Navigate to library with search focus
        console.log('Navigate to search');
      }
    }
  ];

  const formatFileSize = (bytes: number): string => {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'active': return <FiPlay className="status-icon status-active" />;
      case 'processing': return <FiRefreshCw className="status-icon status-processing" />;
      default: return <FiClock className="status-icon status-idle" />;
    }
  };

  if (loading) {
    return (
      <div className="dashboard">
        <div className="loading-state">
          <div className="spinner" />
          <p>Loading dashboard...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="dashboard">
        <div className="error-state">
          <p>Error loading dashboard: {error}</p>
          <button onClick={loadDashboardData} className="retry-button">
            <FiRefreshCw /> Retry
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="dashboard">
      <div className="dashboard-header">
        <div className="dashboard-title">
          <h2>Dashboard</h2>
          <p>Overview of your video library and recent activity</p>
        </div>
        <button onClick={loadDashboardData} className="refresh-button" title="Refresh dashboard">
          <FiRefreshCw />
        </button>
      </div>

      <div className="dashboard-content">
        {/* Quick Actions */}
        <div className="dashboard-section">
          <h3>Quick Actions</h3>
          <div className="quick-actions">
            {quickActions.map(action => (
              <button
                key={action.id}
                className="quick-action-card"
                onClick={action.onClick}
                disabled={action.disabled}
                title={action.description}
              >
                <div className="action-icon">{action.icon}</div>
                <div className="action-content">
                  <span className="action-label">{action.label}</span>
                  <span className="action-description">{action.description}</span>
                </div>
                <FiChevronRight className="action-arrow" />
              </button>
            ))}
          </div>
        </div>

        {/* Stats Overview */}
        {stats && (
          <div className="dashboard-section">
            <h3>Library Overview</h3>
            <div className="stats-grid">
              <div className="stat-card">
                <div className="stat-icon">
                  <FiFilm />
                </div>
                <div className="stat-content">
                  <div className="stat-value">{stats.total_videos?.toLocaleString() || '0'}</div>
                  <div className="stat-label">Total Videos</div>
                </div>
              </div>
              
              <div className="stat-card">
                <div className="stat-icon">
                  <FiClock />
                </div>
                <div className="stat-content">
                  <div className="stat-value">
                    {stats.total_duration_seconds ? formatDuration(stats.total_duration_seconds) : '0m'}
                  </div>
                  <div className="stat-label">Total Duration</div>
                </div>
              </div>
              
              <div className="stat-card">
                <div className="stat-icon">
                  <FiHardDrive />
                </div>
                <div className="stat-content">
                  <div className="stat-value">
                    {stats.total_file_size_bytes ? formatFileSize(stats.total_file_size_bytes) : '0 B'}
                  </div>
                  <div className="stat-label">Storage Used</div>
                </div>
              </div>
              
              <div className="stat-card">
                <div className="stat-icon">
                  <FiCalendar />
                </div>
                <div className="stat-content">
                  <div className="stat-value">Today</div>
                  <div className="stat-label">Last Updated</div>
                </div>
              </div>
            </div>
          </div>
        )}


        {/* Recent Videos */}
        <div className="dashboard-section">
          <div className="section-header">
            <h3>Recent Videos</h3>
            <button className="view-all-button">
              View All <FiChevronRight />
            </button>
          </div>
          
          {recentVideos.length > 0 ? (
            <div className="recent-videos-grid">
              {recentVideos.map(video => (
                <div key={video.id} className="recent-video-wrapper">
                  <VideoCard
                    video={video}
                    onRefresh={loadDashboardData}
                    size="medium"
                  />
                </div>
              ))}
            </div>
          ) : (
            <div className="empty-state">
              <FiFilm className="empty-icon" />
              <h4>No videos yet</h4>
              <p>Start by ingesting some videos to see them here.</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default Dashboard;