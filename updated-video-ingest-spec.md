
## Technical Specification (Updated - May 21, 2025)

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
- Multimodal AI Analysis ⏳ (Planned)
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

### 2.4. Computer Vision Analysis ⏳
- **Exposure analytics** - Percentage of over/under-exposed regions via OpenCV ✅
- **Visual quality scoring** - Technical assessment of blur, noise, and compression artifacts ⏳
- **Scene complexity metrics** - Analysis of visual information density ⏳
- **Shot type estimation** - Wide, medium, close-up based on composition heuristics ⏳

### 2.5. Multimodal AI Analysis ⏳
- **Integrated video processing** - End-to-end analysis via Gemini Flash 2.0
- **Full transcription** - Convert all speech to searchable text
- **Non-speech event detection** - Identify music, applause, crowd noise, ambient sounds
- **Scene labeling** - Automatic categorization (indoor/outdoor, quiet/noisy, etc.)
- **Visual content analysis** - Detailed descriptions of on-screen activity and objects
- **Speaker diarization** - Distinguish between different speakers when possible
- **Contextual summary** - Comprehensive understanding of the video content

### 2.6. Structured Content Analysis ⏳
- **Semantic extraction** - Convert raw video content into structured data
- **Structured JSON output** including:
  - `summary`: 3-5 sentence description of content
  - `keywords`: 5-10 most relevant topical tags
  - `entities`: Named entities (PERSON/ORG/LOCATION)
  - `scene_classification`: Environmental and situational context
  - `sentiment`: Overall emotional tone
  - `content_warnings`: Optional flags for sensitive content
  - `technical_quality`: Assessment of usability

### 2.7. Vector Embeddings & Semantic Search ⏳
- **Text embeddings** - Convert summaries and keywords to vector space
- **Similarity search** - Find clips with related content using vector proximity
- **Natural language queries** - "Show me clips about X" functionality
- **Compound filtering** - Combine semantic search with technical parameters
- **Results ranking** - Intelligent sorting by relevance and quality

### 2.8. Centralized Database Architecture ⏳
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

### 3.5. Multimodal AI Analysis ⏳
1. **Video preparation** - Format video and thumbnails for API submission
2. **Gemini Flash 2.0 processing** - Send full video plus metadata for comprehensive analysis:
   - Full speech transcription
   - Non-speech event detection
   - Visual content analysis
   - Scene classification
   - Entity recognition
3. **Structured data extraction** - Parse API response into standardized schema
4. **Quality validation** - Verify completeness and usefulness of generated content

### 3.6. Vector Embedding Generation ⏳
1. **Text preparation** - Combine summary text and keywords
2. **Vector generation** - Process through embedding model
3. **Dimension verification** - Ensure compatibility with vector database

### 3.7. Database Integration ⏳
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
│                     │     │                 │     │   Storage          │
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

#### 4.2.3. Computer Vision Module ⏳
- **Framework**: OpenCV (Python) ✅
- **Image Processing**: Pillow for thumbnail generation and manipulation ✅
- **Image Quality**: Basic exposure analysis via histograms ✅
- **Advanced Analysis**: Shot type detection, blur detection, noise analysis ⏳

#### 4.2.4. AI Integration Layer ⏳
- **Video Analysis**: Gemini Flash 2.0 API
- **Embedding Service**: OpenAI Embeddings or equivalent

#### 4.2.5. Database Architecture ⏳
- **Primary Database**: Online Supabase Postgres instance
- **Vector Extension**: pgvector enabled in Supabase project
- **Media Storage**: Supabase Storage buckets for thumbnails
- **Security Model**: Row-level security policies via Supabase
- **Cache Strategy**: Local thumbnail caching with remote persistence

#### 4.2.6. Task Queue Management ⏳
- **Framework**: Procrastinate
- **Persistence**: PostgreSQL tables in same database
- **Orchestration**: Priority-based task scheduling

