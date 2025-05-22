# Supabase Implementation Guide
## AI-Powered Video Ingest & Catalog Tool
*Complete Step-by-Step Implementation*

---

## 📋 Table of Contents

1. [Supabase Project Setup](#1-supabase-project-setup)
2. [Database Schema Implementation](#2-database-schema-implementation)
3. [Row Level Security (RLS) Setup](#3-row-level-security-rls-setup)
4. [Python Dependencies & Environment](#4-python-dependencies--environment)
5. [CLI Authentication Implementation](#5-cli-authentication-implementation)
6. [Database Integration Pipeline](#6-database-integration-pipeline)
7. [Vector Embeddings Integration](#7-vector-embeddings-integration)
8. [Hybrid Search Implementation](#8-hybrid-search-implementation)
9. [Testing & Validation](#9-testing--validation)
10. [Deployment & Production](#10-deployment--production)

---

## 1. Supabase Project Setup

### Step 1.1: Create Supabase Project

1. **Go to Supabase Dashboard**
   - Visit: https://supabase.com/dashboard
   - Sign in or create account

2. **Create New Project**
   ```
   Project Name: ai-video-catalog
   Database Password: [Generate strong password - SAVE THIS]
   Region: Choose closest to your location
   Plan: Pro (required for vector extensions)
   ```

3. **Get Project Credentials**
   - Go to Project Settings → API
   - Save these values:
     ```
     Project URL: https://your-project.supabase.co
     Anon/Public Key: eyJ... (anon key)
     Service Role Key: eyJ... (service_role key)
     ```

### Step 1.2: Enable Required Extensions

1. **Go to Database → Extensions**
2. **Enable these extensions:**
   ```sql
   -- Vector similarity search
   vector
   
   -- UUID generation
   uuid-ossp
   
   -- Full-text search (usually enabled by default)
   ```

3. **Verify Extensions (SQL Editor)**
   ```sql
   SELECT * FROM pg_extension WHERE extname IN ('vector', 'uuid-ossp');
   ```

### Step 1.3: Environment Setup

1. **Create `.env` file in project root:**
   ```bash
   # Supabase Configuration
   SUPABASE_URL=https://your-project.supabase.co
   SUPABASE_ANON_KEY=eyJ...
   SUPABASE_SERVICE_ROLE_KEY=eyJ...
   
   # DeepInfra API (for embeddings)
   DEEPINFRA_API_KEY=your_deepinfra_key
   
   # Gemini API (existing)
   GEMINI_API_KEY=your_gemini_key
   ```

2. **Update .gitignore:**
   ```
   .env
   .video_ingest_auth.json
   ```

---

## 2. Database Schema Implementation

### Step 2.1: User Profiles Table

Execute in Supabase SQL Editor:

```sql
-- =====================================================
-- 1. USER PROFILES
-- =====================================================
CREATE TABLE user_profiles (
  id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
  profile_type TEXT CHECK (profile_type IN ('admin', 'user')) DEFAULT 'user',
  display_name TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Enable RLS
ALTER TABLE user_profiles ENABLE ROW LEVEL SECURITY;

-- Insert trigger for new users
CREATE OR REPLACE FUNCTION handle_new_user()
RETURNS TRIGGER AS $$
BEGIN
  INSERT INTO user_profiles (id, profile_type, display_name)
  VALUES (
    NEW.id,
    COALESCE(NEW.raw_user_meta_data->>'profile_type', 'user'),
    COALESCE(NEW.raw_user_meta_data->>'display_name', split_part(NEW.email, '@', 1))
  );
  RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Trigger on auth.users
CREATE TRIGGER on_auth_user_created
  AFTER INSERT ON auth.users
  FOR EACH ROW EXECUTE FUNCTION handle_new_user();
```

### Step 2.2: Core Tables Schema

```sql
-- =====================================================
-- 2. CLIPS - Main video table
-- =====================================================
CREATE TABLE clips (
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
  
  -- Hybrid search support
  searchable_content TEXT GENERATED ALWAYS AS (
    COALESCE(file_name, '') || ' ' ||
    COALESCE(content_summary, '') || ' ' ||
    COALESCE(transcript_preview, '') || ' ' ||
    COALESCE(array_to_string(content_tags, ' '), '') || ' ' ||
    COALESCE(content_category, '')
  ) STORED,
  
  fts tsvector GENERATED ALWAYS AS (
    to_tsvector('english', searchable_content)
  ) STORED,
  
  -- Complex metadata as JSONB
  technical_metadata JSONB,
  camera_details JSONB,
  audio_tracks JSONB,
  subtitle_tracks JSONB,
  thumbnails TEXT[]
);

-- Enable RLS
ALTER TABLE clips ENABLE ROW LEVEL SECURITY;
```

### Step 2.3: Segments Table

```sql
-- =====================================================
-- 3. SEGMENTS - Segment-level analysis
-- =====================================================
CREATE TABLE segments (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  clip_id UUID REFERENCES clips(id) ON DELETE CASCADE,
  user_id UUID REFERENCES auth.users(id) NOT NULL,
  
  -- Segment positioning
  segment_index INTEGER NOT NULL, -- 0-based index for ordering
  start_time_seconds NUMERIC NOT NULL,
  end_time_seconds NUMERIC NOT NULL,
  duration_seconds NUMERIC GENERATED ALWAYS AS (end_time_seconds - start_time_seconds) STORED,
  
  -- Segment metadata
  segment_type TEXT DEFAULT 'auto', -- 'auto', 'scene_change', 'speaker_change', 'manual'
  speaker_id TEXT,
  segment_description TEXT,
  keyframe_timestamp NUMERIC,
  
  -- Segment-level search content
  segment_content TEXT,
  fts tsvector GENERATED ALWAYS AS (
    to_tsvector('english', COALESCE(segment_content, ''))
  ) STORED,
  
  created_at TIMESTAMPTZ DEFAULT NOW(),
  
  -- Constraints
  UNIQUE(clip_id, segment_index),
  CONSTRAINT check_segment_times CHECK (start_time_seconds < end_time_seconds),
  CONSTRAINT check_segment_index CHECK (segment_index >= 0)
);

-- Enable RLS
ALTER TABLE segments ENABLE ROW LEVEL SECURITY;
```

### Step 2.4: Analysis Table

```sql
-- =====================================================
-- 4. ANALYSIS - AI analysis results
-- =====================================================
CREATE TABLE analysis (
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
```

### Step 2.5: Vectors Table

```sql
-- =====================================================
-- 5. VECTORS - Dual embedding strategy
-- =====================================================
CREATE TABLE vectors (
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
```

### Step 2.6: Transcripts Table

```sql
-- =====================================================
-- 6. TRANSCRIPTS - Dedicated transcript table
-- =====================================================
CREATE TABLE transcripts (
  clip_id UUID REFERENCES clips(id) ON DELETE CASCADE,
  user_id UUID REFERENCES auth.users(id) NOT NULL,
  
  -- Transcript structure
  full_text TEXT NOT NULL,
  segments JSONB NOT NULL,     -- AI transcript segments with timestamps
  speakers JSONB,              -- Speaker information
  non_speech_events JSONB,     -- Sound events, music, etc.
  
  -- Transcript search
  fts tsvector GENERATED ALWAYS AS (
    to_tsvector('english', full_text)
  ) STORED,
  
  created_at TIMESTAMPTZ DEFAULT NOW(),
  
  PRIMARY KEY (clip_id)
);

-- Enable RLS
ALTER TABLE transcripts ENABLE ROW LEVEL SECURITY;
```

### Step 2.7: Database Indexes

```sql
-- =====================================================
-- 7. PERFORMANCE INDEXES
-- =====================================================

-- Hybrid search indexes
CREATE INDEX idx_clips_fts ON clips USING gin(fts);
CREATE INDEX idx_segments_fts ON segments USING gin(fts);
CREATE INDEX idx_transcripts_fts ON transcripts USING gin(fts);

-- Vector similarity indexes
CREATE INDEX idx_vectors_summary ON vectors USING hnsw (summary_vector vector_ip_ops);
CREATE INDEX idx_vectors_keyword ON vectors USING hnsw (keyword_vector vector_ip_ops);

-- Segment ordering and time-based queries
CREATE INDEX idx_segments_clip_order ON segments(clip_id, segment_index);
CREATE INDEX idx_segments_time_range ON segments(clip_id, start_time_seconds, end_time_seconds);

-- User and performance indexes
CREATE INDEX idx_clips_user_category ON clips(user_id, content_category);
CREATE INDEX idx_clips_tags ON clips USING gin(content_tags);
CREATE INDEX idx_clips_camera ON clips(camera_make, camera_model) WHERE camera_make IS NOT NULL;
CREATE INDEX idx_clips_duration ON clips(duration_seconds) WHERE duration_seconds IS NOT NULL;

-- Analysis and vector lookup indexes
CREATE INDEX idx_analysis_clip_type ON analysis(clip_id, analysis_type);
CREATE INDEX idx_analysis_segment ON analysis(segment_id) WHERE segment_id IS NOT NULL;
CREATE INDEX idx_vectors_clip_source ON vectors(clip_id, embedding_source);
CREATE INDEX idx_vectors_segment ON vectors(segment_id) WHERE segment_id IS NOT NULL;
```

---

## 3. Row Level Security (RLS) Setup

### Step 3.1: User Profile Policies

```sql
-- =====================================================
-- USER PROFILE POLICIES
-- =====================================================

-- Users can view their own profile
CREATE POLICY "Users can view own profile" ON user_profiles
  FOR SELECT TO authenticated
  USING (id = auth.uid());

-- Users can update their own profile (except profile_type)
CREATE POLICY "Users can update own profile" ON user_profiles
  FOR UPDATE TO authenticated
  USING (id = auth.uid())
  WITH CHECK (
    id = auth.uid() AND 
    profile_type = (SELECT profile_type FROM user_profiles WHERE id = auth.uid())
  );

-- Admins can view all profiles
CREATE POLICY "Admins can view all profiles" ON user_profiles
  FOR SELECT TO authenticated
  USING (
    EXISTS (
      SELECT 1 FROM user_profiles 
      WHERE id = auth.uid() AND profile_type = 'admin'
    )
  );

-- Admins can update any profile
CREATE POLICY "Admins can update any profile" ON user_profiles
  FOR UPDATE TO authenticated
  USING (
    EXISTS (
      SELECT 1 FROM user_profiles 
      WHERE id = auth.uid() AND profile_type = 'admin'
    )
  );
```

### Step 3.2: Clips Table Policies

```sql
-- =====================================================
-- CLIPS TABLE POLICIES
-- =====================================================

-- Users can view their own clips
CREATE POLICY "Users can view own clips" ON clips
  FOR SELECT TO authenticated
  USING (user_id = auth.uid());

-- Users can insert their own clips
CREATE POLICY "Users can insert own clips" ON clips
  FOR INSERT TO authenticated
  WITH CHECK (user_id = auth.uid());

-- Users can update their own clips
CREATE POLICY "Users can update own clips" ON clips
  FOR UPDATE TO authenticated
  USING (user_id = auth.uid())
  WITH CHECK (user_id = auth.uid());

-- Users can delete their own clips
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
```

### Step 3.3: All Other Table Policies

```sql
-- =====================================================
-- SEGMENTS TABLE POLICIES
-- =====================================================

-- Users can only access segments of their own clips
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

-- Admins can access all segments
CREATE POLICY "Admins can access all segments" ON segments
  FOR ALL TO authenticated
  USING (
    EXISTS (
      SELECT 1 FROM user_profiles 
      WHERE id = auth.uid() AND profile_type = 'admin'
    )
  );

-- =====================================================
-- ANALYSIS TABLE POLICIES
-- =====================================================

-- Users can only access analysis of their own clips
CREATE POLICY "Users can view own analysis" ON analysis
  FOR SELECT TO authenticated
  USING (user_id = auth.uid());

CREATE POLICY "Users can insert own analysis" ON analysis
  FOR INSERT TO authenticated
  WITH CHECK (
    user_id = auth.uid() AND
    EXISTS (SELECT 1 FROM clips WHERE id = clip_id AND user_id = auth.uid())
  );

-- Admins can access all analysis
CREATE POLICY "Admins can access all analysis" ON analysis
  FOR ALL TO authenticated
  USING (
    EXISTS (
      SELECT 1 FROM user_profiles 
      WHERE id = auth.uid() AND profile_type = 'admin'
    )
  );

-- =====================================================
-- VECTORS TABLE POLICIES
-- =====================================================

-- Users can only access vectors of their own clips
CREATE POLICY "Users can view own vectors" ON vectors
  FOR SELECT TO authenticated
  USING (user_id = auth.uid());

CREATE POLICY "Users can insert own vectors" ON vectors
  FOR INSERT TO authenticated
  WITH CHECK (
    user_id = auth.uid() AND
    EXISTS (SELECT 1 FROM clips WHERE id = clip_id AND user_id = auth.uid())
  );

-- Admins can access all vectors
CREATE POLICY "Admins can access all vectors" ON vectors
  FOR ALL TO authenticated
  USING (
    EXISTS (
      SELECT 1 FROM user_profiles 
      WHERE id = auth.uid() AND profile_type = 'admin'
    )
  );

-- =====================================================
-- TRANSCRIPTS TABLE POLICIES
-- =====================================================

-- Users can only access transcripts of their own clips
CREATE POLICY "Users can view own transcripts" ON transcripts
  FOR SELECT TO authenticated
  USING (user_id = auth.uid());

CREATE POLICY "Users can insert own transcripts" ON transcripts
  FOR INSERT TO authenticated
  WITH CHECK (
    user_id = auth.uid() AND
    EXISTS (SELECT 1 FROM clips WHERE id = clip_id AND user_id = auth.uid())
  );

-- Admins can access all transcripts
CREATE POLICY "Admins can access all transcripts" ON transcripts
  FOR ALL TO authenticated
  USING (
    EXISTS (
      SELECT 1 FROM user_profiles 
      WHERE id = auth.uid() AND profile_type = 'admin'
    )
  );
```

### Step 3.4: Helper Functions

```sql
-- =====================================================
-- HELPER FUNCTIONS FOR CLI
-- =====================================================

-- Check if user is admin
CREATE OR REPLACE FUNCTION is_admin(user_id UUID DEFAULT auth.uid())
RETURNS BOOLEAN
LANGUAGE SQL
SECURITY DEFINER
AS $$
  SELECT EXISTS (
    SELECT 1 FROM user_profiles 
    WHERE id = user_id AND profile_type = 'admin'
  );
$$;

-- Get user profile info
CREATE OR REPLACE FUNCTION get_user_profile(user_id UUID DEFAULT auth.uid())
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
  WHERE up.id = user_id;
$$;

-- User stats function
CREATE OR REPLACE FUNCTION get_user_stats(user_id UUID DEFAULT auth.uid())
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
    ROUND(SUM(duration_seconds) / 3600.0, 2) as total_duration_hours,
    ROUND(SUM(file_size_bytes) / (1024.0^3), 2) as total_storage_gb,
    COUNT(t.clip_id)::INTEGER as clips_with_transcripts,
    COUNT(DISTINCT a.clip_id)::INTEGER as clips_with_ai_analysis
  FROM clips c
  LEFT JOIN transcripts t ON c.id = t.clip_id
  LEFT JOIN analysis a ON c.id = a.clip_id
  WHERE c.user_id = user_id;
$$;

-- Function to get transcript text for a specific segment
CREATE OR REPLACE FUNCTION get_segment_transcript(
  p_clip_id UUID,
  p_start_time NUMERIC,
  p_end_time NUMERIC
)
RETURNS TEXT
LANGUAGE plpgsql
AS $$
DECLARE
  transcript_segments JSONB;
  segment_text TEXT := '';
  segment JSONB;
BEGIN
  SELECT t.segments INTO transcript_segments
  FROM transcripts t
  WHERE t.clip_id = p_clip_id;
  
  FOR segment IN SELECT * FROM jsonb_array_elements(transcript_segments)
  LOOP
    IF (segment->>'timestamp')::NUMERIC >= p_start_time 
       AND (segment->>'timestamp')::NUMERIC <= p_end_time THEN
      segment_text := segment_text || ' ' || (segment->>'text');
    END IF;
  END LOOP;
  
  RETURN TRIM(segment_text);
END;
$$;

-- Function to insert segment with proper ordering
CREATE OR REPLACE FUNCTION insert_segment(
  p_clip_id UUID,
  p_start_time NUMERIC,
  p_end_time NUMERIC,
  p_segment_type TEXT DEFAULT 'auto',
  p_description TEXT DEFAULT NULL
)
RETURNS UUID
LANGUAGE plpgsql
AS $$
DECLARE
  next_index INTEGER;
  new_segment_id UUID;
BEGIN
  SELECT COALESCE(MAX(segment_index), -1) + 1 INTO next_index
  FROM segments
  WHERE clip_id = p_clip_id;
  
  INSERT INTO segments (
    clip_id, segment_index, start_time_seconds, end_time_seconds,
    segment_type, segment_description, user_id
  )
  VALUES (
    p_clip_id, next_index, p_start_time, p_end_time,
    p_segment_type, p_description, auth.uid()
  )
  RETURNING id INTO new_segment_id;
  
  RETURN new_segment_id;
END;
$$;
```

---

## 4. Python Dependencies & Environment

### Step 4.1: Update Requirements

Create/update `requirements-supabase.txt`:

```txt
# Existing dependencies (from your current requirements.txt)
av>=14.4.0
pymediainfo>=6.0.0
PyExifTool>=0.5.0
opencv-python>=4.8.0
typer[all]>=0.9.0
rich>=13.4.0
pydantic>=2.4.0
structlog>=23.1.0
numpy>=1.24.0
pillow>=10.0.0
polyfile>=0.5.5
hachoir==3.3.0
python-dateutil>=2.8.2
transformers>=4.28.0
torch>=2.0.0
google-generativeai>=0.3.0
python-dotenv>=1.0.0

# New Supabase dependencies
supabase>=2.3.0
tiktoken>=0.5.0
openai>=1.0.0
```

### Step 4.2: Install Dependencies

```bash
pip install -r requirements-supabase.txt
```

### Step 4.3: Configuration Module

Create `video_ingest_tool/supabase_config.py`:

```python
"""
Supabase configuration and client management.
"""

import os
from typing import Optional
from supabase import create_client, Client
from supabase.client import ClientOptions
import structlog

logger = structlog.get_logger(__name__)

# Load environment variables
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

def get_supabase_client(use_service_role: bool = False) -> Client:
    """
    Get Supabase client instance.
    
    Args:
        use_service_role: Use service role key instead of anon key
        
    Returns:
        Configured Supabase client
    """
    if not SUPABASE_URL:
        raise ValueError("SUPABASE_URL environment variable not set")
    
    key = SUPABASE_SERVICE_ROLE_KEY if use_service_role else SUPABASE_ANON_KEY
    if not key:
        key_type = "SUPABASE_SERVICE_ROLE_KEY" if use_service_role else "SUPABASE_ANON_KEY"
        raise ValueError(f"{key_type} environment variable not set")
    
    # Configure client options
    options = ClientOptions(
        auto_refresh_token=True,
        persist_session=True
    )
    
    client = create_client(SUPABASE_URL, key, options)
    return client

def verify_connection() -> bool:
    """
    Verify connection to Supabase.
    
    Returns:
        True if connection successful
    """
    try:
        client = get_supabase_client()
        # Test connection with a simple query
        result = client.table('user_profiles').select('count').execute()
        logger.info("Supabase connection verified")
        return True
    except Exception as e:
        logger.error(f"Supabase connection failed: {str(e)}")
        return False
```

---

## 5. CLI Authentication Implementation

### Step 5.1: Authentication Module

Create `video_ingest_tool/auth.py`:

```python
"""
CLI Authentication module for Supabase integration.
"""

import json
import os
import time
import getpass
from pathlib import Path
from typing import Optional, Dict, Any

import typer
import structlog
from supabase import Client

from .supabase_config import get_supabase_client

logger = structlog.get_logger(__name__)

# Auth file location
AUTH_FILE = Path.home() / ".video_ingest_auth.json"

class AuthManager:
    """Manages CLI authentication with Supabase."""
    
    def __init__(self):
        self.client: Optional[Client] = None
    
    def login(self, email: str, password: str) -> bool:
        """
        Login with email and password.
        
        Args:
            email: User email
            password: User password
            
        Returns:
            True if login successful
        """
        try:
            self.client = get_supabase_client()
            
            # Authenticate
            response = self.client.auth.sign_in_with_password({
                "email": email,
                "password": password
            })
            
            if response.user and response.session:
                # Save session
                self._save_session(response.session)
                logger.info(f"Successfully logged in as {email}")
                return True
            else:
                logger.error("Login failed: No user or session returned")
                return False
                
        except Exception as e:
            logger.error(f"Login failed: {str(e)}")
            return False
    
    def logout(self) -> bool:
        """
        Logout and clear stored session.
        
        Returns:
            True if logout successful
        """
        try:
            # Clear local session file
            if AUTH_FILE.exists():
                AUTH_FILE.unlink()
                logger.info("Successfully logged out")
                return True
            else:
                logger.info("No active session found")
                return True
        except Exception as e:
            logger.error(f"Logout failed: {str(e)}")
            return False
    
    def get_current_session(self) -> Optional[Dict[str, Any]]:
        """
        Get current session if valid.
        
        Returns:
            Session data if valid, None otherwise
        """
        if not AUTH_FILE.exists():
            return None
        
        try:
            session_data = json.loads(AUTH_FILE.read_text())
            
            # Check if token is expired
            expires_at = session_data.get('expires_at', 0)
            if expires_at < time.time():
                # Try to refresh token
                return self._refresh_session(session_data)
            
            return session_data
            
        except Exception as e:
            logger.error(f"Failed to load session: {str(e)}")
            return None
    
    def get_authenticated_client(self) -> Optional[Client]:
        """
        Get authenticated Supabase client.
        
        Returns:
            Authenticated client or None if not logged in
        """
        session = self.get_current_session()
        if not session:
            return None
        
        try:
            client = get_supabase_client()
            # Set the session
            client.auth.set_session(
                access_token=session['access_token'],
                refresh_token=session['refresh_token']
            )
            return client
        except Exception as e:
            logger.error(f"Failed to create authenticated client: {str(e)}")
            return None
    
    def get_user_profile(self) -> Optional[Dict[str, Any]]:
        """
        Get current user profile.
        
        Returns:
            User profile data or None
        """
        client = self.get_authenticated_client()
        if not client:
            return None
        
        try:
            result = client.rpc('get_user_profile').execute()
            if result.data:
                return result.data[0] if isinstance(result.data, list) else result.data
            return None
        except Exception as e:
            logger.error(f"Failed to get user profile: {str(e)}")
            return None
    
    def is_admin(self) -> bool:
        """
        Check if current user is admin.
        
        Returns:
            True if user is admin
        """
        profile = self.get_user_profile()
        return profile and profile.get('profile_type') == 'admin'
    
    def _save_session(self, session) -> None:
        """Save session to local file."""
        session_data = {
            "access_token": session.access_token,
            "refresh_token": session.refresh_token,
            "expires_at": session.expires_at,
            "user_id": session.user.id if session.user else None,
            "email": session.user.email if session.user else None
        }
        
        # Save with restricted permissions
        AUTH_FILE.write_text(json.dumps(session_data, indent=2))
        AUTH_FILE.chmod(0o600)  # Read/write for owner only
    
    def _refresh_session(self, session_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Attempt to refresh expired session."""
        try:
            self.client = get_supabase_client()
            
            # Refresh token
            response = self.client.auth.refresh_session(session_data['refresh_token'])
            
            if response.session:
                self._save_session(response.session)
                return self.get_current_session()
            else:
                # Refresh failed, clear session
                if AUTH_FILE.exists():
                    AUTH_FILE.unlink()
                return None
                
        except Exception as e:
            logger.error(f"Failed to refresh session: {str(e)}")
            # Clear invalid session
            if AUTH_FILE.exists():
                AUTH_FILE.unlink()
            return None

# Global auth manager instance
auth_manager = AuthManager()
```

### Step 5.2: CLI Commands

Update `video_ingest_tool/cli.py` to add authentication commands:

```python
"""
Enhanced CLI with authentication commands.
"""

# Add to your existing imports
import getpass
from .auth import auth_manager

# Add authentication command group
auth_app = typer.Typer(help="Authentication commands")
app.add_typer(auth_app, name="auth")

@auth_app.command()
def login():
    """Login to your video catalog account"""
    
    email = typer.prompt("Email")
    password = getpass.getpass("Password: ")
    
    if auth_manager.login(email, password):
        typer.echo(f"✅ Successfully logged in as {email}")
        
        # Show user profile info
        profile = auth_manager.get_user_profile()
        if profile:
            typer.echo(f"Profile: {profile.get('profile_type', 'user')}")
            if profile.get('display_name'):
                typer.echo(f"Name: {profile['display_name']}")
    else:
        typer.echo("❌ Login failed", err=True)
        raise typer.Exit(1)

@auth_app.command()
def logout():
    """Logout and clear stored session"""
    if auth_manager.logout():
        typer.echo("✅ Successfully logged out")
    else:
        typer.echo("❌ Logout failed", err=True)
        raise typer.Exit(1)

@auth_app.command()
def status():
    """Show current authentication status"""
    session = auth_manager.get_current_session()
    
    if session:
        typer.echo(f"✅ Logged in as: {session.get('email', 'Unknown')}")
        typer.echo(f"User ID: {session.get('user_id', 'Unknown')}")
        
        # Get user profile
        profile = auth_manager.get_user_profile()
        if profile:
            typer.echo(f"Profile type: {profile.get('profile_type', 'user')}")
            typer.echo(f"Display name: {profile.get('display_name', 'Not set')}")
        else:
            typer.echo("⚠️  Session may be invalid")
    else:
        typer.echo("❌ Not logged in")
        typer.echo("Run 'python -m video_ingest_tool auth login' to authenticate")

# Profile management commands
profile_app = typer.Typer(help="User profile commands")
app.add_typer(profile_app, name="profile")

@profile_app.command()
def show():
    """Show user profile information"""
    profile = auth_manager.get_user_profile()
    
    if not profile:
        typer.echo("❌ Not logged in or unable to get profile", err=True)
        raise typer.Exit(1)
    
    typer.echo("📋 User Profile:")
    typer.echo(f"  ID: {profile.get('id')}")
    typer.echo(f"  Type: {profile.get('profile_type', 'user')}")
    typer.echo(f"  Name: {profile.get('display_name', 'Not set')}")
    typer.echo(f"  Created: {profile.get('created_at', 'Unknown')}")

@profile_app.command()
def stats():
    """Show user statistics"""
    client = auth_manager.get_authenticated_client()
    
    if not client:
        typer.echo("❌ Not logged in", err=True)
        raise typer.Exit(1)
    
    try:
        result = client.rpc('get_user_stats').execute()
        stats = result.data[0] if result.data else {}
        
        typer.echo("📊 User Statistics:")
        typer.echo(f"  Total clips: {stats.get('total_clips', 0)}")
        typer.echo(f"  Total duration: {stats.get('total_duration_hours', 0)} hours")
        typer.echo(f"  Total storage: {stats.get('total_storage_gb', 0)} GB")
        typer.echo(f"  Clips with transcripts: {stats.get('clips_with_transcripts', 0)}")
        typer.echo(f"  Clips with AI analysis: {stats.get('clips_with_ai_analysis', 0)}")
        
    except Exception as e:
        typer.echo(f"❌ Failed to get statistics: {str(e)}", err=True)
        raise typer.Exit(1)

# Helper function to check authentication for other commands
def require_authentication():
    """Ensure user is authenticated before proceeding."""
    if not auth_manager.get_current_session():
        typer.echo("❌ Authentication required. Run 'python -m video_ingest_tool auth login'", err=True)
        raise typer.Exit(1)
    
    return auth_manager.get_authenticated_client()
```

---

## 6. Database Integration Pipeline

### Step 6.1: Database Storage Pipeline Step

Create `video_ingest_tool/database_storage.py`:

```python
"""
Database storage pipeline step for Supabase integration.
"""

import os
from typing import Dict, Any, Optional
import structlog

from .auth import auth_manager
from .models import VideoIngestOutput

logger = structlog.get_logger(__name__)

def store_video_in_database(
    video_data: VideoIngestOutput,
    logger=None
) -> Dict[str, Any]:
    """
    Store processed video data in Supabase database.
    
    Args:
        video_data: Processed video data
        logger: Optional logger
        
    Returns:
        Dict with storage results
    """
    client = auth_manager.get_authenticated_client()
    
    if not client:
        raise ValueError("Authentication required for database storage")
    
    try:
        # Prepare clip data
        clip_data = {
            "file_path": video_data.file_info.file_path,
            "local_path": os.path.abspath(video_data.file_info.file_path),
            "file_name": video_data.file_info.file_name,
            "file_checksum": video_data.file_info.file_checksum,
            "file_size_bytes": video_data.file_info.file_size_bytes,
            "duration_seconds": video_data.video.duration_seconds,
            "created_at": video_data.file_info.created_at.isoformat() if video_data.file_info.created_at else None,
            "processed_at": video_data.file_info.processed_at.isoformat(),
            
            # Technical metadata
            "width": video_data.video.resolution.width,
            "height": video_data.video.resolution.height,
            "frame_rate": video_data.video.frame_rate,
            "codec": video_data.video.codec.name,
            "camera_make": video_data.camera.make,
            "camera_model": video_data.camera.model,
            "container": video_data.video.container,
            
            # AI analysis summaries
            "content_category": video_data.analysis.ai_analysis.summary.content_category if video_data.analysis.ai_analysis and video_data.analysis.ai_analysis.summary else None,
            "content_summary": video_data.analysis.content_summary,
            "content_tags": video_data.analysis.content_tags,
            
            # Set transcript preview (first 500 chars)
            "transcript_preview": video_data.analysis.content_summary[:500] if video_data.analysis.content_summary else None,
            
            # Complex metadata as JSONB
            "technical_metadata": {
                "codec_details": video_data.video.codec.model_dump(),
                "color_details": video_data.video.color.model_dump(),
                "exposure_details": video_data.video.exposure.model_dump()
            },
            "camera_details": video_data.camera.model_dump(),
            "audio_tracks": [track.model_dump() for track in video_data.audio_tracks],
            "subtitle_tracks": [track.model_dump() for track in video_data.subtitle_tracks],
            "thumbnails": video_data.thumbnails
        }
        
        # Insert clip
        clip_result = client.table('clips').insert(clip_data).execute()
        clip_id = clip_result.data[0]['id']
        
        if logger:
            logger.info(f"Stored clip in database: {clip_id}")
        
        # Store transcript if available
        if video_data.analysis.ai_analysis and video_data.analysis.ai_analysis.audio_analysis:
            transcript_data = {
                "clip_id": clip_id,
                "full_text": video_data.analysis.ai_analysis.audio_analysis.transcript.full_text if video_data.analysis.ai_analysis.audio_analysis.transcript else "",
                "segments": [seg.model_dump() for seg in video_data.analysis.ai_analysis.audio_analysis.transcript.segments] if video_data.analysis.ai_analysis.audio_analysis.transcript else [],
                "speakers": [speaker.model_dump() for speaker in video_data.analysis.ai_analysis.audio_analysis.speaker_analysis.speakers] if video_data.analysis.ai_analysis.audio_analysis.speaker_analysis else [],
                "non_speech_events": [event.model_dump() for event in video_data.analysis.ai_analysis.audio_analysis.sound_events] if video_data.analysis.ai_analysis.audio_analysis.sound_events else []
            }
            
            client.table('transcripts').insert(transcript_data).execute()
            if logger:
                logger.info(f"Stored transcript for clip: {clip_id}")
        
        # Store AI analysis
        if video_data.analysis.ai_analysis:
            analysis_data = {
                "clip_id": clip_id,
                "analysis_type": "comprehensive",
                "analysis_scope": "full_clip",
                "ai_model": "gemini-flash-2.5",
                "content_category": video_data.analysis.ai_analysis.summary.content_category if video_data.analysis.ai_analysis.summary else None,
                "usability_rating": video_data.analysis.ai_analysis.visual_analysis.technical_quality.usability_rating if video_data.analysis.ai_analysis.visual_analysis and video_data.analysis.ai_analysis.visual_analysis.technical_quality else None,
                "speaker_count": video_data.analysis.ai_analysis.audio_analysis.speaker_analysis.speaker_count if video_data.analysis.ai_analysis.audio_analysis and video_data.analysis.ai_analysis.audio_analysis.speaker_analysis else 0,
                "visual_analysis": video_data.analysis.ai_analysis.visual_analysis.model_dump() if video_data.analysis.ai_analysis.visual_analysis else None,
                "audio_analysis": video_data.analysis.ai_analysis.audio_analysis.model_dump() if video_data.analysis.ai_analysis.audio_analysis else None,
                "content_analysis": video_data.analysis.ai_analysis.content_analysis.model_dump() if video_data.analysis.ai_analysis.content_analysis else None,
                "analysis_summary": video_data.analysis.ai_analysis.summary.model_dump() if video_data.analysis.ai_analysis.summary else None,
                "analysis_file_path": video_data.analysis.ai_analysis.analysis_file_path
            }
            
            client.table('analysis').insert(analysis_data).execute()
            if logger:
                logger.info(f"Stored AI analysis for clip: {clip_id}")
        
        return {
            'clip_id': clip_id,
            'stored_in_database': True,
            'database_url': f"https://supabase.com/dashboard/project/{os.getenv('SUPABASE_PROJECT_ID', 'unknown')}"
        }
        
    except Exception as e:
        if logger:
            logger.error(f"Failed to store video in database: {str(e)}")
        raise
```

### Step 6.2: Update Pipeline

Update `video_ingest_tool/processor.py` to add database storage step:

```python
# Add to your imports
from .database_storage import store_video_in_database
from .auth import auth_manager

# Add new pipeline step
@pipeline.register_step(
    name="database_storage", 
    enabled=False,  # Disabled by default
    description="Store video metadata and analysis in Supabase database"
)
def database_storage_step(data: Dict[str, Any], logger=None) -> Dict[str, Any]:
    """
    Store video data in Supabase database.
    
    Args:
        data: Pipeline data containing the output model
        logger: Optional logger
        
    Returns:
        Dict with database storage results
    """
    # Check authentication
    if not auth_manager.get_current_session():
        if logger:
            logger.warning("Skipping database storage - not authenticated")
        return {
            'database_storage_skipped': True,
            'reason': 'not_authenticated'
        }
    
    output = data.get('output')
    if not output:
        if logger:
            logger.error("No output model found for database storage")
        return {
            'database_storage_failed': True,
            'reason': 'no_output_model'
        }
    
    try:
        result = store_video_in_database(output, logger)
        if logger:
            logger.info(f"Successfully stored video in database: {result.get('clip_id')}")
        return result
        
    except Exception as e:
        if logger:
            logger.error(f"Database storage failed: {str(e)}")
        return {
            'database_storage_failed': True,
            'error': str(e)
        }
```

### Step 6.3: Update CLI Commands

Update your main ingest command to support database storage:

```python
# Update your ingest command in cli.py
@app.command()
def ingest(
    directory: str = typer.Argument(..., help="Directory to scan for video files"),
    recursive: bool = typer.Option(True, "--recursive/--no-recursive", help="Scan subdirectories"),
    limit: Optional[int] = typer.Option(None, "--limit", help="Limit number of files to process"),
    output_dir: Optional[str] = typer.Option(None, "--output-dir", help="Output directory for results"),
    config_file: Optional[str] = typer.Option(None, "--config", help="Pipeline configuration file"),
    enable: Optional[str] = typer.Option(None, "--enable", help="Comma-separated list of steps to enable"),
    disable: Optional[str] = typer.Option(None, "--disable", help="Comma-separated list of steps to disable"),
    store_database: bool = typer.Option(False, "--store-database", help="Store results in Supabase database"),
    generate_embeddings: bool = typer.Option(False, "--generate-embeddings", help="Generate vector embeddings"),
    compression_fps: int = typer.Option(5, "--compression-fps", help="Video compression frame rate"),
    compression_bitrate: str = typer.Option("1000k", "--compression-bitrate", help="Video compression bitrate")
):
    """
    Scan a directory for video files and extract metadata.
    """
    # Check authentication if database storage requested
    if store_database or generate_embeddings:
        require_authentication()
    
    # Your existing setup code...
    start_time = time.time()
    
    # Setup logging and get paths
    logger, json_dir, timestamp = setup_logging()
    run_dir = os.path.dirname(json_dir)
    thumbnails_dir = os.path.join(run_dir, "thumbnails")
    os.makedirs(thumbnails_dir, exist_ok=True)
    
    # Configure pipeline
    pipeline_config = get_default_pipeline_config()
    
    # Load config from file if specified
    if config_file:
        with open(config_file, 'r') as f:
            file_config = json.load(f)
            pipeline_config.update(file_config)
    
    # Apply command-line overrides
    if enable:
        for step in enable.split(','):
            pipeline_config[step.strip()] = True
    
    if disable:
        for step in disable.split(','):
            pipeline_config[step.strip()] = False
    
    # Enable database features if requested
    if store_database:
        pipeline_config['database_storage'] = True
    
    if generate_embeddings:
        pipeline_config['generate_embeddings'] = True
        pipeline_config['database_storage'] = True  # Embeddings require database
    
    # Save active configuration
    config_path = os.path.join(run_dir, "pipeline_config.json")
    with open(config_path, 'w') as f:
        json.dump(pipeline_config, f, indent=2)
    
    # Process files with updated configuration
    # ... rest of your existing ingest logic remains the same
```

---

## 7. Vector Embeddings Integration

### Step 7.1: Embedding Service

Create `video_ingest_tool/embeddings.py`:

```python
"""
Vector embeddings generation using BAAI/bge-m3 via DeepInfra.
"""

import os
import openai
import tiktoken
from typing import List, Dict, Any, Optional, Tuple
import structlog

logger = structlog.get_logger(__name__)

# Configure OpenAI client for DeepInfra
def get_embedding_client():
    """Get OpenAI client configured for DeepInfra API."""
    return openai.OpenAI(
        api_key=os.getenv("DEEPINFRA_API_KEY"),
        base_url="https://api.deepinfra.com/v1/openai"
    )

def count_tokens(text: str) -> int:
    """
    Count tokens in text using tiktoken.
    
    Args:
        text: Text to count tokens for
        
    Returns:
        Number of tokens
    """
    try:
        encoding = tiktoken.get_encoding("cl100k_base")  # GPT-4 encoding
        return len(encoding.encode(text))
    except Exception as e:
        logger.warning(f"Failed to count tokens: {str(e)}")
        # Rough estimate: 1 token ≈ 4 characters
        return len(text) // 4

def truncate_text(text: str, max_tokens: int = 3500) -> Tuple[str, str]:
    """
    Intelligently truncate text to fit token limit.
    
    Args:
        text: Text to truncate
        max_tokens: Maximum token limit
        
    Returns:
        Tuple of (truncated_text, truncation_method)
    """
    token_count = count_tokens(text)
    
    if token_count <= max_tokens:
        return text, "none"
    
    try:
        encoding = tiktoken.get_encoding("cl100k_base")
        tokens = encoding.encode(text)
        
        # Truncate to max_tokens
        truncated_tokens = tokens[:max_tokens]
        truncated_text = encoding.decode(truncated_tokens)
        
        return truncated_text, "first_n_tokens"
        
    except Exception as e:
        logger.warning(f"Failed to truncate with tiktoken: {str(e)}")
        # Fallback: character-based truncation
        char_limit = max_tokens * 4  # Rough estimate
        return text[:char_limit], "char_estimate"

def prepare_embedding_content(
    summary: Optional[str] = None,
    transcript: Optional[str] = None,
    keywords: Optional[List[str]] = None,
    entities: Optional[List[str]] = None,
    activities: Optional[List[str]] = None
) -> Tuple[str, str, Dict[str, Any]]:
    """
    Prepare content for embedding generation.
    
    Args:
        summary: AI-generated summary
        transcript: Full transcript text
        keywords: List of keywords/tags
        entities: List of detected entities
        activities: List of activities
        
    Returns:
        Tuple of (summary_content, keyword_content, metadata)
    """
    # Prepare summary content (priority 1: summary + key info)
    summary_parts = []
    if summary:
        summary_parts.append(f"Summary: {summary}")
    if entities:
        summary_parts.append(f"Entities: {', '.join(entities[:10])}")  # Top 10 entities
    if activities:
        summary_parts.append(f"Activities: {', '.join(activities[:5])}")  # Top 5 activities
    
    summary_content = " ".join(summary_parts)
    
    # Prepare keyword content (priority 2: keywords + tags)
    keyword_parts = []
    if keywords:
        keyword_parts.append(" ".join(keywords))
    
    keyword_content = " ".join(keyword_parts)
    
    # Add transcript if there's room
    if transcript:
        # Calculate remaining space for summary embedding
        summary_tokens = count_tokens(summary_content)
        remaining_summary_tokens = 3500 - summary_tokens
        
        if remaining_summary_tokens > 100:  # Leave some buffer
            transcript_excerpt, _ = truncate_text(transcript, remaining_summary_tokens)
            summary_content += f" Transcript: {transcript_excerpt}"
    
    # Truncate both contents to be safe
    summary_content, summary_truncation = truncate_text(summary_content, 3500)
    keyword_content, keyword_truncation = truncate_text(keyword_content, 3500)
    
    metadata = {
        "summary_tokens": count_tokens(summary_content),
        "keyword_tokens": count_tokens(keyword_content),
        "summary_truncation": summary_truncation,
        "keyword_truncation": keyword_truncation,
        "original_transcript_length": len(transcript) if transcript else 0
    }
    
    return summary_content, keyword_content, metadata

def generate_embeddings(
    summary_content: str,
    keyword_content: str,
    logger=None
) -> Tuple[List[float], List[float]]:
    """
    Generate embeddings using BAAI/bge-m3.
    
    Args:
        summary_content: Content for summary embedding
        keyword_content: Content for keyword embedding
        logger: Optional logger
        
    Returns:
        Tuple of (summary_embedding, keyword_embedding)
    """
    try:
        client = get_embedding_client()
        
        # Generate summary embedding
        summary_response = client.embeddings.create(
            input=summary_content,
            model="BAAI/bge-m3",
            encoding_format="float"
        )
        summary_embedding = summary_response.data[0].embedding
        
        # Generate keyword embedding
        keyword_response = client.embeddings.create(
            input=keyword_content,
            model="BAAI/bge-m3",
            encoding_format="float"
        )
        keyword_embedding = keyword_response.data[0].embedding
        
        if logger:
            logger.info(f"Generated embeddings - Summary: {len(summary_embedding)}D, Keywords: {len(keyword_embedding)}D")
        
        return summary_embedding, keyword_embedding
        
    except Exception as e:
        if logger:
            logger.error(f"Failed to generate embeddings: {str(e)}")
        raise

def store_embeddings(
    clip_id: str,
    summary_embedding: List[float],
    keyword_embedding: List[float],
    summary_content: str,
    keyword_content: str,
    original_content: str,
    metadata: Dict[str, Any],
    logger=None
) -> bool:
    """
    Store embeddings in Supabase database.
    
    Args:
        clip_id: Clip ID
        summary_embedding: Summary vector
        keyword_embedding: Keyword vector
        summary_content: Content used for summary embedding
        keyword_content: Content used for keyword embedding
        original_content: Original full content before truncation
        metadata: Embedding metadata
        logger: Optional logger
        
    Returns:
        True if successful
    """
    from .auth import auth_manager
    
    client = auth_manager.get_authenticated_client()
    if not client:
        raise ValueError("Authentication required for storing embeddings")
    
    try:
        vector_data = {
            "clip_id": clip_id,
            "embedding_type": "full_clip",
            "embedding_source": "combined",
            "summary_vector": summary_embedding,
            "keyword_vector": keyword_embedding,
            "embedded_content": f"Summary: {summary_content}\nKeywords: {keyword_content}",
            "original_content": original_content,
            "token_count": metadata["summary_tokens"] + metadata["keyword_tokens"],
            "original_token_count": count_tokens(original_content),
            "truncation_method": metadata["summary_truncation"]
        }
        
        result = client.table('vectors').insert(vector_data).execute()
        
        if logger:
            logger.info(f"Stored embeddings for clip: {clip_id}")
        
        return True
        
    except Exception as e:
        if logger:
            logger.error(f"Failed to store embeddings: {str(e)}")
        raise
```

### Step 7.2: Embedding Pipeline Step

Add to `video_ingest_tool/processor.py`:

```python
# Add to imports
from .embeddings import prepare_embedding_content, generate_embeddings, store_embeddings

@pipeline.register_step(
    name="generate_embeddings", 
    enabled=False,  # Disabled by default
    description="Generate vector embeddings for semantic search"
)
def generate_embeddings_step(data: Dict[str, Any], logger=None) -> Dict[str, Any]:
    """
    Generate and store vector embeddings.
    
    Args:
        data: Pipeline data containing clip_id and analysis data
        logger: Optional logger
        
    Returns:
        Dict with embedding results
    """
    # Check authentication
    from .auth import auth_manager
    if not auth_manager.get_current_session():
        if logger:
            logger.warning("Skipping embedding generation - not authenticated")
        return {
            'embeddings_skipped': True,
            'reason': 'not_authenticated'
        }
    
    clip_id = data.get('clip_id')
    if not clip_id:
        if logger:
            logger.error("No clip_id found for embedding generation")
        return {
            'embeddings_failed': True,
            'reason': 'no_clip_id'
        }
    
    try:
        # Extract content from AI analysis
        ai_analysis_summary = data.get('ai_analysis_summary', {})
        full_ai_analysis = data.get('full_ai_analysis_data', {})
        
        # Prepare content
        summary = ai_analysis_summary.get('overall_summary')
        transcript = None
        keywords = data.get('content_tags', [])
        entities = []
        activities = []
        
        # Extract from full AI analysis if available
        if full_ai_analysis:
            if 'audio_analysis' in full_ai_analysis and full_ai_analysis['audio_analysis'].get('transcript'):
                transcript = full_ai_analysis['audio_analysis']['transcript'].get('full_text')
            
            if 'content_analysis' in full_ai_analysis:
                content_analysis = full_ai_analysis['content_analysis']
                if 'entities' in content_analysis:
                    entities_data = content_analysis['entities']
                    # Extract entity names
                    for person in entities_data.get('people_details', []):
                        if person.get('description'):
                            entities.append(person['description'])
                    for location in entities_data.get('locations', []):
                        entities.append(location.get('name', ''))
                    for obj in entities_data.get('objects_of_interest', []):
                        entities.append(obj.get('object', ''))
                
                # Extract activities
                for activity in content_analysis.get('activity_summary', []):
                    activities.append(activity.get('activity', ''))
        
        # Prepare embedding content
        summary_content, keyword_content, metadata = prepare_embedding_content(
            summary=summary,
            transcript=transcript,
            keywords=keywords,
            entities=entities,
            activities=activities
        )
        
        # Generate embeddings
        summary_embedding, keyword_embedding = generate_embeddings(
            summary_content, keyword_content, logger
        )
        
        # Store embeddings
        original_content = f"{summary or ''}\n{transcript or ''}\n{' '.join(keywords)}"
        store_embeddings(
            clip_id=clip_id,
            summary_embedding=summary_embedding,
            keyword_embedding=keyword_embedding,
            summary_content=summary_content,
            keyword_content=keyword_content,
            original_content=original_content,
            metadata=metadata,
            logger=logger
        )
        
        return {
            'embeddings_generated': True,
            'summary_tokens': metadata['summary_tokens'],
            'keyword_tokens': metadata['keyword_tokens'],
            'truncation_applied': metadata['summary_truncation'] != 'none'
        }
        
    except Exception as e:
        if logger:
            logger.error(f"Embedding generation failed: {str(e)}")
        return {
            'embeddings_failed': True,
            'error': str(e)
        }
```

---

## 8. Hybrid Search Implementation

### Step 8.1: Hybrid Search Function

Add this function to your Supabase database (SQL Editor):

```sql
-- =====================================================
-- HYBRID SEARCH FUNCTION
-- =====================================================

CREATE OR REPLACE FUNCTION hybrid_search_videos(
  query_text TEXT,
  query_summary_embedding vector(1024),
  query_keyword_embedding vector(1024),
  user_id_filter UUID,
  match_count INT DEFAULT 10,
  fulltext_weight FLOAT DEFAULT 1.0,
  summary_weight FLOAT DEFAULT 1.0,
  keyword_weight FLOAT DEFAULT 0.8,
  rrf_k INT DEFAULT 50
)
RETURNS TABLE (
  id UUID,
  file_name TEXT,
  local_path TEXT,
  content_summary TEXT,
  content_tags TEXT[],
  duration_seconds NUMERIC,
  camera_make TEXT,
  camera_model TEXT,
  similarity_score FLOAT,
  search_rank FLOAT
)
LANGUAGE SQL
AS $
WITH fulltext AS (
  SELECT
    c.id, c.file_name, c.local_path, c.content_summary, 
    c.content_tags, c.duration_seconds, c.camera_make, c.camera_model,
    ROW_NUMBER() OVER(ORDER BY ts_rank_cd(c.fts, websearch_to_tsquery(query_text)) DESC) as rank_ix
  FROM clips c
  WHERE c.user_id = user_id_filter
    AND c.fts @@ websearch_to_tsquery(query_text)
  LIMIT LEAST(match_count, 30) * 2
),
summary_semantic AS (
  SELECT
    c.id, c.file_name, c.local_path, c.content_summary,
    c.content_tags, c.duration_seconds, c.camera_make, c.camera_model,
    (v.summary_vector <#> query_summary_embedding) * -1 as similarity_score,
    ROW_NUMBER() OVER (ORDER BY v.summary_vector <#> query_summary_embedding) as rank_ix
  FROM clips c
  JOIN vectors v ON c.id = v.clip_id
  WHERE c.user_id = user_id_filter
    AND v.embedding_type = 'full_clip'
  LIMIT LEAST(match_count, 30) * 2
),
keyword_semantic AS (
  SELECT
    c.id,
    (v.keyword_vector <#> query_keyword_embedding) * -1 as similarity_score,
    ROW_NUMBER() OVER (ORDER BY v.keyword_vector <#> query_keyword_embedding) as rank_ix
  FROM clips c
  JOIN vectors v ON c.id = v.clip_id
  WHERE c.user_id = user_id_filter
    AND v.embedding_type = 'full_clip'
  LIMIT LEAST(match_count, 30) * 2
)
SELECT
  COALESCE(ft.id, ss.id) as id,
  COALESCE(ft.file_name, ss.file_name) as file_name,
  COALESCE(ft.local_path, ss.local_path) as local_path,
  COALESCE(ft.content_summary, ss.content_summary) as content_summary,
  COALESCE(ft.content_tags, ss.content_tags) as content_tags,
  COALESCE(ft.duration_seconds, ss.duration_seconds) as duration_seconds,
  COALESCE(ft.camera_make, ss.camera_make) as camera_make,
  COALESCE(ft.camera_model, ss.camera_model) as camera_model,
  COALESCE(ss.similarity_score, 0.0) as similarity_score,
  -- RRF SCORING WITH DUAL VECTORS
  COALESCE(1.0 / (rrf_k + ft.rank_ix), 0.0) * fulltext_weight +
  COALESCE(1.0 / (rrf_k + ss.rank_ix), 0.0) * summary_weight +
  COALESCE(1.0 / (rrf_k + ks.rank_ix), 0.0) * keyword_weight as search_rank
FROM fulltext ft
FULL OUTER JOIN summary_semantic ss ON ft.id = ss.id
FULL OUTER JOIN keyword_semantic ks ON COALESCE(ft.id, ss.id) = ks.id
ORDER BY search_rank DESC
LIMIT match_count;
$;