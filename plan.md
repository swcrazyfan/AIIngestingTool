# AI-Powered Video Ingest & Catalog Tool
## Technical Specification (Updated - May 22, 2025)

> **✅ = Implemented** | **⏳ = Partially Implemented** | **🔄 = In Progress** | **⭐ = New/Modified**

---

## 1. System Overview

The AI-Powered Video Ingest & Catalog Tool is a comprehensive CLI solution for automating the analysis, categorization, and retrieval of video content at scale. Operating as a command-line utility with a future lightweight server backend, it transforms raw video footage into a richly annotated, searchable database without modifying the original files.

This tool addresses the critical challenges in video asset management:
- Automatic extraction of technical and semantic metadata
- Intelligent scene understanding through multimodal AI
- Efficient search and retrieval based on content, not just filenames
- Centralized organization of video assets and associated metadata

The system combines modern computer vision, audio analysis, and multimodal AI to create what is essentially a "Lightroom for video," but with capabilities far beyond manual tagging systems and accessible entirely through a powerful command-line interface. The architecture is designed for future refactoring into a FastAPI application without significant code changes.

**Current Implementation Status:**
- Content Discovery Phase ✅
- Technical Metadata Extraction ✅
- Thumbnail Generation ✅
- Basic Computer Vision Analysis ✅
- Modular Pipeline Framework ✅ ⭐
- Configurable Processing Steps ✅ ⭐ 
- AI-Powered Video Analysis ✅ ⭐ (Gemini Flash 2.5 integration)
- Comprehensive AI Analysis ✅ ⭐ (Visual, Audio, Content analysis)
- Video Compression for AI Analysis ✅ ⭐
- Advanced Audio Track Extraction ✅ ⭐
- HDR and Advanced Color Metadata ✅ ⭐
- Subtitle Track Analysis ✅ ⭐
- Advanced Codec Analysis ✅ ⭐
- Database Integration ⏳ (Planned)
- Task Queue System ⏳ (Planned)
- Vector Embeddings & Search ⏳ (Planned)

---

## 2. Core Features

### 2.1. Non-Destructive Batch Ingest ✅
- **CLI-driven operation** - Scan any folder structure containing video files via command-line parameters
- **Zero file manipulation** - No renaming, moving, or altering original media
- **Deduplication** - Checksum-based identification of previously processed content
- **Scalable processing** - Handle dozens to thousands of clips in a single operation
- **Format agnostic** - Support for professional (ProRes, DNxHD) and consumer formats (MP4, MOV)
- **Automation-ready** - Scriptable interface for inclusion in larger workflows
- **Configurable pipeline** ✅ ⭐ - Enable/disable specific processing steps via command line or config files

### 2.2. Technical Metadata Extraction ✅
- **Camera identification** - Make, model, serial number (when available)
- **Codec specifications** - Format, bit-depth, compression ratio
- **Resolution & frame rate** - Including variable frame rate detection
- **Color information** - Color space, transfer characteristics, primaries
- **Container fingerprinting** - Identify source workflows by container structure
- **Recording timestamps** - Creation and modification metadata

### 2.3. Thumbnail Generation ✅
- **Intelligent frame sampling** - Up to 30 keyframes per clip, evenly distributed
- **Scene-aware selection** - Preference for high-information frames
- **Multi-resolution storage** - Generate thumbnails at multiple sizes for different uses
- **Local storage** - All thumbnails stored locally with future Supabase Storage integration

### 2.4. Computer Vision Analysis ✅
- **Exposure analytics** - Percentage of over/under-exposed regions via OpenCV ✅
- **Visual quality scoring** - Technical assessment of blur, noise, and compression artifacts ⏳
- **Scene complexity metrics** - Analysis of visual information density ⏳
- **Shot type estimation** - Wide, medium, close-up based on composition heuristics ⏳
- **AI-based focal length detection** ✅ ⭐ - Detect focal length category when EXIF data is unavailable

### 2.5. Multimodal AI Analysis ✅ ⭐
- **Integrated video processing** - End-to-end analysis via Gemini Flash 2.5 ✅
- **Video compression for AI** - Automatic compression with hardware acceleration ✅
- **Full transcription** - Convert all speech to searchable text ✅
- **Non-speech event detection** - Identify music, applause, crowd noise, ambient sounds ✅  
- **Scene labeling** - Automatic categorization (indoor/outdoor, quiet/noisy, etc.) ✅
- **Visual content analysis** - Detailed descriptions of on-screen activity and objects ✅
- **Speaker diarization** - Distinguish between different speakers when possible ✅
- **Contextual summary** - Comprehensive understanding of the video content ✅
- **Technical quality assessment** - AI-powered analysis of video usability ✅
- **Text and graphics detection** - Recognition of on-screen text and logos ✅
- **Keyframe recommendations** - AI-suggested thumbnails for best representation ✅
- **Entity recognition** - People, locations, and objects identification ✅
- **Activity analysis** - Detection and classification of activities in video ✅
- **Content warnings** - Automatic flagging of sensitive content ✅

### 2.6. Advanced Metadata Extraction ✅ ⭐
- **Audio track analysis** - Detailed audio stream metadata ✅
- **Subtitle track extraction** - Embedded subtitle information ✅  
- **HDR metadata** - HDR10, HDR10+, Dolby Vision detection ✅
- **Advanced color metadata** - Color space, primaries, transfer characteristics ✅
- **Codec parameter analysis** - Detailed codec configuration and settings ✅
- **Extended EXIF data** - GPS coordinates, advanced camera settings ✅
- **Master display information** - HDR mastering display data ✅

### 2.7. Structured Content Analysis ✅ ⭐
- **Semantic extraction** - Convert raw video content into structured data ✅
- **Structured JSON output** including:
  - `summary`: 3-5 sentence description of content ✅
  - `keywords`: 5-10 most relevant topical tags ✅
  - `entities`: Named entities (PERSON/ORG/LOCATION) ✅
  - `scene_classification`: Environmental and situational context ✅
  - `sentiment`: Overall emotional tone ✅
  - `content_warnings`: Optional flags for sensitive content ✅
  - `technical_quality`: Assessment of usability ✅
  - `visual_analysis`: Shot types, technical quality, text detection ✅
  - `audio_analysis`: Transcription, speaker analysis, sound events ✅
  - `activity_summary`: Key activities and their importance ✅

### 2.8. Vector Embeddings & Semantic Search ⏳
- **Text embeddings** - Convert summaries and keywords to vector space
- **Similarity search** - Find clips with related content using vector proximity
- **Natural language queries** - "Show me clips about X" functionality
- **Compound filtering** - Combine semantic search with technical parameters
- **Results ranking** - Intelligent sorting by relevance and quality

### 2.9. Centralized Database Architecture ⏳
- **Relational data model** - Normalized tables for clips, metadata, analysis
- **Vector storage** - Optimized for semantic similarity searches
- **Thumbnail management** - Organized storage with relevant linking
- **Realtime synchronization** - Immediate updates across all interfaces
- **Row-level security** - Granular access control for multi-user environments
- **Integrated task queue** - PostgreSQL-based job scheduling and execution tracking

---

## 3. Technical Workflow

