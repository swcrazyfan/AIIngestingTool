import React, { useState, useEffect } from 'react';
import { FiFolder, FiPlus, FiSettings, FiMoreHorizontal, FiHardDrive, FiVideo, FiClock } from 'react-icons/fi';
import { formatFileSize, formatDuration } from '../utils/format';

interface Project {
  id: string;
  name: string;
  path: string;
  status: 'active' | 'processing' | 'idle';
  videoCount: number;
  totalSize: number;
  totalDuration: number;
  lastProcessed?: string;
}

const ProjectsPanel: React.FC = () => {
  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedProject, setSelectedProject] = useState<string>('all');

  useEffect(() => {
    // Simulate loading projects - replace with your API call
    setTimeout(() => {
      setProjects([
        {
          id: 'wedding-2024',
          name: 'Wedding Project 2024',
          path: '/Users/john/Videos/Wedding2024',
          status: 'active',
          videoCount: 45,
          totalSize: 2.3e9, // 2.3GB
          totalDuration: 5400, // 90 minutes
          lastProcessed: '2024-01-15T10:30:00Z'
        },
        {
          id: 'corporate-videos',
          name: 'Corporate Training Videos',
          path: '/Users/john/Videos/Corporate',
          status: 'idle',
          videoCount: 12,
          totalSize: 890e6, // 890MB
          totalDuration: 2400, // 40 minutes
          lastProcessed: '2024-01-10T14:20:00Z'
        }
      ]);
      setLoading(false);
    }, 1000);
  }, []);

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'active': return '#16a34a';
      case 'processing': return '#0066cc';
      case 'idle': return '#6b7280';
      default: return '#6b7280';
    }
  };

  if (loading) {
    return (
      <div className="video-library">
        <div className="loading-state">
          <div className="spinner" />
          <h3>Loading Projects</h3>
          <p>Getting your project information...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="video-library">
      {/* Header using your existing style */}
      <div className="library-header">
        <h3>Projects</h3>
        <div className="library-controls">
          <button className="refresh-button">
            <FiPlus />
          </button>
        </div>
      </div>

      {/* Project selection using your existing filter style */}
      <div className="filter-controls">
        <div className="filter-group">
          <label>Current Project:</label>
          <select 
            value={selectedProject} 
            onChange={(e) => setSelectedProject(e.target.value)}
          >
            <option value="all">All Projects</option>
            {projects.map(project => (
              <option key={project.id} value={project.id}>
                {project.name}
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* Projects grid using your existing video grid */}
      <div className="video-grid">
        {projects.map((project) => (
          <div key={project.id} className="video-card">
            <div className="video-thumbnail">
              <div className="thumbnail-placeholder">
                <FiFolder />
              </div>
              <div className="ai-badge" style={{ backgroundColor: getStatusColor(project.status) }}>
                {project.status}
              </div>
            </div>
            
            <div className="video-info">
              <div className="video-title">{project.name}</div>
              <div className="video-meta">
                <span><FiVideo /> {project.videoCount} videos</span>
                <span><FiHardDrive /> {formatFileSize(project.totalSize)}</span>
                <span><FiClock /> {formatDuration(project.totalDuration)}</span>
              </div>
              <div className="video-summary">
                {project.path}
              </div>
            </div>

            <div className="video-actions">
              <button>
                <FiSettings />
                Configure
              </button>
              <button>
                <FiMoreHorizontal />
                Options
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

export default ProjectsPanel;
