#!/usr/bin/env python3
"""
Task Queue System for Video Ingestor Tool

This module provides a PostgreSQL-based task queue system for the Video Ingestor Tool 
using Procrastinate. All tasks are stored in the database for reliable processing
and persistence between application restarts.

The tasks are defined for different stages of the video processing pipeline.
Compatible with Procrastinate 3.2.2
"""

import os
import logging
import json
import psycopg # For psycopg.errors
import sys
from typing import Dict, Any, Optional, List, Union
import datetime
from pathlib import Path
import uuid

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    # Load from .env file if it exists
    load_dotenv()
    print("DEBUG: Loaded environment variables from .env file")
except ImportError:
    print("DEBUG: python-dotenv not installed, using environment variables directly")

import structlog

print(f"DEBUG: sys.path in task_queue.py: {sys.path}")

# Get logger
logger = structlog.get_logger(__name__)

# Import Procrastinate with PostgreSQL connector
try:
    print("DEBUG: Attempting to import procrastinate...")
    import procrastinate
    print(f"DEBUG: procrastinate imported successfully. Version: {getattr(procrastinate, '__version__', 'N/A')}")
    print("DEBUG: Attempting to import procrastinate.App and procrastinate.PsycopgConnector...")
    from procrastinate import App, PsycopgConnector
    print("DEBUG: procrastinate.App and procrastinate.PsycopgConnector imported successfully.")
    PROCRASTINATE_AVAILABLE = True
except ImportError as e:
    print(f"DEBUG: ImportError occurred: {e}")
    logger.error("Procrastinate not available. Install with 'pip install procrastinate psycopg2-binary'")
    PROCRASTINATE_AVAILABLE = False
    # Create dummy App class for type checking
    class App: # type: ignore
        pass
except Exception as e:
    print(f"DEBUG: An unexpected error occurred during import: {e}")
    logger.error(f"Unexpected error importing Procrastinate: {e}")
    PROCRASTINATE_AVAILABLE = False
    class App: # type: ignore
        pass

def get_db_config() -> Dict[str, Any]:
    """
    Get database configuration from environment variables.
    Environment variables are loaded from .env file if available.
    
    Returns:
        Dict[str, Any]: Database configuration dictionary
    """
    raw_host = os.environ.get("VIDEOINGESTOR_DB_HOST", "localhost")
    resolved_host = "127.0.0.1" if raw_host == "localhost" else raw_host
    return {
        "host": resolved_host,
        "user": os.environ.get("VIDEOINGESTOR_DB_USER", "postgres"),
        "password": os.environ.get("VIDEOINGESTOR_DB_PASSWORD", "password"),
        "dbname": os.environ.get("VIDEOINGESTOR_DB_NAME", "videoingestor"),
        "port": int(os.environ.get("VIDEOINGESTOR_DB_PORT", "5432")),
    }

# Database configuration
DB_CONFIG = get_db_config()

def create_app(db_config: Optional[Dict[str, Any]] = None) -> App:
    """
    Create a Procrastinate App instance with PostgreSQL connector.
    
    Args:
        db_config: Database configuration dictionary
        
    Returns:
        App: Configured Procrastinate App
    """
    if not PROCRASTINATE_AVAILABLE:
        logger.error("Cannot create app: Procrastinate is not installed")
        sys.exit(1)
        
    try:
        logger.info("Creating Procrastinate App with PostgreSQL")
        config = db_config or DB_CONFIG
        
        # First check if psycopg2 is available
        try:
            import psycopg2
            print(f"DEBUG: psycopg2 version: {psycopg2.__version__}")
        except ImportError:
            print("DEBUG: psycopg2 is not installed. Trying to use psycopg instead.")
        
        # Create the connector
        connector = PsycopgConnector(
            kwargs={
                "host": config["host"],
                "user": config["user"],
                "password": config["password"],
                "dbname": config["dbname"],
                "port": config["port"],
            }
        )
        logger.info(f"Connected to PostgreSQL database: {config['dbname']} on {config['host']}:{config['port']}")
    except Exception as e:
        logger.error(f"Failed to connect to PostgreSQL: {str(e)}")
        print(f"\nDEBUG: Detailed connection error: {repr(e)}")
        print("\nPlease ensure PostgreSQL is running and accessible with the following settings:")
        config_display = DB_CONFIG.copy()
        config_display['password'] = '********'  # Hide password
        for key, value in config_display.items():
            print(f"  {key}: {value}")
        print("\nYou can set these values using environment variables:")
        print("  VIDEOINGESTOR_DB_HOST, VIDEOINGESTOR_DB_PORT, VIDEOINGESTOR_DB_USER,")
        print("  VIDEOINGESTOR_DB_PASSWORD, VIDEOINGESTOR_DB_NAME\n")
        sys.exit(1)
    
    app = App(connector=connector)
    return app


