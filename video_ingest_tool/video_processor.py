#!/usr/bin/env python3
"""
Video Processor Module

This module contains the core video processing functions, completely independent of any task
queue implementation. This ensures they can be used both directly and as registered tasks.
"""

import os
import sys
import json
import hashlib
import uuid
import datetime
import math
from typing import Dict, Any, List, Optional, Union
import logging

# Try to import structlog for structured logging
try:
    import structlog
    HAS_STRUCTLOG = True
except ImportError:
    HAS_STRUCTLOG = False
    print("WARNING: structlog package not found. Install with 'pip install structlog' for enhanced logging.")
    
# Configure basic logging if structlog is not available
if HAS_STRUCTLOG:
    logger = structlog.get_logger(__name__)
else:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)-5.5s] [%(name)s] %(message)s"
    )
    logger = logging.getLogger(__name__)

# Define missing_deps to track missing dependencies
missing_deps = []

# Import necessary libraries
try:
    import av
except ImportError:
    missing_deps.append("av")
    print("WARNING: av package not found. Install with 'pip install av' for video processing.")

try:
    import pymediainfo
except ImportError:
    missing_deps.append("pymediainfo")
    print("WARNING: pymediainfo package not found. Install with 'pip install pymediainfo' for metadata extraction.")

try:
    import exiftool
except ImportError:
    missing_deps.append("pyexiftool")
    print("WARNING: pyexiftool package not found. Install with 'pip install pyexiftool' for metadata extraction.")

try:
    import cv2
except ImportError:
    missing_deps.append("opencv-python")
    print("WARNING: opencv-python package not found. Install with 'pip install opencv-python' for image analysis.")

try:
    from PIL import Image
except ImportError:
    missing_deps.append("pillow")
    print("WARNING: pillow package not found. Install with 'pip install pillow' for image processing.")

try:
    from dateutil import parser as dateutil_parser
except ImportError:
    missing_deps.append("python-dateutil")
    print("WARNING: python-dateutil package not found. Install with 'pip install python-dateutil' for date parsing.")

# Display missing dependencies
if missing_deps:
    print("\nMISSING DEPENDENCIES: Please install these packages for full functionality:")
    print(f"pip install {' '.join(missing_deps)}\n")

# Get logger
logger = structlog.get_logger(__name__)

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

def generate_thumbnails(file_path: str, output_dir: str, count: int = 5) -> List[str]:
    """
    Generate thumbnails from video file using PyAV.
    
    Args:
        file_path: Path to the video file
        output_dir: Directory to save thumbnails
        count: Number of thumbnails to generate
        
    Returns:
        List[str]: Paths to generated thumbnails
    """
    logger.info("Generating thumbnails", path=file_path, count=count)
    thumbnail_paths = []
    
    try:
        os.makedirs(output_dir, exist_ok=True)
        
        with av.open(file_path) as container:
            duration = float(container.duration / 1000000) if container.duration else 0
            
            if duration <= 0:
                logger.error("Could not determine video duration", path=file_path)
                return []
            
            positions = [duration * i / (count + 1) for i in range(1, count + 1)]
            
            if not container.streams.video:
                logger.error("No video stream found", path=file_path)
                return []
                
            stream = container.streams.video[0]
            
            for i, position in enumerate(positions):
                output_path = os.path.join(output_dir, f"{os.path.basename(file_path)}_{i}.jpg")
                
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
        
        logger.info("Thumbnail generation complete", path=file_path, count=len(thumbnail_paths))
        return thumbnail_paths
    
    except Exception as e:
        logger.error("Thumbnail generation failed", path=file_path, error=str(e))
        return []