#### 4.2.7. Command-Line Interface ✅
- **Framework**: Typer for rich CLI experience
- **Output Formatting**: Rich for colored terminal output and progress bars
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
- **Implementation**: ✅ Procrastinate tasks with explicit dependencies
- **Standard Pipeline Stages**:
  1. ✅ **Validation**: Format check, corruption detection, checksum generation
  2. ✅ **Metadata Extraction**: Technical parameters, container analysis
  3. ✅ **Thumbnail Generation**: Key frame sampling, thumbnail creation
  4. ✅ **Technical Analysis**: Exposure metrics (basic implementation)
  5. ⏳ **Multimodal AI Analysis**: Comprehensive video content analysis via Gemini Flash 2.0
  6. ⏳ **Vector Embedding**: Semantic embedding generation
  7. ⏳ **Database Integration**: Final results stored in JSON (will be updated to Supabase)
- **Execution Properties**:
  - Stage dependencies managed via Procrastinate locks
  - Parallel execution where possible using worker concurrency
  - Built-in checkpointing via job status tracking
  - Failure handling with automatic retries and queueing locks

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
python video_ingestor.py /path/to/videos/

# With custom parameters
python video_ingestor.py /path/to/videos/ --recursive --output-dir=output

# Monitor progress with detailed output (built-in)
python video_ingestor.py /path/to/videos/ --limit=5

# Future parameters (planned)
python video_ingestor.py /path/to/videos/ --focus=audio-analysis --skip-visual
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
**VideoFile (Pydantic Model)**
```python
class VideoFile(BaseModel):
    """Video file model with basic information and technical metadata"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    file_path: str
    file_name: str
    file_checksum: str
    file_size_bytes: int
    created_at: Optional[datetime.datetime] = None
    processed_at: datetime.datetime = Field(default_factory=datetime.datetime.now)
    duration_seconds: Optional[float] = None
    technical_metadata: Optional[TechnicalMetadata] = None
    thumbnail_paths: List[str] = []

class TechnicalMetadata(BaseModel):
    """Technical metadata extracted from video files"""
    codec: Optional[str] = None
    container: Optional[str] = None
    resolution_width: Optional[int] = None
    resolution_height: Optional[int] = None
    aspect_ratio: Optional[str] = None
    frame_rate: Optional[float] = None
    bit_rate_kbps: Optional[int] = None
    duration_seconds: Optional[float] = None
    exposure_warning: Optional[bool] = None
    exposure_stops: Optional[float] = None
    overexposed_percentage: Optional[float] = None
    underexposed_percentage: Optional[float] = None
    bit_depth: Optional[int] = None
    color_space: Optional[str] = None
    camera_make: Optional[str] = None
    camera_model: Optional[str] = None
    focal_length: Optional[str] = None
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

### 6.2. Current Implementation Details ✅

#### 6.2.1. File Processing Pipeline
```python
def process_video_file(file_path: str, thumbnails_dir: str) -> VideoFile:
    """
    Process a video file to extract metadata and generate thumbnails.
    
    Args:
        file_path: Path to the video file
        thumbnails_dir: Directory to save thumbnails
        
    Returns:
        VideoFile: Processed video file object
    """
    # Calculate checksum for deduplication
    checksum = calculate_checksum(file_path)
    
    # Extract metadata from multiple sources
    mediainfo_data = extract_mediainfo(file_path)
    ffprobe_data = extract_ffprobe_info(file_path)
    exiftool_data = extract_exiftool_info(file_path)
    
    # Combine and normalize metadata
    metadata = {**exiftool_data, **ffprobe_data, **mediainfo_data}
    
    # Generate thumbnails
    thumbnail_dir = os.path.join(thumbnails_dir, checksum)
    thumbnail_paths = generate_thumbnails(file_path, thumbnail_dir)
    
    # Analyze exposure using the first thumbnail
    exposure_data = {}
    if thumbnail_paths:
        exposure_data = analyze_exposure(thumbnail_paths[0])
    
    # Calculate aspect ratio
    aspect_ratio_str = calculate_aspect_ratio_str(
        metadata.get('width'), 
        metadata.get('height')
    )
    
    # Create structured technical metadata
    technical_metadata = TechnicalMetadata(
        codec=metadata.get('codec'),
        container=metadata.get('container'),
        resolution_width=metadata.get('width'),
        resolution_height=metadata.get('height'),
        aspect_ratio=aspect_ratio_str,
        frame_rate=metadata.get('frame_rate'),
        bit_rate_kbps=int(metadata.get('overall_bit_rate') / 1000) if metadata.get('overall_bit_rate') else None,
        duration_seconds=metadata.get('duration_seconds'),
        exposure_warning=exposure_data.get('exposure_warning'),
        exposure_stops=exposure_data.get('exposure_stops'),
        overexposed_percentage=exposure_data.get('overexposed_percentage'),
        underexposed_percentage=exposure_data.get('underexposed_percentage'),
        bit_depth=metadata.get('bit_depth'),
        color_space=metadata.get('color_space'),
        camera_make=metadata.get('camera_make'),
        camera_model=metadata.get('camera_model'),
        focal_length=metadata.get('focal_length')
    )
    
    # Create complete video file object
    video_file = VideoFile(
        file_path=file_path,
        file_name=os.path.basename(file_path),
        file_checksum=checksum,
        file_size_bytes=os.path.getsize(file_path),
        created_at=metadata.get('created_at'),
        duration_seconds=metadata.get('duration_seconds'),
        technical_metadata=technical_metadata,
        thumbnail_paths=thumbnail_paths
    )
    
    return video_file