### 3.1. Content Discovery Phase ✅
1. **Directory scanning** - Recursive traversal of target folders
2. **File identification** - Filter for supported video formats using Polyfile and mimetypes
3. **Checksum generation** - Create unique file fingerprints with MD5
4. **Deduplication** - Compare against previously processed checksums
5. **Batch preparation** - Organize processing queue by priority and dependencies

### 3.2. Technical Metadata Extraction ✅
1. **Container analysis** - Parse file structure using multiple tools:
   - `PyAV` for standardized metadata
   - `pymediainfo` for detailed technical parameters
   - `ExifTool` for manufacturer-specific metadata
   - `Polyfile` for file type detection and container fingerprinting
2. **Data normalization** - Reconcile potentially conflicting metadata sources
3. **Technical validation** - Flag potential issues (corrupt files, incomplete metadata)

### 3.3. Thumbnail Generation ✅
1. **Frame sampling** - Extract frames at regular intervals (configurable count per clip)
2. **Visual analysis** - Score frames for information content and technical quality
3. **Selection refinement** - Ensure diverse representation of content
4. **Multi-resolution generation** - Create thumbnails at specified sizes
5. **Storage organization** - Store thumbnails with checksum-based directories

### 3.4. Computer Vision Processing ⏳
1. **Frame preparation** - Normalize selected frames for analysis ✅
2. **Exposure calculation** - Histogram analysis for over/under exposure percentage ✅
3. **Quality metrics** - Analyze blur, noise, and compression artifacts ⏳
4. **Shot classification** - Determine shot types and composition characteristics ⏳
5. **AI Focal Length Detection** ✅ ⭐ - Use AI to detect focal length when EXIF data is unavailable

### 3.5. Pipeline Configuration ✅ ⭐
1. **Step Registration** - Pipeline steps registered with name, description, and default status
2. **Conditional Execution** - Steps can be individually enabled or disabled
3. **Configuration Methods**:
   - Command-line parameters (`--enable`, `--disable`)
   - JSON configuration files
   - Programmatic API
4. **Documentation** - Self-documenting pipeline with `list_steps` command

### 3.6. Multimodal AI Analysis ✅ ⭐
1. **Video preparation** - Format video and thumbnails for API submission ✅
2. **Video compression** - Automatic compression with hardware acceleration support ✅
3. **Gemini Flash 2.5 processing** - Send full video plus metadata for comprehensive analysis: ✅
   - Full speech transcription ✅
   - Non-speech event detection ✅
   - Visual content analysis ✅
   - Scene classification ✅
   - Entity recognition ✅
   - Technical quality assessment ✅
   - Text and graphics detection ✅
   - Keyframe recommendations ✅
4. **Structured data extraction** - Parse API response into standardized schema ✅
5. **Quality validation** - Verify completeness and usefulness of generated content ✅
6. **Separate AI analysis files** - Store detailed analysis in separate JSON files ✅

### 3.7. Vector Embedding Generation ⏳
1. **Text preparation** - Combine summary text and keywords
2. **Vector generation** - Process through embedding model
3. **Dimension verification** - Ensure compatibility with vector database

### 3.8. Database Integration ⏳
1. **Schema validation** - Verify all required fields are present
2. **Transaction preparation** - Group related operations
3. **Database upsert** - Insert or update all tables in proper sequence:
   - Clips table (core metadata)
   - Technical details table
   - Analysis results table
   - Transcript storage
   - Tag/entity tables
   - Vector storage
4. **Relation verification** - Ensure all cross-references maintain integrity
5. **Index updates** - Refresh search indices as needed

---

## 4. System Architecture

### 4.1. Component Overview
```
┌─────────────────────┐     ┌─────────────────┐     ┌────────────────────┐
│ Ingest & Processing │────▶│ AI Services     │────▶│ Data Storage       │
│                     │     │                 │     │                    │
│ - Directory Scanner │     │ - Gemini Flash  │     │ - Supabase         │
│ - File Processor    │     │   2.0 (Video)   │     │   Postgres         │
│ - Metadata Extractor│     │ - Embedding     │     │ - pgvector         │
│ - Thumbnail Gen     │     │   Service       │     │   Extension        │
│ - CV Analysis       │     │                 │     │ - Supabase         │
│ - Pipeline System   │     │                 │     │   Storage          │
└─────────────────────┘     └─────────────────┘     └────────────────────┘
          │                                                   ▲
          │                                                   │
          ▼                                                   │
┌─────────────────────┐                            ┌─────────────────────┐
│ Task Queue System   │                            │ CLI Interface       │
│                     │                            │                     │
│ - Job Scheduler     │◀───────────────────────────│ - Command Parser    │
│ - Worker Management │                            │ - Progress Display  │
│ - Error Handling    │────────────────────────────▶│ - Result Formatter │
│ - Progress Tracking │                            │ - Query Interface   │
└─────────────────────┘                            └─────────────────────┘
```

### 4.2. Key Components

#### 4.2.1. Core Processing Engine
- **Language**: Python (3.9+)
- **Pipeline Framework**: ✅ ⭐ Custom pipeline system with configurable steps
- **Concurrency**: asyncio + ProcessPoolExecutor for CPU-bound tasks (future)
- **API Wrapper**: Custom client for AI service integration (future)
- **Database Client**: Supabase Python client (future)
- **Task Queue**: Procrastinate (PostgreSQL-based distributed task queue) (future)
- **Future FastAPI Compatibility**: Core functions designed as isolated services

#### 4.2.2. Metadata & Container Parsing ✅
- **PyAV**: Video frame extraction and container metadata
- **MediaInfo**: Detailed technical specifications via pymediainfo
- **ExifTool**: Manufacturer-specific metadata via PyExifTool
- **Polyfile**: File identification and container fingerprinting

#### 4.2.3. Computer Vision Module ✅
- **Framework**: OpenCV (Python) ✅
- **Image Processing**: Pillow for thumbnail generation and manipulation ✅
- **Image Quality**: Basic exposure analysis via histograms ✅
- **AI Models**: Focal length detection using transformers ✅ ⭐
- **Advanced Analysis**: Shot type detection, blur detection, noise analysis ⏳

#### 4.2.4. AI Integration Layer ✅ ⭐
- **Video Analysis**: Gemini Flash 2.5 API ✅
- **Video Compression**: Hardware-accelerated video compression ✅
- **Comprehensive Analysis**: Visual, audio, and content analysis ✅
- **Structured Output**: JSON schema-based response parsing ✅
- **Embedding Service**: OpenAI Embeddings or equivalent ⏳

#### 4.2.5. Video Processing System ✅ ⭐
- **VideoCompressor**: Hardware-accelerated compression with codec selection ✅
- **VideoAnalyzer**: Gemini Flash 2.5 integration for comprehensive analysis ✅
- **VideoProcessor**: End-to-end pipeline processor ✅
- **Configurable Compression**: FPS, bitrate, and quality settings ✅
- **Multiple Codec Support**: H.264, H.265, VideoToolbox hardware acceleration ✅

#### 4.2.6. Database Architecture ⏳
- **Primary Database**: Online Supabase Postgres instance
- **Vector Extension**: pgvector enabled in Supabase project
- **Media Storage**: Supabase Storage buckets for thumbnails
- **Security Model**: Row-level security policies via Supabase
- **Cache Strategy**: Local thumbnail caching with remote persistence

