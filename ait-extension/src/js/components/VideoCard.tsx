import React, { useState, useEffect } from 'react';
import { VideoFile } from '../types/api';
import { evalTS } from '../lib/utils/bolt';
import { formatDuration } from '../utils/format';
import { FiPlay, FiFolder, FiSearch, FiClock, FiCamera, FiInfo } from 'react-icons/fi';
import SimilarVideosModal from './SimilarVideosModal';
import VideoDetailsModal from './VideoDetailsModal';
import { thumbnailCache, CACHE_EXPIRATION, cleanupCacheEntry } from './shared/ThumbnailCache';
import { CardSize, ViewMode } from './VideoLibrary';
import '../styles/VideoCard.scss';

interface VideoCardProps {
  video: VideoFile;
  onRefresh: () => void;
  size?: CardSize;
  viewMode?: ViewMode;
}

const VideoCard: React.FC<VideoCardProps> = ({ 
  video, 
  onRefresh, 
  size = 'medium', 
  viewMode = 'tiles' 
}) => {
  const [showSimilar, setShowSimilar] = useState(false);
  const [showDetails, setShowDetails] = useState(false);
  const [thumbnailError, setThumbnailError] = useState(false);
  const [imgSrc, setImgSrc] = useState<string | null>(null);

  // Helper function to truncate filename
  const truncateFilename = (filename: string, maxLength = 24) => {
    if (filename.length <= maxLength) return filename;
    
    // Get the file extension
    const lastDotIndex = filename.lastIndexOf('.');
    const extension = lastDotIndex !== -1 ? filename.slice(lastDotIndex) : '';
    
    // Calculate how much of the name we can show
    const nameLength = maxLength - extension.length - 3; // 3 for "..."
    
    // Return truncated name + ... + extension
    return filename.slice(0, nameLength) + '...' + extension;
  };
  
  // Format camera display
  const getCameraInfo = () => {
    if (!video.camera_make && !video.camera_model) return null;
    
    // If we have both make and model
    if (video.camera_make && video.camera_model) {
      // If the model already includes the make (e.g., "Canon EOS R5"), don't repeat it
      if (video.camera_model.includes(video.camera_make)) {
        return video.camera_model;
      }
      // Otherwise show both
      return `${video.camera_make} ${video.camera_model}`;
    }
    
    // Return whichever one we have
    return video.camera_make || video.camera_model;
  };

  // Load thumbnail with caching
  useEffect(() => {
    const loadThumbnail = async () => {
      if (!video.id) return;
      
      try {
        const clipId = video.id.toString();
        const now = Date.now();
        
        // Check if we have a valid cached version
        if (thumbnailCache[clipId]) {
          const cache = thumbnailCache[clipId];
          
          // Check if cache is still valid (not expired)
          if (now - cache.timestamp < CACHE_EXPIRATION) {
            // If we have a blob object URL, use it
            if (cache.objectUrl) {
              setImgSrc(cache.objectUrl);
              return;
            }
            
            // If we have a blob but no object URL, create one
            if (cache.blob) {
              const objectUrl = URL.createObjectURL(cache.blob);
              thumbnailCache[clipId].objectUrl = objectUrl;
              setImgSrc(objectUrl);
              return;
            }
          } else {
            // Clean up expired cache
            cleanupCacheEntry(clipId);
          }
        }
        
        // If no valid cache exists, load from API
        const apiUrl = `http://localhost:8000/api/thumbnail/${clipId}`;
        
        // Fetch the image as a blob
        const response = await fetch(apiUrl);
        if (!response.ok) throw new Error('Failed to load thumbnail');
        
        const blob = await response.blob();
        const objectUrl = URL.createObjectURL(blob);
        
        // Cache the blob and object URL
        thumbnailCache[clipId] = {
          url: apiUrl,
          timestamp: now,
          blob: blob,
          objectUrl: objectUrl
        };
        
        setImgSrc(objectUrl);
      } catch (error) {
        console.error('Error loading thumbnail:', error);
        setThumbnailError(true);
      }
    };
    
    loadThumbnail();
    
    // Cleanup function to revoke object URLs
    return () => {
      if (video.id) {
        // Only cleanup this component's specific object URL on unmount
        const clipId = video.id.toString();
        if (thumbnailCache[clipId]?.objectUrl) {
          URL.revokeObjectURL(thumbnailCache[clipId].objectUrl!);
          // Note: We don't delete from cache here to keep it for future use
          // Just revoke the URL to free memory
          thumbnailCache[clipId].objectUrl = undefined;
        }
      }
    };
  }, [video.id]);

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

  // Determine if we have AI thumbnails
  const hasAiThumbnails = video.all_thumbnail_urls?.some(t => t.is_ai_selected) || false;
  
  // Get camera info for display
  const cameraInfo = getCameraInfo();
  
  // Determine filename max length based on card size
  const getMaxFilenameLength = () => {
    switch (size) {
      case 'small': return 16;
      case 'large': return 32;
      default: return 24; // medium
    }
  };
  
  return (
    <>
      <div className={`video-card video-card-${size} ${viewMode === 'rows' ? 'video-card-row' : ''}`}>
        <div className="video-thumbnail" onClick={() => setShowDetails(true)} style={{ cursor: 'pointer' }}>
          {imgSrc && !thumbnailError ? (
            <img 
              src={imgSrc} 
              alt={video.file_name} 
              onError={() => setThumbnailError(true)}
            />
          ) : (
            <div className="thumbnail-placeholder">
              <span>{video.file_name.substring(0, 1).toUpperCase()}</span>
            </div>
          )}
          {hasAiThumbnails && (
            <div className="ai-badge" title="AI-selected thumbnail">AI</div>
          )}
        </div>
        
        <div className="video-info">
          <h3 
            className="video-title" 
            title={video.file_name} 
            onClick={() => setShowDetails(true)}
            style={{ cursor: 'pointer' }}
          >
            {truncateFilename(video.file_name, getMaxFilenameLength())}
          </h3>
          
          <div className="video-meta">
            <span title={`Duration: ${formatDuration(video.duration_seconds)}`}>
              <FiClock /> {formatDuration(video.duration_seconds)}
            </span>
            
            {cameraInfo && (
              <span title={`Camera: ${cameraInfo}`}>
                <FiCamera /> {cameraInfo}
              </span>
            )}
          </div>

          {video.content_summary && (
            <p className="video-summary" title={video.content_summary}>
              {video.content_summary}
            </p>
          )}

          {video.content_tags && video.content_tags.length > 0 && (
            <div className="video-tags">
              {video.content_tags.slice(0, size === 'small' ? 2 : 3).map((tag, index) => (
                <span key={index} className="tag">{tag}</span>
              ))}
              {video.content_tags.length > (size === 'small' ? 2 : 3) && (
                <span className="tag more-tag">+{video.content_tags.length - (size === 'small' ? 2 : 3)}</span>
              )}
            </div>
          )}
        </div>

        <div className="video-actions">
          <button onClick={addToTimeline} title="Add to Timeline">
            <FiPlay /> {size !== 'small' && 'Timeline'}
          </button>
          
          <button onClick={addToProject} title="Import to Project">
            <FiFolder /> {size !== 'small' && 'Import'}
          </button>
          
          <button onClick={() => setShowSimilar(true)} title="Find Similar">
            <FiSearch /> {size !== 'small' && 'Similar'}
          </button>
          
          <button onClick={() => setShowDetails(true)} title="Show Details">
            <FiInfo /> {size !== 'small' && 'Details'}
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
