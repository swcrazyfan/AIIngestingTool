import React, { useState, useEffect } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { PlayCircle, Camera, Volume2, FileText, Settings, X, Image, Trash2 } from 'lucide-react';
import { FiPlay, FiFolder, FiSearch, FiInfo } from 'react-icons/fi';
import { VideoFile, TranscriptData, AnalysisData } from '../types/api';
import { clipsApi } from '../api/client';
import { formatDuration } from '../utils/format';
import AccordionItem from './AccordionItem';
import '../styles/Modal.scss';
import '../styles/VideoCard.scss';
import { thumbnailCache, CACHE_EXPIRATION } from './shared/ThumbnailCache';

interface VideoDetailsCardProps {
  video: VideoFile;
  onImport?: () => void;
  onAddToTimeline?: () => void;
  onFindSimilar?: () => void;
  onClose?: () => void;
  onDelete?: (clipId: string) => void;
}

interface ClipDetailsResponse {
  clip: VideoFile;
  transcript?: TranscriptData | null;
  analysis?: AnalysisData | null;
}

const parseCameraDetails = (clipData: any) => {
  // Check if camera_details is already a proper object
  if (clipData.camera_details && typeof clipData.camera_details === 'object') {
    return clipData.camera_details;
  }
  
  // If camera_details is a JSON string, parse it
  if (clipData.camera_details && typeof clipData.camera_details === 'string') {
    try {
      return JSON.parse(clipData.camera_details);
    } catch (e) {
      console.error('Failed to parse camera_details string:', e);
    }
  }
  
  // Create a default structure from legacy fields
  return {
    make: clipData.camera_make || null,
    model: clipData.camera_model || null,
    lens_model: clipData.lens_model || clipData.camera_lens || null,
    focal_length: {
      value_mm: clipData.focal_length || null,
      category: null
    },
    settings: {
      f_stop: clipData.f_stop || null,
      iso: clipData.iso || null,
      shutter_speed: clipData.shutter_speed || null,
      white_balance: clipData.white_balance || null,
      exposure_mode: clipData.exposure_mode || null
    }
  };
};

const fetchClipDetails = async (clipId: string | number): Promise<ClipDetailsResponse> => {
  try {
    // Use the API client instead of direct fetch
    const result = await clipsApi.getDetails(String(clipId));
    
    if (!result.clip) {
      throw new Error('Clip not found');
    }
    
    // Log the raw API response for debugging
    console.log("Raw API Response for clip:", JSON.stringify(result.clip, null, 2));
    
    // Get the clip object and ensure all properties are preserved
    const rawClip = result.clip;
    
    // Parse AI-selected thumbnails JSON if it exists
    let aiThumbnails = [];
    if (rawClip.ai_selected_thumbnails_json) {
      try {
        aiThumbnails = typeof rawClip.ai_selected_thumbnails_json === 'string' 
          ? JSON.parse(rawClip.ai_selected_thumbnails_json)
          : rawClip.ai_selected_thumbnails_json;
      } catch (e) {
        console.error('Failed to parse AI thumbnails JSON:', e);
        aiThumbnails = [];
      }
    }
    
    // Combine regular thumbnails and AI thumbnails into a unified structure
    const allThumbnailUrls: Array<{
      url: string;
      filename?: string;
      is_ai_selected: boolean;
      rank?: string | number | null;
      timestamp?: string | null;
      description?: string | null;
      reason?: string | null;
      index?: number;
    }> = [];
    
    // Add regular thumbnails (non-AI)
    if (rawClip.thumbnails && Array.isArray(rawClip.thumbnails)) {
      rawClip.thumbnails.forEach((thumbPath: string, index: number) => {
        // Skip AI thumbnails (they start with "AI_")
        const filename = thumbPath.split('/').pop() || '';
        if (!filename.startsWith('AI_')) {
          allThumbnailUrls.push({
            url: thumbPath,
            is_ai_selected: false,
            timestamp: null,
            rank: null,
            description: null,
            reason: null,
            index: index
          });
        }
      });
    }
    
    // Add AI-selected thumbnails
    if (aiThumbnails && Array.isArray(aiThumbnails)) {
      aiThumbnails.forEach((aiThumb: any, index: number) => {
        allThumbnailUrls.push({
          url: aiThumb.path,
          is_ai_selected: true,
          timestamp: aiThumb.timestamp,
          rank: aiThumb.rank,
          description: aiThumb.description,
          reason: aiThumb.reason,
          index: index
        });
      });
    }
    
    // Create a structured clip object preserving nested properties
    const clip: VideoFile = {
      ...rawClip,
      // Add the unified thumbnail structure
      all_thumbnail_urls: allThumbnailUrls,
      // Explicitly copy nested objects to ensure they're present
      camera_details: rawClip.camera_details,
      technical_metadata: rawClip.technical_metadata,
      audio_tracks: rawClip.audio_tracks
    };
    
    // Extract transcript and analysis from the API response
    const transcript = result.transcript || (clip.full_transcript ? {
      clip_id: String(clip.id),
      text: clip.full_transcript
    } : null);
    
    const analysis = result.analysis || {
      clip_id: String(clip.id),
      summary: clip.content_summary || undefined,
      tags: clip.content_tags || undefined
    };
    
    // Log the processed data for debugging
    console.log("Processed all_thumbnail_urls:", clip.all_thumbnail_urls);
    console.log("Processed camera_details:", clip.camera_details);
    console.log("Processed technical_metadata:", clip.technical_metadata);
    
    // Process nested JSON fields that might be stored as strings
    const processedClip = {
      ...clip,
      camera_details: parseCameraDetails(clip),
      technical_metadata: typeof clip.technical_metadata === 'string' 
        ? JSON.parse(clip.technical_metadata || '{}') 
        : (clip.technical_metadata || {}),
      audio_tracks: typeof clip.audio_tracks === 'string' 
        ? JSON.parse(clip.audio_tracks || '[]') 
        : (clip.audio_tracks || [])
    };
    
    return {
      clip: processedClip,
      transcript,
      analysis
    };
  } catch (error) {
    console.error('Error fetching clip details:', error);
    throw error;
  }
};