# We'll create the app instance later to avoid circular imports
app = None

# Define tasks for each stage of the pipeline
def calculate_checksum(file_path: str, block_size: int = 65536) -> str:
    """
    Calculate MD5 checksum of a file.
    
    Args:
        file_path: Path to the file
        block_size: Block size for reading the file
        
    Returns:
        str: Hex digest of MD5 checksum
    """
    logger.info("Calculating checksum", path=file_path)
    hash_md5 = hashlib.md5()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(block_size), b""):
            hash_md5.update(chunk)
    checksum = hash_md5.hexdigest()
    logger.info("Checksum calculated", path=file_path, checksum=checksum)
    return checksum

def validate_video_file(file_path: str, job_id: str) -> Dict[str, Any]:
    """
    Validate a video file and generate its checksum.
    
    Args:
        file_path: Path to the video file
        job_id: Unique identifier for the job
        
    Returns:
        Dict: Validation result including file path and checksum
    """
    logger.info("Starting video file validation", file_path=file_path, job_id=job_id)
    
    try:
        # Check if file exists
        if not os.path.exists(file_path):
            logger.error("File not found", file_path=file_path, job_id=job_id)
            return {"status": "error", "message": f"File not found: {file_path}", "job_id": job_id}
        
        # Get file size
        file_size = os.path.getsize(file_path)
        
        # Calculate checksum using local function
        checksum = calculate_checksum(file_path)
        
        logger.info("Video file validation completed", 
                    file_path=file_path, 
                    file_size=file_size, 
                    checksum=checksum, 
                    job_id=job_id)
        
        # Queue the next task in the pipeline
        extract_metadata.defer(
            file_path=file_path,
            checksum=checksum,
            job_id=job_id
        )
        
        return {
            "status": "success",
            "file_path": file_path,
            "file_name": os.path.basename(file_path),
            "file_size_bytes": file_size,
            "file_checksum": checksum,
            "job_id": job_id
        }
    except Exception as e:
        logger.error("Error validating video file", 
                     file_path=file_path, 
                     error=str(e), 
                     job_id=job_id)
        return {"status": "error", "message": str(e), "job_id": job_id}


def extract_mediainfo(file_path: str) -> Dict[str, Any]:
    """
    Extract technical metadata using pymediainfo.
    
    Args:
        file_path: Path to the video file
        
    Returns:
        Dict: Technical metadata
    """
    logger.info("Extracting MediaInfo metadata", path=file_path)
    try:
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
        
        logger.info("MediaInfo extraction successful", path=file_path)
        return metadata
    
    except Exception as e:
        logger.error("MediaInfo extraction failed", path=file_path, error=str(e))
        return {}