def analyze_exposure(thumbnail_path: str) -> Dict[str, Any]:
    """
    Analyze exposure in an image.
    
    Args:
        thumbnail_path: Path to the thumbnail image
        
    Returns:
        Dict: Exposure analysis results including warning flag and exposure deviation in stops
    """
    logger.info("Analyzing exposure", path=thumbnail_path)
    try:
        image = cv2.imread(thumbnail_path)
        
        if image is None:
            logger.error("Failed to load image", path=thumbnail_path)
            return {
                'exposure_warning': False,
                'exposure_stops': 0.0,
                'overexposed_percentage': 0.0,
                'underexposed_percentage': 0.0
            }
        
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        
        hist = cv2.calcHist([gray], [0], None, [256], [0, 256])
        hist = hist.flatten() / (gray.shape[0] * gray.shape[1])
        
        overexposed = sum(hist[240:])
        underexposed = sum(hist[:16])
        
        # Calculate exposure warning flag
        exposure_warning = overexposed > 0.05 or underexposed > 0.05
        
        # Estimate exposure deviation in stops
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
        
        logger.info("Exposure analysis complete", path=thumbnail_path, result=result)
        return result
    
    except Exception as e:
        logger.error("Exposure analysis failed", path=thumbnail_path, error=str(e))
        return {
            'exposure_warning': False,
            'exposure_stops': 0.0,
            'overexposed_percentage': 0.0,
            'underexposed_percentage': 0.0
        }

def process_video_file(file_path: str, thumbnails_dir: str) -> Dict[str, Any]:
    """
    Process a video file to extract metadata and generate thumbnails.
    This is the main function for direct processing (non-queued).
    
    Args:
        file_path: Path to the video file
        thumbnails_dir: Directory to save thumbnails
        
    Returns:
        Dict: Processed video file data
    """
    logger.info("Processing video file", path=file_path)
    
    try:
        # Calculate checksum
        checksum = calculate_checksum(file_path)
        
        file_size = os.path.getsize(file_path)
        
        # Extract metadata
        mediainfo_data = extract_mediainfo(file_path)
        ffprobe_data = extract_ffprobe_info(file_path)
        exiftool_data = extract_exiftool_info(file_path)
        
        # Combine metadata from all sources
        metadata = {**exiftool_data, **ffprobe_data, **mediainfo_data}
        
        # Create thumbnails directory with checksum as name
        thumbnail_dir = os.path.join(thumbnails_dir, checksum)
        thumbnail_paths = generate_thumbnails(file_path, thumbnail_dir)
        
        # Analyze exposure
        exposure_data = {}
        if thumbnail_paths:
            exposure_data = analyze_exposure(thumbnail_paths[0])
        
        # Calculate aspect ratio
        aspect_ratio_str = calculate_aspect_ratio_str(metadata.get('width'), metadata.get('height'))
        
        # Create result object
        result = {
            "id": str(uuid.uuid4()),
            "file_path": file_path,
            "file_name": os.path.basename(file_path),
            "file_checksum": checksum,
            "file_size_bytes": file_size,
            "created_at": metadata.get('created_at'),
            "processed_at": datetime.datetime.now().isoformat(),
            "duration_seconds": metadata.get('duration_seconds'),
            "technical_metadata": {
                "codec": metadata.get('codec'),
                "container": metadata.get('container'),
                "resolution_width": metadata.get('width'),
                "resolution_height": metadata.get('height'),
                "aspect_ratio": aspect_ratio_str,
                "frame_rate": metadata.get('frame_rate'),
                "bit_rate_kbps": int(metadata.get('overall_bit_rate') / 1000) if metadata.get('overall_bit_rate') else None,
                "duration_seconds": metadata.get('duration_seconds'),
                "exposure_warning": exposure_data.get('exposure_warning'),
                "exposure_stops": exposure_data.get('exposure_stops'),
                "overexposed_percentage": exposure_data.get('overexposed_percentage'),
                "underexposed_percentage": exposure_data.get('underexposed_percentage'),
                "bit_depth": metadata.get('bit_depth'),
                "color_space": metadata.get('color_space'),
                "camera_make": metadata.get('camera_make'),
                "camera_model": metadata.get('camera_model'),
                "focal_length": metadata.get('focal_length')
            },
            "thumbnail_paths": thumbnail_paths
        }
        
        logger.info("Video processing complete", path=file_path, id=result["id"])
        return result
    
    except Exception as e:
        logger.error("Error processing video file", path=file_path, error=str(e))
        raise

# Task-specific functions below - these will be registered as Procrastinate tasks in task_queue.py

