import React, { useState, useEffect } from 'react';
import { searchApi } from '../api/client';
import { VideoFile } from '../types/api';
import VideoCard from './VideoCard';
import SearchBar from './SearchBar';
import { FiFilm } from 'react-icons/fi';
import '../styles/VideoLibrary.scss';

const VideoLibrary: React.FC = () => {
  const [videos, setVideos] = useState<VideoFile[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [searchType, setSearchType] = useState<'hybrid' | 'semantic' | 'fulltext' | 'transcripts'>('hybrid');

  const loadVideos = async (query?: string) => {
    setLoading(true);
    try {
      // If there's a search query, use it. Otherwise, pass empty string to get recent videos
      const searchQuery = query !== undefined ? query : '';
      const results = await searchApi.search(searchQuery, searchType);
      setVideos(results.results || []);
    } catch (error) {
      console.error('Failed to load videos:', error);
      setVideos([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadVideos();
  }, []);

  const handleSearch = (query: string, type: typeof searchType) => {
    setSearchQuery(query);
    setSearchType(type);
    // Always perform the search, even if query is empty (will show recent videos)
    loadVideos(query);
  };

  return (
    <div className="video-library">
      <SearchBar onSearch={handleSearch} />
      
      <div className="library-header">
        <h3>{searchQuery ? `Search results for "${searchQuery}"` : 'Recent Videos'}</h3>
        <button 
          onClick={() => loadVideos(searchQuery)} 
          className="refresh-button"
          title="Refresh"
        >
          🔄
        </button>
      </div>
      
      <div className="video-grid">
        {loading ? (
          <div className="loading-state">
            <div className="spinner" />
            <p>Loading videos...</p>
          </div>
        ) : videos.length > 0 ? (
          videos.map((video) => (
            <VideoCard key={video.id} video={video} onRefresh={() => loadVideos(searchQuery)} />
          ))
        ) : (
          <div className="empty-state">
            <FiFilm size={48} />
            <h3>No videos found</h3>
            <p>{searchQuery ? 'Try a different search query' : 'Process some videos to get started'}</p>
          </div>
        )}
      </div>
    </div>
  );
};

export default VideoLibrary;
