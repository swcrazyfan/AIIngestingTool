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
  thumbnail_url?: string | null;
  all_thumbnail_urls?: Array<{
    url: string;
    filename: string;
    is_ai_selected: boolean;
    rank?: string | number;
    timestamp?: string;
    description?: string;
    reason?: string;
  }>;
  width?: number | null;
  height?: number | null;
  frame_rate?: string | number | null; 
  file_size_bytes?: number | null;
  created_at_timestamp?: string | null; 
  audio_tracks?: any[]; 
  video_tracks?: any[]; 
  full_transcript?: string;

  // New fields from the API response
  camera_details?: {
    make?: string | null;
    model?: string | null;
    lens_model?: string | null;
    focal_length?: {
      category?: string;
      source?: string;
      value_mm?: number;
    };
    settings?: {
      exposure_mode?: string;
      f_stop?: number;
      iso?: number;
      shutter_speed?: string | number;
      white_balance?: string;
    };
    location?: {
      gps_altitude?: number | null;
      gps_latitude?: number | null;
      gps_longitude?: number | null;
      location_name?: string | null;
    };
  };

  technical_metadata?: {
    codec_details?: {
      name?: string;
      level?: string;
      profile?: string;
      bit_depth?: number;
      scan_type?: string;
      bitrate_kbps?: number;
      bitrate_mode?: string;
      chroma_subsampling?: string;
      cabac?: string | null;
      gop_size?: string | number | null;
      ref_frames?: string | number | null;
      field_order?: string | null;
      pixel_format?: string | null;
    };
    color_details?: {
      color_space?: string;
      color_range?: string;
      color_primaries?: string;
      matrix_coefficients?: string;
      transfer_characteristics?: string;
      hdr?: {
        is_hdr?: boolean;
        format?: string | null;
        max_cll?: number | null;
        max_fall?: number | null;
        master_display?: string | null;
      };
    };
    exposure_details?: {
      stops?: number;
      warning?: boolean;
      overexposed_percentage?: number;
      underexposed_percentage?: number;
    };
  };

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

export interface ProcessedFile {
  file_name?: string;
  path?: string;
  status: 'completed' | 'processing' | 'waiting' | 'failed' | 'skipped';
  progress?: number;
  error?: string;
  current_step?: string;
  progress_percentage?: number;
}

export interface IngestProgress {
  status: 'idle' | 'starting' | 'running' | 'scanning' | 'processing' | 'completed' | 'failed';
  progress: number;
  message: string;
  current_file?: string;
  error?: string;
  processed_count?: number;
  results_count?: number;
  failed_count?: number;
  total_count?: number;
  processed_files?: ProcessedFile[];
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
