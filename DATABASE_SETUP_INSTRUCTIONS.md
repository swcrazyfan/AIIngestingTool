# Database Setup Instructions

## Complete AI Ingesting Tool Database Schema

Your `database_setup.sql` file now contains the **complete schema** based on your SUPABASE_IMPLEMENTATION.md:

### ✅ What's Included:

1. **User Profiles** (with auto-creation trigger) - ✅ This fixes your profile creation issue
2. **Clips Table** - Main video metadata storage
3. **Segments Table** - Segment-level analysis
4. **Analysis Table** - AI analysis results 
5. **Vectors Table** - Vector embeddings for search
6. **Transcripts Table** - Video transcriptions
7. **Performance Indexes** - Optimized for search and queries
8. **Row Level Security Policies** - Complete security setup
9. **Helper Functions** - Utility functions for the CLI

### 🚀 How to Apply:

1. **Go to your Supabase Dashboard**
   - Visit: https://supabase.com/dashboard
   - Select your project: https://dwnujuxvakiqsqnimkby.supabase.co

2. **Open SQL Editor**
   - Click "SQL Editor" in the left sidebar
   - Click "New Query"

3. **Copy and Paste**
   - Copy the ENTIRE contents of `database_setup.sql`  
   - Paste into the SQL Editor

4. **Run the Script**
   - Click "Run" or press Ctrl+Enter
   - This will create all tables, indexes, policies, and functions

### 🧪 Test After Setup:

```bash
# Test the connection (should show all tables as "Exists")
conda activate video-ingest
cd /Users/developer/Development/GitHub/AIIngestingTool
python test_supabase.py

# Test authentication
python -m video_ingest_tool auth signup
python -m video_ingest_tool auth login
python -m video_ingest_tool auth status
```

### 🔑 Key Features:

- **Auto Profile Creation**: Users automatically get profiles when they sign up
- **Row Level Security**: Users can only see their own data
- **Admin Support**: Admin users can see all data
- **Vector Search Ready**: Supports BAAI/bge-m3 embeddings
- **Full Text Search**: Built-in search across all content
- **Segment Support**: Ready for future segment-level analysis

This is the complete database schema that will support all your AI Ingesting Tool features!
