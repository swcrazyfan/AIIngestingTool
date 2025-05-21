#!/usr/bin/env python3
"""
AI-Powered Video Ingest & Catalog Tool - Alpha Test Implementation

This script implements the initial steps of the video ingestion and cataloging process:
1. Content Discovery Phase - Scan directories for video files and create checksums
2. Technical Metadata Extraction - Extract detailed information about video files

No task queuing or DB is used for this alpha version. All processing steps are 
logged to the terminal and to timestamped log files, and data is saved to JSON.
"""

import os
import sys
import json
import time
import datetime
import hashlib
import uuid
import pathlib
import subprocess
from typing import Any, Dict, List, Optional, Tuple, Union
import mimetypes
import shutil
import glob

# Try to import polyfile, but provide a fallback if not available
try:
    from polyfile.magic import MagicMatcher
    HAS_POLYFILE = True
except ImportError:
    HAS_POLYFILE = False
    print("Warning: 'polyfile' module not found. Falling back to mimetypes for file detection.")
    print("To install: pip install polyfile")

# Try to import transformers for AI-based focal length detection, but provide a fallback if not available
try:
    from transformers import pipeline
    import torch
    HAS_TRANSFORMERS = True
except ImportError:
    HAS_TRANSFORMERS = False
    print("Warning: 'transformers' module not found. AI-based focal length detection will be disabled.")
    print("To enable this feature, install: pip install transformers torch")

import av
import pymediainfo
import typer
import rich
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeRemainingColumn, track
from rich.panel import Panel
from rich.logging import RichHandler
from rich.table import Table
import structlog
import numpy as np
import cv2
from PIL import Image
from pydantic import BaseModel, Field, validator
import exiftool
import logging
from logging import FileHandler
from rich.logging import RichHandler
from dateutil import parser as dateutil_parser
import math

# Initialize console for rich output
console = Console()

def setup_logging():
    """
    Setup logging configurations for both file and console output.
    Returns the logger and timestamp for current run.
    """
    # Get the package directory
    package_dir = os.path.dirname(os.path.abspath(__file__))
    parent_dir = os.path.dirname(package_dir)
    
    # Configure logging
    log_dir = os.path.join(parent_dir, "logs")
    os.makedirs(log_dir, exist_ok=True)
    
    # Create a timestamp for current run
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = os.path.join(log_dir, f"ingestor_{timestamp}.log")
    
    # Ensure JSON output directory exists
    json_dir = os.path.join(parent_dir, "json_output")
    os.makedirs(json_dir, exist_ok=True)
    
    # Configure structlog to integrate with standard logging
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.stdlib.add_logger_name,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="%Y-%m-%d %H:%M:%S.%f", utc=False),
            structlog.processors.StackInfoRenderer(),
            structlog.dev.set_exc_info,
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.make_filtering_bound_logger(min_level=logging.INFO),
        context_class=dict,
        cache_logger_on_first_use=True,
    )
    
    # Configure standard Python logging handlers
    log_format = "%(message)s"
    
    # Console Handler (using Rich for pretty output)
    rich_console_handler = RichHandler(console=console, rich_tracebacks=True, markup=True, show_path=False)
    rich_console_handler.setFormatter(logging.Formatter(log_format))
    rich_console_handler.setLevel(logging.INFO)
    
    # File Handler (plain text)
    file_log_handler = FileHandler(log_file, mode='w', encoding='utf-8')
    file_log_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)-5.5s] [%(name)s] %(message)s"))
    file_log_handler.setLevel(logging.INFO)
    
    # Get the root logger and add handlers
    std_root_logger = logging.getLogger()
    std_root_logger.addHandler(rich_console_handler)
    std_root_logger.addHandler(file_log_handler)
    std_root_logger.setLevel(logging.INFO)
    
    # Create a logger instance using structlog
    logger = structlog.get_logger(__name__)
    logger.info("Logging configured successfully for console and file.")
    
    return logger, timestamp, json_dir, log_file

# Initialize logging
logger, timestamp, json_dir, log_file = setup_logging()

# Focal length category ranges (in mm, for full-frame equivalent)
FOCAL_LENGTH_RANGES = {
    "ULTRA-WIDE": (8, 18),    # Ultra wide-angle: 8-18mm
    "WIDE": (18, 35),         # Wide-angle: 18-35mm
    "MEDIUM": (35, 70),       # Standard/Normal: 35-70mm
    "LONG-LENS": (70, 200),   # Short telephoto: 70-200mm
    "TELEPHOTO": (200, 800)   # Telephoto: 200-800mm
}