def extract_ffprobe_info(file_path: str) -> Dict[str, Any]:
    """
    Extract technical metadata using PyAV (which uses FFmpeg libraries).
    
    Args:
        file_path: Path to the video file
        
    Returns:
        Dict: Technical metadata
    """
    logger.info("Extracting PyAV metadata", path=file_path)
    try:
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
                
                codec_ctx = getattr(video_stream, 'codec_context', None)
                codec_name_val = 'unknown'
                if codec_ctx:
                    codec_name_val = getattr(codec_ctx, 'name', None)
                    if not codec_name_val:
                        codec_name_val = getattr(codec_ctx, 'long_name', 'unknown')

                frame_rate = None
                if video_stream.average_rate:
                    frame_rate = float(video_stream.average_rate)
                
                bit_depth = None
                if hasattr(video_stream, 'bits_per_coded_sample'):
                    bit_depth = video_stream.bits_per_coded_sample
                
                metadata.update({
                    'format_name': container.format.name,
                    'format_long_name': container.format.long_name,
                    'codec': codec_name_val,
                    'width': video_stream.width,
                    'height': video_stream.height,
                    'frame_rate': frame_rate,
                    'bit_depth': bit_depth
                })
            
            logger.info("PyAV extraction successful", path=file_path)
            return metadata
    
    except Exception as e:
        logger.error("PyAV extraction failed", path=file_path, error=str(e))
        return {}

def extract_exiftool_info(file_path: str) -> Dict[str, Any]:
    """
    Extract metadata using ExifTool.
    
    Args:
        file_path: Path to the video file
        
    Returns:
        Dict: Technical metadata
    """
    logger.info("Extracting ExifTool metadata", path=file_path)
    try:
        with exiftool.ExifToolHelper() as et:
            metadata = et.get_metadata(file_path)[0]
            
            exif_data = {
                'camera_make': metadata.get('EXIF:Make'),
                'camera_model': metadata.get('EXIF:Model'),
                'focal_length': metadata.get('EXIF:FocalLength'),
                'created_at': parse_datetime_string(metadata.get('EXIF:CreateDate') or metadata.get('QuickTime:CreateDate') or metadata.get('QuickTime:CreationDate')),
                'gps_latitude': metadata.get('EXIF:GPSLatitude'),
                'gps_longitude': metadata.get('EXIF:GPSLongitude'),
            }
            
            exif_data = {k: v for k, v in exif_data.items() if v is not None}
            
            logger.info("ExifTool extraction successful", path=file_path)
            return exif_data
            
    except Exception as e:
        logger.error("ExifTool extraction failed", path=file_path, error=str(e))
        return {}

def parse_datetime_string(date_str: Optional[str]) -> Optional[datetime.datetime]:
    """Parse a date string into a datetime object, handling various formats and UTC."""
    if not date_str:
        return None
    try:
        parsable_date_str = date_str.replace(":", "-", 2) if date_str.count(':') > 1 else date_str
        dt = dateutil_parser.parse(parsable_date_str)
        return dt
    except (ValueError, TypeError) as e:
        logger.warning(f"Could not parse date string: {date_str}", error=str(e))
        return None

def calculate_aspect_ratio_str(width: Optional[int], height: Optional[int]) -> Optional[str]:
    """Calculate aspect ratio as a string (e.g., '16:9')."""
    if not width or not height or width <= 0 or height <= 0:
        return None
    common_divisor = math.gcd(width, height)
    return f"{width // common_divisor}:{height // common_divisor}"

def extract_metadata(file_path: str, checksum: str, job_id: str) -> Dict[str, Any]:
    """
    Extract technical metadata from a video file.
    
    Args:
        file_path: Path to the video file
        checksum: File checksum
        job_id: Unique identifier for the job
        
    Returns:
        Dict: Metadata extraction result
    """
    logger.info("Starting metadata extraction", file_path=file_path, job_id=job_id)
    
    try:
        # Extract metadata using different tools
        mediainfo_data = extract_mediainfo(file_path)
        ffprobe_data = extract_ffprobe_info(file_path)
        exiftool_data = extract_exiftool_info(file_path)
        
        # Combine metadata from all sources
        metadata = {**exiftool_data, **ffprobe_data, **mediainfo_data}
        
        # Calculate aspect ratio
        aspect_ratio_str = calculate_aspect_ratio_str(metadata.get('width'), metadata.get('height'))
        metadata['aspect_ratio'] = aspect_ratio_str
        
        logger.info("Metadata extraction completed", file_path=file_path, job_id=job_id)
        
        # Create thumbnails directory path
        thumbnails_dir = os.path.join(os.path.dirname(os.path.dirname(file_path)), "output", "thumbnails")
        os.makedirs(thumbnails_dir, exist_ok=True)
        
        # Queue the next task in the pipeline
        generate_thumbnails.defer(
            file_path=file_path,
            thumbnails_dir=os.path.join(thumbnails_dir, checksum),
            checksum=checksum,
            metadata=metadata,
            job_id=job_id
        )
        
        return {
            "status": "success",
            "file_path": file_path,
            "file_checksum": checksum,
            "metadata": metadata,
            "job_id": job_id
        }
    except Exception as e:
        logger.error("Error extracting metadata", 
                     file_path=file_path, 
                     error=str(e), 
                     job_id=job_id)
        return {"status": "error", "message": str(e), "job_id": job_id}