#### 4.2.7. Task Queue Management ⏳
- **Framework**: Procrastinate
- **Persistence**: PostgreSQL tables in same database
- **Orchestration**: Priority-based task scheduling

#### 4.2.8. Command-Line Interface ✅
- **Framework**: Typer for rich CLI experience
- **Output Formatting**: Rich for colored terminal output and progress bars
- **Pipeline Configuration**: ✅ ⭐ Command-line parameters and JSON config files for steps
- **Configuration**: YAML-based config files with CLI overrides (future)
- **Query Interface**: Natural language parsing for content searches (future)
- **Extensibility**: Plugin architecture for future commands
- **FastAPI Readiness**: Command handlers designed for future API endpoint conversion

### 4.3. Task Queue System ⭐

#### 4.3.1. Procrastinate Integration 🔄
- **Framework**: Procrastinate (PostgreSQL-based task queue)
- **Configuration**:
  - ✅ Direct integration with PostgreSQL database
  - ✅ No additional message broker required
  - ✅ Leverages PostgreSQL's LISTEN/NOTIFY for efficient polling
- **Key Features Used**:
  - ✅ Task locks for preventing concurrent execution
  - ✅ Job prioritization via queue configuration
  - ✅ Automatic retries with configurable backoff
  - ✅ Detailed job status tracking within PostgreSQL

#### 4.3.2. System-Wide Task Management 🔄
- **Queue Structure**: Multiple named queues in Procrastinate
  - ✅ `ingest`: Directory scanning and file validation
  - ✅ `processing`: CPU-intensive video and audio tasks
  - ✅ `storage`: Database and JSON storage operations
  - ⏳ `ai`: External AI service communication
  - ⏳ `system`: System operations and maintenance
- **Priority Handling**:
  - ✅ Priority implemented via queue ordering
  - ⏳ Interactive tasks get higher priority than batch tasks
- **Execution Model**:
  - ✅ Procrastinate workers pull jobs from PostgreSQL
  - ✅ Task status tracking via native Procrastinate tables
  - ⏳ Health monitoring via built-in healthchecks

#### 4.3.3. Per-File Task Pipeline 🔄
- **Task Graph**: Each file processed through a simplified directed acyclic graph (DAG) of tasks
- **Implementation**: Modular pipeline with configurable steps ✅ ⭐
- **Standard Pipeline Stages**:
  1. ✅ **Validation**: Format check, corruption detection, checksum generation
  2. ✅ **Metadata Extraction**: Technical parameters, container analysis
  3. ✅ **Thumbnail Generation**: Key frame sampling, thumbnail creation
  4. ✅ **Technical Analysis**: Exposure metrics (basic implementation)
  5. ⏳ **Multimodal AI Analysis**: Comprehensive video content analysis via Gemini Flash 2.0
  6. ⏳ **Vector Embedding**: Semantic embedding generation
  7. ⏳ **Database Integration**: Final results stored in JSON (will be updated to Supabase)
- **Execution Properties**:
  - Pipeline step configuration via CLI or config files ✅ ⭐
  - Parallel execution where possible using worker concurrency (future)
  - Built-in checkpointing via job status tracking (future)
  - Failure handling with automatic retries and queueing locks (future)

#### 4.3.4. Task Status Tracking
- **Status States**: Mapped to Procrastinate job states
  - `PENDING`: Task scheduled but not yet executable
  - `TODO`: Task ready to be executed
  - `DOING`: Task currently being processed
  - `SUCCEEDED`: Task successfully completed
  - `FAILED`: Task failed (with error details)
  - `CANCELLED`: Task cancelled before execution
- **Metadata Storage**:
  - Core job data in PostgreSQL `procrastinate_jobs` table
  - Detailed job status and results in the same database
  - Job history directly queryable with SQL

#### 4.3.5. CLI Task Management Commands
```bash
# View task queue status across all queues
video-catalog queue status

# View tasks for a specific file
video-catalog queue file-status /path/to/video.mp4

# Cancel pending tasks
video-catalog queue cancel --task-id=TASK_ID

# Retry failed tasks
video-catalog queue retry --task-id=TASK_ID

# Start a worker for specific queues
video-catalog queue worker --queues=ingest,processing

# Run health checks on the task queue
video-catalog queue healthchecks
```

---

## 5. Command-Line Interface

### 5.1. Initial Setup ⏳
```bash
# Install the tool
pip install video-catalog-tool

# Configure Supabase connection to your online instance
video-catalog config init --supabase-url=URL --supabase-key=KEY --supabase-project=PROJECT_ID

# Apply the Procrastinate schema to your database
video-catalog schema apply

# Set processing preferences
video-catalog config set --thumbnails=20 --analysis-depth=full
```

### 5.2. Content Ingestion ✅
```bash
# Basic directory scan and process
python -m video_ingest_tool ingest /path/to/videos/

# With custom parameters
python -m video_ingest_tool ingest /path/to/videos/ --recursive --output-dir=output

# Monitor progress with detailed output (built-in)
python -m video_ingest_tool ingest /path/to/videos/ --limit=5

# Configure processing pipeline ✅ ⭐
python -m video_ingest_tool ingest /path/to/videos/ --disable=hdr_extraction,ai_focal_length
python -m video_ingest_tool ingest /path/to/videos/ --enable=thumbnail_generation --disable=exposure_analysis
python -m video_ingest_tool ingest /path/to/videos/ --config=pipeline_config.json

# List all available pipeline steps ✅ ⭐
python -m video_ingest_tool list_steps

# Configure AI video analysis ✅ ⭐ (disabled by default due to API costs)
python -m video_ingest_tool ingest /path/to/videos/ --enable=ai_video_analysis

# Configure video compression for AI analysis ✅ ⭐
python -m video_ingest_tool ingest /path/to/videos/ --compression-fps=5 --compression-bitrate=1000k

# Future parameters (planned)
python -m video_ingest_tool ingest /path/to/videos/ --focus=audio-analysis --skip-visual
```

### 5.3. Content Query ⏳
```bash
# List all processed clips
video-catalog list

# Filter by technical parameters
video-catalog list --resolution=1080p --camera="Sony A7"

# Search by natural language
video-catalog search "outdoor clips with crowds"
video-catalog search "interview footage with good lighting"
video-catalog search "clips mentioning product launch"

# Export results to various formats
video-catalog search "winter scenes" --export=json > winter_clips.json
video-catalog search "client meeting" --export=csv > client_meetings.csv
```

### 5.4. Content Management ⏳
```bash
# Create metadata collections
video-catalog collection create "Project Alpha"

# Add clips to collections
video-catalog collection add "Project Alpha" --clip-ids=ID1,ID2,ID3

# Tag content
video-catalog tag add "interview,primary" --clip-id=ID1

# Generate reports
video-catalog report storage-usage --format=text
video-catalog report content-summary --collection="Project Alpha"
```

### 5.5. System Management ⏳
```bash
# Check system status
video-catalog system status

# Update AI models
video-catalog system update-models

# Check Procrastinate and Supabase connection
video-catalog system healthchecks

# View active tasks and worker status
video-catalog system tasks

# Start a worker for processing tasks
video-catalog worker --queues=ingest,processing,ai

# Backup configuration
video-catalog config backup my-settings.yml
```