def categorize_focal_length(focal_length: Optional[Union[str, int, float]]) -> Optional[str]:
    """
    Categorize a focal length value into a standard category.
    
    Args:
        focal_length: The focal length value (can be string, int, or float)
        
    Returns:
        str: The focal length category (ULTRA-WIDE, WIDE, MEDIUM, LONG-LENS, TELEPHOTO) or None if not determinable
    """
    if focal_length is None:
        return None
    
    try:
        # Convert focal length to float if it's a string or other type
        if isinstance(focal_length, str):
            # Clean up string - remove 'mm' suffix and any spaces
            focal_length = focal_length.lower().replace('mm', '').strip()
        
        focal_mm = float(focal_length)
        
        # Determine category based on range
        for category, (min_val, max_val) in FOCAL_LENGTH_RANGES.items():
            if min_val <= focal_mm <= max_val:
                logger.info(f"Categorized focal length {focal_mm}mm as {category}")
                return category
        
        # Handle extreme values
        if focal_mm < 8:
            logger.info(f"Categorized focal length {focal_mm}mm as ULTRA-WIDE (extreme)")
            return "ULTRA-WIDE"
        elif focal_mm > 800:
            logger.info(f"Categorized focal length {focal_mm}mm as TELEPHOTO (extreme)")
            return "TELEPHOTO"
        
        return None
    except (ValueError, TypeError) as e:
        logger.warning(f"Could not categorize focal length: {focal_length}", error=str(e))
        return None

# Define our data models with Pydantic
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
    focal_length_mm: Optional[float] = None  # Numerical focal length in millimeters
    focal_length_category: Optional[str] = None  # Categorized focal length: ULTRA-WIDE, WIDE, MEDIUM, etc.
    # Deprecated field - kept for backward compatibility but will be removed in future versions
    focal_length: Optional[str] = None  # DEPRECATED

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

# Utility Functions
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

def map_focal_length_to_category(focal_length):
    """
    Map a numeric focal length (in mm) to a category string.
    
    Args:
        focal_length: Numeric focal length in mm, or None
        
    Returns:
        str: Category string like "ULTRA-WIDE", "WIDE", etc. or None if input is None
    """
    if focal_length is None:
        return None
    
    # Convert to float if it's not already
    try:
        focal_length_float = float(focal_length)
    except (ValueError, TypeError):
        return None
    
    # Map focal length ranges to categories (for full-frame equivalent)
    if focal_length_float < 18:
        return "ULTRA-WIDE"
    elif 18 <= focal_length_float < 35:
        return "WIDE"
    elif 35 <= focal_length_float < 70:
        return "MEDIUM"
    elif 70 <= focal_length_float < 200:
        return "LONG-LENS"
    elif focal_length_float >= 200:
        return "TELEPHOTO"
    else:
        return None

def calculate_aspect_ratio_str(width: Optional[int], height: Optional[int]) -> Optional[str]:
    """Calculate aspect ratio as a string (e.g., '16:9')."""
    if not width or not height or width <= 0 or height <= 0:
        return None
    common_divisor = math.gcd(width, height)
    return f"{width // common_divisor}:{height // common_divisor}"

def scan_directory(directory: str, recursive: bool = True) -> List[str]:
    """
    Scan directory for video files.
    
    Args:
        directory: Directory to scan
        recursive: Whether to scan subdirectories
        
    Returns:
        List[str]: List of video file paths
    """
    logger.info("Scanning directory", directory=directory, recursive=recursive)
    video_files = []
    
    with Progress(console=console, transient=True) as progress:
        task = progress.add_task("[cyan]Scanning directory...", total=None)
        
        for root, dirs, files in os.walk(directory):
            progress.update(task, advance=1, description=f"[cyan]Scanning {root}")
            
            for file in files:
                file_path = os.path.join(root, file)
                if is_video_file(file_path):
                    video_files.append(file_path)
                    logger.info("Found video file", path=file_path)
            
            if not recursive:
                dirs.clear()
    
    logger.info("Directory scan complete", video_count=len(video_files))
    return video_files