def generate_thumbnails(
    file_path: str, 
    thumbnails_dir: str, 
    checksum: str, 
    metadata: Dict[str, Any], 
    job_id: str
) -> Dict[str, Any]:
    """
    Generate thumbnails from a video file.
    
    Args:
        file_path: Path to the video file
        thumbnails_dir: Directory to save thumbnails
        checksum: File checksum
        metadata: Extracted metadata
        job_id: Unique identifier for the job
        
    Returns:
        Dict: Thumbnail generation result
    """
    logger.info("Starting thumbnail generation", file_path=file_path, job_id=job_id)
    
    try:
        # Create the thumbnails directory
        os.makedirs(thumbnails_dir, exist_ok=True)
        
        # Generate thumbnails
        thumbnail_paths = []
        
        try:
            with av.open(file_path) as container:
                duration = float(container.duration / 1000000) if container.duration else 0
                
                if duration <= 0:
                    logger.error("Could not determine video duration", path=file_path)
                    return {"status": "error", "message": "Could not determine video duration", "job_id": job_id}
                
                count = 5  # Default number of thumbnails
                positions = [duration * i / (count + 1) for i in range(1, count + 1)]
                
                if not container.streams.video:
                    logger.error("No video stream found", path=file_path)
                    return {"status": "error", "message": "No video stream found", "job_id": job_id}
                    
                stream = container.streams.video[0]
                
                for i, position in enumerate(positions):
                    output_path = os.path.join(thumbnails_dir, f"{os.path.basename(file_path)}_{i}.jpg")
                    
                    container.seek(int(position * 1000000), stream=stream)
                    
                    for frame in container.decode(video=0):
                        img = frame.to_image()
                        
                        width, height = img.size
                        new_width = 640
                        new_height = int(height * new_width / width)
                        img = img.resize((new_width, new_height), Image.LANCZOS)
                        
                        img.save(output_path, quality=95)
                        
                        thumbnail_paths.append(output_path)
                        logger.info("Generated thumbnail", path=output_path, position=position)
                        break
        
        except Exception as e:
            logger.error("Error in thumbnail generation", error=str(e))
            # Continue with the process even if thumbnail generation fails
        
        logger.info("Thumbnail generation completed", 
                    file_path=file_path, 
                    count=len(thumbnail_paths), 
                    job_id=job_id)
        
        # Queue the next task in the pipeline - analyze exposure
        if thumbnail_paths:
            analyze_exposure.defer(
                file_path=file_path,
                thumbnail_paths=thumbnail_paths,
                checksum=checksum,
                metadata=metadata,
                job_id=job_id
            )
        else:
            # Skip exposure analysis if no thumbnails were generated
            save_results.defer(
                file_path=file_path,
                checksum=checksum,
                metadata=metadata,
                thumbnail_paths=[],
                exposure_data={},
                aspect_ratio_str=metadata.get('aspect_ratio'),
                job_id=job_id
            )
        
        return {
            "status": "success",
            "file_path": file_path,
            "file_checksum": checksum,
            "thumbnail_paths": thumbnail_paths,
            "job_id": job_id
        }
    except Exception as e:
        logger.error("Error generating thumbnails", 
                     file_path=file_path, 
                     error=str(e), 
                     job_id=job_id)
        return {"status": "error", "message": str(e), "job_id": job_id}


