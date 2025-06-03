import React, { useState, useEffect, useCallback } from 'react';
import { searchApi, videosApi } from '../api/client';
import { VideoFile, SearchType, SortField, SortOrder } from '../types/api';
import VideoCard from './VideoCard';
import SearchBar from './SearchBar';
import AccordionItem from './AccordionItem';
import { evalTS } from '../lib/utils/bolt';
import { 
  FiSearch, FiGrid, FiList, FiFilter, FiTag, FiMapPin, FiCamera, FiStar, 
  FiEye, FiShuffle, FiGlobe, FiInfo, FiMic, FiChevronDown, FiChevronUp, 
  FiBookmark, FiPlus, FiSettings, FiClock, FiVideo, FiRefreshCw, FiFilm,
  FiFolder, FiTrendingUp, FiActivity, FiHeart, FiPlay, FiSquare
} from 'react-icons/fi';
import { BsGrid3X3, BsGrid3X2, BsGrid1X2, BsGrid } from 'react-icons/bs';
import '../styles/VideoLibrary.scss';

// Define card size type and view mode
export type CardSize = 'small' | 'medium' | 'large';
export type ViewMode = 'tiles' | 'rows';

const VideoLibrary: React.FC = () => {
  const [videos, setVideos] = useState<VideoFile[]>([]);
  const [originalFetchedVideos, setOriginalFetchedVideos] = useState<VideoFile[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [currentSearchTerm, setCurrentSearchTerm] = useState('');
  const [activeSearchType, setActiveSearchType] = useState<SearchType>('hybrid');
  const [sortBy, setSortBy] = useState<SortField>('processed_at');
  const [sortOrder, setSortOrder] = useState<SortOrder>('descending');
  const [dateStart, setDateStart] = useState<string>('');
  const [dateEnd, setDateEnd] = useState<string>('');
  const [cardSize, setCardSize] = useState<CardSize>('small');
  const [viewMode, setViewMode] = useState<ViewMode>('tiles');
  const [showAdvancedFilters, setShowAdvancedFilters] = useState(false);
  const [selectedFilter, setSelectedFilter] = useState<string>('all');

  // Load videos function
  const loadVideoData = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      
      const result = await videosApi.list({ 
        sortBy, 
        sortOrder, 
        limit: 50 
      });
      
      let filteredVideos = result.results || [];
      
      // Apply client-side filtering based on selectedFilter
      if (selectedFilter === 'recent') {
        // Show videos from the last 7 days
        const sevenDaysAgo = new Date();
        sevenDaysAgo.setDate(sevenDaysAgo.getDate() - 7);
        
        filteredVideos = filteredVideos.filter(video => {
          const videoDate = new Date(video.processed_at || video.created_at_timestamp || '');
          return videoDate >= sevenDaysAgo;
        });
      }
      
      // Apply date range filtering if dates are set
      if (dateStart || dateEnd) {
        filteredVideos = filteredVideos.filter(video => {
          const videoDate = new Date(video.processed_at || video.created_at_timestamp || '');
          
          if (dateStart && videoDate < new Date(dateStart)) {
            return false;
          }
          
          if (dateEnd) {
            const endDate = new Date(dateEnd);
            endDate.setHours(23, 59, 59, 999); // Include the entire end date
            if (videoDate > endDate) {
              return false;
            }
          }
          
          return true;
        });
      }
      
      setVideos(filteredVideos);
      setOriginalFetchedVideos(result.results || []);
    } catch (error: any) {
      console.error('Failed to load videos:', error);
      setError(error.message || 'Failed to load videos');
      setVideos([]);
    } finally {
      setLoading(false);
    }
  }, [sortBy, sortOrder, selectedFilter, dateStart, dateEnd]);

  // Load data on mount
  useEffect(() => {
    loadVideoData();
  }, [loadVideoData]);

  // Handle search
  const handleSearch = async (query: string, type: SearchType) => {
    setCurrentSearchTerm(query);
    setActiveSearchType(type);
    
    if (query.trim()) {
      try {
        setLoading(true);
        setError(null);
        
        // Perform actual search using the API
        const searchResult = await searchApi.search(query, type, 50);
        setVideos(searchResult.results || []);
      } catch (error: any) {
        console.error('Search failed:', error);
        setError(error.message || 'Search failed');
        setVideos([]);
      } finally {
        setLoading(false);
      }
    } else {
      // If query is empty, reload all videos
      loadVideoData();
    }
  };

  // Handle refresh
  const handleRefresh = () => {
    if (refreshing) return;
    setRefreshing(true);
    
    // If there's an active search, re-run the search
    if (currentSearchTerm.trim()) {
      handleSearch(currentSearchTerm, activeSearchType).finally(() => {
        setRefreshing(false);
      });
    } else {
      // Otherwise reload all videos
      loadVideoData().finally(() => {
        setRefreshing(false);
      });
    }
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

      {/* View Controls */}
      <div className="view-controls">
        <div className="view-mode-controls">
          <button
            className={`view-mode-button ${viewMode === 'tiles' ? 'active' : ''}`}
            onClick={() => setViewMode('tiles')}
            title="Grid View"
          >
            <FiGrid />
          </button>
          <button
            className={`view-mode-button ${viewMode === 'rows' ? 'active' : ''}`}
            onClick={() => setViewMode('rows')}
            title="List View"
          >
            <FiList />
          </button>
        </div>
        
        {viewMode === 'tiles' && (
          <div className="size-controls">
            <button
              className={`size-button ${cardSize === 'small' ? 'active' : ''}`}
              onClick={() => setCardSize('small')}
              data-size="S"
              title="Small cards"
            >
              <BsGrid3X3 />
            </button>
            <button
              className={`size-button ${cardSize === 'medium' ? 'active' : ''}`}
              onClick={() => setCardSize('medium')}
              data-size="M"
              title="Medium cards"
            >
              <BsGrid />
            </button>
            <button
              className={`size-button ${cardSize === 'large' ? 'active' : ''}`}
              onClick={() => setCardSize('large')}
              data-size="L"
              title="Large cards"
            >
              <FiSquare />
            </button>
          </div>
        )}
        
        <button
          className={`refresh-button ${refreshing ? 'refreshing' : ''}`}
          onClick={handleRefresh}
          disabled={refreshing}
          title="Refresh Library"
        >
          <FiRefreshCw />
        </button>
      </div>

      {/* Error display */}
      {error && (
        <div className="error-message">
          <p>{error}</p>
          <button onClick={() => {
            setError(null);
            if (currentSearchTerm.trim()) {
              handleSearch(currentSearchTerm, activeSearchType);
            } else {
              loadVideoData();
            }
          }}>
            Retry
          </button>
        </div>
      )}

      {/* Advanced Filters - Now toggled by button */}
      {showAdvancedFilters && (
        <div className="advanced-filters-container">
          <div className="filter-controls">
            <div className="filter-group">
              <label>Sort By:</label>
              <select 
                value={sortBy} 
                onChange={(e) => setSortBy(e.target.value as SortField)}
                title="Select sort criteria"
              >
                <option value="processed_at">Recently Processed</option>
                <option value="created_at">Date Created</option>
                <option value="file_name">File Name</option>
                <option value="duration_seconds">Duration</option>
              </select>
            </div>
            
            <div className="filter-group">
              <label>Order:</label>
              <select 
                value={sortOrder} 
                onChange={(e) => setSortOrder(e.target.value as SortOrder)}
                title="Select sort order"
              >
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
            
            <button className="apply-filters-button" onClick={() => {
              // Clear search term when applying filters
              setCurrentSearchTerm('');
              loadVideoData();
            }}>
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
            className={`collection-card ${selectedFilter === 'all' ? 'active' : ''}`}
            onClick={() => setSelectedFilter('all')}
          >
            <FiGrid />
            <span>All Videos</span>
          </button>
        </div>
      </AccordionItem>

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