---

## 6. Implementation Details

### 6.1. Data Model

#### 6.1.1. Current Implementation ✅
**VideoIngestOutput (Pydantic Model)** ✅ ⭐
```python
class VideoIngestOutput(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    file_info: FileInfo
    video: VideoDetails
    audio_tracks: List[AudioTrack] = Field(default_factory=list)
    subtitle_tracks: List[SubtitleTrack] = Field(default_factory=list)
    camera: CameraDetails
    thumbnails: List[str] = Field(default_factory=list)
    analysis: AnalysisDetails
```

**Comprehensive Analysis Models** ✅ ⭐
```python
class ComprehensiveAIAnalysis(BaseModel):
    """Complete AI analysis results from Gemini Flash 2.5"""
    summary: Optional[AIAnalysisSummary] = None
    visual_analysis: Optional[VisualAnalysis] = None
    audio_analysis: Optional[AudioAnalysis] = None
    content_analysis: Optional[ContentAnalysis] = None
    analysis_file_path: Optional[str] = None  # Path to detailed JSON file

class VisualAnalysis(BaseModel):
    """Complete visual analysis results"""
    shot_types: List[ShotType] = Field(default_factory=list)
    technical_quality: Optional[TechnicalQuality] = None
    text_and_graphics: Optional[TextAndGraphics] = None
    keyframe_analysis: Optional[KeyframeAnalysis] = None

class AudioAnalysis(BaseModel):
    """Complete audio analysis results"""
    transcript: Optional[Transcript] = None
    speaker_analysis: Optional[SpeakerAnalysis] = None
    sound_events: List[SoundEvent] = Field(default_factory=list)
    audio_quality: Optional[AudioQuality] = None

class ContentAnalysis(BaseModel):
    """Complete content analysis results"""
    entities: Optional[Entities] = None
    activity_summary: List[Activity] = Field(default_factory=list)
    content_warnings: List[ContentWarning] = Field(default_factory=list)
```

**Advanced Metadata Models** ✅ ⭐
```python
class VideoHDRDetails(BaseModel):
    is_hdr: bool = False
    format: Optional[str] = None # HDR10, HDR10+, Dolby Vision
    master_display: Optional[str] = None
    max_cll: Optional[int] = None
    max_fall: Optional[int] = None

class AudioTrack(BaseModel):
    """Audio track metadata"""
    track_id: Optional[str] = None
    codec: Optional[str] = None
    channels: Optional[int] = None
    sample_rate: Optional[int] = None
    bit_rate_kbps: Optional[int] = None
    language: Optional[str] = None
    duration_seconds: Optional[float] = None

class SubtitleTrack(BaseModel):
    """Subtitle track metadata"""
    track_id: Optional[str] = None
    codec: Optional[str] = None
    language: Optional[str] = None
    format: Optional[str] = None
    embedded: Optional[bool] = None
```

#### 6.1.2. Future Database Schema ⏳

```sql
CREATE TABLE clips (
  id UUID PRIMARY KEY,
  file_path TEXT NOT NULL,
  file_name TEXT NOT NULL,
  file_checksum TEXT UNIQUE NOT NULL,
  duration_seconds NUMERIC NOT NULL,
  created_at TIMESTAMP,
  processed_at TIMESTAMP,
  file_size_bytes BIGINT NOT NULL
);
```

```sql
CREATE TABLE technical_metadata (
  clip_id UUID REFERENCES clips(id),
  codec TEXT,
  container TEXT,
  width INTEGER,
  height INTEGER,
  frame_rate NUMERIC,
  bit_depth INTEGER,
  color_space TEXT,
  camera_make TEXT,
  camera_model TEXT,
  exposure_issues JSONB,
  exposure_warnings BOOLEAN,
  exposure_stops NUMERIC,
  focal_length NUMERIC,
  shot_type TEXT
);
```

```sql
CREATE TABLE thumbnails (
  id UUID PRIMARY KEY,
  clip_id UUID REFERENCES clips(id),
  frame_number INTEGER,
  timestamp_seconds NUMERIC,
  storage_path TEXT,
  width INTEGER,
  height INTEGER,
  is_keyframe BOOLEAN
);
```

```sql
CREATE TABLE analysis_results (
  clip_id UUID REFERENCES clips(id),
  summary TEXT,
  keywords TEXT[],
  entities JSONB,
  scene_classification TEXT[],
  sentiment TEXT,
  content_warnings TEXT[],
  raw_ai_response JSONB
);
```

```sql
CREATE TABLE transcripts (
  clip_id UUID REFERENCES clips(id),
  full_text TEXT,
  segments JSONB,
  speakers JSONB,
  non_speech_events JSONB
);
```

```sql
CREATE TABLE vectors (
  clip_id UUID REFERENCES clips(id),
  summary_vector vector(1536),
  keyword_vector vector(1536)
);
```

#### 6.1.3. Procrastinate Tables ⏳
The task queue functionality will be implemented using Procrastinate, which adds several tables to the database:

```sql
-- Core jobs table
CREATE TABLE procrastinate_jobs (
  id SERIAL PRIMARY KEY,
  queue_name TEXT NOT NULL,
  task_name TEXT NOT NULL,
  lock TEXT,
  queueing_lock TEXT,
  args JSONB NOT NULL,
  status TEXT NOT NULL,
  scheduled_at TIMESTAMPTZ,
  attempts INTEGER NOT NULL,
  max_attempts INTEGER NOT NULL,
  ... additional fields for job management
);

-- Periodic tasks definition table
CREATE TABLE procrastinate_periodic_tasks (
  id SERIAL PRIMARY KEY,
  task_name TEXT NOT NULL,
  cron TEXT NOT NULL,
  ...
);

-- Events table for tracking job status changes
CREATE TABLE procrastinate_events (
  id SERIAL PRIMARY KEY,
  job_id INTEGER REFERENCES procrastinate_jobs(id),
  type TEXT NOT NULL,
  timestamp TIMESTAMPTZ NOT NULL DEFAULT now(),
  ...
);
```

### 6.2. Current Implementation Details

#### 6.2.1. Pipeline Architecture ✅ ⭐
```python
# Define the pipeline and register steps
pipeline = ProcessingPipeline()

@pipeline.register_step(
    name="checksum_generation", 
    enabled=True,
    description="Calculate file checksum for deduplication"
)
def generate_checksum(data: Dict[str, Any], logger=None) -> Dict[str, Any]:
    # Implementation of the step
    # ...

# Main processing function using the pipeline
def process_video_file(file_path: str, thumbnails_dir: str, logger=None, config: Dict[str, bool] = None) -> VideoIngestOutput:
    # Configure pipeline if config is provided
    if config:
        pipeline.configure_steps(config)
    
    # Initial data
    initial_data = {
        'file_path': file_path,
        'processed_at': datetime.datetime.now()
    }
    
    # Execute pipeline
    result = pipeline.execute_pipeline(
        initial_data, 
        thumbnails_dir=thumbnails_dir,
        logger=logger
    )
    
    # Return the output model
    output = result.get('output')
    
    return output
```

