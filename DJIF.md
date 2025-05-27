# Video Ingestion Tool Refactoring Plan

## Current Status
**Progress:** 21/21 components refactored (100% complete)
**Testing Status:** All refactored components (21/21) successfully tested

## High-level Plan
1. ✅ Create new modular directory structure
2. ✅ Set up pipeline architecture
3. ✅ Migrate extraction steps to dedicated modules
4. ✅ Migrate analysis steps to dedicated modules
5. ✅ Migrate processing steps to dedicated modules
6. ✅ Migrate storage steps to dedicated modules
7. ✅ Refactor configuration system
8. ✅ Refactor video processor
9. ✅ Update command-line interface
10. ✅ Clean up the original processor.py file
11. ✅ Remove original files and finalize structure

## Current Structure Analysis

The video_ingest_tool has the following structure issues:

1. **Monolithic processor.py file**: Most pipeline steps are defined in a single 1500-line file
2. **Empty pipeline/ and steps/ directories**: These directories exist but don't contain any files (only cache)
3. **Scattered extractors**: Split across multiple files (extractors.py, extractors_extended.py, extractors_hdr.py)
4. **Disconnected VideoProcessor class**: In video_processor.py but not integrated clearly with the pipeline
5. **Unclear categorization of steps**: Steps have descriptive names but aren't organized in categories
6. **Mixed functionality in processor.py**: Includes step definitions, pipeline execution, and helper functions
7. **Multiple processes in single files**: Some related but distinct processes are grouped together

## Refactoring Goals

1. Maintain backward compatibility with CLI commands and API functions
2. Improve code organization without changing functionality
3. Make the pipeline steps clearer and better organized
4. Reduce file sizes by splitting large modules
5. Improve maintainability and discoverability
6. **Each distinct process should have its own file**

## Implementation Phases

> **Status Legend**:  
> ⬜ = Waiting / Not Started  
> 🔄 = In Progress  
> ✅ = Completed

### Phase 1: Directory Structure Setup

- ✅ Create base directory structure
  ```bash
  mkdir -p video_ingest_tool/pipeline
  mkdir -p video_ingest_tool/steps/{extraction,analysis,processing,storage}
  mkdir -p video_ingest_tool/config
  mkdir -p video_ingest_tool/extractors
  mkdir -p video_ingest_tool/video_processor
  ```

### Phase 2: Pipeline Architecture

- ✅ Create pipeline base module
  - ✅ Create `pipeline/base.py` with `ProcessingPipeline` and `ProcessingStep` classes
  - ✅ Create `pipeline/registry.py` with step registration system
  - ✅ Create `pipeline/__init__.py` with proper exports

### Phase 3: Extraction Steps Migration

- ✅ Migrate MediaInfo extraction
  - ✅ Create `extractors/media.py` 
  - ✅ Create `steps/extraction/mediainfo.py`
  - ✅ Update imports in respective `__init__.py` files
  - ✅ Test extraction functionality

- ✅ Migrate FFprobe extraction
  - ✅ Update `extractors/media.py` with FFprobe function
  - ✅ Create `steps/extraction/ffprobe.py`
  - ✅ Update imports in respective `__init__.py` files
  - ✅ Test extraction functionality

- ✅ Migrate EXIF extraction
  - ✅ Create `extractors/exif.py`
  - ✅ Create `steps/extraction/exiftool.py` for basic EXIF
  - ✅ Create `steps/extraction/extended_exif.py` for extended EXIF
  - ✅ Update imports in respective `__init__.py` files
  - ✅ Test extraction functionality

- ✅ Migrate codec parameter extraction
  - ✅ Create `extractors/codec.py`
  - ✅ Create `steps/extraction/codec.py`
  - ✅ Update imports in respective `__init__.py` files
  - ✅ Test extraction functionality

- ✅ Migrate HDR metadata extraction
  - ✅ Create `extractors/hdr.py`
  - ✅ Create `steps/extraction/hdr.py`
  - ✅ Update imports in respective `__init__.py` files
  - ✅ Test extraction functionality

- ✅ Migrate track extraction
  - ✅ Create `extractors/tracks.py`
  - ✅ Create `steps/extraction/audio_tracks.py`
  - ✅ Create `steps/extraction/subtitle_tracks.py`
  - ✅ Update imports in respective `__init__.py` files
  - ✅ Test extraction functionality

