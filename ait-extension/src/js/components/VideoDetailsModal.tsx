import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { PlayCircle, Camera, Volume2, FileText, Settings, X } from 'lucide-react';
import { FiPlay, FiFolder, FiSearch } from 'react-icons/fi';
import { VideoFile } from '../types/api';
import { formatDuration } from '../utils/format';
import '../styles/Modal.scss';

interface VideoDetailsCardProps {
  video: VideoFile;
  onImport?: () => void;
  onAddToTimeline?: () => void;
  onFindSimilar?: () => void;
  onClose?: () => void;
}

interface ClipDetailsResponse {
  clip: VideoFile;
  transcript: {
    id?: number;
    clip_id?: string;
    full_text?: string;
  } | null;
  analysis: {
    id?: number;
    clip_id?: string;
    summary?: string;
    tags?: string[];
  } | null;
}

const fetchClipDetails = async (clipId: string | number): Promise<ClipDetailsResponse> => {
  const response = await fetch(`http://localhost:8000/api/clips/${clipId}`);
  if (!response.ok) {
    const errorData = await response.json().catch(() => ({ message: 'Network response was not ok and failed to parse error JSON.' }));
    throw new Error(errorData.message || 'Network response was not ok');
  }
  return response.json();
};

const VideoDetailsModal: React.FC<VideoDetailsCardProps> = ({ 
  video, 
  onImport, 
  onAddToTimeline, 
  onFindSimilar,
  onClose = () => {} // Provide a default empty function
}) => {
  const [activeTab, setActiveTab] = useState('overview');

  const { data, isLoading, error, isError } = useQuery<ClipDetailsResponse, Error>({
    queryKey: ['clipDetails', video.id],
    queryFn: () => fetchClipDetails(video.id),
    enabled: !!video.id,
  });

  const formatFileSize = (bytes: number | undefined | null): string => {
    if (bytes === null || typeof bytes === 'undefined') return 'N/A';
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  };

  const displayClip = data?.clip || video;

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
              {displayClip.thumbnail_path ? (
                <img 
                  src={`http://localhost:8000/api/thumbnail/${displayClip.id}`} 
                  alt={`${displayClip.file_name} thumbnail`} 
                  className="thumbnail-image"
                  onError={(e) => {
                    const target = e.currentTarget;
                    target.style.display = 'none';
                    const nextSibling = target.nextElementSibling as HTMLElement;
                    if (nextSibling) {
                      nextSibling.style.display = 'flex';
                    }
                  }}
                />
              ) : null}
              <PlayCircle size={24} className="thumbnail-play-icon" />
            </div>
          </div>

          {/* Action Buttons */}
          <div className="action-buttons">
            <button className="action-button action-button-blue" onClick={onImport}>
              <FiFolder />
              <span>Import</span>
            </button>
            <button className="action-button action-button-green" onClick={onAddToTimeline}>
              <FiPlay />
              <span>Timeline</span>
            </button>
            <button className="action-button action-button-purple" onClick={onFindSimilar}>
              <FiSearch />
              <span>Similar</span>
            </button>
          </div>

          {/* Navigation Tabs */}
          <div className="modal-tabs">
            <div
              className={`modal-tab ${activeTab === 'overview' ? 'active' : ''}`}
              onClick={() => setActiveTab('overview')}
            >
              <FileText size={16} />
              <span>Overview</span>
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

                {data?.analysis?.summary && (
                  <div className="analysis-section">
                    <h3 className="section-title">
                      <FileText size={16} />
                      AI Analysis Summary
                    </h3>
                    <p className="section-content">{data.analysis.summary}</p>
                  </div>
                )}

                {data?.transcript?.full_text && (
                  <div className="analysis-section">
                    <h3 className="section-title">
                      <FileText size={16} />
                      Transcript
                    </h3>
                    <p className="section-content transcript">
                      "{data.transcript.full_text.length > 200 
                        ? data.transcript.full_text.substring(0, 200) + '...' 
                        : data.transcript.full_text}"
                    </p>
                  </div>
                )}

                {data?.analysis?.tags && data.analysis.tags.length > 0 && (
                  <div className="tag-list">
                    {data.analysis.tags.map((tag, index) => (
                      <span key={index} className="tag">
                        {tag}
                      </span>
                    ))}
                  </div>
                )}
              </div>
            )}

            {activeTab === 'camera' && (
              <div className="tab-pane">
                <div className="metadata-rows">
                  <div className="metadata-row">
                    <div className="metadata-row-label"><Camera size={16} /> Make</div>
                    <div className="metadata-row-value">{displayClip.camera_make || 'N/A'}</div>
                  </div>
                  <div className="metadata-row">
                    <div className="metadata-row-label">Model</div>
                    <div className="metadata-row-value">{displayClip.camera_model || 'N/A'}</div>
                  </div>
                  <div className="metadata-row">
                    <div className="metadata-row-label">Lens</div>
                    <div className="metadata-row-value">{displayClip.lens_model || 'N/A'}</div>
                  </div>
                  <div className="metadata-row">
                    <div className="metadata-row-label">Focal Length</div>
                    <div className="metadata-row-value">{displayClip.focal_length ? `${displayClip.focal_length}mm` : 'N/A'}</div>
                  </div>
                  <div className="metadata-row">
                    <div className="metadata-row-label">Aperture</div>
                    <div className="metadata-row-value">{displayClip.f_stop ? `f/${displayClip.f_stop}` : 'N/A'}</div>
                  </div>
                  <div className="metadata-row">
                    <div className="metadata-row-label">ISO</div>
                    <div className="metadata-row-value">{displayClip.iso || 'N/A'}</div>
                  </div>
                  <div className="metadata-row">
                    <div className="metadata-row-label">Shutter Speed</div>
                    <div className="metadata-row-value">{displayClip.shutter_speed ? `1/${Math.round(1/parseFloat(String(displayClip.shutter_speed)))}s` : 'N/A'}</div>
                  </div>
                  <div className="metadata-row">
                    <div className="metadata-row-label">White Balance</div>
                    <div className="metadata-row-value">{displayClip.white_balance || 'N/A'}</div>
                  </div>
                  <div className="metadata-row">
                    <div className="metadata-row-label">Exposure Mode</div>
                    <div className="metadata-row-value">{displayClip.exposure_mode || 'N/A'}</div>
                  </div>
                </div>
              </div>
            )}

            {activeTab === 'audio' && (
              <div className="tab-pane">
                <div className="metadata-rows">
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
                </div>
              </div>
            )}

            {activeTab === 'technical' && (
              <div className="tab-pane">
                <div className="metadata-rows">
                  <div className="metadata-row">
                    <div className="metadata-row-label"><Settings size={16} /> Container</div>
                    <div className="metadata-row-value">{displayClip.container_format || 'N/A'}</div>
                  </div>
                  <div className="metadata-row">
                    <div className="metadata-row-label">Video Codec</div>
                    <div className="metadata-row-value">{displayClip.video_codec || 'N/A'}</div>
                  </div>
                  <div className="metadata-row">
                    <div className="metadata-row-label">Color Space</div>
                    <div className="metadata-row-value">{displayClip.color_space || 'N/A'}</div>
                  </div>
                  <div className="metadata-row">
                    <div className="metadata-row-label">Bit Depth</div>
                    <div className="metadata-row-value">{displayClip.bit_depth ? `${displayClip.bit_depth}-bit` : 'N/A'}</div>
                  </div>
                  <div className="metadata-row">
                    <div className="metadata-row-label">Profile</div>
                    <div className="metadata-row-value">{displayClip.codec_profile || 'N/A'}</div>
                  </div>
                  <div className="metadata-row">
                    <div className="metadata-row-label">Level</div>
                    <div className="metadata-row-value">{displayClip.codec_level || 'N/A'}</div>
                  </div>
                  <div className="metadata-row">
                    <div className="metadata-row-label">Scan Type</div>
                    <div className="metadata-row-value">{displayClip.scan_type || 'N/A'}</div>
                  </div>
                  <div className="metadata-row">
                    <div className="metadata-row-label">HDR Support</div>
                    <div className="metadata-row-value">{displayClip.hdr_format || 'No'}</div>
                  </div>
                  <div className="metadata-row">
                    <div className="metadata-row-label">File Path</div>
                    <div className="metadata-row-value">{displayClip.local_path || 'N/A'}</div>
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

export default VideoDetailsModal;