const VideoDetailsModal: React.FC<VideoDetailsCardProps> = ({ 
  video, 
  onImport, 
  onAddToTimeline, 
  onFindSimilar,
  onClose = () => {},
  onDelete
}) => {
  const [activeTab, setActiveTab] = useState('overview');
  const [mainThumbnailSrc, setMainThumbnailSrc] = useState<string | null>(null);
  const [thumbnailLoadErrors, setThumbnailLoadErrors] = useState<{[key: string]: boolean}>({});
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);

  const queryClient = useQueryClient();

  const { data, isLoading, error, isError } = useQuery<ClipDetailsResponse, Error>({
    queryKey: ['clipDetails', video.id],
    queryFn: () => fetchClipDetails(video.id),
    enabled: !!video.id,
  });

  // Load main thumbnail with caching
  useEffect(() => {
    const loadMainThumbnail = async () => {
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
              setMainThumbnailSrc(cache.objectUrl);
              return;
            }
            
            // If we have a blob but no object URL, create one
            if (cache.blob) {
              const objectUrl = URL.createObjectURL(cache.blob);
              thumbnailCache[clipId].objectUrl = objectUrl;
              setMainThumbnailSrc(objectUrl);
              return;
            }
          }
        }
        
        // Load main thumbnail via API proxy
        const apiUrl = `http://localhost:8001/api/thumbnail/${clipId}`;
        
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
        
        setMainThumbnailSrc(objectUrl);
      } catch (error) {
        console.error('Error loading main thumbnail:', error);
        setMainThumbnailSrc(null);
      }
    };
    
    loadMainThumbnail();
  }, [video.id]);

  const formatFileSize = (bytes: number | undefined | null): string => {
    if (bytes === null || typeof bytes === 'undefined') return 'N/A';
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  };

  const handleDelete = async () => {
    setIsDeleting(true);
    setDeleteError(null);
    
    try {
      const response = await fetch(`http://localhost:8001/api/clips/${video.id}`, {
        method: 'DELETE',
        headers: {
          'Content-Type': 'application/json',
        },
      });

      const result = await response.json();

      if (response.ok && result.success) {
        // Success - close modal and notify parent
        setShowDeleteConfirm(false);
        onClose();
        if (onDelete) {
          onDelete(video.id.toString());
        }
        
        // Invalidate queries to refresh the data
        queryClient.invalidateQueries({ queryKey: ['clipDetails', video.id] });
        queryClient.invalidateQueries({ queryKey: ['clips'] }); // Invalidate clips list if it exists
        
      } else {
        // Error from API
        setDeleteError(result.error || 'Failed to delete clip');
      }
    } catch (error) {
      console.error('Delete request failed:', error);
      setDeleteError('Network error: Failed to delete clip');
    } finally {
      setIsDeleting(false);
    }
  };

  const displayClip = data?.clip || video;

  // Helper function to get thumbnail URL through proxy
  const getThumbnailUrl = (thumbnailUrl: string, originalId: string) => {
    // If already an API URL or no ID provided, use as-is
    if (thumbnailUrl.includes('/api/thumbnail/') || !originalId) {
      return thumbnailUrl;
    }
    
    // Otherwise, route through our thumbnail proxy
    return `http://localhost:8001/api/thumbnail/${originalId}`;
  };

  // Add this near the beginning of the component function, after the useQuery hook
  useEffect(() => {
    if (data?.clip) {
      console.log("Camera details data:", {
        camera_details: data.clip.camera_details,
        camera_make: data.clip.camera_make,
        camera_model: data.clip.camera_model
      });
    }
  }, [data]);

  // Also log displayClip when it changes
  useEffect(() => {
    console.log("Display clip camera details:", {
      camera_details: displayClip.camera_details,
      camera_make: displayClip.camera_make,
      camera_model: displayClip.camera_model
    });
  }, [displayClip]);

  if (isLoading) {
    return (
      <div className="modal-overlay" onClick={onClose}>
        <div className="modal-content" onClick={(e) => e.stopPropagation()}>
          <div className="modal-header">
            <h2>Loading...</h2>
            <button onClick={onClose} className="close-button" title="Close modal" aria-label="Close">
              <X />
            </button>
          </div>
          <div className="modal-body">
            <div className="loading-state">
              <div className="spinner" />
              <p>Loading video details...</p>
            </div>
          </div>
        </div>
      </div>
    );
  }

  if (isError) {
    return (
      <div className="modal-overlay" onClick={onClose}>
        <div className="modal-content" onClick={(e) => e.stopPropagation()}>
          <div className="modal-header">
            <h2>Error</h2>
            <button onClick={onClose} className="close-button" title="Close modal" aria-label="Close">
              <X />
            </button>
          </div>
          <div className="modal-body">
            <div className="error-state">
              <p>Error loading video details: {error?.message || 'Unknown error'}</p>
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h2>{displayClip.file_name}</h2>
          <button onClick={onClose} className="close-button" title="Close modal" aria-label="Close">
            <X />
          </button>
        </div>

        <div className="modal-body">
          <p className="source-info">Video Metadata Analysis</p>
          
          <div className="video-info-header">
            <div className="video-title-section">
              <div className="video-icon">
                <PlayCircle size={32} />
              </div>
              <div>
                <h3>{displayClip.file_name}</h3>
              </div>
            </div>
            
            {/* Thumbnail Preview */}
            <div className="video-thumbnail">
              {mainThumbnailSrc ? (
                <img 
                  src={mainThumbnailSrc} 
                  alt={`${displayClip.file_name} thumbnail`} 
                  className="thumbnail-image"
                  onError={() => {
                    setMainThumbnailSrc(null);
                  }}
                />
              ) : (
                <div className="thumbnail-placeholder">
                  <span>{displayClip.file_name.substring(0, 1).toUpperCase()}</span>
                </div>
              )}
              <PlayCircle size={24} className="thumbnail-play-icon" />
            </div>
          </div>

          {/* Action Buttons */}
          <div className="video-actions">
            {onImport && (
              <button onClick={onImport} title="Import to Project">
                <FiFolder />
                <span>Import</span>
              </button>
            )}
            
            {onAddToTimeline && (
              <button onClick={onAddToTimeline} title="Add to Timeline">
                <FiPlay />
                <span>Timeline</span>
              </button>
            )}
            
            {onFindSimilar && (
              <button onClick={onFindSimilar} title="Find Similar">
                <FiSearch />
                <span>Similar</span>
              </button>
            )}
            
            <button 
              onClick={() => setShowDeleteConfirm(true)} 
              title="Delete Clip"
              className="delete-button"
              style={{
                backgroundColor: '#dc3545',
                color: 'white',
                border: 'none',
                borderRadius: '4px',
                padding: '8px 12px',
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: '4px',
                fontSize: '14px',
                fontWeight: '500',
                transition: 'background-color 0.2s'
              }}
              onMouseOver={(e) => e.currentTarget.style.backgroundColor = '#c82333'}
              onMouseOut={(e) => e.currentTarget.style.backgroundColor = '#dc3545'}
            >
              <Trash2 size={16} />
              <span>Delete</span>
            </button>
          </div>

          <div className="modal-tabs">
            <div
              className={`modal-tab ${activeTab === 'overview' ? 'active' : ''}`}
              onClick={() => setActiveTab('overview')}
            >
              <FileText size={16} />
              <span>Overview</span>
            </div>
            <div
              className={`modal-tab ${activeTab === 'thumbnails' ? 'active' : ''}`}
              onClick={() => setActiveTab('thumbnails')}
            >
              <Image size={16} />
              <span>Thumbnails</span>
            </div>
            <div
              className={`modal-tab ${activeTab === 'camera' ? 'active' : ''}`}
              onClick={() => setActiveTab('camera')}
            >
              <Camera size={16} />
              <span>Camera</span>
            </div>
            <div
              className={`modal-tab ${activeTab === 'audio' ? 'active' : ''}`}
              onClick={() => setActiveTab('audio')}
            >
              <Volume2 size={16} />
              <span>Audio</span>
            </div>
            <div
              className={`modal-tab ${activeTab === 'technical' ? 'active' : ''}`}
              onClick={() => setActiveTab('technical')}
            >
              <Settings size={16} />
              <span>Technical</span>
            </div>
          </div>

          {/* Content */}
          <div className="tab-content">
            {activeTab === 'overview' && (
              <div className="tab-pane">
                <div className="metadata-grid">
                  <div className="metadata-card">
                    <div className="metadata-value">
                      {formatDuration(displayClip.duration_seconds)}
                    </div>
                    <div className="metadata-label">Duration</div>
                  </div>
                  <div className="metadata-card">
                    <div className="metadata-value">
                      {displayClip.width && displayClip.height ? `${displayClip.width}x${displayClip.height}` : 'N/A'}
                    </div>
                    <div className="metadata-label">Resolution</div>
                  </div>
                  <div className="metadata-card">
                    <div className="metadata-value">
                      {formatFileSize(displayClip.file_size_bytes)}
                    </div>
                    <div className="metadata-label">File Size</div>
                  </div>
                  <div className="metadata-card">
                    <div className="metadata-value">
                      {displayClip.frame_rate ? `${parseFloat(String(displayClip.frame_rate)).toFixed(2)} fps` : 'N/A'}
                    </div>
                    <div className="metadata-label">Frame Rate</div>
                  </div>
                </div>

                {data?.analysis?.summary || displayClip.content_summary ? (
                  <AccordionItem title="AI Analysis Summary" startOpen={true}>
                    <p className="section-content">{data?.analysis?.summary || displayClip.content_summary}</p>
                  </AccordionItem>
                ) : null}

                {data?.transcript?.text || displayClip.full_transcript ? (
                  <AccordionItem title="Full Transcript" startOpen={false}>
                    <div className="full-transcript-text">
                      {data?.transcript?.text || displayClip.full_transcript}
                    </div>
                  </AccordionItem>
                ) : null}

                {(data?.analysis?.tags || displayClip.content_tags) && 
                  ((data?.analysis?.tags && data.analysis.tags.length > 0) || 
                   (displayClip.content_tags && displayClip.content_tags.length > 0)) && (
                  <div className="tag-list">
                    {(data?.analysis?.tags || displayClip.content_tags || []).map((tag, index) => (
                      <span key={index} className="tag">
                        {tag}
                      </span>
                    ))}
                  </div>
                )}
              </div>
            )}

            {activeTab === 'thumbnails' && (
              <div className="tab-pane">
                <h3 className="section-title">
                  <Image size={16} />
                  All Thumbnails
                </h3>
                
                {displayClip.all_thumbnail_urls && displayClip.all_thumbnail_urls.length > 0 ? (
                  <div className="thumbnail-gallery">
                    {displayClip.all_thumbnail_urls.map((thumbnail, index) => {
                      // Create unique key for this thumbnail
                      const thumbKey = `${displayClip.id}-${index}`;
                      // Check if we had a loading error for this thumbnail
                      const hasError = thumbnailLoadErrors[thumbKey];
                      
                      return (
                        <div 
                          key={thumbKey} 
                          className={`thumbnail-item ${thumbnail.is_ai_selected ? 'ai-selected' : ''}`}
                          title={thumbnail.is_ai_selected ? `${thumbnail.description || ''} ${thumbnail.reason || ''}` : ''}
                        >
                          {!hasError ? (
                            <img 
                              src={getThumbnailUrl(thumbnail.url, displayClip.id.toString())}
                              alt={`Thumbnail ${index + 1}`}
                              onError={() => {
                                setThumbnailLoadErrors(prev => ({
                                  ...prev,
                                  [thumbKey]: true
                                }));
                              }}
                            />
                          ) : (
                            <div className="thumbnail-placeholder">
                              <span>{index + 1}</span>
                            </div>
                          )}
                          {thumbnail.is_ai_selected && (
                            <div className="thumbnail-metadata">
                              <div className="ai-badge">AI #{thumbnail.rank}</div>
                              {thumbnail.timestamp && (
                                <div className="timestamp">{thumbnail.timestamp}</div>
                              )}
                              {thumbnail.description && (
                                <div className="description">{thumbnail.description}</div>
                              )}
                            </div>
                          )}
                        </div>
                      );
                    })}
                  </div>
                ) : (
                  <p className="no-thumbnails">No thumbnails available</p>
                )}
              </div>
            )}

            {activeTab === 'camera' && (
              <div className="tab-pane">
                <div className="metadata-rows">
                  <div className="metadata-row">
                    <div className="metadata-row-label"><Camera size={16} /> Make</div>
                    <div className="metadata-row-value">
                      {displayClip.camera_details && displayClip.camera_details.make 
                        ? displayClip.camera_details.make 
                        : (displayClip.camera_make || 'N/A')}
                    </div>
                  </div>
                  <div className="metadata-row">
                    <div className="metadata-row-label">Model</div>
                    <div className="metadata-row-value">
                      {displayClip.camera_details && displayClip.camera_details.model 
                        ? displayClip.camera_details.model 
                        : (displayClip.camera_model || 'N/A')}
                    </div>
                  </div>
                  <div className="metadata-row">
                    <div className="metadata-row-label">Lens</div>
                    <div className="metadata-row-value">
                      {displayClip.camera_details && displayClip.camera_details.lens_model 
                        ? displayClip.camera_details.lens_model 
                        : 'N/A'}
                    </div>
                  </div>
                  <div className="metadata-row">
                    <div className="metadata-row-label">Focal Length</div>
                    <div className="metadata-row-value">
                      {displayClip.camera_details && displayClip.camera_details.focal_length && displayClip.camera_details.focal_length.value_mm
                        ? `${displayClip.camera_details.focal_length.value_mm}mm`
                        : (displayClip.focal_length ? `${displayClip.focal_length}mm` : 'N/A')}
                    </div>
                  </div>
                  <div className="metadata-row">
                    <div className="metadata-row-label">Focal Length Category</div>
                    <div className="metadata-row-value">
                      {displayClip.camera_details && displayClip.camera_details.focal_length && displayClip.camera_details.focal_length.category
                        ? displayClip.camera_details.focal_length.category
                        : 'N/A'}
                    </div>
                  </div>
                  <div className="metadata-row">
                    <div className="metadata-row-label">Aperture</div>
                    <div className="metadata-row-value">
                      {displayClip.camera_details && displayClip.camera_details.settings && displayClip.camera_details.settings.f_stop
                        ? `f/${displayClip.camera_details.settings.f_stop}`
                        : (displayClip.f_stop ? `f/${displayClip.f_stop}` : 'N/A')}
                    </div>
                  </div>
                  <div className="metadata-row">
                    <div className="metadata-row-label">ISO</div>
                    <div className="metadata-row-value">
                      {displayClip.camera_details && displayClip.camera_details.settings && displayClip.camera_details.settings.iso 
                        ? displayClip.camera_details.settings.iso 
                        : (displayClip.iso || 'N/A')}
                    </div>
                  </div>
                  <div className="metadata-row">
                    <div className="metadata-row-label">Shutter Speed</div>
                    <div className="metadata-row-value">
                      {displayClip.camera_details && displayClip.camera_details.settings && displayClip.camera_details.settings.shutter_speed
                        ? `1/${Math.round(1/parseFloat(String(displayClip.camera_details.settings.shutter_speed)))}s`
                        : (displayClip.shutter_speed ? `1/${Math.round(1/parseFloat(String(displayClip.shutter_speed)))}s` : 'N/A')}
                    </div>
                  </div>
                  <div className="metadata-row">
                    <div className="metadata-row-label">White Balance</div>
                    <div className="metadata-row-value">
                      {displayClip.camera_details && displayClip.camera_details.settings && displayClip.camera_details.settings.white_balance
                        ? displayClip.camera_details.settings.white_balance
                        : (displayClip.white_balance || 'N/A')}
                    </div>
                  </div>
                  <div className="metadata-row">
                    <div className="metadata-row-label">Exposure Mode</div>
                    <div className="metadata-row-value">
                      {displayClip.camera_details && displayClip.camera_details.settings && displayClip.camera_details.settings.exposure_mode
                        ? displayClip.camera_details.settings.exposure_mode
                        : (displayClip.exposure_mode || 'N/A')}
                    </div>
                  </div>
                </div>
              </div>
            )}

            {activeTab === 'audio' && (
              <div className="tab-pane">
                <div className="metadata-rows">
                  {displayClip.audio_tracks && displayClip.audio_tracks.length > 0 ? (
                    // Show data from the first audio track
                    <>
                      <div className="metadata-row">
                        <div className="metadata-row-label"><Volume2 size={16} /> Codec</div>
                        <div className="metadata-row-value">
                          {displayClip.audio_tracks[0].codec || displayClip.audio_codec || 'N/A'}
                        </div>
                      </div>
                      <div className="metadata-row">
                        <div className="metadata-row-label">Bitrate</div>
                        <div className="metadata-row-value">
                          {displayClip.audio_tracks[0].bit_rate_kbps ? 
                            `${(displayClip.audio_tracks[0].bit_rate_kbps / 1000).toFixed(0)} kbps` : 
                            (displayClip.audio_bitrate ? `${displayClip.audio_bitrate} kbps` : 'N/A')}
                        </div>
                      </div>
                      <div className="metadata-row">
                        <div className="metadata-row-label">Channels</div>
                        <div className="metadata-row-value">
                          {displayClip.audio_tracks[0].channels || displayClip.audio_channels || 'N/A'}
                          {displayClip.audio_tracks[0].channel_layout && ` (${displayClip.audio_tracks[0].channel_layout})`}
                        </div>
                      </div>
                      <div className="metadata-row">
                        <div className="metadata-row-label">Sample Rate</div>
                        <div className="metadata-row-value">
                          {displayClip.audio_tracks[0].sample_rate ? 
                            `${displayClip.audio_tracks[0].sample_rate} Hz` : 
                            (displayClip.audio_sample_rate ? `${displayClip.audio_sample_rate} Hz` : 'N/A')}
                        </div>
                      </div>
                      <div className="metadata-row">
                        <div className="metadata-row-label">Bit Depth</div>
                        <div className="metadata-row-value">
                          {displayClip.audio_tracks[0].bit_depth ? 
                            `${displayClip.audio_tracks[0].bit_depth}-bit` : 'N/A'}
                        </div>
                      </div>
                      <div className="metadata-row">
                        <div className="metadata-row-label">Duration</div>
                        <div className="metadata-row-value">
                          {displayClip.audio_tracks[0].duration_seconds ? 
                            formatDuration(displayClip.audio_tracks[0].duration_seconds) : 
                            (displayClip.audio_duration_seconds ? formatDuration(displayClip.audio_duration_seconds) : 'N/A')}
                        </div>
                      </div>
                      <div className="metadata-row">
                        <div className="metadata-row-label">Language</div>
                        <div className="metadata-row-value">
                          {displayClip.audio_tracks[0].language || displayClip.audio_language || 'N/A'}
                        </div>
                      </div>
                    </>
                  ) : (
                    // Fallback to legacy fields if no audio_tracks
                    <>
                      <div className="metadata-row">
                        <div className="metadata-row-label"><Volume2 size={16} /> Codec</div>
                        <div className="metadata-row-value">{displayClip.audio_codec || 'N/A'}</div>
                      </div>
                      <div className="metadata-row">
                        <div className="metadata-row-label">Bitrate</div>
                        <div className="metadata-row-value">{displayClip.audio_bitrate ? `${displayClip.audio_bitrate} kbps` : 'N/A'}</div>
                      </div>
                      <div className="metadata-row">
                        <div className="metadata-row-label">Channels</div>
                        <div className="metadata-row-value">{displayClip.audio_channels || 'N/A'}</div>
                      </div>
                      <div className="metadata-row">
                        <div className="metadata-row-label">Sample Rate</div>
                        <div className="metadata-row-value">{displayClip.audio_sample_rate ? `${displayClip.audio_sample_rate} Hz` : 'N/A'}</div>
                      </div>
                      <div className="metadata-row">
                        <div className="metadata-row-label">Duration</div>
                        <div className="metadata-row-value">{displayClip.audio_duration_seconds ? formatDuration(displayClip.audio_duration_seconds) : 'N/A'}</div>
                      </div>
                      <div className="metadata-row">
                        <div className="metadata-row-label">Language</div>
                        <div className="metadata-row-value">{displayClip.audio_language || 'N/A'}</div>
                      </div>
                    </>
                  )}
                </div>
              </div>
            )}

            {activeTab === 'technical' && (
              <div className="tab-pane">
                <div className="metadata-rows">
                  <div className="metadata-row">
                    <div className="metadata-row-label"><Settings size={16} /> Container</div>
                    <div className="metadata-row-value">{displayClip.container || 'N/A'}</div>
                  </div>
                  <div className="metadata-row">
                    <div className="metadata-row-label">Video Codec</div>
                    <div className="metadata-row-value">{displayClip.codec || 'N/A'}</div>
                  </div>
                  <div className="metadata-row">
                    <div className="metadata-row-label">Color Space</div>
                    <div className="metadata-row-value">
                      {displayClip.technical_metadata?.color_details?.color_space || 'N/A'}
                    </div>
                  </div>
                  <div className="metadata-row">
                    <div className="metadata-row-label">Bit Depth</div>
                    <div className="metadata-row-value">
                      {displayClip.technical_metadata?.codec_details?.bit_depth 
                        ? `${displayClip.technical_metadata.codec_details.bit_depth}-bit` 
                        : 'N/A'}
                    </div>
                  </div>
                  <div className="metadata-row">
                    <div className="metadata-row-label">Profile</div>
                    <div className="metadata-row-value">
                      {displayClip.technical_metadata?.codec_details?.profile || 'N/A'}
                    </div>
                  </div>
                  <div className="metadata-row">
                    <div className="metadata-row-label">Level</div>
                    <div className="metadata-row-value">
                      {displayClip.technical_metadata?.codec_details?.level || 'N/A'}
                    </div>
                  </div>
                  <div className="metadata-row">
                    <div className="metadata-row-label">Scan Type</div>
                    <div className="metadata-row-value">
                      {displayClip.technical_metadata?.codec_details?.scan_type || 'N/A'}
                    </div>
                  </div>
                  <div className="metadata-row">
                    <div className="metadata-row-label">HDR Support</div>
                    <div className="metadata-row-value">
                      {displayClip.technical_metadata?.color_details?.hdr?.is_hdr ? 
                        (displayClip.technical_metadata.color_details.hdr.format || 'Yes') : 
                        'No'}
                    </div>
                  </div>
                  <div className="metadata-row">
                    <div className="metadata-row-label">File Path</div>
                    <div className="metadata-row-value">{displayClip.local_path || 'N/A'}</div>
                  </div>
                </div>
              </div>
            )}
          </div>

          {/* Add this debug section at the end of the tab-content div */}
          {activeTab === 'technical' && (
            <details className="debug-data" style={{ marginTop: '20px', fontSize: '12px', fontFamily: 'monospace' }}>
              <summary>Debug Data</summary>
              <pre style={{ maxHeight: '200px', overflow: 'auto' }}>
                {JSON.stringify({
                  id: displayClip.id,
                  camera_details: displayClip.camera_details,
                  technical_metadata: displayClip.technical_metadata,
                  audio_tracks: displayClip.audio_tracks
                }, null, 2)}
              </pre>
            </details>
          )}

          {activeTab === 'camera' && (
            <details className="debug-data" style={{ marginTop: '20px', fontSize: '12px', fontFamily: 'monospace' }}>
              <summary>Camera Data Debug</summary>
              <div style={{ background: '#222', padding: '10px', borderRadius: '4px' }}>
                <p><strong>Raw camera_details type:</strong> {displayClip.camera_details ? typeof displayClip.camera_details : 'undefined'}</p>
                <p><strong>camera_make:</strong> {displayClip.camera_make}</p>
                <p><strong>camera_model:</strong> {displayClip.camera_model}</p>
                <pre style={{ maxHeight: '200px', overflow: 'auto' }}>
                  {JSON.stringify(displayClip.camera_details, null, 2)}
                </pre>
              </div>
            </details>
          )}
        </div>
      </div>

      {/* Delete Confirmation Dialog */}
      {showDeleteConfirm && (
        <div className="modal-overlay" style={{ zIndex: 1001 }}>
          <div className="modal-content" style={{ maxWidth: '400px', padding: '20px' }}>
            <div className="modal-header">
              <h3 style={{ color: '#dc3545', margin: 0 }}>Confirm Deletion</h3>
              <button 
                onClick={() => {
                  setShowDeleteConfirm(false);
                  setDeleteError(null);
                }} 
                className="close-button" 
                title="Cancel" 
                aria-label="Cancel"
              >
                <X />
              </button>
            </div>
            
            <div className="modal-body">
              <p style={{ marginBottom: '16px' }}>
                Are you sure you want to delete this clip?
              </p>
              
              <div style={{ 
                backgroundColor: '#f8f9fa', 
                padding: '12px', 
                borderRadius: '4px', 
                marginBottom: '16px',
                border: '1px solid #dee2e6'
              }}>
                <p style={{ margin: '0 0 4px 0', fontWeight: '500' }}>
                  {displayClip.file_name}
                </p>
                <p style={{ margin: 0, fontSize: '14px', color: '#6c757d' }}>
                  Duration: {formatDuration(displayClip.duration_seconds)} • 
                  Size: {formatFileSize(displayClip.file_size_bytes)}
                </p>
              </div>
              
              {deleteError && (
                <div style={{
                  backgroundColor: '#f8d7da',
                  color: '#721c24',
                  padding: '8px 12px',
                  borderRadius: '4px',
                  marginBottom: '16px',
                  border: '1px solid #f5c6cb',
                  fontSize: '14px'
                }}>
                  {deleteError}
                </div>
              )}
              
              <div style={{ 
                display: 'flex', 
                gap: '12px', 
                justifyContent: 'flex-end',
                marginTop: '20px'
              }}>
                <button
                  onClick={() => {
                    setShowDeleteConfirm(false);
                    setDeleteError(null);
                  }}
                  disabled={isDeleting}
                  style={{
                    backgroundColor: '#6c757d',
                    color: 'white',
                    border: 'none',
                    borderRadius: '4px',
                    padding: '8px 16px',
                    cursor: isDeleting ? 'not-allowed' : 'pointer',
                    fontSize: '14px',
                    opacity: isDeleting ? 0.6 : 1
                  }}
                >
                  Cancel
                </button>
                
                <button
                  onClick={handleDelete}
                  disabled={isDeleting}
                  style={{
                    backgroundColor: '#dc3545',
                    color: 'white',
                    border: 'none',
                    borderRadius: '4px',
                    padding: '8px 16px',
                    cursor: isDeleting ? 'not-allowed' : 'pointer',
                    fontSize: '14px',
                    fontWeight: '500',
                    opacity: isDeleting ? 0.6 : 1,
                    display: 'flex',
                    alignItems: 'center',
                    gap: '4px'
                  }}
                >
                  {isDeleting ? (
                    <>
                      <div style={{
                        width: '16px',
                        height: '16px',
                        border: '2px solid #ffffff',
                        borderTop: '2px solid transparent',
                        borderRadius: '50%',
                        animation: 'spin 1s linear infinite'
                      }} />
                      Deleting...
                    </>
                  ) : (
                    <>
                      <Trash2 size={16} />
                      Delete
                    </>
                  )}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default VideoDetailsModal;