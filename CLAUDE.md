# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Current Development Context
- **Active Branch**: `supabase` (implementing database integration)
- **Main Branch**: `main` (stable release)
- **Current Focus**: Supabase database integration and authentication
- **Status**: Core processing pipeline complete, database integration in progress

## Project Overview

This is an AI-Powered Video Ingest & Catalog Tool - a comprehensive CLI application for automated video content analysis, categorization, and metadata extraction. The tool processes video files through a configurable pipeline to extract technical metadata, generate thumbnails, perform AI-powered content analysis, and output structured JSON data.

## Architecture

### Core Components

**Main Entry Point**: `video_ingest_tool/__main__.py` - imports and runs the CLI
**CLI Interface**: `video_ingest_tool/cli.py` - Typer-based command-line interface with two main commands:
- `ingest` - Main processing command with extensive configuration options
- `list_steps` - Shows available pipeline steps

**Processing Pipeline**: `video_ingest_tool/pipeline.py` - Modular pipeline system with:
- `ProcessingPipeline` class for managing configurable steps
- `ProcessingStep` class for individual processing operations
- Decorator-based step registration system
- Runtime enable/disable configuration

**Data Models**: `video_ingest_tool/models.py` - Comprehensive Pydantic models including:
- `VideoIngestOutput` - Main output model containing all extracted data
- Technical metadata models (video, audio, subtitle tracks)
- AI analysis models (visual, audio, content analysis)
- 25+ detailed model classes for structured data

### Key Processing Modules

- `discovery.py` - Directory scanning and file discovery
- `processor.py` - Main processing orchestration and pipeline execution
- `extractors.py`, `extractors_extended.py`, `extractors_hdr.py` - Metadata extraction using multiple tools
- `video_processor.py` - AI video analysis and compression
- `output.py` - JSON output and file organization
- `config.py` - Logging setup and configuration
- `utils.py` - Utility functions

## Common Development Commands

### Running the Tool
```bash
# Basic usage - process videos in a directory
python -m video_ingest_tool ingest /path/to/videos/

# With configuration options
python -m video_ingest_tool ingest /path/to/videos/ --recursive --limit=5 --output-dir=output

# Configure pipeline steps
python -m video_ingest_tool ingest /path/to/videos/ --disable=hdr_extraction,ai_focal_length
python -m video_ingest_tool ingest /path/to/videos/ --enable=ai_video_analysis --fps=5 --bitrate=1000k

# List available pipeline steps
python -m video_ingest_tool list_steps
```

### Development Setup
```bash
# Install dependencies
pip install -r requirements.txt

# External dependencies required:
# - FFmpeg (must be in PATH)
# - ExifTool (must be in PATH)

# Set up environment variables (copy and modify)
cp .env.example .env
# Edit .env with your API keys
```

### Authentication Commands (Supabase Integration)
```bash
# Login to your account
python -m video_ingest_tool auth login

# Check authentication status
python -m video_ingest_tool auth status

# View user profile and statistics
python -m video_ingest_tool profile show
python -m video_ingest_tool profile stats

# Logout
python -m video_ingest_tool auth logout
```

### Database Integration Commands
```bash
# Process videos and store in database
python -m video_ingest_tool ingest /path/to/videos/ --store-database

# Generate vector embeddings for semantic search
python -m video_ingest_tool ingest /path/to/videos/ --store-database --generate-embeddings

# Test database connection
python -m video_ingest_tool test-db
```

## Important Implementation Details

### Pipeline System
The tool uses a modular pipeline architecture where each processing step can be individually enabled/disabled:
- Steps are registered using decorators in `processor.py`
- Configuration via CLI parameters (`--enable`, `--disable`) or JSON config files
- Each step receives data dictionary and returns updates to merge back

### AI Integration
- **Gemini Flash 2.5** integration for comprehensive video analysis (disabled by default due to API costs)
- Hardware-accelerated video compression for AI processing
- Structured AI analysis output including transcription, visual analysis, content analysis
- Separate detailed AI analysis JSON files

