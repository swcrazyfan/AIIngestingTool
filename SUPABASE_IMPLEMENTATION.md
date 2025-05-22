# Supabase Implementation Guide
## AI-Powered Video Ingest & Catalog Tool Database Integration

> **Complete step-by-step implementation guide for integrating Supabase with the video ingest tool**

---

## Table of Contents

1. [Project Setup](#1-project-setup)
2. [Database Schema Implementation](#2-database-schema-implementation)
3. [Authentication Setup](#3-authentication-setup)
4. [Python Client Integration](#4-python-client-integration)
5. [Pipeline Integration](#5-pipeline-integration)
6. [Vector Embeddings Implementation](#6-vector-embeddings-implementation)
7. [Hybrid Search Implementation](#7-hybrid-search-implementation)
8. [CLI Commands](#8-cli-commands)
9. [Testing & Validation](#9-testing--validation)
10. [Deployment & Configuration](#10-deployment--configuration)

---

## 1. Project Setup

### 1.1. Create Supabase Project

1. **Go to [supabase.com](https://supabase.com) and sign up/login**

2. **Create a new project:**
   - Click "New Project"
   - Organization: Select or create
   - Project Name: `ai-video-catalog`
   - Database Password: Generate strong password (save it!)
   - Region: Choose closest to your location
   - Pricing Plan: Start with Free tier

3. **Wait for project creation** (~2-5 minutes)

4. **Get your project credentials:**
   - Go to Project Settings → API
   - Copy your `Project URL` 
   - Copy your `anon public` key
   - Copy your `service_role secret` key (for admin operations)

### 1.2. Enable Required Extensions

1. **Go to Database → Extensions**

2. **Enable these extensions:**
   ```sql
   -- Enable UUID generation
   CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
   
   -- Enable vector similarity search
   CREATE EXTENSION IF NOT EXISTS "vector";
   ```

3. **Verify extensions are enabled:**
   ```sql
   SELECT * FROM pg_extension WHERE extname IN ('uuid-ossp', 'vector');
   ```

### 1.3. Configure Environment Variables

Create a `.env` file in your project root:

```bash
# Supabase Configuration
SUPABASE_URL=https://your-project-ref.supabase.co
SUPABASE_ANON_KEY=your-anon-key-here
SUPABASE_SERVICE_ROLE_KEY=your-service-role-key-here

# AI Service Configuration (existing)
GEMINI_API_KEY=your-gemini-api-key
DEEPINFRA_API_KEY=your-deepinfra-api-key

# Vector Embedding Configuration
EMBEDDING_MODEL=BAAI/bge-m3
EMBEDDING_DIMENSIONS=1024
EMBEDDING_MAX_TOKENS=3500
```

---

## 2. Database Schema Implementation

### 2.1. Create Core Tables

Execute these SQL commands in Supabase SQL Editor:

```sql
-- =====================================================
-- 1. USER PROFILES (extends built-in auth.users)
-- =====================================================

CREATE TABLE user_profiles (
  id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
  profile_type TEXT CHECK (profile_type IN ('admin', 'user')) DEFAULT 'user',
  full_name TEXT,
  avatar_url TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- =====================================================
-- 2. CLIPS - Main video table
-- =====================================================

CREATE TABLE clips (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID REFERENCES auth.users(id) NOT NULL,
  
  -- File information
  file_path TEXT NOT NULL,
  local_path TEXT NOT NULL, -- Absolute local file system path
  file_name TEXT NOT NULL,
  file_checksum TEXT UNIQUE NOT NULL,
  file_size_bytes BIGINT NOT NULL,
  duration_seconds NUMERIC,
  created_at TIMESTAMPTZ,
  processed_at TIMEST