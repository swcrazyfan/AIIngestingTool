# Video Ingest Tool Architecture

## Overview

The Video Ingest Tool is a modular pipeline system designed to process video files, extract metadata, analyze content, and store results. The system has been refactored to improve modularity, maintainability, and extensibility.

## Core Components

### Pipeline System

The core of the application is a flexible pipeline architecture that:
- Defines a sequence of processing steps
- Allows steps to be enabled/disabled
- Passes data between steps
- Handles errors gracefully

**Key Files:**
- `pipeline/base.py` - Contains `ProcessingPipeline` and `ProcessingStep` classes
- `pipeline/registry.py` - Handles step registration and pipeline creation

### Step Categories

Steps are organized into four main categories:

1. **Extraction Steps** - Extract metadata from video files
   - MediaInfo extraction
   - FFprobe extraction
   - EXIF extraction
   - Codec parameter extraction
   - HDR metadata extraction
   - Audio/subtitle track extraction

2. **Analysis Steps** - Analyze video content
   - Thumbnail generation
   - Exposure analysis
   - Focal length detection
   - AI video analysis with Gemini

3. **Processing Steps** - Process extracted data
   - Checksum generation
   - Duplicate detection
   - Metadata consolidation

4. **Storage Steps** - Store and index processed data
   - Model creation
   - Database storage
   - Vector embeddings generation

### Video Processing Components

Specialized components for video compression and AI analysis:

- `VideoCompressor` - Hardware-accelerated video compression with ffmpeg
- `VideoAnalyzer` - AI-powered video analysis using Gemini Flash 2.5
- `VideoProcessor` - Orchestrates compression and analysis workflows

### Configuration System

Configuration management for pipeline and components:

- `config/constants.py` - System-wide constants
- `config/settings.py` - Configuration management
- `config/logging.py` - Logging setup

## Directory Structure

```
video_ingest_tool/
├── pipeline/                      # Pipeline infrastructure
│   ├── base.py                    # Core pipeline classes
│   └── registry.py                # Step registration system
├── steps/                         # Pipeline steps
│   ├── extraction/                # Metadata extraction steps
│   ├── analysis/                  # Analysis steps
│   ├── processing/                # Processing steps
│   └── storage/                   # Database and model steps
├── extractors/                    # Low-level extraction functions
│   ├── media.py                   # MediaInfo and FFprobe
│   ├── exif.py                    # EXIF extraction
│   ├── codec.py                   # Codec parameters
│   ├── hdr.py                     # HDR metadata
│   └── tracks.py                  # Audio/subtitle tracks
├── video_processor/               # Video processing components
│   ├── compression.py             # VideoCompressor class
│   ├── analysis.py                # VideoAnalyzer class
│   └── processor.py               # Main VideoProcessor class
├── config/                        # Configuration
│   ├── constants.py               # Constants and feature flags
│   ├── settings.py                # Configuration management
│   └── logging.py                 # Logging setup
└── processor.py                   # Main entry point
```

## Data Flow

1. **Input** - Video file path is provided to the pipeline
2. **Extraction** - Metadata is extracted from the video file
3. **Processing** - Extracted data is processed (checksums, deduplication)
4. **Analysis** - Video content is analyzed (thumbnails, exposure, AI)
5. **Storage** - Results are stored in database and indexed for search
6. **Output** - A comprehensive model is returned with all processed data

## Extension Points

The system can be extended by:

1. **Adding new steps** - Register new steps with `@register_step` decorator
2. **Creating extractors** - Add new extraction functions in `extractors/`
3. **Enhancing analysis** - Add new analysis tools in `steps/analysis/`
4. **Storage integrations** - Implement new storage backends in `steps/storage/`

## Configuration

Configuration is managed through:

1. **Environment variables** - Loaded from `.env` file
2. **Constants** - Defined in `config/constants.py`
3. **Step settings** - Configure steps through the pipeline API

## Usage Example

```python
from video_ingest_tool.processor import process_video_file

# Process a video file
result = process_video_file(
    file_path="path/to/video.mp4",
    thumbnails_dir="output/thumbnails",
    compression_fps=5,
    compression_bitrate="500k"
)

# Access processed data
video_details = result.video
camera_info = result.camera
analysis = result.analysis
``` 