import React, { useState, useEffect } from 'react';
import { searchApi } from '../api/client';
import { VideoFile } from '../types/api';
import VideoCard from './VideoCard';
import { FiX } from 'react-icons/fi';
import '../styles/SimilarVideosModal.scss';

interface SimilarVideosModalProps {
  sourceVideo: VideoFile;
  onClose: () => void;
}

const SimilarVideosModal: React.FC<SimilarVideosModalProps> = ({ sourceVideo, onClose }) => {
  const [similarVideos, setSimilarVideos] = useState<VideoFile[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const loadSimilar = async () => {
      try {
        const results = await searchApi.findSimilar(sourceVideo.id);
        setSimilarVideos(results.results || []);
      } catch (error) {
        console.error('Failed to load similar videos:', error);
      } finally {
        setLoading(false);
      }
    };

    loadSimilar();
  }, [sourceVideo.id]);

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h2>Similar Videos</h2>
          <button onClick={onClose} className="close-button">
            <FiX />
          </button>
        </div>

        <div className="modal-body">
          <p className="source-info">Videos similar to: <strong>{sourceVideo.file_name}</strong></p>
          
          {loading ? (
            <div className="loading-state">
              <div className="spinner" />
              <p>Finding similar videos...</p>
            </div>
          ) : similarVideos.length > 0 ? (
            <div className="similar-videos-grid">
              {similarVideos.map((video) => (
                <VideoCard key={video.id} video={video} onRefresh={() => {}} />
              ))}
            </div>
          ) : (
            <div className="empty-state">
              <p>No similar videos found</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default SimilarVideosModal;
