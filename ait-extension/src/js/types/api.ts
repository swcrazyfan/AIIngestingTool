// Type declarations for AI Ingest Tool API

export interface IngestOptions {
  recursive?: boolean;
  ai_analysis?: boolean;
  generate_embeddings?: boolean;
  store_database?: boolean;
  force_reprocess?: boolean;
}

export type SearchType = 'semantic' | 'fulltext' | 'hybrid' | 'transcripts' | 'similar' | 'recent';

export type SortField = "processed_at" | "file_name" | "duration_seconds" | "created_at";
export type SortOrder = "ascending" | "descending";

export interface VideoFile {
  id: string | number;
  file_name: string;
  file_path: string;
  local_path: string;
  duration_seconds: number;
  content_summary?: string | null;
  content_tags?: string[] | null;
  camera_make?: string | null;
  camera_model?: string | null;
  content_category?: string;
  processed_at: string;
  transcript_preview?: string;
  similarity_score?: number;
  search_rank?: number;
  thumbnail_path?: string | null;
  width?: number | null;
  height?: number | null;
  frame_rate?: string | number | null; 
  file_size_bytes?: number | null;
  created_at_timestamp?: string | null; 
  audio_tracks?: any[]; 
  video_tracks?: any[]; 

  // New fields from the design example
  codec?: string | null; // e.g., "avc1" (video codec)
  container?: string | null; // e.g., "MPEG-4"

  // Detailed camera info
  lens_model?: string | null;
  focal_length?: string | number | null;
  f_stop?: string | number | null;
  iso?: string | number | null;
  shutter_speed?: string | number | null;
  white_balance?: string | null;
  exposure_mode?: string | null;

  // Detailed audio info
  audio_codec?: string | null; // e.g., "AAC"
  audio_bitrate?: string | number | null; // e.g., "256" or "256 kbps"
  audio_channels?: string | number | null; // e.g., "Stereo" or 2
  audio_sample_rate?: string | number | null; // e.g., "48 kHz" or 48000
  audio_duration_seconds?: number | null;
  audio_language?: string | null;

  // Technical details
  container_format?: string | null;
  video_codec?: string | null;
  color_space?: string | null;
  bit_depth?: string | number | null;
  codec_profile?: string | null;
  codec_level?: string | null;
  scan_type?: string | null;
  hdr_format?: string | null;

  // Legacy camera info (keeping for backward compatibility)
  camera_lens?: string | null;
  camera_focal_length?: string | null;
  camera_aperture?: string | null;
  camera_iso?: string | null;
  camera_shutter_speed?: string | null;

  // Legacy technical details (keeping for backward compatibility)
  technical_color_space?: string | null;
  technical_bit_depth?: string | null;
  technical_profile?: string | null;
  technical_level?: string | null;
}

export interface IngestProgress {
  status: 'idle' | 'running' | 'scanning' | 'processing' | 'completed' | 'failed';
  progress: number;
  message: string;
  error?: string;
  processed_count?: number;
  results_count?: number;
  failed_count?: number;
  total_count?: number;
}

export interface AuthStatus {
  authenticated: boolean;
  user?: {
    id: string;
    email: string;
    profile_type: string;
  };
}

export interface SearchResults {
  results: VideoFile[];
  total: number; 
  query?: string; 
  search_type?: SearchType; 
}

export interface ApiResponse<T = any> {
  success: boolean;
  data?: T;
  error?: string;
}

export interface TranscriptData {
  id?: string;
  clip_id?: string;
  language?: string;
  text?: string;
  segments?: Array<{ start_time: number; end_time: number; text: string; speaker?: string }>;
}

export interface AnalysisData {
  id?: string;
  clip_id?: string;
  summary?: string;
  tags?: string[];
  key_frames?: Array<{ timestamp: number; image_url: string; score?: number }>;
}

export interface VideoDetails {
  clip: VideoFile; 
  transcript?: TranscriptData | null;
  analysis?: AnalysisData | null;
}

export interface CatalogStats {
  total_videos: number;
  total_duration_seconds: number;
  total_file_size_bytes: number;
  videos_by_category?: Record<string, number>;
}

export interface PipelineStep {
  id: string;
  name: string;
  description?: string;
  enabled_by_default?: boolean;
}

export interface ListVideoOptions {
  sortBy?: SortField;
  sortOrder?: SortOrder;
  limit?: number;
  offset?: number;
  dateStart?: string; 
  dateEnd?: string;   
}