### Output Structure
Creates timestamped run directories with organized output:
```
run_YYYYMMDD_HHMMSS/
├── json/          # Individual video JSON files
├── thumbnails/    # Video thumbnails by checksum
├── ai_analysis/   # Detailed AI analysis files
├── compressed/    # Compressed videos for AI analysis
└── logs/          # Processing logs
```

### Key Features
- **Non-destructive processing** - never modifies original files
- **Checksum-based deduplication** - avoids reprocessing identical files
- **Comprehensive metadata extraction** - technical, HDR, audio, subtitle metadata
- **Intelligent thumbnail generation** - evenly distributed keyframes
- **Configurable pipeline** - enable/disable specific processing steps
- **Rich CLI interface** - progress bars, tables, colored output
- **Structured data models** - 25+ Pydantic models for type safety

## Dependencies and Requirements

### Python Dependencies
The project has extensive dependencies listed in `plan.md` section 8.1, including:
- PyAV, pymediainfo, PyExifTool for metadata extraction
- OpenCV, Pillow for image processing
- Typer, Rich for CLI interface
- Pydantic for data validation
- Google Generative AI for AI analysis
- Transformers, PyTorch for AI focal length detection

### External Dependencies
- **FFmpeg** - must be installed and available in PATH
- **ExifTool** - must be installed and available in PATH

## Database Integration (In Progress)
The codebase is transitioning to Supabase PostgreSQL integration:

### Current Status
- **Database Schema**: Complete schema designed in `SUPABASE_IMPLEMENTATION.md`
- **Authentication System**: Implemented in `auth.py` with JWT tokens
- **Vector Embeddings**: Ready for BAAI/bge-m3 via DeepInfra API
- **CLI Commands**: Auth and profile management commands available

### Key Files for Database Work
- `supabase_config.py` - Supabase client configuration
- `auth.py` - Authentication management
- `SUPABASE_IMPLEMENTATION.md` - Complete implementation guide
- `DATABASE_SETUP_INSTRUCTIONS.md` - Setup instructions
- `SUPABASE_FIX.sql` - Database fixes and migrations

### Environment Variables Required
```bash
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_ANON_KEY=your_anon_key
SUPABASE_SERVICE_ROLE_KEY=your_service_role_key
DEEPINFRA_API_KEY=your_deepinfra_key
GEMINI_API_KEY=your_gemini_key
```

## Testing and Validation
- `test_supabase.py` - Database connection testing
- Use existing comprehensive data models for test fixtures
- Test files should follow the existing project structure

## Development Best Practices
- Always check authentication before database operations
- Use the pipeline system for new processing steps
- Store absolute local paths for CLI file access
- Follow the existing Pydantic model patterns

## Common Development Tasks

### Adding a New Pipeline Step
1. Open `video_ingest_tool/processor.py`
2. Use the `@pipeline.register_step()` decorator
3. Set enabled=False by default for experimental features
4. Include comprehensive error handling and logging

### Database Operations
1. Always check authentication with `auth_manager.get_current_session()`
2. Use authenticated client: `auth_manager.get_authenticated_client()`
3. Follow the database schema in `SUPABASE_IMPLEMENTATION.md`
4. Test connections with `test_supabase.py`

### Running Tests
```bash
# Test database connection
python test_supabase.py

# Test video processing on sample files
python -m video_ingest_tool ingest /path/to/test/videos/ --limit=1

# Test specific pipeline steps
python -m video_ingest_tool ingest /path/to/test/videos/ --enable=checksum_generation --disable=all_others
```

## Troubleshooting

### Common Issues
- **FFmpeg not found**: Ensure FFmpeg is installed and in PATH
- **ExifTool not found**: Install ExifTool and verify PATH
- **Authentication failed**: Check `.env` file and Supabase credentials
- **Database connection failed**: Verify Supabase URL and keys
- **Pipeline step failed**: Check logs in `logs/` directory

### Debug Mode
- Enable verbose logging by checking `config.py`
- View pipeline step execution in real-time
- Check individual JSON outputs in run directories