```

#### 6.2.2. Technical Metadata Extraction

```python
def extract_mediainfo(file_path: str) -> Dict[str, Any]:
    """
    Extract technical metadata using pymediainfo.
    """
    media_info = pymediainfo.MediaInfo.parse(file_path)
    
    general_track = next((track for track in media_info.tracks if track.track_type == 'General'), None)
    video_track = next((track for track in media_info.tracks if track.track_type == 'Video'), None)
    
    metadata = {}
    
    if general_track:
        metadata.update({
            'container': general_track.format,
            'duration_seconds': float(general_track.duration) / 1000 if general_track.duration else None,
            'file_size_bytes': general_track.file_size,
            'created_at': parse_datetime_string(general_track.encoded_date)
        })
    
    if video_track:
        metadata.update({
            'codec': video_track.codec_id or video_track.format,
            'width': video_track.width,
            'height': video_track.height,
            'frame_rate': float(video_track.frame_rate) if video_track.frame_rate else None,
            'bit_depth': video_track.bit_depth,
            'color_space': video_track.color_space
        })
    
    return metadata

def extract_ffprobe_info(file_path: str) -> Dict[str, Any]:
    """
    Extract technical metadata using PyAV (which uses FFmpeg libraries).
    """
    with av.open(file_path) as container:
        duration_seconds = None
        if container.duration is not None:
            duration_seconds = float(container.duration) / 1000000.0
        
        metadata = {
            'duration_seconds': duration_seconds,
            'file_size_bytes': os.path.getsize(file_path)
        }
        
        video_streams = [s for s in container.streams.video if s.type == 'video']
        if video_streams:
            video_stream = video_streams[0]
            
            # Extract codec information
            codec_ctx = getattr(video_stream, 'codec_context', None)
            codec_name_val = 'unknown'
            if codec_ctx:
                codec_name_val = getattr(codec_ctx, 'name', None)
                if not codec_name_val:
                    codec_name_val = getattr(codec_ctx, 'long_name', 'unknown')

            # Extract frame rate
            frame_rate = None
            if video_stream.average_rate:
                frame_rate = float(video_stream.average_rate)
            
            metadata.update({
                'format_name': container.format.name,
                'format_long_name': container.format.long_name,
                'codec': codec_name_val,
                'width': video_stream.width,
                'height': video_stream.height,
                'frame_rate': frame_rate,
                'bit_depth': getattr(video_stream, 'bits_per_coded_sample', None)
            })
        
        return metadata