#### 6.2.2. Technical Metadata Extraction

```python
@pipeline.register_step(
    name="mediainfo_extraction", 
    enabled=True,
    description="Extract metadata using MediaInfo"
)
def extract_mediainfo_step(data: Dict[str, Any], logger=None) -> Dict[str, Any]:
    """Extract metadata using MediaInfo."""
    file_path = data.get('file_path')
    mediainfo_data = extract_mediainfo(file_path, logger)
    
    return {
        'mediainfo_data': mediainfo_data
    }

@pipeline.register_step(
    name="ffprobe_extraction", 
    enabled=True,
    description="Extract metadata using FFprobe/PyAV"
)
def extract_ffprobe_step(data: Dict[str, Any], logger=None) -> Dict[str, Any]:
    """Extract metadata using FFprobe/PyAV."""
    file_path = data.get('file_path')
    ffprobe_data = extract_ffprobe_info(file_path, logger)
    
    return {
        'ffprobe_data': ffprobe_data
    }

@pipeline.register_step(
    name="exiftool_extraction", 
    enabled=True,
    description="Extract EXIF metadata"
)
def extract_exiftool_step(data: Dict[str, Any], logger=None) -> Dict[str, Any]:
    """Extract metadata using ExifTool."""
    file_path = data.get('file_path')
    exiftool_data = extract_exiftool_info(file_path, logger)
    
    return {
        'exiftool_data': exiftool_data
    }
```

#### 6.2.3. Thumbnail Generation

```python
@pipeline.register_step(
    name="thumbnail_generation", 
    enabled=True,
    description="Generate thumbnails from video"
)
def generate_thumbnails_step(data: Dict[str, Any], thumbnails_dir=None, logger=None) -> Dict[str, Any]:
    """Generate thumbnails for a video file."""
    file_path = data.get('file_path')
    checksum = data.get('checksum')
    
    thumbnail_dir_for_file = os.path.join(thumbnails_dir, checksum)
    thumbnail_paths = generate_thumbnails(file_path, thumbnail_dir_for_file, logger=logger)
    
    return {
        'thumbnail_paths': thumbnail_paths
    }
```

#### 6.2.4. AI Video Analysis ✅ ⭐

```python
@pipeline.register_step(
    name="ai_video_analysis", 
    enabled=False,  # Disabled by default due to API costs
    description="Perform comprehensive AI video analysis using Gemini Flash 2.5"
)
def ai_video_analysis_step(data: Dict[str, Any], thumbnails_dir=None, logger=None, 
                         compression_fps: int = 5, compression_bitrate: str = '1000k') -> Dict[str, Any]:
    """Perform comprehensive AI video analysis using Gemini Flash 2.5."""
    file_path = data.get('file_path')
    
    # Initialize VideoProcessor with compression configuration
    config = Config()
    compression_config = {
        'fps': compression_fps,
        'video_bitrate': compression_bitrate,
        'max_dimension': 1280,
        'crf_value': 23,
        'audio_bitrate': '128k',
        'audio_channels': 2,
        'hardware_acceleration': True
    }
    
    video_processor = VideoProcessor(config, compression_config=compression_config)
    
    # Determine output directory for compressed files
    run_dir = os.path.dirname(thumbnails_dir) if thumbnails_dir else None
    
    # Process the video (this will compress and analyze)
    result = video_processor.process(file_path, run_dir)
    
    # Get the analysis results
    analysis_json = result.get('analysis_json', {})
    
    # Save detailed AI analysis to separate file
    if run_dir:
        ai_analysis_dir = os.path.join(run_dir, "ai_analysis")
        os.makedirs(ai_analysis_dir, exist_ok=True)
        
        input_basename = os.path.basename(file_path)
        ai_filename = f"{os.path.splitext(input_basename)[0]}_AI_analysis.json"
        ai_analysis_path = os.path.join(ai_analysis_dir, ai_filename)
        
        # Save the complete AI analysis
        save_to_json(analysis_json, ai_analysis_path, logger)
    else:
        ai_analysis_path = None
    
    # Create summary for main JSON (lightweight)
    ai_summary = _create_ai_summary(analysis_json)
    
    return {
        'ai_analysis_summary': ai_summary,
        'ai_analysis_file_path': ai_analysis_path,
        'compressed_video_path': result.get('compressed_path')
    }
```

#### 6.2.5. Video Compression System ✅ ⭐

```python
class VideoCompressor:
    """Handles video compression using ffmpeg with hardware acceleration when available."""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = {
            'fps': 5,
            'video_bitrate': '1000k',
            'max_dimension': 1280,
            'crf_value': 23,
            'audio_bitrate': '128k',
            'audio_channels': 2,
            'hardware_acceleration': True
        }
        if config:
            self.config.update(config)
    
    def _select_best_codec(self) -> str:
        """Select the best available codec based on priorities and system capabilities."""
        # Priority order: VideoToolbox h264/h265 (macOS) > libx265 > libx264
        if self.config['hardware_acceleration'] and platform.system() == 'Darwin':
            vt_availability = self._check_videotoolbox_availability()
            if vt_availability['h264_videotoolbox']:
                return 'h264_videotoolbox'
            elif vt_availability['hevc_videotoolbox']:
                return 'hevc_videotoolbox'
        
        # Check for software HEVC support
        if self._check_codec_availability('libx265'):
            return 'libx265'
        
        # Default to libx264 as fallback
        return 'libx264'
    
    def compress(self, input_path: str, output_dir: str = None) -> str:
        """Compress video using ffmpeg with the best available codec."""
        # Implementation includes:
        # - Automatic codec selection
        # - Hardware acceleration when available
        # - Intelligent scaling based on max_dimension
        # - Quality-based encoding (CRF) for software codecs
        # - Bitrate-based encoding for hardware codecs
        pass
```

### 6.3. Future Procrastinate Integration ⏳

#### 6.3.1. Task Definition and Configuration
```python
import procrastinate
from procrastinate import PsycopgConnector

# Initialize the app with Supabase PostgreSQL connection
app = procrastinate.App(
    connector=PsycopgConnector(
        kwargs={
            "host": SUPABASE_HOST,
            "user": SUPABASE_USER,
            "password": SUPABASE_PASSWORD,
            "database": SUPABASE_DATABASE,
        }
    ),
    import_paths=["video_catalog.tasks"]
)

# Defining a task for processing video files
@app.task(queue="ingest", max_attempts=3)
def process_video_file(file_path, config=None):
    """
    Process a video file, extracting metadata and generating thumbnails.
    Will be retried up to 3 times if it fails.
    """
    try:
        # Calculate checksum for deduplication
        checksum = calculate_checksum(file_path)
        
        # Queue the next task in the pipeline
        extract_metadata.defer(file_path=file_path, checksum=checksum, config=config)
        
        return {"status": "success", "file": file_path, "checksum": checksum}
    except Exception as e:
        logger.error(f"Error processing {file_path}: {str(e)}")
        raise  # This will trigger Procrastinate's retry mechanism
```

### 6.4. Future AI Integration ⏳