def validate_video_file(file_path: str, job_id: str) -> Dict[str, Any]:
    """
    Validate a video file and generate its checksum.
    Intended to be registered as a task.
    
    Args:
        file_path: Path to the video file
        job_id: Unique identifier for the job
        
    Returns:
        Dict: Validation result including file path and checksum
    """
    print(f"\n\nDEBUG WORKER: Starting validation for {file_path} with job ID {job_id}\n\n")
    logger.info("Starting video file validation", file_path=file_path, job_id=job_id)
    
    try:
        # Check if file exists
        if not os.path.exists(file_path):
            logger.error("File not found", file_path=file_path, job_id=job_id)
            return {"status": "error", "message": f"File not found: {file_path}", "job_id": job_id}
        
        # Get file size
        file_size = os.path.getsize(file_path)
        
        # Calculate checksum
        checksum = calculate_checksum(file_path)
        
        logger.info("Video file validation completed", 
                    file_path=file_path, 
                    file_size=file_size, 
                    checksum=checksum, 
                    job_id=job_id)
        
        # Try to chain the next task directly
        try:
            # Import task_queue here to avoid circular imports
            import video_ingest_tool.task_queue as task_queue
            if task_queue.PROCRASTINATE_AVAILABLE and hasattr(task_queue, 'extract_metadata'):
                task_queue.extract_metadata.defer(
                    file_path=file_path,
                    checksum=checksum,
                    job_id=job_id
                )
                logger.info("Chained to metadata extraction", file_path=file_path, job_id=job_id)
        except Exception as e:
            logger.error("Error chaining to metadata extraction", error=str(e), job_id=job_id)
            # Continue despite chaining error - worker can pick up manually
        
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
        raise

def extract_metadata_task(file_path: str, checksum: str, job_id: str) -> Dict[str, Any]:
    """
    Extract technical metadata from a video file.
    Intended to be registered as a task.
    
    Args:
        file_path: Path to the video file
        checksum: File checksum
        job_id: Unique identifier for the job
        
    Returns:
        Dict: Metadata extraction result
    """
    print(f"\n\nDEBUG WORKER: Starting metadata extraction for {file_path} with job ID {job_id}\n\n")
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
        
        # Try to chain the next task directly
        try:
            # Create thumbnails directory path
            thumbnails_dir = os.path.join(os.path.dirname(os.path.dirname(file_path)), "output", "thumbnails")
            os.makedirs(thumbnails_dir, exist_ok=True)
            
            # Import task_queue here to avoid circular imports
            import video_ingest_tool.task_queue as task_queue
            if task_queue.PROCRASTINATE_AVAILABLE and hasattr(task_queue, 'generate_thumbnails'):
                task_queue.generate_thumbnails.defer(
                    file_path=file_path,
                    thumbnails_dir=os.path.join(thumbnails_dir, checksum),
                    checksum=checksum,
                    metadata=metadata,
                    job_id=job_id
                )
                logger.info("Chained to thumbnail generation", file_path=file_path, job_id=job_id)
        except Exception as e:
            logger.error("Error chaining to thumbnail generation", error=str(e), job_id=job_id)
            # Continue despite chaining error - worker can pick up manually
        
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
        raise