### Phase 4: Analysis Steps Migration

- ✅ Migrate thumbnail generation
  - ✅ Create `steps/analysis/thumbnails.py`
  - ✅ Update imports in `steps/analysis/__init__.py`
  - ✅ Test thumbnail generation

- ✅ Migrate exposure analysis
  - ✅ Create `steps/analysis/exposure.py`
  - ✅ Update imports in `steps/analysis/__init__.py`
  - ✅ Test exposure analysis

- ✅ Migrate focal length detection
  - ✅ Create `steps/analysis/focal_length.py`
  - ✅ Update imports in `steps/analysis/__init__.py`
  - ✅ Test focal length detection

- ✅ Migrate video analysis with Gemini
  - ✅ Create `steps/analysis/video_analysis.py`
  - ✅ Create `video_processor/analysis.py` for AI analysis class
  - ✅ Update imports in respective `__init__.py` files
  - ✅ Test video analysis

### Phase 5: Processing Steps Migration

- ✅ Migrate checksum generation
  - ✅ Create `steps/processing/checksum.py`
  - ✅ Update imports in `steps/processing/__init__.py`
  - ✅ Test checksum generation

- ✅ Migrate duplicate check
  - ✅ Create `steps/processing/duplicate.py`
  - ✅ Update imports in `steps/processing/__init__.py`
  - ✅ Test duplicate check

- ✅ Migrate metadata consolidation
  - ✅ Create `steps/processing/metadata.py`
  - ✅ Update imports in `steps/processing/__init__.py`
  - ✅ Test metadata consolidation

### Phase 6: Storage Steps Migration

- ✅ Migrate model creation
  - ✅ Create `steps/storage/model_creation.py`
  - ✅ Update imports in `steps/storage/__init__.py`
  - ✅ Test model creation

- ✅ Migrate database storage
  - ✅ Create `steps/storage/database_storage.py`
  - ✅ Update imports in `steps/storage/__init__.py`
  - ✅ Test database storage

- ✅ Migrate vector embeddings
  - ✅ Create `steps/storage/embeddings.py`
  - ✅ Update imports in `steps/storage/__init__.py`
  - ✅ Test vector embeddings

### Phase 7: Video Processor Refactoring

- ✅ Split video processor components
  - ✅ Create `video_processor/compression.py` for VideoCompressor
  - ✅ Create `video_processor/processor.py` for main VideoProcessor
  - ✅ Create `video_processor/__init__.py` with exports
  - ✅ Test video processor components

### Phase 8: Configuration Refactoring

- ✅ Refactor configuration system
  - ✅ Create `config/constants.py` for all constants
  - ✅ Create `config/settings.py` for configuration management
  - ✅ Create `config/logging.py` for logging setup
  - ✅ Create `config/__init__.py` with exports
  - ✅ Migrate compression configuration to constants
  - ✅ Test configuration system

### Phase 9: Main Processor Update

- ✅ Update main processor for compatibility
  - ✅ Update imports in `processor.py` to use new locations
  - ✅ Update `process_video_file` to use registry
  - ✅ Test overall processing pipeline

### Phase 10: Documentation and Cleanup

- ✅ Update docstrings in all new files
- ✅ Add module-level documentation
- ✅ Create high-level architectural overview
- ✅ Fix duplicate step registration issue
  - ✅ Modify processor.py to prevent registering the same steps twice
  - ✅ Comment out or remove original @register_step decorators while keeping functions for reference
- ✅ Remove commented-out code from original files
- ✅ Run linter and fix issues
- ✅ Test entire codebase

### Phase 11: File Removal and Final Cleanup

