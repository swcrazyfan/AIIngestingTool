// Type declarations for AI Ingest Tool API

export interface IngestOptions {
  recursive?: boolean;
  ai_analysis?: boolean;
  generate_embeddings?: boolean;
  store_database?: boolean;
}

export type SearchType = 'semantic' | 'fulltext' | 'hybrid' | 'transcripts' | 'similar';

export interface VideoFile {
  id: string;
  file_name: string;
  file_path: string;
  local_path: string;
  duration_seconds: number;
  content_summary?: string;
  content_tags?: string[];
  camera_make?: string;
  camera_model?: string;
  content_category?: string;
  processed_at: string;
  transcript_preview?: string;
  similarity_score?: number;
  search_rank?: number;
}

export interface IngestProgress {
  status: 'idle' | 'running' | 'completed' | 'failed';
  progress: number;
  message: string;
  results_count?: number;
  failed_count?: number;
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
  count: number;
}

export interface ApiResponse<T = any> {
  success: boolean;
  data?: T;
  error?: string;
}