def generate_thumbnails_task(
    file_path: str, 
    thumbnails_dir: str, 
    checksum: str, 
    metadata: Dict[str, Any], 
    job_id: str
) -> Dict[str, Any]:
    """
    Generate thumbnails from a video file.
    Intended to be registered as a task.
    
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
        thumbnail_paths = generate_thumbnails(file_path, thumbnails_dir)
        
        logger.info("Thumbnail generation completed", 
                    file_path=file_path, 
                    count=len(thumbnail_paths), 
                    job_id=job_id)
        
        # Try to chain the next task directly
        try:
            # Import task_queue here to avoid circular imports
            import video_ingest_tool.task_queue as task_queue
            
            if task_queue.PROCRASTINATE_AVAILABLE:
                if thumbnail_paths and hasattr(task_queue, 'analyze_exposure'):
                    # Chain to exposure analysis if we have thumbnails
                    task_queue.analyze_exposure.defer(
                        file_path=file_path,
                        thumbnail_paths=thumbnail_paths,
                        checksum=checksum,
                        metadata=metadata,
                        job_id=job_id
                    )
                    logger.info("Chained to exposure analysis", file_path=file_path, job_id=job_id)
                elif hasattr(task_queue, 'save_results'):
                    # Skip exposure analysis if no thumbnails were generated
                    task_queue.save_results.defer(
                        file_path=file_path,
                        checksum=checksum,
                        metadata=metadata,
                        thumbnail_paths=[],
                        exposure_data={},
                        aspect_ratio_str=metadata.get('aspect_ratio'),
                        job_id=job_id
                    )
                    logger.info("Chained to save results (skipping exposure analysis)", file_path=file_path, job_id=job_id)
        except Exception as e:
            logger.error("Error chaining next task", error=str(e), job_id=job_id)
            # Continue despite chaining error - worker can pick up manually
        
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
        raise

def analyze_exposure_task(
    file_path: str,
    thumbnail_paths: List[str],
    checksum: str,
    metadata: Dict[str, Any],
    job_id: str
) -> Dict[str, Any]:
    """
    Analyze exposure in thumbnails.
    Intended to be registered as a task.
    
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
        exposure_data = {
            "histograms": [],
            "overexposed_percentage": 0.0,
            "underexposed_percentage": 0.0,
            "average_brightness": 0.0
        }
        
        if thumbnail_paths:
            # Analyze first thumbnail
            thumb_analysis = analyze_exposure(thumbnail_paths[0])
            exposure_data.update(thumb_analysis)
        
        logger.info("Exposure analysis completed", 
                    file_path=file_path, 
                    exposure_warning=exposure_data.get('exposure_warning', False), 
                    job_id=job_id)
        
        # Try to chain the next task directly
        try:
            # Import task_queue here to avoid circular imports
            import video_ingest_tool.task_queue as task_queue
            if task_queue.PROCRASTINATE_AVAILABLE and hasattr(task_queue, 'save_results'):
                task_queue.save_results.defer(
                    file_path=file_path,
                    checksum=checksum,
                    metadata=metadata,
                    thumbnail_paths=thumbnail_paths,
                    exposure_data=exposure_data,
                    aspect_ratio_str=metadata.get('aspect_ratio'),
                    job_id=job_id
                )
                logger.info("Chained to save results", file_path=file_path, job_id=job_id)
        except Exception as e:
            logger.error("Error chaining to save results", error=str(e), job_id=job_id)
            # Continue despite chaining error - worker can pick up manually
        
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
        raise

def save_results_task(
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
    Intended to be registered as a task.
    
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
        # Create result object
        video_file_dict = {
            "id": str(uuid.uuid4()),
            "file_path": file_path,
            "file_name": os.path.basename(file_path),
            "file_checksum": checksum,
            "file_size_bytes": metadata.get('file_size_bytes', 0),
            "created_at": metadata.get('created_at'),
            "processed_at": datetime.datetime.now().isoformat(),
            "duration_seconds": metadata.get('duration_seconds'),
            "technical_metadata": {
                "codec": metadata.get('codec'),
                "container": metadata.get('container'),
                "resolution_width": metadata.get('width'),
                "resolution_height": metadata.get('height'),
                "aspect_ratio": aspect_ratio_str,
                "frame_rate": metadata.get('frame_rate'),
                "bit_rate_kbps": int(metadata.get('bit_rate', 0) / 1000) if metadata.get('bit_rate') else None,
                "duration_seconds": metadata.get('duration_seconds'),
                "exposure_warning": exposure_data.get('exposure_warning'),
                "exposure_stops": exposure_data.get('exposure_stops'),
                "overexposed_percentage": exposure_data.get('overexposed_percentage'),
                "underexposed_percentage": exposure_data.get('underexposed_percentage'),
                "bit_depth": metadata.get('bit_depth'),
                "color_space": metadata.get('color_space'),
                "camera_make": metadata.get('camera_make'),
                "camera_model": metadata.get('camera_model'),
                "focal_length": metadata.get('focal_length')
            },
            "thumbnail_paths": thumbnail_paths
        }
        
        # Save to JSON
        json_dir = os.path.join(os.path.dirname(os.path.dirname(file_path)), "json_output")
        os.makedirs(json_dir, exist_ok=True)
        
        json_path = os.path.join(json_dir, f"{video_file_dict['id']}.json")
        
        # Handle datetime objects
        def json_serial(obj):
            """JSON serializer for objects not serializable by default json code"""
            if isinstance(obj, (datetime.datetime, datetime.date)):
                return obj.isoformat()
            raise TypeError(f"Type {type(obj)} not serializable")
        
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
        raise

if __name__ == "__main__":
    print("This module is not meant to be run directly.")