#### 6.4.1. Gemini Flash 2.0 Multimodal Analysis
```python
@app.task(queue="ai", max_attempts=5, retry_delay=30)
async def analyze_video_content(video_file_path, thumbnails, metadata, job_id):
    """
    Process entire video through Gemini Flash 2.0 API with retry logic.
    Handles both visual content and audio in a single call.
    """
    try:
        # Load video file
        video_bytes = await read_file_chunks(video_file_path)
        
        # Prepare thumbnails (sampled frames) as base64
        thumbnail_encodings = []
        for thumbnail_path in thumbnails:
            img_bytes = await storage.get_file(thumbnail_path)
            thumbnail_encodings.append(encode_image_base64(img_bytes))
        
        # Create multimodal prompt with video, thumbnails and metadata context
        prompt = f"""
        Analyze this video content comprehensively. The video contains both visual 
        and audio information. Additional context:
        
        Technical metadata: {json.dumps(metadata)}
        
        Please provide a complete analysis including:
        1. Detailed transcript of speech content
        2. Non-speech audio events and scene sounds
        3. Visual scene descriptions and classifications
        4. Key entities (people, organizations, locations)
        5. Overall content summary
        6. Sentiment analysis
        7. Relevant keywords and tags
        """
        
        # Make a single comprehensive API call to Gemini Flash 2.0
        response = await gemini_client.analyze_content(
            content={
                "video": video_bytes,
                "images": thumbnail_encodings,
                "text": prompt
            },
            output_format="json",
            response_schema={
                "transcript": "string",
                "non_speech_events": ["string"],
                "scene_descriptions": ["string"],
                "entities": {
                    "persons": ["string"],
                    "organizations": ["string"],
                    "locations": ["string"]
                },
                "summary": "string",
                "sentiment": "string",
                "keywords": ["string"]
            }
        )
        
        # Store results and queue embedding generation
        await store_analysis_results.defer_async(
            job_id=job_id, 
            analysis=response
        )
        
        # Queue embedding generation as the next pipeline step
        await generate_embeddings.defer_async(
            job_id=job_id,
            summary=response["summary"],
            keywords=response["keywords"]
        )
        
        return response
    except Exception as e:
        logger.error(f"API error during video analysis: {str(e)}")
        raise
```

---

## 7. Next Implementation Steps ⭐

### 7.1. Database Integration Phase ⏳

#### 7.1.1. Supabase Project Setup ⏳
1. **Create Supabase Project:**
   - ⏳ Set up new Supabase project with PostgreSQL database
   - ⏳ Enable pgvector extension for vector embeddings
   - ⏳ Configure project settings and API keys

2. **Database Schema Design:**
   - ⏳ Create users table with built-in auth integration
   - ⏳ Create user_profiles table with profile_types (admin, user)
   - ⏳ Create video_clips table for main video metadata
   - ⏳ Create video_embeddings table for vector storage
   - ⏳ Create video_analysis table for AI analysis results
   - ⏳ Set up proper foreign key relationships

3. **Row Level Security (RLS) Implementation:**
   - ⏳ Enable RLS on all tables
   - ⏳ Create policies for user-based data access
   - ⏳ Implement admin vs user permission levels
   - ⏳ Secure vector embeddings with user ownership

#### 7.1.2. CLI Authentication System ⏳
1. **Authentication Flow:**
   - ⏳ Implement email/password login via CLI prompts
   - ⏳ Use JWT tokens with refresh token handling
   - ⏳ Store session tokens securely in user home directory (~/.video_ingest_auth.json)
   - ⏳ Implement automatic token refresh for long-running processes
   - ⏳ Add logout functionality to clear stored tokens

2. **User Management:**
   - ⏳ Sign-up functionality with profile type selection
   - ⏳ User session persistence across CLI invocations
   - ⏳ Profile type enforcement (admin vs user access levels)
   - ⏳ Email verification integration

3. **CLI Commands:**
   ```bash
   # Authentication commands
   python -m video_ingest_tool auth login
   python -m video_ingest_tool auth signup
   python -m video_ingest_tool auth logout
   python -m video_ingest_tool auth status
   ```

#### 7.1.3. Vector Embeddings Integration ⏳
1. **DeepInfra API Integration:**
   - ⏳ Use BAAI/bge-m3 model via DeepInfra's OpenAI-compatible API
   - ⏳ API endpoint: https://api.deepinfra.com/v1/openai
   - ⏳ Model: "BAAI/bge-m3" with float encoding format
   - ⏳ Handle API key configuration and rate limiting

2. **Content Preparation for Embeddings:**
   - ⏳ Extract full transcript text (exclude timestamped segments to save tokens)
   - ⏳ Combine with AI analysis summary and key metadata
   - ⏳ Implement token counting with tiktoken library
   - ⏳ Enforce 3500 token limit - truncate transcript if needed
   - ⏳ Create structured content string for embedding generation

3. **Vector Storage:**
   - ⏳ Store embeddings in pgvector format in Supabase
   - ⏳ Link embeddings to user ownership via RLS
   - ⏳ Index vectors for efficient similarity search
   - ⏳ Implement embedding versioning for content updates

#### 7.1.4. Database Schema Details ⏳

**Core Tables:**
```sql
-- Built-in Supabase auth.users table (managed by Supabase)
-- Additional user profiles table
CREATE TABLE user_profiles (
  id UUID PRIMARY KEY REFERENCES auth.users(id),
  profile_type TEXT CHECK (profile_type IN ('admin', 'user')) DEFAULT 'user',  
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Main video clips table
CREATE TABLE video_clips (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID REFERENCES auth.users(id) NOT NULL,
  file_path TEXT NOT NULL,
  file_name TEXT NOT NULL,
  file_checksum TEXT UNIQUE NOT NULL,
  file_size_bytes BIGINT NOT NULL,
  duration_seconds NUMERIC,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  processed_at TIMESTAMPTZ DEFAULT NOW()
);

-- Video segments table (for future segment-level analysis) ⭐
CREATE TABLE video_segments (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  video_clip_id UUID REFERENCES video_clips(id) ON DELETE CASCADE,
  user_id UUID REFERENCES auth.users(id) NOT NULL,
  segment_index INTEGER NOT NULL, -- 0-based index of segment within clip
  start_time_seconds NUMERIC NOT NULL,
  end_time_seconds NUMERIC NOT NULL,
  duration_seconds NUMERIC GENERATED ALWAYS AS (end_time_seconds - start_time_seconds) STORED,
  segment_type TEXT DEFAULT 'auto', -- 'auto', 'scene_change', 'speaker_change', 'manual'
  transcript_text TEXT, -- Transcript for this segment only
  description TEXT, -- AI-generated description of this segment
  keyframe_path TEXT, -- Path to representative keyframe for this segment
  created_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(video_clip_id, segment_index)
);

-- Vector embeddings table (supports both full-clip and segment-level embeddings) ⭐
CREATE TABLE video_embeddings (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  video_clip_id UUID REFERENCES video_clips(id) ON DELETE CASCADE,
  video_segment_id UUID REFERENCES video_segments(id) ON DELETE CASCADE, -- NULL for full-clip embeddings
  user_id UUID REFERENCES auth.users(id) NOT NULL,
  embedding_type TEXT NOT NULL CHECK (embedding_type IN ('full_clip', 'segment', 'keyframe')),
  embedding vector(1024), -- BAAI/bge-m3 produces 1024-dimensional vectors
  content_text TEXT NOT NULL, -- The text that was embedded
  token_count INTEGER NOT NULL,
  embedding_source TEXT NOT NULL, -- 'transcript', 'ai_summary', 'combined', 'visual_description'
  created_at TIMESTAMPTZ DEFAULT NOW(),
  -- Ensure either video_clip_id OR video_segment_id is set, not both for segments
  CONSTRAINT check_embedding_scope CHECK (
    (embedding_type = 'full_clip' AND video_segment_id IS NULL) OR
    (embedding_type IN ('segment', 'keyframe') AND video_segment_id IS NOT NULL)
  )
);

-- AI analysis results (detailed JSON storage)
CREATE TABLE video_analysis (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  video_clip_id UUID REFERENCES video_clips(id) ON DELETE CASCADE,
  video_segment_id UUID REFERENCES video_segments(id) ON DELETE CASCADE, -- NULL for full-clip analysis
  user_id UUID REFERENCES auth.users(id) NOT NULL,
  analysis_type TEXT NOT NULL, -- 'comprehensive', 'visual', 'audio', 'content', 'segment_summary'
  analysis_scope TEXT NOT NULL CHECK (analysis_scope IN ('full_clip', 'segment')),
  analysis_data JSONB NOT NULL,
  ai_model TEXT DEFAULT 'gemini-flash-2.5',
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for performance ⭐
CREATE INDEX idx_video_segments_clip_time ON video_segments(video_clip_id, start_time_seconds, end_time_seconds);
CREATE INDEX idx_video_segments_user ON video_segments(user_id, created_at DESC);
CREATE INDEX idx_video_embeddings_type ON video_embeddings(embedding_type, user_id);
CREATE INDEX idx_video_embeddings_segment ON video_embeddings(video_segment_id) WHERE video_segment_id IS NOT NULL;
CREATE INDEX idx_video_embeddings_vector ON video_embeddings USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
```