- ✅ Remove original files after ensuring all functionality is migrated:
  - ✅ Review `video_ingest_tool/processor.py` vs refactored modules to ensure complete migration
  - ✅ Rename `video_ingest_tool/processor.py` to `video_ingest_tool/processor.py.bak`
  - ✅ Run all tests to verify functionality is preserved
  
  - ✅ Review `video_ingest_tool/video_processor.py` vs video_processor/* modules to ensure complete migration  
  - ✅ Rename `video_ingest_tool/video_processor.py` to `video_ingest_tool/video_processor.py.bak`
  - ✅ Run all tests to verify functionality is preserved
  
  - ✅ Review `video_ingest_tool/extractors.py` vs extractors/* modules to ensure complete migration
  - ✅ Rename `video_ingest_tool/extractors.py` to `video_ingest_tool/extractors.py.bak`
  - ✅ Run all tests to verify functionality is preserved
  
  - ✅ Review `video_ingest_tool/extractors_extended.py` vs extractors/* modules to ensure complete migration
  - ✅ Rename `video_ingest_tool/extractors_extended.py` to `video_ingest_tool/extractors_extended.py.bak`
  - ✅ Run all tests to verify functionality is preserved
  
  - ✅ Review `video_ingest_tool/extractors_hdr.py` vs extractors/* modules to ensure complete migration
  - ✅ Rename `video_ingest_tool/extractors_hdr.py` to `video_ingest_tool/extractors_hdr.py.bak`
  - ✅ Run all tests to verify functionality is preserved

- ✅ Final integration test after all original files are renamed
- ✅ Update documentation to reflect new file structure

## Detailed Structure Reference

### Pipeline Structure

```
pipeline/
├── __init__.py                     # Re-exports all pipeline components
├── base.py                         # ProcessingPipeline and ProcessingStep classes
└── registry.py                     # Pipeline registry with step management
```

### Steps Structure

```
steps/
├── __init__.py                     # Exports all steps
├── extraction/                     # Metadata extraction steps
│   ├── __init__.py
│   ├── mediainfo.py                # MediaInfo extraction only
│   ├── ffprobe.py                  # FFprobe extraction only
│   ├── exiftool.py                 # Basic EXIF extraction
│   ├── extended_exif.py            # Extended EXIF extraction
│   ├── codec.py                    # Codec parameter extraction
│   ├── hdr.py                      # HDR metadata extraction
│   ├── audio_tracks.py             # Audio track extraction
│   └── subtitle_tracks.py          # Subtitle track extraction
├── analysis/                       # Analysis steps
│   ├── __init__.py
│   ├── thumbnails.py               # Thumbnail generation only
│   ├── exposure.py                 # Exposure analysis only
│   ├── focal_length.py             # AI focal length detection only
│   └── video_analysis.py           # Comprehensive video analysis with Gemini
├── processing/                     # Processing steps
│   ├── __init__.py
│   ├── checksum.py                 # Checksum generation
│   ├── duplicate.py                # Duplicate detection and handling
│   └── metadata.py                 # Metadata consolidation
└── storage/                        # Database and model steps
    ├── __init__.py
    ├── model_creation.py           # Model creation only
    ├── database_storage.py         # Database storage only
    └── embeddings.py               # Vector embeddings only
```

### Extractors Structure

```
extractors/
├── __init__.py                     # Re-exports all extractors
├── media.py                        # Media-related extraction (MediaInfo, FFprobe)
├── exif.py                         # EXIF extraction (basic and extended)
├── codec.py                        # Codec and format extraction
├── hdr.py                          # HDR metadata extraction
├── tracks.py                       # Audio/subtitle track extraction
└── utils.py                        # Shared extraction utilities
```

### Video Processor Structure

```
video_processor/
├── __init__.py                     # Re-exports main classes
├── compression.py                  # VideoCompressor class
├── analysis.py                     # VideoAnalyzer class for Gemini analysis
└── processor.py                    # Main VideoProcessor class
```

### Configuration Structure

```
config/
├── __init__.py                     # Re-exports configs
├── constants.py                    # Constants and feature flags
├── settings.py                     # Configuration management
└── logging.py                      # Logging setup
```

## Implementation Guidelines

### Maintaining Backward Compatibility

- Keep all current function signatures unchanged
- Use import re-exports to preserve import locations
- Maintain the same pipeline step names
- Keep the same default pipeline configuration
- Ensure that the CLI and API continue to work without modification

### Testing Each Component

After migrating each component, perform proper testing:

1. **Registration Testing**: Run `test_pipeline.py` to verify steps are registered correctly
2. **Functionality Testing**: Run `test_functionality.py` to verify each step works with actual video files
3. **CLI Verification**: Run `