# Functions for Content Discovery Phase
def is_video_file(file_path: str) -> bool:
    """
    Check if a file is a video file based on MIME type.
    
    Args:
        file_path: Path to the file to check
        
    Returns:
        bool: True if the file is a video, False otherwise
    """
    try:
        # Use polyfile for file type detection if available
        if HAS_POLYFILE:
            with open(file_path, 'rb') as f:
                # Read a small chunk, as PolyFile can work with partial data
                # and some files might be very large.
                file_bytes = f.read(2048) # Read first 2KB for type detection
                for match in MagicMatcher.DEFAULT_INSTANCE.match(file_bytes):
                    for mime_type in match.mimetypes:
                        if mime_type.startswith('video/'):
                            logger.info("File type detected (polyfile)", path=file_path, mime_type=mime_type)
                            return True
        
        # Fallback to mimetypes if polyfile is not available or doesn't find a video
        mime_type, _ = mimetypes.guess_type(file_path)
        if mime_type and mime_type.startswith('video/'):
            logger.info("File type detected (mimetypes)", path=file_path, mime_type=mime_type)
            return True
            
        # Additional fallback: check extensions
        file_ext = os.path.splitext(file_path.lower())[1]
        video_extensions = ['.mp4', '.mov', '.avi', '.wmv', '.flv', '.mkv', '.webm', '.m4v', '.mpg', '.mpeg']
        if file_ext in video_extensions:
            logger.info("File type detected (extension)", path=file_path, extension=file_ext)
            return True
            
        return False
    except Exception as e:
        logger.error("Error detecting file type", path=file_path, error=str(e))
        # Ultimate fallback to mimetypes if everything else errors out
        try:
            mime_type, _ = mimetypes.guess_type(file_path)
            return bool(mime_type and mime_type.startswith('video/'))
        except:
            return False

# Functions for Technical Metadata Extraction
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

