import React, { useState, useEffect, useCallback, useRef } from 'react';
import { searchApi, videosApi } from '../api/client';
import { VideoFile, SearchType, SortField, SortOrder } from '../types/api';
import { useAuth } from '../contexts/AuthContext';
import VideoCard from './VideoCard';
import SearchBar from './SearchBar';
import AccordionItem from './AccordionItem';
import { 
  FiSearch, FiGrid, FiList, FiFilter, FiTag, FiMapPin, FiCamera, FiStar, 
  FiEye, FiShuffle, FiGlobe, FiInfo, FiMic, FiChevronDown, FiChevronUp, 
  FiBookmark, FiPlus, FiSettings, FiClock, FiVideo, FiRefreshCw, FiFilm,
  FiFolder, FiTrendingUp, FiActivity, FiHeart, FiPlay
} from 'react-icons/fi';
import { BsGrid3X3, BsGrid3X2, BsGrid1X2 } from 'react-icons/bs';
import { useWebSocket } from '../contexts/WebSocketContext';
import '../styles/VideoLibrary.scss';

// Define card size type and view mode
export type CardSize = 'small' | 'medium' | 'large';
export type ViewMode = 'tiles' | 'rows';

const VideoLibrary: React.FC = () => {
  const { authStatus } = useAuth();
  const isGuestMode = !authStatus?.authenticated;
  
  const [videos, setVideos] = useState<VideoFile[]>([]);
  const [originalFetchedVideos, setOriginalFetchedVideos] = useState<VideoFile[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [currentSearchTerm, setCurrentSearchTerm] = useState('');
  const [activeSearchType, setActiveSearchType] = useState<SearchType>('hybrid');
  const [sortBy, setSortBy] = useState<SortField>('processed_at');
  const [sortOrder, setSortOrder] = useState<SortOrder>('descending');
  const [dateStart, setDateStart] = useState<string>('');
  const [dateEnd, setDateEnd] = useState<string>('');
  const [cardSize, setCardSize] = useState<CardSize>('medium');
  const [viewMode, setViewMode] = useState<ViewMode>('tiles');
  const [showAdvancedFilters, setShowAdvancedFilters] = useState(false); // New state for filter button
  const [selectedFilter, setSelectedFilter] = useState<string>('all'); // Combined state

  const { search: wsSearch, connected } = useWebSocket();

  // Load videos function
  const loadVideoData = useCallback(async () => {
    try {
      setLoading(true);
      const result = await videosApi.list({ 
        sortBy, 
        sortOrder, 
        limit: 50 
      });
      setVideos(result.results || []);
      setOriginalFetchedVideos(result.results || []);
    } catch (error) {
      console.error('Failed to load videos:', error);
      setVideos([]);
    } finally {
      setLoading(false);
    }
  }, [sortBy, sortOrder, selectedFilter]);

  // Load data on mount
  useEffect(() => {
    loadVideoData();
  }, [loadVideoData]);

  // Handle search
  const handleSearch = (query: string, type: SearchType) => {
    setCurrentSearchTerm(query);
    setActiveSearchType(type);
    
    if (query.trim()) {
      // Perform search logic here
      console.log('Searching for:', query, 'with type:', type);
    } else {
      loadVideoData();
    }
  };

  // Handle refresh
  const handleRefresh = () => {
    if (refreshing) return;
    setRefreshing(true);
    setTimeout(() => {
      loadVideoData();
      setRefreshing(false);
    }, 1000);
  };

  return (
    <div className="video-library">
      <div className="search-bar-container">
        <SearchBar onSearch={handleSearch} />
        <button
          className={`filter-toggle-button ${showAdvancedFilters ? 'active' : ''}`}
          onClick={() => setShowAdvancedFilters(!showAdvancedFilters)}
          title="Toggle Advanced Filters"
        >
          <FiFilter />
        </button>
      </div>

      {/* Advanced Filters - Now toggled by button */}
      {showAdvancedFilters && (
        <div className="advanced-filters-container">
          <div className="filter-controls">
            <div className="filter-group">
              <label>Sort By:</label>
              <select value={sortBy} onChange={(e) => setSortBy(e.target.value as SortField)}>
                <option value="processed_at">Recently Processed</option>
                <option value="created_at">Date Created</option>
                <option value="file_name">File Name</option>
                <option value="duration_seconds">Duration</option>
              </select>
            </div>
            
            <div className="filter-group">
              <label>Order:</label>
              <select value={sortOrder} onChange={(e) => setSortOrder(e.target.value as SortOrder)}>
                <option value="descending">Newest First</option>
                <option value="ascending">Oldest First</option>
              </select>
            </div>
            
            <div className="filter-group">
              <label>Date Range:</label>
              <input
                type="date"
                value={dateStart}
                onChange={(e) => setDateStart(e.target.value)}
                placeholder="Start Date"
              />
              <input
                type="date"
                value={dateEnd}
                onChange={(e) => setDateEnd(e.target.value)}
                placeholder="End Date"
              />
            </div>
            
            <button className="apply-filters-button" onClick={loadVideoData}>
              Apply Filters
            </button>
          </div>
        </div>
      )}

      {/* Combined Collections & Categories */}
      <AccordionItem title="Collections & Categories" startOpen={false}>
        <div className="collections-grid">
          {/* Smart Collections */}
          <button
            className={`collection-card ${selectedFilter === 'recent' ? 'active' : ''}`}
            onClick={() => setSelectedFilter('recent')}
          >
            <FiClock />
            <span>Recently Added</span>
          </button>
          <button
            className={`collection-card ${selectedFilter === 'favorites' ? 'active' : ''}`}
            onClick={() => setSelectedFilter('favorites')}
          >
            <FiHeart />
            <span>Favorites</span>
          </button>
          <button
            className={`collection-card ${selectedFilter === 'untagged' ? 'active' : ''}`}
            onClick={() => setSelectedFilter('untagged')}
          >
            <FiTag />
            <span>Untagged</span>
          </button>
          <button
            className={`collection-card ${selectedFilter === 'hdr' ? 'active' : ''}`}
            onClick={() => setSelectedFilter('hdr')}
          >
            <FiStar />
            <span>HDR Content</span>
          </button>
          {/* Categories */}
          <button
            className={`collection-card ${selectedFilter === 'all' ? 'active' : ''}`}
            onClick={() => setSelectedFilter('all')}
          >
            <FiGrid />
            <span>All Videos</span>
          </button>
          <button
            className={`collection-card ${selectedFilter === 'camera' ? 'active' : ''}`}
            onClick={() => setSelectedFilter('camera')}
          >
            <FiCamera />
            <span>Camera Footage</span>
          </button>
          <button
            className={`collection-card ${selectedFilter === 'screen' ? 'active' : ''}`}
            onClick={() => setSelectedFilter('screen')}
          >
            <FiActivity />
            <span>Screen Recordings</span>
          </button>
          <button
            className={`collection-card ${selectedFilter === 'ai' ? 'active' : ''}`}
            onClick={() => setSelectedFilter('ai')}
          >
            <FiTrendingUp />
            <span>AI Generated</span>
          </button>
        </div>
      </AccordionItem>

      {/* Controls */}
      <div className="library-header">
        <h3>Videos ({videos.length})</h3>
        <div className="library-controls">
          {/* View Mode Toggle */}
          <div className="view-toggle">
            <button
              className={`view-button ${viewMode === 'tiles' ? 'active' : ''}`}
              onClick={() => setViewMode('tiles')}
              title="Tiles View"
            >
              <BsGrid3X3 />
            </button>
            <button
              className={`view-button ${viewMode === 'rows' ? 'active' : ''}`}
              onClick={() => setViewMode('rows')}
              title="Rows View"
            >
              <FiList />
            </button>
          </div>

          {/* Card Size Selector (only for tiles) */}
          {viewMode === 'tiles' && (
            <div className="card-size-selector">
              <button
                className={`size-button ${cardSize === 'small' ? 'active' : ''}`}
                onClick={() => setCardSize('small')}
                data-size="S"
              >
                <BsGrid3X3 />
              </button>
              <button
                className={`size-button ${cardSize === 'medium' ? 'active' : ''}`}
                onClick={() => setCardSize('medium')}
                data-size="M"
              >
                <BsGrid3X2 />
              </button>
              <button
                className={`size-button ${cardSize === 'large' ? 'active' : ''}`}
                onClick={() => setCardSize('large')}
                data-size="L"
              >
                <BsGrid1X2 />
              </button>
            </div>
          )}

          {/* Refresh Button */}
          <button className="refresh-button" onClick={handleRefresh} disabled={refreshing}>
            <FiRefreshCw className={refreshing ? 'refreshing' : ''} />
          </button>
        </div>
      </div>

      {/* Video Grid/List */}
      {loading ? (
        <div className="loading-state">
          <div className="spinner" />
          <h3>Loading Videos</h3>
          <p>Getting your video library...</p>
        </div>
      ) : videos.length > 0 ? (
        <div className={`video-container ${viewMode === 'tiles' 
          ? `video-grid video-grid-${cardSize}` 
          : 'video-rows'
        }`}>
          {videos.map((video) => (
            <VideoCard 
              key={video.id} 
              video={video} 
              onRefresh={handleRefresh}
              size={cardSize}
              viewMode={viewMode}
            />
          ))}
        </div>
      ) : (
        <div className="empty-state">
          <FiVideo />
          <h3>No Videos Found</h3>
          <p>
            {currentSearchTerm 
              ? `No videos match "${currentSearchTerm}". Try a different search term.`
              : 'Process some videos to see them appear here.'
            }
          </p>
        </div>
      )}
    </div>
  );
};

export default VideoLibrary;