def analyze_exposure(
    file_path: str,
    thumbnail_paths: List[str],
    checksum: str,
    metadata: Dict[str, Any],
    job_id: str
) -> Dict[str, Any]:
    """
    Analyze exposure in thumbnails.
    
    Args:
        file_path: Path to the video file
        thumbnail_paths: Paths to generated thumbnails
        checksum: File checksum
        metadata: Extracted metadata
        job_id: Unique identifier for the job
        
    Returns:
        Dict: Exposure analysis result
    """
    logger.info("Starting exposure analysis", 
                file_path=file_path, 
                thumbnails_count=len(thumbnail_paths), 
                job_id=job_id)
    
    try:
        import cv2
        import numpy as np
        
        exposure_data = {
            "histograms": [],
            "overexposed_percentage": 0.0,
            "underexposed_percentage": 0.0,
            "average_brightness": 0.0
        }
        
        total_brightness = 0.0
        total_overexposed = 0.0
        total_underexposed = 0.0
        
        for thumb_path in thumbnail_paths:
            # Read image
            img = cv2.imread(thumb_path)
            if img is None:
                continue
                
            # Convert to grayscale
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            
            # Calculate histogram
            hist = cv2.calcHist([gray], [0], None, [256], [0, 256])
            hist = hist.flatten() / hist.sum()
            
            # Calculate brightness metrics
            avg_brightness = np.mean(gray) / 255.0
        
        logger.info("Exposure analysis completed", 
                    file_path=file_path, 
                    exposure_warning=exposure_data.get('exposure_warning', False), 
                    job_id=job_id)
        
        # Queue the next task in the pipeline
        save_results.defer(
            file_path=file_path,
            checksum=checksum,
            metadata=metadata,
            thumbnail_paths=thumbnail_paths,
            exposure_data=exposure_data,
            aspect_ratio_str=metadata.get('aspect_ratio'),
            job_id=job_id
        )
        
        return {
            "status": "success",
            "file_path": file_path,
            "file_checksum": checksum,
            "thumbnail_paths": thumbnail_paths,
            "exposure_data": exposure_data,
            "job_id": job_id
        }
    except Exception as e:
        logger.error("Error analyzing exposure", 
                     file_path=file_path, 
                     error=str(e), 
                     job_id=job_id)
        return {"status": "error", "message": str(e), "job_id": job_id}


