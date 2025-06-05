# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

The AI Video Ingest Tool is a comprehensive system for processing, analyzing, and managing video files with AI-powered insights. It consists of two main components:

1. **Python Backend** (`video_ingest_tool/`) - Video processing pipeline and API server
2. **Adobe Premiere Pro Extension** (`ait-extension/`) - Frontend interface for video professionals

## Development Commands

### Environment Setup
```bash
# Activate conda environment (REQUIRED for ALL Python operations)
conda activate video-ingest

# Install Python dependencies
pip install -r requirements.txt

# Install frontend dependencies
cd ait-extension && yarn install
```

**CRITICAL**: All Python commands must be prefixed with `conda activate video-ingest &&` or run within an activated environment. The Python dependencies are installed in this conda environment, not globally.

### Service Management
```bash
# Start all services (Prefect server, worker, API server)
./start_all_services.sh

# Or use CLI commands individually
conda activate video-ingest && python -m video_ingest_tool.cli start-services all
conda activate video-ingest && python -m video_ingest_tool.cli stop-services all
conda activate video-ingest && python -m video_ingest_tool.cli services-status
```

### Core Operations
```bash
# Ingest videos
conda activate video-ingest && python -m video_ingest_tool.cli ingest /path/to/videos

# Search functionality
conda activate video-ingest && python -m video_ingest_tool.cli search query "search terms"
conda activate video-ingest && python -m video_ingest_tool.cli search similar <clip-id>

# Clip management
conda activate video-ingest && python -m video_ingest_tool.cli clip list
conda activate video-ingest && python -m video_ingest_tool.cli clip show <clip-id>

# Category management (NEW)
conda activate video-ingest && python -m video_ingest_tool.cli category list
conda activate video-ingest && python -m video_ingest_tool.cli category show "Tutorial"
```

### Frontend Development
```bash
cd ait-extension/

# Development mode with hot reload
yarn dev

# Build for production
yarn build

# Package as ZXP for distribution
yarn zxp
```

### Testing
```bash
# Run all tests
conda activate video-ingest && pytest

# Test markers available:
# - integration: tests requiring external services
```

## Architecture Overview

### Backend Pipeline System
- **Modular Processing Pipeline**: 15+ configurable steps organized in categories (Processing, Extraction, Analysis, Storage)
- **DuckDB Database**: Local database for metadata storage with vector search capabilities
- **Prefect Orchestration**: Background task processing with concurrency limits
- **API Server**: Flask + SocketIO for REST API and real-time WebSocket communication

### Frontend Extension
- **React 18 + TypeScript** with Adobe CEP integration
- **Real-time Communication** with Python backend via WebSocket
- **Video Library Interface** for browsing, searching, and timeline integration

### Database Schema
The main table `app_data.clips` contains:
- File metadata (path, checksum, size, codec details)
- Camera information (make, model, settings, GPS)
- AI analysis results (categories, tags, summary, transcript)
- Multiple embeddings for semantic search (summary, keyword, thumbnail embeddings)

## Key Configuration

### Port Configuration (`config/ports.json`)
- Prefect server: 4201
- API server: 8001
- All services use standardized URLs

### Pipeline Configuration
Steps can be enabled/disabled individually. Key concurrency limits:
- `video_compression_step`: 2
- `ai_analysis_step`: 1
- `transcription_step`: 2
- `embedding_step`: 1

### Environment Variables
- `PREFECT_API_URL`: http://127.0.0.1:4201/api
- `PREFECT_API_DATABASE_CONNECTION_URL`: sqlite+aiosqlite:///./data/prefect.db

## Development Workflow

1. **Start Services**: Always run `./start_all_services.sh` before development
2. **Code Changes**: Backend changes require service restart; frontend has hot reload
3. **Testing**: Run `pytest` for backend tests; frontend has no specific test configuration
4. **Database**: DuckDB files are stored locally in `data/` directory

## Important Implementation Details

### Search Capabilities
- **Hybrid Search**: Combines semantic and full-text search
- **Vector Similarity**: Multiple embedding types (1024 and 1152 dimensions)
- **HNSW Indexes**: For efficient similarity search

### AI Integration
- **Gemini Flash 2.5**: Primary AI analysis engine
- **Multi-modal Analysis**: Video content, shot detection, quality assessment
- **Thumbnail Selection**: AI-powered best frame selection

### File Processing
- **Media Extraction**: FFprobe, MediaInfo, ExifTool integration
- **Background Processing**: Prefect manages long-running video analysis
- **Progress Tracking**: Real-time updates via WebSocket

## Extension Integration

The Adobe Premiere Pro extension provides:
- Direct timeline integration (add clips at playhead position)
- Metadata display and search interface
- Batch processing directory selection
- Real-time progress monitoring

## Critical Dependencies

- **Python 3.x** with conda environment management
- **Adobe Premiere Pro 2020+** for extension functionality
- **FFmpeg** and media processing tools
- **Node.js 16+** with Yarn for frontend development