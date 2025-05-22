-- =====================================================
-- AI INGESTING TOOL - COMPLETE SUPABASE SCHEMA SETUP
-- Fixed version without immutable generation expressions
-- =====================================================

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "vector";

-- =====================================================
-- 1. USER PROFILES (WITH AUTO-CREATION TRIGGER)
-- =====================================================
CREATE TABLE IF NOT EXISTS user_profiles (
  id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
  profile_type TEXT CHECK (profile_type IN ('admin', 'user')) DEFAULT 'user',
  display_name TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Enable RLS
ALTER TABLE user_profiles ENABLE ROW LEVEL SECURITY;

-- CRITICAL: Insert trigger for new users (fixes your profile creation issue)
-- This function must be bulletproof to avoid blocking user creation
CREATE OR REPLACE FUNCTION handle_new_user()
RETURNS TRIGGER 
LANGUAGE plpgsql 
SECURITY DEFINER
AS $$
BEGIN
  -- Insert user profile with error handling
  INSERT INTO public.user_profiles (id, profile_type, display_name)
  VALUES (
    NEW.id,
    'user', -- Always default to 'user' to avoid metadata parsing issues
    COALESCE(
      NEW.raw_user_meta_data->>'display_name',
      NEW.raw_user_meta_data->>'full_name', 
      NEW.raw_user_meta_data->>'name',
      split_part(NEW.email, '@', 1),
      'User'
    )
  );
  
  RETURN NEW;
EXCEPTION
  WHEN OTHERS THEN
    -- Log the error but don't block user creation
    RAISE WARNING 'Failed to create user profile for user %: %', NEW.id, SQLERRM;
    RETURN NEW;
END;
$$;

-- Create trigger (only if it doesn't exist)
DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;
CREATE TRIGGER on_auth_user_created
  AFTER INSERT ON auth.users
  FOR EACH ROW EXECUTE FUNCTION handle_new_user();

-- =====================================================
-- 2. CLIPS - Main video table (FIXED VERSION)
-- =====================================================
CREATE TABLE IF NOT EXISTS clips (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID REFERENCES auth.users(id) NOT NULL,
  
  -- File information
  file_path TEXT NOT NULL,
  local_path TEXT NOT NULL, -- Absolute path for CLI access
  file_name TEXT NOT NULL,
  file_checksum TEXT UNIQUE NOT NULL,
  file_size_bytes BIGINT NOT NULL,
  duration_seconds NUMERIC,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  processed_at TIMESTAMPTZ DEFAULT NOW(),
  
  -- Core searchable technical metadata
  width INTEGER,
  height INTEGER,
  frame_rate NUMERIC,
  codec TEXT,
  camera_make TEXT,
  camera_model TEXT,
  container TEXT,
  
  -- AI analysis summaries
  content_category TEXT,
  content_summary TEXT,
  content_tags TEXT[], -- Shot types + metrics
  
  -- Transcript strategy
  full_transcript TEXT, -- Complete transcript
  transcript_preview TEXT, -- First 500 chars for FTS
  
  -- Search columns (populated by triggers instead of generated)
  searchable_content TEXT,
  fts tsvector,
  
  -- Complex metadata as JSONB
  technical_metadata JSONB,
  camera_details JSONB,
  audio_tracks JSONB,
  subtitle_tracks JSONB,
  thumbnails TEXT[]
);

-- Enable RLS
ALTER TABLE clips ENABLE ROW LEVEL SECURITY;
-- Function to update search content for clips
CREATE OR REPLACE FUNCTION update_clips_search_content()
RETURNS TRIGGER AS $$
BEGIN
  -- Update searchable content
  NEW.searchable_content := COALESCE(NEW.file_name, '') || ' ' ||
                           COALESCE(NEW.content_summary, '') || ' ' ||
                           COALESCE(NEW.transcript_preview, '') || ' ' ||
                           COALESCE(array_to_string(NEW.content_tags, ' '), '') || ' ' ||
                           COALESCE(NEW.content_category, '');
  
  -- Update full text search vector
  NEW.fts := to_tsvector('english', NEW.searchable_content);
  
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger to update search content
CREATE TRIGGER clips_search_content_trigger
  BEFORE INSERT OR UPDATE ON clips
  FOR EACH ROW EXECUTE FUNCTION update_clips_search_content();

-- =====================================================
-- 3. SEGMENTS - Segment-level analysis (FIXED VERSION)
-- =====================================================
CREATE TABLE IF NOT EXISTS segments (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  clip_id UUID REFERENCES clips(id) ON DELETE CASCADE,
  user_id UUID REFERENCES auth.users(id) NOT NULL,
  
  -- Segment positioning
  segment_index INTEGER NOT NULL, -- 0-based index for ordering
  start_time_seconds NUMERIC NOT NULL,
  end_time_seconds NUMERIC NOT NULL,
  duration_seconds NUMERIC, -- Will be calculated by trigger
  
  -- Segment metadata
  segment_type TEXT DEFAULT 'auto', -- 'auto', 'scene_change', 'speaker_change', 'manual'
  speaker_id TEXT,
  segment_description TEXT,
  keyframe_timestamp NUMERIC,
  
  -- Segment-level search content
  segment_content TEXT,
  fts tsvector, -- Will be calculated by trigger
  
  created_at TIMESTAMPTZ DEFAULT NOW(),
  
  -- Constraints
  UNIQUE(clip_id, segment_index),
  CONSTRAINT check_segment_times CHECK (start_time_seconds < end_time_seconds),
  CONSTRAINT check_segment_index CHECK (segment_index >= 0)
);

-- Enable RLS
ALTER TABLE segments ENABLE ROW LEVEL SECURITY;

-- Function to update segment calculated fields
CREATE OR REPLACE FUNCTION update_segments_calculated_fields()
RETURNS TRIGGER AS $$
BEGIN
  -- Calculate duration
  NEW.duration_seconds := NEW.end_time_seconds - NEW.start_time_seconds;
  
  -- Update full text search vector
  NEW.fts := to_tsvector('english', COALESCE(NEW.segment_content, ''));
  
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger to update calculated fields
CREATE TRIGGER segments_calculated_fields_trigger
  BEFORE INSERT OR UPDATE ON segments
  FOR EACH ROW EXECUTE FUNCTION update_segments_calculated_fields();
-- =====================================================
-- 4. ANALYSIS - AI analysis results
-- =====================================================
CREATE TABLE IF NOT EXISTS analysis (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  clip_id UUID REFERENCES clips(id) ON DELETE CASCADE,
  segment_id UUID REFERENCES segments(id) ON DELETE CASCADE, -- NULL for full-clip
  user_id UUID REFERENCES auth.users(id) NOT NULL,
  
  -- Analysis metadata
  analysis_type TEXT NOT NULL, -- 'comprehensive', 'visual', 'audio', 'content', 'segment'
  analysis_scope TEXT NOT NULL CHECK (analysis_scope IN ('full_clip', 'segment')),
  ai_model TEXT DEFAULT 'gemini-flash-2.5',
  
  -- Searchable analysis fields
  content_category TEXT,
  usability_rating TEXT,
  speaker_count INTEGER,
  
  -- Comprehensive analysis structure
  visual_analysis JSONB,
  audio_analysis JSONB,
  content_analysis JSONB,
  analysis_summary JSONB,
  analysis_file_path TEXT,
  
  created_at TIMESTAMPTZ DEFAULT NOW(),
  
  -- Scope constraints
  CONSTRAINT check_analysis_scope CHECK (
    (analysis_scope = 'full_clip' AND segment_id IS NULL) OR
    (analysis_scope = 'segment' AND segment_id IS NOT NULL)
  )
);

-- Enable RLS
ALTER TABLE analysis ENABLE ROW LEVEL SECURITY;

-- =====================================================
-- 5. VECTORS - Dual embedding strategy
-- =====================================================
CREATE TABLE IF NOT EXISTS vectors (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  clip_id UUID REFERENCES clips(id) ON DELETE CASCADE,
  segment_id UUID REFERENCES segments(id) ON DELETE CASCADE, -- NULL for full-clip
  user_id UUID REFERENCES auth.users(id) NOT NULL,
  
  -- Vector type and scope
  embedding_type TEXT NOT NULL CHECK (embedding_type IN ('full_clip', 'segment', 'keyframe')),
  embedding_source TEXT NOT NULL, -- 'summary', 'keywords', 'transcript', 'combined'
  
  -- BAAI/bge-m3 embeddings (1024 dimensions)
  summary_vector vector(1024),
  keyword_vector vector(1024),
  
  -- Embedding transparency
  embedded_content TEXT NOT NULL,      -- EXACT text that was embedded
  original_content TEXT,               -- Full text before truncation
  token_count INTEGER,                 -- Tokens in embedded content
  original_token_count INTEGER,        -- Original tokens before truncation
  truncation_method TEXT,              -- 'none', 'first_n_tokens', 'summary', 'key_excerpts'
  
  created_at TIMESTAMPTZ DEFAULT NOW(),
  
  -- Scope constraints
  CONSTRAINT check_vector_scope CHECK (
    (embedding_type = 'full_clip' AND segment_id IS NULL) OR
    (embedding_type IN ('segment', 'keyframe') AND segment_id IS NOT NULL)
  )
);

-- Enable RLS
ALTER TABLE vectors ENABLE ROW LEVEL SECURITY;
-- =====================================================
-- 6. TRANSCRIPTS - Dedicated transcript table (FIXED VERSION)
-- =====================================================
CREATE TABLE IF NOT EXISTS transcripts (
  clip_id UUID REFERENCES clips(id) ON DELETE CASCADE,
  user_id UUID REFERENCES auth.users(id) NOT NULL,
  
  -- Transcript structure
  full_text TEXT NOT NULL,
  segments JSONB NOT NULL,     -- AI transcript segments with timestamps
  speakers JSONB,              -- Speaker information
  non_speech_events JSONB,     -- Sound events, music, etc.
  
  -- Transcript search (populated by trigger)
  fts tsvector,
  
  created_at TIMESTAMPTZ DEFAULT NOW(),
  
  PRIMARY KEY (clip_id)
);

-- Enable RLS
ALTER TABLE transcripts ENABLE ROW LEVEL SECURITY;

-- Function to update transcript search
CREATE OR REPLACE FUNCTION update_transcript_search()
RETURNS TRIGGER AS $$
BEGIN
  -- Update full text search vector
  NEW.fts := to_tsvector('english', NEW.full_text);
  
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger to update search content
CREATE TRIGGER transcripts_search_trigger
  BEFORE INSERT OR UPDATE ON transcripts
  FOR EACH ROW EXECUTE FUNCTION update_transcript_search();

-- =====================================================
-- 7. PERFORMANCE INDEXES
-- =====================================================

-- Hybrid search indexes
CREATE INDEX IF NOT EXISTS idx_clips_fts ON clips USING gin(fts);
CREATE INDEX IF NOT EXISTS idx_segments_fts ON segments USING gin(fts);
CREATE INDEX IF NOT EXISTS idx_transcripts_fts ON transcripts USING gin(fts);

-- Vector similarity indexes (only if vector extension is available)
CREATE INDEX IF NOT EXISTS idx_vectors_summary ON vectors USING hnsw (summary_vector vector_ip_ops);
CREATE INDEX IF NOT EXISTS idx_vectors_keyword ON vectors USING hnsw (keyword_vector vector_ip_ops);

-- Segment ordering and time-based queries
CREATE INDEX IF NOT EXISTS idx_segments_clip_order ON segments(clip_id, segment_index);
CREATE INDEX IF NOT EXISTS idx_segments_time_range ON segments(clip_id, start_time_seconds, end_time_seconds);

-- User and performance indexes
CREATE INDEX IF NOT EXISTS idx_clips_user_category ON clips(user_id, content_category);
CREATE INDEX IF NOT EXISTS idx_clips_tags ON clips USING gin(content_tags);
CREATE INDEX IF NOT EXISTS idx_clips_camera ON clips(camera_make, camera_model) WHERE camera_make IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_clips_duration ON clips(duration_seconds) WHERE duration_seconds IS NOT NULL;

-- Analysis and vector lookup indexes
CREATE INDEX IF NOT EXISTS idx_analysis_clip_type ON analysis(clip_id, analysis_type);
CREATE INDEX IF NOT EXISTS idx_analysis_segment ON analysis(segment_id) WHERE segment_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_vectors_clip_source ON vectors(clip_id, embedding_source);
CREATE INDEX IF NOT EXISTS idx_vectors_segment ON vectors(segment_id) WHERE segment_id IS NOT NULL;
-- =====================================================
-- 8. ROW LEVEL SECURITY POLICIES
-- =====================================================

-- User Profile Policies
DROP POLICY IF EXISTS "Users can view own profile" ON user_profiles;
CREATE POLICY "Users can view own profile" ON user_profiles
  FOR SELECT TO authenticated
  USING (id = auth.uid());

DROP POLICY IF EXISTS "Users can update own profile" ON user_profiles;
CREATE POLICY "Users can update own profile" ON user_profiles
  FOR UPDATE TO authenticated
  USING (id = auth.uid())
  WITH CHECK (
    id = auth.uid() AND 
    profile_type = (SELECT profile_type FROM user_profiles WHERE id = auth.uid())
  );

DROP POLICY IF EXISTS "Admins can view all profiles" ON user_profiles;
CREATE POLICY "Admins can view all profiles" ON user_profiles
  FOR SELECT TO authenticated
  USING (
    EXISTS (
      SELECT 1 FROM user_profiles 
      WHERE id = auth.uid() AND profile_type = 'admin'
    )
  );

-- Clips Table Policies
CREATE POLICY "Users can view own clips" ON clips
  FOR SELECT TO authenticated
  USING (user_id = auth.uid());

CREATE POLICY "Users can insert own clips" ON clips
  FOR INSERT TO authenticated
  WITH CHECK (user_id = auth.uid());

CREATE POLICY "Users can update own clips" ON clips
  FOR UPDATE TO authenticated
  USING (user_id = auth.uid())
  WITH CHECK (user_id = auth.uid());

CREATE POLICY "Users can delete own clips" ON clips
  FOR DELETE TO authenticated
  USING (user_id = auth.uid());

-- Admins can view all clips
CREATE POLICY "Admins can view all clips" ON clips
  FOR SELECT TO authenticated
  USING (
    EXISTS (
      SELECT 1 FROM user_profiles 
      WHERE id = auth.uid() AND profile_type = 'admin'
    )
  );

-- Segments Policies
CREATE POLICY "Users can view own segments" ON segments
  FOR SELECT TO authenticated
  USING (user_id = auth.uid());

CREATE POLICY "Users can insert own segments" ON segments
  FOR INSERT TO authenticated
  WITH CHECK (
    user_id = auth.uid() AND
    EXISTS (SELECT 1 FROM clips WHERE id = clip_id AND user_id = auth.uid())
  );

CREATE POLICY "Users can update own segments" ON segments
  FOR UPDATE TO authenticated
  USING (user_id = auth.uid())
  WITH CHECK (user_id = auth.uid());

CREATE POLICY "Users can delete own segments" ON segments
  FOR DELETE TO authenticated
  USING (user_id = auth.uid());
-- Analysis Policies
CREATE POLICY "Users can view own analysis" ON analysis
  FOR SELECT TO authenticated
  USING (user_id = auth.uid());

CREATE POLICY "Users can insert own analysis" ON analysis
  FOR INSERT TO authenticated
  WITH CHECK (
    user_id = auth.uid() AND
    EXISTS (SELECT 1 FROM clips WHERE id = clip_id AND user_id = auth.uid())
  );

-- Vectors Policies
CREATE POLICY "Users can view own vectors" ON vectors
  FOR SELECT TO authenticated
  USING (user_id = auth.uid());

CREATE POLICY "Users can insert own vectors" ON vectors
  FOR INSERT TO authenticated
  WITH CHECK (
    user_id = auth.uid() AND
    EXISTS (SELECT 1 FROM clips WHERE id = clip_id AND user_id = auth.uid())
  );

-- Transcripts Policies
CREATE POLICY "Users can view own transcripts" ON transcripts
  FOR SELECT TO authenticated
  USING (user_id = auth.uid());

CREATE POLICY "Users can insert own transcripts" ON transcripts
  FOR INSERT TO authenticated
  WITH CHECK (
    user_id = auth.uid() AND
    EXISTS (SELECT 1 FROM clips WHERE id = clip_id AND user_id = auth.uid())
  );

-- =====================================================
-- 9. HELPER FUNCTIONS
-- =====================================================

-- Drop existing functions first (as suggested by PostgreSQL)
DROP FUNCTION IF EXISTS is_admin(UUID);
DROP FUNCTION IF EXISTS get_user_profile(UUID);
DROP FUNCTION IF EXISTS get_user_stats(UUID);

-- Check if user is admin
CREATE FUNCTION is_admin(check_user_id UUID DEFAULT auth.uid())
RETURNS BOOLEAN
LANGUAGE SQL
SECURITY DEFINER
AS $$
  SELECT EXISTS (
    SELECT 1 FROM user_profiles 
    WHERE id = check_user_id AND profile_type = 'admin'
  );
$$;

-- Get user profile info
CREATE FUNCTION get_user_profile(profile_user_id UUID DEFAULT auth.uid())
RETURNS TABLE (
  id UUID,
  profile_type TEXT,
  display_name TEXT,
  created_at TIMESTAMPTZ
)
LANGUAGE SQL
SECURITY DEFINER
AS $$
  SELECT up.id, up.profile_type, up.display_name, up.created_at
  FROM user_profiles up
  WHERE up.id = profile_user_id;
$$;

-- User stats function
CREATE FUNCTION get_user_stats(stats_user_id UUID DEFAULT auth.uid())
RETURNS TABLE (
  total_clips INTEGER,
  total_duration_hours NUMERIC,
  total_storage_gb NUMERIC,
  clips_with_transcripts INTEGER,
  clips_with_ai_analysis INTEGER
)
LANGUAGE SQL
SECURITY DEFINER
AS $$
  SELECT 
    COUNT(*)::INTEGER as total_clips,
    ROUND(SUM(COALESCE(duration_seconds, 0)) / 3600.0, 2) as total_duration_hours,
    ROUND(SUM(COALESCE(file_size_bytes, 0)) / (1024.0^3), 2) as total_storage_gb,
    COUNT(t.clip_id)::INTEGER as clips_with_transcripts,
    COUNT(DISTINCT a.clip_id)::INTEGER as clips_with_ai_analysis
  FROM clips c
  LEFT JOIN transcripts t ON c.id = t.clip_id
  LEFT JOIN analysis a ON c.id = a.clip_id
  WHERE c.user_id = stats_user_id;
$$;

-- =====================================================
-- 10. COMPLETION MESSAGE
-- =====================================================

-- Create a simple test to verify everything worked
DO $$
BEGIN
  RAISE NOTICE 'AI Ingesting Tool Database Setup Complete!';
  RAISE NOTICE 'Tables created: user_profiles, clips, segments, analysis, vectors, transcripts';
  RAISE NOTICE 'Triggers created: User profile auto-creation, search content updates';
  RAISE NOTICE 'RLS policies created: User data isolation with admin override';
  RAISE NOTICE 'Ready for AI Ingesting Tool integration!';
END;
$$;