def save_results(
    file_path: str,
    checksum: str,
    metadata: Dict[str, Any],
    thumbnail_paths: List[str],
    exposure_data: Dict[str, Any],
    aspect_ratio_str: Optional[str],
    job_id: str
) -> Dict[str, Any]:
    """
    Save processing results to JSON.
    
    Args:
        file_path: Path to the video file
        checksum: File checksum
        metadata: Extracted metadata
        thumbnail_paths: Paths to generated thumbnails
        exposure_data: Exposure analysis data
        aspect_ratio_str: Aspect ratio as a string (e.g., '16:9')
        job_id: Unique identifier for the job
        
    Returns:
        Dict: Result of saving the data
    """
    logger.info("Saving processing results", file_path=file_path, job_id=job_id)
    
    try:
        # Define VideoFile and TechnicalMetadata classes locally to avoid circular imports
        from pydantic import BaseModel, Field
        
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
            focal_length: Optional[Union[str, float, int]] = None
            
            class Config:
                arbitrary_types_allowed = True
        
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
        
        # Create TechnicalMetadata object
        tech_metadata = TechnicalMetadata(
            codec=metadata.get('codec'),
            container=metadata.get('container'),
            resolution_width=metadata.get('width'),
            resolution_height=metadata.get('height'),
            aspect_ratio=aspect_ratio_str,
            frame_rate=metadata.get('frame_rate'),
            bit_rate_kbps=int(metadata.get('bit_rate', 0) / 1000) if metadata.get('bit_rate') else None,
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
        
        # Create VideoFile object
        video_file = VideoFile(
            file_path=file_path,
            file_name=os.path.basename(file_path),
            file_checksum=checksum,
            file_size_bytes=metadata.get('file_size_bytes', 0),
            created_at=metadata.get('created_at'),
            duration_seconds=metadata.get('duration_seconds'),
            technical_metadata=tech_metadata,
            thumbnail_paths=thumbnail_paths
        )
        
        # Save to JSON
        json_dir = os.path.join(os.path.dirname(os.path.dirname(file_path)), "json_output")
        os.makedirs(json_dir, exist_ok=True)
        
        json_path = os.path.join(json_dir, f"{video_file.id}.json")
        
        # Convert to dict and handle datetime objects
        try:
            # For Pydantic v2
            video_file_dict = video_file.model_dump()
        except AttributeError:
            # For Pydantic v1
            video_file_dict = video_file.dict()
        
        # Convert nested objects to dictionaries
        if 'technical_metadata' in video_file_dict and video_file_dict['technical_metadata']:
            try:
                # For Pydantic v2
                video_file_dict['technical_metadata'] = tech_metadata.model_dump()
            except AttributeError:
                # For Pydantic v1
                video_file_dict['technical_metadata'] = tech_metadata.dict()
        
        # Handle datetime objects
        def json_serial(obj):
            """JSON serializer for objects not serializable by default json code"""
            if isinstance(obj, (datetime.datetime, datetime.date)):
                return obj.isoformat()
            raise TypeError(f"Type {type(obj)} not serializable")
        
        # Debug output
        logger.info(f"JSON data: {video_file_dict}")
        
        with open(json_path, 'w') as f:
            json.dump(video_file_dict, f, indent=2, default=json_serial)
        
        logger.info("Results saved to JSON", file_path=file_path, json_path=json_path, job_id=job_id)
        
        return {
            "status": "success",
            "file_path": file_path,
            "file_checksum": checksum,
            "json_path": json_path,
            "job_id": job_id
        }
    except Exception as e:
        logger.error("Error saving results", 
                     file_path=file_path, 
                     error=str(e), 
                     job_id=job_id)
        return {"status": "error", "message": str(e), "job_id": job_id}


# Initialize the app and apply task decorators
def init_app():
    """
    Initialize the Procrastinate app and apply task decorators.
    """
    global app
    print("DEBUG: Initializing Procrastinate app and applying task decorators")
    
    if app is None and PROCRASTINATE_AVAILABLE:
        app = create_app()
        
        # Apply task decorators
        global validate_video_file, extract_metadata, generate_thumbnails, analyze_exposure, save_results
        validate_video_file = app.task(queue="validation")(validate_video_file)
        extract_metadata = app.task(queue="metadata")(extract_metadata)
        generate_thumbnails = app.task(queue="thumbnails")(generate_thumbnails)
        analyze_exposure = app.task(queue="analysis")(analyze_exposure)
        save_results = app.task(queue="results")(save_results)
    
    return app


def ensure_schema(app: 'App') -> bool:
    """
    Ensures that the database schema is properly set up using Procrastinate's
    programmatic schema applier. This is typically called at worker startup.
    Procrastinate's apply_schema is designed to be idempotent.

    Args:
        app: The initialized Procrastinate App instance.

    Returns:
        bool: True if schema application was successful, False otherwise.
    """
    if not app:
        print("ERROR: Procrastinate app instance is not provided or not initialized for ensure_schema.")
        logger.error("Procrastinate app instance is None in ensure_schema.")
        return False

    try:
        print("Attempting to apply/verify Procrastinate schema...")
        with app.open():  # Ensures DB connection is available
            app.schema_manager.apply_schema()
        print("Procrastinate schema applied/verified successfully programmatically.")
        return True
    except procrastinate.exceptions.ConnectorException as e:
        err_msg = f"Database ConnectorException during schema application: {type(e).__name__} - {e}"
        # Check if the underlying psycopg error is about a duplicate object/type
        # This can happen if the schema is already correctly applied by the CLI
        # and app.schema_manager.apply_schema() is less idempotent for ENUMs etc.
        is_duplicate_object_error = False
        # Ensure psycopg.errors is accessible
        if hasattr(psycopg, 'errors') and e.__cause__ and isinstance(e.__cause__, psycopg.errors.DuplicateObject):
            is_duplicate_object_error = True
        
        if is_duplicate_object_error:
            warn_msg = f"Warning during schema apply/verify: {err_msg}. Assuming schema is OK as this often means objects already exist."
            print(f"WARNING: {warn_msg}")
            logger.warning(warn_msg, exc_info=False) # Log as warning, traceback might be too noisy if it's expected
            return True # Proceed, assuming CLI handled actual schema issues
        else:
            print(f"ERROR: {err_msg}")
            import traceback
            traceback.print_exc() # Print traceback to stdout for immediate visibility
            logger.error(err_msg, exc_info=True)
            return False
    except Exception as e:
        err_msg = f"Unexpected error during schema application: {type(e).__name__} - {e}"
        print(f"ERROR: {err_msg}")
        import traceback
        traceback.print_exc() # Print traceback to stdout for immediate visibility
        logger.error(err_msg, exc_info=True)
        return False

def run_worker(queues: Optional[List[str]] = None, concurrency: int = 1) -> None:
    """
    Run a worker to process tasks from the queue.
    
    Args:
        queues: List of queue names to listen to. If None, listen to all queues.
        concurrency: Number of concurrent jobs to process.
    """
    try:
        app = init_app()
        if not app:
            print("ERROR: Failed to initialize Procrastinate app for worker.")
            logger.error("Failed to initialize Procrastinate app for worker.")
            return

        print("Verifying database schema before starting worker...")
        if not ensure_schema(app): # Call simplified ensure_schema
            print("ERROR: Database schema verification/application failed. Worker cannot start.")
            print("       Please ensure the schema is correctly applied. For robust schema management,")
            print("       it's recommended to use the Procrastinate CLI:")
            print("         conda run -n video-ingest env PYTHONPATH=. procrastinate --app=video_ingestor.app schema --apply")
            logger.error("Database schema verification/application failed. Worker will not start.")
            return
        
        print(f"Starting Procrastinate worker with concurrency={concurrency}...")
        if queues:
            print(f"Listening on queues: {', '.join(queues)}")
        else:
            print("Listening on queues: all")
        
        # Start the worker with improved configuration
        # Based on Procrastinate documentation examples
        with app.open():
            app.run_worker(
                queues=queues,
                concurrency=concurrency,
                wait=True,
                listen_notify=False  # Disable LISTEN/NOTIFY to save one connection
            )
    except Exception as e:
        detailed_error = f"Worker error: {type(e).__name__}: {str(e)}\nFull repr: {repr(e)}"
        print(detailed_error)
        logger.error("Worker failed to start or encountered an error", exc_info=True)
        print("\nPossible solutions:")
        print("1. Ensure PostgreSQL is running")
        print("2. Check that the database 'videoingestor' exists")
        print("3. Verify the user 'postgres' has permission to access the database")
        print("4. Check that all required tables and columns exist")


def enqueue_video_processing(file_path: str) -> str:
    """
    Enqueue a video file for processing.
    
    Args:
        file_path: Path to the video file
        
    Returns:
        str: Job ID
    """
    # Initialize app if not already done
    app = init_app()
    if not app:
        logger.error("Failed to initialize app")
        return ""
    
    # Generate a unique job ID
    job_id = str(uuid.uuid4())
    
    # Enqueue the first task
    validate_video_file.defer(file_path=file_path, job_id=job_id)
    
    logger.info("Video processing job enqueued", file_path=file_path, job_id=job_id)
    return job_id


# Initialize the app when this module is imported
init_app()