def detect_focal_length_with_ai(image_path: str) -> Tuple[Optional[str], Optional[float]]:
    """
    Use AI to detect the focal length category from an image when EXIF data is not available.
    
    Args:
        image_path: Path to the image file
        
    Returns:
        Tuple[Optional[str], Optional[float]]: Focal length category and approximate value in mm
    """
    if not HAS_TRANSFORMERS:
        logger.warning("AI-based focal length detection requested but transformers library is not available", 
                     path=image_path)
        return None, None
    
    try:
        logger.info("Using AI to detect focal length", path=image_path)
        
        # Device selection logic - prioritize MPS, then CUDA, then CPU
        if hasattr(torch, 'backends') and hasattr(torch.backends, 'mps') and torch.backends.mps.is_available():
            device = "mps"
        elif torch.cuda.is_available():
            device = "cuda"
        else:
            device = "cpu"
        
        logger.info(f"Using device for AI model: {device}")
        
        # Create a pipeline using the Hugging Face model
        pipe = pipeline("image-classification", model="tonyassi/camera-lens-focal-length", device=device)
        
        # Load the image
        pil_image = Image.open(image_path)
        
        # Run the model to estimate focal length category
        prediction_result = pipe(pil_image)
        
        # Extract the top prediction
        if prediction_result and len(prediction_result) > 0:
            top_prediction = prediction_result[0]
            category = top_prediction["label"]
            confidence = top_prediction["score"]
            
            # Get approximate focal length (midpoint of the range)
            min_val, max_val = FOCAL_LENGTH_RANGES[category]
            approx_focal_length = (min_val + max_val) / 2
            
            logger.info(f"AI detected focal length category: {category} (confidence: {confidence:.4f})",
                      path=image_path, category=category, confidence=confidence)
            logger.info(f"Approximate focal length: {approx_focal_length}mm", 
                      path=image_path, focal_length=approx_focal_length)
            
            return category, approx_focal_length
        else:
            logger.warning("AI model did not return predictions for focal length", path=image_path)
            return None, None
            
    except Exception as e:
        logger.error("Error using AI to detect focal length", path=image_path, error=str(e))
        return None, None

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
            # Extract bit rate information from general track if available
            if hasattr(general_track, 'overall_bit_rate') and general_track.overall_bit_rate:
                try:
                    # Convert to int and handle different formats (sometimes includes 'kb/s')
                    bit_rate_str = str(general_track.overall_bit_rate).lower().replace('kb/s', '').strip()
                    metadata['bit_rate_kbps'] = int(float(bit_rate_str))
                    logger.info(f"MediaInfo bit rate (general): {metadata['bit_rate_kbps']} kbps", path=file_path)
                except (ValueError, TypeError):
                    logger.warning("Could not parse general track bit rate", path=file_path)
            
            metadata.update({
                'container': general_track.format,
                'duration_seconds': float(general_track.duration) / 1000 if general_track.duration else None,
                'file_size_bytes': general_track.file_size,
                'created_at': parse_datetime_string(general_track.encoded_date)
            })
        
        if video_track:
            # Extract bit rate information from video track if available
            if hasattr(video_track, 'bit_rate') and video_track.bit_rate:
                try:
                    # Convert to int and handle different formats
                    bit_rate_str = str(video_track.bit_rate).lower().replace('kb/s', '').strip()
                    video_bit_rate = int(float(bit_rate_str))
                    # Only update if not already set or if video track bit rate is more specific
                    if 'bit_rate_kbps' not in metadata or video_bit_rate > 0:
                        metadata['bit_rate_kbps'] = video_bit_rate
                        logger.info(f"MediaInfo bit rate (video): {metadata['bit_rate_kbps']} kbps", path=file_path)
                except (ValueError, TypeError):
                    logger.warning("Could not parse video track bit rate", path=file_path)
            
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
            
            # Get file size
            file_size = os.path.getsize(file_path)
            
            metadata = {
                'duration_seconds': duration_seconds,
                'file_size_bytes': file_size
            }
            
            # Calculate bit rate if duration is available
            if duration_seconds and duration_seconds > 0:
                # Calculate bit rate in bits per second
                bit_rate = (file_size * 8) / duration_seconds
                # Convert to kbps
                metadata['bit_rate_kbps'] = int(bit_rate / 1000)
                logger.info(f"Calculated bit rate: {metadata['bit_rate_kbps']} kbps", path=file_path)
            
            video_streams = [s for s in container.streams.video if s.type == 'video']
            if video_streams:
                video_stream = video_streams[0]
                
                # Try to get bit rate from stream if available
                if hasattr(video_stream, 'bit_rate') and video_stream.bit_rate:
                    metadata['bit_rate_kbps'] = int(video_stream.bit_rate / 1000)
                    logger.info(f"Stream bit rate: {metadata['bit_rate_kbps']} kbps", path=file_path)
                
                codec_ctx = getattr(video_stream, 'codec_context', None)
                codec_name_val = 'unknown'
                if codec_ctx:
                    codec_name_val = getattr(codec_ctx, 'name', None)
                    if not codec_name_val:
                        codec_name_val = getattr(codec_ctx, 'long_name', 'unknown')
                    
                    # Try to get bit rate from codec context if available
                    if hasattr(codec_ctx, 'bit_rate') and codec_ctx.bit_rate:
                        metadata['bit_rate_kbps'] = int(codec_ctx.bit_rate / 1000)
                        logger.info(f"Codec bit rate: {metadata['bit_rate_kbps']} kbps", path=file_path)

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
            
            # Get the raw focal length
            focal_length_raw = metadata.get('EXIF:FocalLength')
            
            # Map numeric focal length to categories using the utility function
            focal_length_category = None
            if focal_length_raw is not None:
                focal_length_category = categorize_focal_length(focal_length_raw)
            
            exif_data = {
                'camera_make': metadata.get('EXIF:Make'),
                'camera_model': metadata.get('EXIF:Model'),
                'focal_length_mm': focal_length_raw if isinstance(focal_length_raw, (int, float)) else None,
                'focal_length_category': focal_length_category,
                # Keep focal_length for backward compatibility
                'focal_length': focal_length_category,
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


def process_video_file(file_path: str, thumbnails_dir: str) -> VideoFile:
    """
    Process a video file to extract metadata and generate thumbnails.
    
    Args:
        file_path: Path to the video file
        thumbnails_dir: Directory to save thumbnails
        
    Returns:
        VideoFile: Processed video file object
    """
    logger.info("Processing video file", path=file_path)
    
    checksum = calculate_checksum(file_path)
    
    file_size = os.path.getsize(file_path)
    
    mediainfo_data = extract_mediainfo(file_path)
    ffprobe_data = extract_ffprobe_info(file_path)
    exiftool_data = extract_exiftool_info(file_path)
    
    metadata = {**exiftool_data, **ffprobe_data, **mediainfo_data}
    
    thumbnail_dir = os.path.join(thumbnails_dir, checksum)
    thumbnail_paths = generate_thumbnails(file_path, thumbnail_dir)
    
    exposure_data = {}
    if thumbnail_paths:
        exposure_data = analyze_exposure(thumbnail_paths[0])
    
    # Check if focal length data is missing from EXIF and try AI-based detection
    if not metadata.get('focal_length_category') and not metadata.get('focal_length_mm') and thumbnail_paths:
        logger.info("Focal length not found in EXIF data, attempting AI-based detection", path=file_path)
        category, approx_value = detect_focal_length_with_ai(thumbnail_paths[0])
        
        if category and approx_value:
            # Update metadata with AI-detected values
            metadata['focal_length_category'] = category
            metadata['focal_length_mm'] = approx_value
            metadata['focal_length'] = category  # For backward compatibility
            metadata['focal_length_source'] = 'AI'  # Mark the source as AI for reference
            logger.info("Successfully detected focal length using AI", 
                      path=file_path, category=category, value=approx_value)
    
    aspect_ratio_str = calculate_aspect_ratio_str(metadata.get('width'), metadata.get('height'))
    
    technical_metadata = TechnicalMetadata(
        codec=metadata.get('codec'),
        container=metadata.get('container'),
        resolution_width=metadata.get('width'),
        resolution_height=metadata.get('height'),
        aspect_ratio=aspect_ratio_str,
        frame_rate=metadata.get('frame_rate'),
        bit_rate_kbps=metadata.get('bit_rate_kbps'),  # Directly use the bit_rate_kbps that was already calculated
        duration_seconds=metadata.get('duration_seconds'),
        exposure_warning=exposure_data.get('exposure_warning'),
        exposure_stops=exposure_data.get('exposure_stops'),
        overexposed_percentage=exposure_data.get('overexposed_percentage'),
        underexposed_percentage=exposure_data.get('underexposed_percentage'),
        bit_depth=metadata.get('bit_depth'),
        color_space=metadata.get('color_space'),
        camera_make=metadata.get('camera_make'),
        camera_model=metadata.get('camera_model'),
        focal_length_mm=metadata.get('focal_length_mm'),
        focal_length_category=metadata.get('focal_length_category'),
        # Keep this for backward compatibility
        focal_length=metadata.get('focal_length')
    )
    
    video_file = VideoFile(
        file_path=file_path,
        file_name=os.path.basename(file_path),
        file_checksum=checksum,
        file_size_bytes=file_size,
        created_at=metadata.get('created_at'),
        duration_seconds=metadata.get('duration_seconds'),
        technical_metadata=technical_metadata,
        thumbnail_paths=thumbnail_paths
    )
    
    logger.info("Video processing complete", path=file_path, id=video_file.id)
    return video_file
    
    video_file = VideoFile(
        file_path=file_path,
        file_name=os.path.basename(file_path),
        file_checksum=checksum,
        file_size_bytes=file_size,
        created_at=metadata.get('created_at'),
        duration_seconds=metadata.get('duration_seconds'),
        technical_metadata=technical_metadata,
        thumbnail_paths=thumbnail_paths
    )
    
    logger.info("Video processing complete", path=file_path, id=video_file.id)
    return video_file

def save_to_json(data: Any, filename: str) -> None:
    """
    Save data to JSON file.
    
    Args:
        data: Data to save
        filename: Output filename
    """
    logger.info("Saving data to JSON", filename=filename)
    if isinstance(data, BaseModel):
        data = data.model_dump()
    elif isinstance(data, list) and all(isinstance(item, BaseModel) for item in data):
        data = [item.model_dump() for item in data]
    
    with open(filename, 'w') as f:
        json.dump(data, f, indent=2, default=str)
    
    logger.info("Data saved to JSON", filename=filename)

# CLI Application
app = typer.Typer(help="AI-Powered Video Ingest & Catalog Tool - Alpha Test")

@app.command()
def ingest(
    directory: str = typer.Argument(..., help="Directory to scan for video files"),
    recursive: bool = typer.Option(True, "--recursive/--no-recursive", "-r/-nr", help="Scan subdirectories"),
    output_dir: str = typer.Option("output", "--output-dir", "-o", help="Output directory for thumbnails and JSON"),
    limit: int = typer.Option(0, "--limit", "-l", help="Limit number of files to process (0 = no limit)")
):
    """
    Scan a directory for video files and extract metadata.
    """
    start_time = time.time()
    
    # Create a timestamped run directory
    run_timestamp = timestamp  # Use the timestamp created during setup_logging
    run_dir = os.path.join(output_dir, f"run_{run_timestamp}")
    os.makedirs(run_dir, exist_ok=True)
    
    # Create subdirectories for this run
    thumbnails_dir = os.path.join(run_dir, "thumbnails")
    os.makedirs(thumbnails_dir, exist_ok=True)
    
    # Create a run-specific JSON directory
    run_json_dir = os.path.join(run_dir, "json")
    os.makedirs(run_json_dir, exist_ok=True)
    
    logger.info("Starting ingestion process", 
                directory=directory, 
                recursive=recursive,
                output_dir=run_dir,
                limit=limit)
    
    console.print(Panel.fit(
        "[bold blue]AI-Powered Video Ingest & Catalog Tool[/bold blue]\n"
        f"[cyan]Directory:[/cyan] {directory}\n"
        f"[cyan]Recursive:[/cyan] {recursive}\n"
        f"[cyan]Output Directory:[/cyan] {run_dir}\n"
        f"[cyan]File Limit:[/cyan] {limit if limit > 0 else 'No limit'}\n"
        f"[cyan]Log File:[/cyan] {log_file}",
        title="Alpha Test",
        border_style="green"
    ))
    
    console.print(f"[bold yellow]Step 1:[/bold yellow] Scanning directory for video files...")
    video_files = scan_directory(directory, recursive)
    
    if limit > 0 and len(video_files) > limit:
        video_files = video_files[:limit]
        logger.info("Applied file limit", limit=limit)
    
    console.print(f"[green]Found {len(video_files)} video files[/green]")
    
    console.print(f"[bold yellow]Step 2:[/bold yellow] Processing video files...")
    processed_files = []
    failed_files = []
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        TimeRemainingColumn(),
        console=console,  
        transient=True    
    ) as progress:
        task = progress.add_task("[green]Processing videos...", total=len(video_files))
        
        for file_path in video_files:
            progress.update(task, advance=0, description=f"[cyan]Processing {os.path.basename(file_path)}")
            
            try:
                video_file = process_video_file(file_path, thumbnails_dir)
                processed_files.append(video_file)
                
                # Save individual JSON to run-specific directory
                individual_json_path = os.path.join(run_json_dir, f"{video_file.id}.json")
                save_to_json(video_file, individual_json_path)
                
                # Also save a copy to the global JSON directory for backward compatibility
                global_json_path = os.path.join(json_dir, f"{video_file.id}.json")
                save_to_json(video_file, global_json_path)
                
            except Exception as e:
                failed_files.append(file_path)
                logger.error("Error processing video file", path=file_path, error=str(e))
            
            progress.update(task, advance=1)
    
    # Save summary JSON to run-specific directory
    run_summary_path = os.path.join(run_json_dir, f"all_videos.json")
    save_to_json(processed_files, run_summary_path)
    
    # Also save to global JSON directory with timestamp for backward compatibility
    global_summary_path = os.path.join(json_dir, f"all_videos_{run_timestamp}.json")
    save_to_json(processed_files, global_summary_path)
    
    # Create a copy of the log file in the run directory
    run_log_file = os.path.join(run_dir, f"ingestor.log")
    try:
        shutil.copy2(log_file, run_log_file)
        logger.info("Copied log file to run directory", source=log_file, destination=run_log_file)
    except Exception as e:
        logger.error("Failed to copy log file to run directory", error=str(e))
    
    # Check if we had failed files and warn the user
    if failed_files:
        console.print(f"[bold red]Warning:[/bold red] Failed to process {len(failed_files)} file(s):", style="red")
        for f in failed_files:
            console.print(f"  - {f}", style="red")
    
    end_time = time.time()
    processing_time = end_time - start_time
    
    summary_table = Table(title="Processing Summary")
    summary_table.add_column("Metric", style="cyan")
    summary_table.add_column("Value", style="green")
    
    summary_table.add_row("Total files processed", str(len(processed_files)))
    if failed_files:
        summary_table.add_row("Failed files", str(len(failed_files)))
    summary_table.add_row("Processing time", f"{processing_time:.2f} seconds")
    summary_table.add_row("Average time per file", f"{processing_time / len(processed_files):.2f} seconds" if processed_files else "N/A")
    summary_table.add_row("Run directory", run_dir)
    summary_table.add_row("Summary JSON", run_summary_path)
    summary_table.add_row("Log file", run_log_file)
    
    console.print(summary_table)
    
    logger.info("Ingestion process completed", 
                files_processed=len(processed_files),
                failed_files=len(failed_files),
                processing_time=processing_time,
                run_directory=run_dir)