def extract_exiftool_info(file_path: str) -> Dict[str, Any]:
    """
    Extract metadata using ExifTool.
    """
    with exiftool.ExifToolHelper() as et:
        metadata = et.get_metadata(file_path)[0]
        
        exif_data = {
            'camera_make': metadata.get('EXIF:Make'),
            'camera_model': metadata.get('EXIF:Model'),
            'focal_length': metadata.get('EXIF:FocalLength'),
            'created_at': parse_datetime_string(
                metadata.get('EXIF:CreateDate') or 
                metadata.get('QuickTime:CreateDate') or 
                metadata.get('QuickTime:CreationDate')
            ),
            'gps_latitude': metadata.get('EXIF:GPSLatitude'),
            'gps_longitude': metadata.get('EXIF:GPSLongitude'),
        }
        
        exif_data = {k: v for k, v in exif_data.items() if v is not None}
        return exif_data
```

#### 6.2.3. Thumbnail Generation

```python
def generate_thumbnails(file_path: str, output_dir: str, count: int = 5) -> List[str]:
    """
    Generate thumbnails from video file using PyAV.
    """
    thumbnail_paths = []
    
    # Create output directory
    os.makedirs(output_dir, exist_ok=True)
    
    with av.open(file_path) as container:
        # Calculate duration
        duration = float(container.duration / 1000000) if container.duration else 0
        
        if duration <= 0:
            return []
        
        # Calculate evenly distributed positions
        positions = [duration * i / (count + 1) for i in range(1, count + 1)]
        
        if not container.streams.video:
            return []
            
        stream = container.streams.video[0]
        
        for i, position in enumerate(positions):
            output_path = os.path.join(output_dir, f"{os.path.basename(file_path)}_{i}.jpg")
            
            # Seek to position
            container.seek(int(position * 1000000), stream=stream)
            
            # Extract and save frame
            for frame in container.decode(video=0):
                img = frame.to_image()
                
                # Resize for thumbnail
                width, height = img.size
                new_width = 640
                new_height = int(height * new_width / width)
                img = img.resize((new_width, new_height), Image.LANCZOS)
                
                img.save(output_path, quality=95)
                
                thumbnail_paths.append(output_path)
                break
    
    return thumbnail_paths
```

#### 6.2.4. Exposure Analysis

```python
def analyze_exposure(thumbnail_path: str) -> Dict[str, Any]:
    """
    Analyze exposure in an image using OpenCV.
    Returns exposure warning flag and exposure deviation in stops.
    """
    image = cv2.imread(thumbnail_path)
    
    # Convert to grayscale
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    
    # Calculate histogram
    hist = cv2.calcHist([gray], [0], None, [256], [0, 256])
    hist = hist.flatten() / (gray.shape[0] * gray.shape[1])
    
    # Calculate over/under exposure
    overexposed = sum(hist[240:])
    underexposed = sum(hist[:16])
    
    # Calculate exposure warning
    exposure_warning = overexposed > 0.05 or underexposed > 0.05
    
    # Estimate exposure deviation in stops
    # (This would be calculated based on histogram distribution)
    exposure_stops = 0.0
    if overexposed > underexposed and overexposed > 0.05:
        # Rough approximation of stops overexposed
        exposure_stops = math.log2(overexposed * 20)
    elif underexposed > 0.05:
        # Rough approximation of stops underexposed (negative value)
        exposure_stops = -math.log2(underexposed * 20)
    
    result = {
        'exposure_warning': exposure_warning,
        'exposure_stops': exposure_stops,
        'overexposed_percentage': float(overexposed * 100),
        'underexposed_percentage': float(underexposed * 100)
    }
    
    return result
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

