import React, { useState, useEffect, useCallback } from 'react';
import { searchApi, videosApi } from '../api/client';
import { VideoFile, SearchType, SortField, SortOrder } from '../types/api';
import VideoCard from './VideoCard';
import SearchBar from './SearchBar';
import AccordionItem from './AccordionItem';
import { FiFilm, FiRefreshCw } from 'react-icons/fi';
import { useWebSocket } from '../contexts/WebSocketContext';
import '../styles/VideoLibrary.scss';

const VideoLibrary: React.FC = () => {
  const [videos, setVideos] = useState<VideoFile[]>([]);
  const [originalFetchedVideos, setOriginalFetchedVideos] = useState<VideoFile[]>([]);
  const [loading, setLoading] = useState(true);
  const [currentSearchTerm, setCurrentSearchTerm] = useState('');
  const [activeSearchType, setActiveSearchType] = useState<'hybrid' | 'semantic' | 'fulltext' | 'transcripts'>('hybrid');
  const [sortBy, setSortBy] = useState<SortField>('processed_at');
  const [sortOrder, setSortOrder] = useState<SortOrder>('descending');
  const [dateStart, setDateStart] = useState<string>('');
  const [dateEnd, setDateEnd] = useState<string>('');

  const { search: wsSearch, connected } = useWebSocket();

  const applyClientSideFiltersAndSort = useCallback(() => {
    if (!originalFetchedVideos) return;

    let processedVideos = [...originalFetchedVideos];

    if (dateStart) {
      const startDate = new Date(dateStart + 'T00:00:00');
      processedVideos = processedVideos.filter(video => {
        const videoDateStr = video.created_at_timestamp || video.processed_at;
        if (!videoDateStr) return false;
        return new Date(videoDateStr) >= startDate;
      });
    }
    if (dateEnd) {
      const endDate = new Date(dateEnd + 'T23:59:59');
      processedVideos = processedVideos.filter(video => {
        const videoDateStr = video.created_at_timestamp || video.processed_at;
        if (!videoDateStr) return false;
        return new Date(videoDateStr) <= endDate;
      });
    }

    processedVideos.sort((a, b) => {
      let valA: any;
      let valB: any;

      switch (sortBy) {
        case 'created_at':
          valA = a.created_at_timestamp;
          valB = b.created_at_timestamp;
          break;
        case 'duration_seconds':
          valA = a.duration_seconds;
          valB = b.duration_seconds;
          break;
        case 'file_name':
        case 'processed_at':
          valA = a[sortBy];
          valB = b[sortBy];
          break;
        default:
          valA = a[sortBy as keyof VideoFile];
          valB = b[sortBy as keyof VideoFile];
      }

      if (valA == null && valB == null) return 0;
      if (valA == null) return sortOrder === 'ascending' ? -1 : 1;
      if (valB == null) return sortOrder === 'ascending' ? 1 : -1;

      if (typeof valA === 'number' && typeof valB === 'number') {
        return sortOrder === 'ascending' ? valA - valB : valB - valA;
      }
      if (String(valA) < String(valB)) return sortOrder === 'ascending' ? -1 : 1;
      if (String(valA) > String(valB)) return sortOrder === 'ascending' ? 1 : -1;
      return 0;
    });

    setVideos(processedVideos);
  }, [originalFetchedVideos, sortBy, sortOrder, dateStart, dateEnd]);

  const fetchVideoList = useCallback(async () => {
    setLoading(true);
    try {
      console.log('Fetching initial video list...');
      const options: any = { limit: 200 };
      const results = await videosApi.list(options);
      setOriginalFetchedVideos(results.results || []);
    } catch (error) {
      console.error('Failed to load video list:', error);
      setOriginalFetchedVideos([]);
      setVideos([]);
    } finally {
      setLoading(false);
    }
  }, []);

  const performKeywordSearch = useCallback(async (query: string, type: 'hybrid' | 'semantic' | 'fulltext' | 'transcripts') => {
    // Reset filter and sort states
    setSortBy('processed_at');
    setSortOrder('descending');
    setDateStart('');
    setDateEnd('');

    setLoading(true);
    setVideos([]); // Clear displayed videos immediately to show loading state
    setOriginalFetchedVideos([]); // Clear original videos to avoid processing stale data
    setCurrentSearchTerm(query);
    setActiveSearchType(type);
    try {
      let searchResults: VideoFile[] = [];
      if (connected) {
        console.log('Using WebSocket for keyword search:', query, type);
        try {
          const results = await wsSearch({ query, search_type: type, limit: 200 });
          searchResults = results.results || [];
        } catch (wsError) {
          console.error('WebSocket keyword search failed, falling back to HTTP:', wsError);
          const httpResults = await searchApi.search(query, type, 200);
          searchResults = httpResults.results || [];
        }
      } else {
        console.log('Using HTTP API for keyword search (WebSocket not connected):', query, type);
        const httpResults = await searchApi.search(query, type, 200);
        searchResults = httpResults.results || [];
      }
      setOriginalFetchedVideos(searchResults);
    } catch (error) {
      console.error('Failed to perform keyword search:', error);
      setOriginalFetchedVideos([]);
      setVideos([]);
    } finally {
      setLoading(false);
    }
  }, [connected, wsSearch]);

  useEffect(() => {
    fetchVideoList();
  }, [fetchVideoList]);

  useEffect(() => {
    applyClientSideFiltersAndSort();
  }, [originalFetchedVideos, sortBy, sortOrder, dateStart, dateEnd, applyClientSideFiltersAndSort]);

  const handleSearch = (query: string, type: 'hybrid' | 'semantic' | 'fulltext' | 'transcripts') => {
    if (query.trim()) {
      performKeywordSearch(query, type);
    } else {
      fetchVideoList();
    }
  };

  const handleRefresh = () => {
    if (currentSearchTerm) {
      performKeywordSearch(currentSearchTerm, activeSearchType);
    } else {
      fetchVideoList();
    }
  };

  return (
    <div className="video-library">
      <SearchBar onSearch={handleSearch} />

      <AccordionItem title="Filter & Sort Options" startOpen={false}>
        <div className="filter-controls">
          <div className="filter-group">
            <label htmlFor="sort-by">Sort By:</label>
            <select id="sort-by" value={sortBy} onChange={(e) => setSortBy(e.target.value as SortField)}>
              <option value="processed_at">Processed Date</option>
              <option value="file_name">File Name</option>
              <option value="duration_seconds">Duration</option>
              <option value="created_at">Created Date</option>
            </select>
          </div>
          <div className="filter-group">
            <label htmlFor="sort-order">Order:</label>
            <select id="sort-order" value={sortOrder} onChange={(e) => setSortOrder(e.target.value as SortOrder)}>
              <option value="descending">Descending</option>
              <option value="ascending">Ascending</option>
            </select>
          </div>
          <div className="filter-group">
            <label htmlFor="date-start">Date Start:</label>
            <input type="date" id="date-start" value={dateStart} onChange={(e) => setDateStart(e.target.value)} />
          </div>
          <div className="filter-group">
            <label htmlFor="date-end">Date End:</label>
            <input type="date" id="date-end" value={dateEnd} onChange={(e) => setDateEnd(e.target.value)} />
          </div>
        </div>
      </AccordionItem>
      
      <div className="library-header">
        <h3>{currentSearchTerm ? `Search results for "${currentSearchTerm}"` : 'Browse Videos'}</h3>
        <button 
          onClick={handleRefresh} 
          className="refresh-button"
          title="Refresh"
        >
          <FiRefreshCw />
        </button>
      </div>
      
      <div className="video-grid">
        {loading && videos.length === 0 ? (
          <div className="loading-state">
            <div className="spinner"></div>
            <p>Loading videos...</p>
          </div>
        ) : videos.length > 0 ? (
          videos.map((video) => (
            <VideoCard key={video.id} video={video} onRefresh={handleRefresh} />
          ))
        ) : (
          <div className="empty-state">
            <FiFilm size={48} />
            <h3>No videos found</h3>
            <p>{currentSearchTerm ? 'Try a different search query or clear filters.' : 'Ingest some videos or clear filters.'}</p>
          </div>
        )}
      </div>
    </div>
  );
};

export default VideoLibrary;
