# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

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
# Install dependencies (no requirements.txt - check plan.md for dependency list)
pip install av pymediainfo PyExifTool opencv-python typer[all] rich pydantic structlog numpy pillow polyfile hachoir python-dateutil transformers torch google-generativeai python-dotenv

# External dependencies required:
# - FFmpeg (must be in PATH)
# - ExifTool (must be in PATH)
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

## Future Database Integration
The codebase is designed for future Supabase PostgreSQL integration with:
- Detailed database schema planned in `SUPABASE_IMPLEMENTATION.md`
- Vector embeddings for semantic search
- Multi-user authentication and row-level security
- Task queue system with Procrastinate

## Testing
Currently no test files exist. When adding tests, follow the existing project structure and use the comprehensive data models for test fixtures.