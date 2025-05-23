import React, { useState } from 'react';
import { VideoFile } from '../types/api';
import { evalTS } from '../lib/utils/bolt';
import { formatDuration } from '../utils/format';
import { FiPlay, FiFolder, FiSearch, FiClock, FiCamera, FiInfo } from 'react-icons/fi';
import SimilarVideosModal from './SimilarVideosModal';
import VideoDetailsModal from './VideoDetailsModal';
import '../styles/VideoCard.scss';

interface VideoCardProps {
  video: VideoFile;
  onRefresh: () => void;
}

const VideoCard: React.FC<VideoCardProps> = ({ video, onRefresh }) => {
  const [showSimilar, setShowSimilar] = useState(false);
  const [showDetails, setShowDetails] = useState(false);

  const addToTimeline = async () => {
    try {
      await evalTS("addVideoToTimeline", video.local_path);
    } catch (error) {
      console.error('Failed to add to timeline:', error);
    }
  };

  const addToProject = async () => {
    try {
      await evalTS("importVideoToProject", video.local_path);
    } catch (error) {
      console.error('Failed to import to project:', error);
    }
  };

  const revealInFinder = async () => {
    try {
      await evalTS("revealInFinder", video.local_path);
    } catch (error) {
      console.error('Failed to reveal in finder:', error);
    }
  };
  return (
    <>
      <div className="video-card">
        <div className="video-info">
          <h3 className="video-title">{video.file_name}</h3>
          
          <div className="video-meta">
            <span><FiClock /> {formatDuration(video.duration_seconds)}</span>
            {video.camera_make && (
              <span><FiCamera /> {video.camera_make} {video.camera_model}</span>
            )}
          </div>

          {video.content_summary && (
            <p className="video-summary">{video.content_summary}</p>
          )}

          {video.content_tags && video.content_tags.length > 0 && (
            <div className="video-tags">
              {video.content_tags.slice(0, 5).map((tag, index) => (
                <span key={index} className="tag">{tag}</span>
              ))}
            </div>
          )}
        </div>

        <div className="video-actions">
          <button onClick={addToTimeline} title="Add to Timeline">
            <FiPlay /> Timeline
          </button>
          
          <button onClick={addToProject} title="Import to Project">
            <FiFolder /> Import
          </button>
          
          <button onClick={() => setShowSimilar(true)} title="Find Similar">
            <FiSearch /> Similar
          </button>
          <button onClick={() => setShowDetails(true)} title="Show Details">
            <FiInfo /> Details 
          </button>
        </div>
      </div>

      {showSimilar && (
        <SimilarVideosModal
          sourceVideo={video}
          onClose={() => setShowSimilar(false)}
        />
      )}

      {showDetails && (
        <VideoDetailsModal
          video={video} 
          onClose={() => setShowDetails(false)}
        />
      )}
    </>
  );
};

export default VideoCard;