**RLS Policies:**
```sql
-- Enable RLS on all tables
ALTER TABLE user_profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE video_clips ENABLE ROW LEVEL SECURITY;  
ALTER TABLE video_segments ENABLE ROW LEVEL SECURITY; -- ⭐
ALTER TABLE video_embeddings ENABLE ROW LEVEL SECURITY;
ALTER TABLE video_analysis ENABLE ROW LEVEL SECURITY;

-- User can only see their own data
CREATE POLICY "Users can view own video clips" ON video_clips
  FOR SELECT TO authenticated 
  USING (user_id = auth.uid());

CREATE POLICY "Users can view own video segments" ON video_segments -- ⭐
  FOR SELECT TO authenticated
  USING (user_id = auth.uid());

CREATE POLICY "Users can view own embeddings" ON video_embeddings
  FOR SELECT TO authenticated
  USING (user_id = auth.uid());

CREATE POLICY "Users can view own video analysis" ON video_analysis
  FOR SELECT TO authenticated
  USING (user_id = auth.uid());

-- Users can insert their own data
CREATE POLICY "Users can insert own video segments" ON video_segments -- ⭐
  FOR INSERT TO authenticated
  WITH CHECK (user_id = auth.uid());

CREATE POLICY "Users can insert own embeddings" ON video_embeddings
  FOR INSERT TO authenticated
  WITH CHECK (user_id = auth.uid());

-- Admins can see all data
CREATE POLICY "Admins can view all video clips" ON video_clips
  FOR SELECT TO authenticated
  USING (
    EXISTS (
      SELECT 1 FROM user_profiles 
      WHERE id = auth.uid() AND profile_type = 'admin'
    )
  );

CREATE POLICY "Admins can view all video segments" ON video_segments -- ⭐
  FOR SELECT TO authenticated
  USING (
    EXISTS (
      SELECT 1 FROM user_profiles 
      WHERE id = auth.uid() AND profile_type = 'admin'
    )
  );
```

#### 7.1.5. Pipeline Integration ⏳
1. **New Pipeline Step:**
   ```python
   @pipeline.register_step(
       name="supabase_storage", 
       enabled=True,
       description="Store video metadata and analysis in Supabase database"
   )
   def supabase_storage_step(data: Dict[str, Any], logger=None) -> Dict[str, Any]:
       # Store in Supabase instead of JSON files
       pass
   ```

2. **Vector Embedding Step:**
   ```python
   @pipeline.register_step(
       name="generate_embeddings", 
       enabled=True,
       description="Generate vector embeddings for semantic search"
   )
   def generate_embeddings_step(data: Dict[str, Any], logger=None) -> Dict[str, Any]:
       # Generate and store vector embeddings
       pass
   ```

3. **Authentication Requirement:**
   - ⏳ All pipeline operations require authenticated user
   - ⏳ User ID automatically attached to all stored records
   - ⏳ RLS policies enforce data isolation between users

#### 7.1.7. Future Segment-Level Search Capabilities ⭐

**Database Schema Support for Segments:**
- **video_segments table**: Ready for storing segment-level data with time boundaries
- **Flexible embeddings table**: Supports both full-clip and segment-level embeddings
- **Segment types**: Automatic segmentation, scene changes, speaker changes, manual segments
- **Performance indexes**: Optimized for time-based and vector similarity queries

**Future Search Features (Database-Ready):**
```bash
# Segment-level search (future implementation)
python -m video_ingest_tool db search "discussion about pricing" --segment-level
python -m video_ingest_tool db search --timestamp="00:05:30" --context-seconds=30
python -m video_ingest_tool db find-similar --segment-id="seg_123" --limit=10

# Time-based segment queries (future implementation)  
python -m video_ingest_tool db segments --clip-id="clip_123" --start="00:02:00" --end="00:05:00"
python -m video_ingest_tool db segments --duration-min=30 --duration-max=120
```

**Segment Processing Pipeline (Future):**
1. **Automatic Segmentation**: Scene change detection, speaker diarization boundaries
2. **Manual Segmentation**: User-defined time boundaries via CLI or future web interface
3. **Segment Analysis**: Individual AI analysis for each segment
4. **Segment Embeddings**: Vector generation for precise timestamp-based search
5. **Cross-Segment Search**: Find related content across different parts of videos

**Database Queries Enabled by Schema:**
```sql
-- Find segments within time range
SELECT * FROM video_segments 
WHERE video_clip_id = $1 
AND start_time_seconds >= $2 
AND end_time_seconds <= $3;

-- Semantic search within segments
SELECT vs.*, ve.content_text,
       ve.embedding <=> $1 as similarity
FROM video_segments vs
JOIN video_embeddings ve ON vs.id = ve.video_segment_id
WHERE ve.embedding_type = 'segment'
ORDER BY similarity
LIMIT 10;

-- Find overlapping segments across clips
SELECT vs1.video_clip_id, vs1.start_time_seconds, vs2.video_clip_id, vs2.start_time_seconds
FROM video_segments vs1
JOIN video_embeddings ve1 ON vs1.id = ve1.video_segment_id
JOIN video_embeddings ve2 ON ve1.embedding <=> ve2.embedding < 0.3
JOIN video_segments vs2 ON ve2.video_segment_id = vs2.id
WHERE vs1.video_clip_id != vs2.video_clip_id;
```
```bash
# Enhanced ingest command with authentication
python -m video_ingest_tool ingest /path/to/videos/ --store-database

# New database management commands  
python -m video_ingest_tool db search "outdoor scenes"
python -m video_ingest_tool db search --similar-to="clip_id" --limit=10
python -m video_ingest_tool db list --user-only
python -m video_ingest_tool db stats
python -m video_ingest_tool db export --format=json

# Admin commands (requires admin profile)
python -m video_ingest_tool admin users list
python -m video_ingest_tool admin users promote user@example.com admin
python -m video_ingest_tool admin clips list --all-users
```