#### 6.3.2. Task Pipeline Orchestration
```python
# Metadata extraction task
@app.task(queue="processing", lock="{file_path}")
def extract_metadata(file_path, checksum, config=None):
    """
    Extract metadata as a separate Procrastinate task.
    The lock ensures only one instance can process the same file at a time.
    """
    try:
        # Extract metadata from multiple sources
        mediainfo_data = extract_mediainfo(file_path)
        ffprobe_data = extract_ffprobe_info(file_path)
        exiftool_data = extract_exiftool_info(file_path)
        
        # Combine and normalize metadata
        metadata = {**exiftool_data, **ffprobe_data, **mediainfo_data}
        
        # Queue thumbnail generation as the next step
        generate_thumbnails.defer(
            file_path=file_path, 
            checksum=checksum, 
            metadata=metadata,
            config=config
        )
        
        return {"status": "success", "file": file_path, "metadata": "extracted"}
    except Exception as e:
        logger.error(f"Error extracting metadata from {file_path}: {str(e)}")
        raise
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

### 7.1. Database Integration Phase
1. **Configure Supabase:**
   - ⏳ Set up Supabase project
   - ⏳ Create database schema based on section 6.1 definitions
   - ⏳ Enable pgvector extension

2. **Implement Database Layer:**
   - ⏳ Create database connection module
   - ⏳ Implement CRUD operations for all tables
   - ⏳ Add configuration for database credentials
   - ⏳ Convert current JSON storage to database storage

3. **Refactor Current Code:**
   - ⏳ Modify VideoFile model to match database schema
   - ⏳ Update process_video_file to store in database
   - ⏳ Implement functions to query and update database records

### 7.2. Task Queue Implementation Phase 🔄
1. **Set Up Procrastinate:** ✅
   - ✅ Add Procrastinate to requirements
   - ✅ Configure Procrastinate to use PostgreSQL
   - ✅ Create task schema (Procrastinate applies automatically)

2. **Refactor Pipeline into Tasks:** ✅
   - ✅ Split process_video_file into discrete tasks
   - ✅ Implement dependencies between tasks
   - ✅ Ensure proper error handling and retry logic

3. **Add Worker Management:** ✅
   - ✅ Create worker process
   - ✅ Implement queue management commands
   - ✅ Add health checks and monitoring
   - ✅ Support for running multiple workers with configurable concurrency

### 7.3. Multimodal AI Integration Phase ⏳
1. **Gemini Flash 2.0 Setup:**
   - ⏳ Create API client for Gemini Flash 2.0
   - ⏳ Implement authentication and request handling
   - ⏳ Set up proper error handling and rate limiting

2. **Video Analysis Integration:**
   - ⏳ Implement video preparation for API
   - ⏳ Create structured data parsing from responses
   - ⏳ Store and link analysis results in database

3. **Embedding Generation:**
   - ⏳ Implement embedding API client
   - ⏳ Create vector generation and storage
   - ⏳ Set up pgvector for similarity searches

### 7.4. CLI Enhancement Phase
1. **Command Structure Expansion:**
   - Implement search commands
   - Add collection and tag management
   - Create system management commands

2. **Natural Language Search:**
   - Implement vector-based semantic search
   - Create query parsing and refinement
   - Add compound filtering with technical parameters

3. **Output Formatting:**
   - Create exporters for different formats (JSON, CSV)
   - Enhance terminal output with Rich
   - Implement report generation

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

### 8.2. Future Dependencies ⏳
- Supabase client for Python
- Procrastinate (PostgreSQL-based task queue)
- psycopg (PostgreSQL adapter)
- langchain or API clients for:
  - Gemini Flash 2.0
  - Embedding service
- pgvector for vector operations

### 8.3. System Requirements
- **Minimum**: 4-core CPU, 16GB RAM, 50GB storage for local caching
- **Recommended**: 8-core CPU, 32GB RAM, SSD storage, GPU
- **Network**: High-speed internet for AI service and Supabase communication
- **OS Support**: macOS, Windows 10/11, Linux (Ubuntu 20.04+)

---

## 9. Conclusion

The AI-Powered Video Ingest & Catalog Tool is being developed in phases, with solid progress on the content discovery and technical metadata extraction components. The current implementation provides a reliable foundation for automated video file processing, storing results in JSON format with well-structured data models.

The next phases of development will focus on:
1. Implementing database integration with Supabase
2. Setting up a task queue system with Procrastinate
3. Adding multimodal AI analysis with Gemini Flash 2.0
4. Creating vector embeddings for semantic search
5. Expanding the CLI interface for comprehensive content management

This phased approach ensures stable, incremental progress while building toward the comprehensive video asset management solution described in the original specification. Each component is designed to be modular and reusable, maintaining compatibility with future expansions and potential refactoring into a FastAPI-based service.