### 7.2. Vector Embeddings & Search Implementation ⏳
1. **Embedding Generation:**
   - ⏳ Implement embedding API client
   - ⏳ Create vector generation from AI analysis summaries
   - ⏳ Set up pgvector for similarity searches

2. **Search Interface:**
   - ⏳ Implement natural language query processing
   - ⏳ Create compound filtering (semantic + technical parameters)
   - ⏳ Add CLI search commands

### 7.3. Task Queue Implementation Phase ⏳
1. **Set Up Procrastinate:** ⏳
   - ⏳ Add Procrastinate to requirements
   - ⏳ Configure Procrastinate to use PostgreSQL
   - ⏳ Create task schema (Procrastinate applies automatically)

2. **Refactor Pipeline into Tasks:** ⏳
   - ✅ Split processing into discrete steps (pipeline already modular)
   - ⏳ Convert pipeline steps to Procrastinate tasks
   - ⏳ Implement dependencies between tasks
   - ⏳ Ensure proper error handling and retry logic

3. **Add Worker Management:** ⏳
   - ⏳ Create worker process
   - ⏳ Implement queue management commands
   - ⏳ Add health checks and monitoring
   - ⏳ Support for running multiple workers with configurable concurrency

### 7.4. CLI Enhancement Phase ⏳
1. **Command Structure Expansion:**
   - ✅ Add step configuration functionality
   - ✅ Add list_steps command
   - ✅ Add AI analysis configuration
   - ⏳ Implement search commands
   - ⏳ Add collection and tag management
   - ⏳ Create system management commands

2. **Natural Language Search:**
   - ⏳ Implement vector-based semantic search
   - ⏳ Create query parsing and refinement
   - ⏳ Add compound filtering with technical parameters

3. **Output Formatting:**
   - ✅ Provide detailed pipeline information
   - ✅ Comprehensive AI analysis display
   - ⏳ Create exporters for different formats (JSON, CSV)
   - ⏳ Implement report generation

### 7.5. Performance & Scalability Improvements ⏳
1. **Optimization:**
   - ⏳ Implement parallel processing for multiple files
   - ⏳ Add caching for AI analysis results
   - ⏳ Optimize thumbnail generation and storage

2. **Resource Management:**
   - ⏳ Add resource usage monitoring
   - ⏳ Implement configurable concurrency limits
   - ⏳ Add memory and disk usage controls

---

## 8. Technical Requirements

### 8.1. Current Dependencies ✅
- Python 3.9+ (tested with 3.10, 3.11, and 3.12)
- FFmpeg installed and in PATH
- ExifTool installed and in PATH
- Python packages:
  - av>=14.4.0 (PyAV for video processing)
  - pymediainfo>=6.0.0 (MediaInfo wrapper)
  - PyExifTool>=0.5.0 (ExifTool wrapper)
  - opencv-python>=4.8.0 (Computer vision)
  - typer[all]>=0.9.0 (CLI framework)
  - rich>=13.4.0 (Terminal formatting)
  - pydantic>=2.4.0 (Data validation)
  - structlog>=23.1.0 (Structured logging)
  - numpy>=1.24.0 (Numerical operations)
  - pillow>=10.0.0 (Image processing)
  - polyfile>=0.5.5 (File type detection)
  - hachoir==3.3.0 (Binary parsing)
  - python-dateutil>=2.8.2 (Date parsing)
  - transformers>=4.28.0 (Optional: for AI focal length detection) ✅ ⭐
  - torch>=2.0.0 (Optional: for AI focal length detection) ✅ ⭐
  - google-generativeai>=0.3.0 (Gemini Flash 2.5 API) ✅ ⭐
  - python-dotenv>=1.0.0 (Environment variable management) ✅ ⭐

### 8.2. Future Dependencies ⏳
- supabase>=2.3.0 (Python client for database operations) ⏳ ⭐
- tiktoken>=0.5.0 (Token counting for embedding limits) ⏳ ⭐  
- openai>=1.0.0 (DeepInfra API client via OpenAI interface) ⏳ ⭐
- Procrastinate (PostgreSQL-based task queue)
- psycopg (PostgreSQL adapter)
- langchain or API clients for:
  - Gemini Flash 2.5 ✅ (already implemented)
  - Additional embedding services (backup options)
- pgvector for vector operations

### 8.3. System Requirements
- **Minimum**: 4-core CPU, 16GB RAM, 50GB storage for local caching
- **Recommended**: 8-core CPU, 32GB RAM, SSD storage, GPU
- **Network**: High-speed internet for AI service and Supabase communication
- **OS Support**: macOS, Windows 10/11, Linux (Ubuntu 20.04+)

---

## 9. Conclusion

The AI-Powered Video Ingest & Catalog Tool has made significant progress beyond the initial specification, with several major features now fully implemented. The system has evolved from a basic metadata extraction tool into a comprehensive video analysis platform powered by state-of-the-art AI.

**Major Accomplishments Since Last Update:**
- ✅ Complete multimodal AI analysis integration with Gemini Flash 2.5
- ✅ Hardware-accelerated video compression system
- ✅ Comprehensive audio and subtitle track analysis
- ✅ Advanced HDR and color metadata extraction
- ✅ Detailed codec parameter analysis
- ✅ AI-powered visual, audio, and content analysis
- ✅ Structured JSON output with full analysis results
- ✅ Configurable pipeline with granular step control

Recent improvements include:
- ✅ Refactored modular architecture with clear separation of concerns
- ✅ Configurable pipeline with the ability to enable/disable specific steps
- ✅ Enhanced CLI interface with step configuration and documentation
- ✅ AI-based focal length detection for videos lacking EXIF data
- ✅ Comprehensive video analysis using Gemini Flash 2.5
- ✅ Hardware-accelerated video compression with multiple codec support
- ✅ Advanced metadata extraction for audio tracks, subtitles, HDR, and color information
- ✅ Structured AI analysis with separate detailed JSON files
- ✅ Improved data models that align with future database schema

The system now provides end-to-end video analysis capabilities that were originally planned for later phases, making it a powerful tool for video content understanding and cataloging. The next phases of development will focus on:
1. Implementing database integration with Supabase
2. Adding vector embeddings for semantic search capabilities
3. Setting up a task queue system with Procrastinate for scalable processing
4. Expanding the CLI interface for comprehensive content management and search

This accelerated development demonstrates the modular design's effectiveness, allowing for rapid feature addition while maintaining code quality and system stability. Each component remains designed to be modular and reusable, maintaining compatibility with future expansions and potential refactoring into a FastAPI-based service.
