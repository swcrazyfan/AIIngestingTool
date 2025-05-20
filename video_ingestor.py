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
from polyfile.magic import MagicMatcher

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

# Configure logging
log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
os.makedirs(log_dir, exist_ok=True)

# Create a timestamp for current run
timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
log_file = os.path.join(log_dir, f"ingestor_{timestamp}.log")
json_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "json_output")
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
    quality_score: Optional[float] = None
    overexposed_percentage: Optional[float] = None
    underexposed_percentage: Optional[float] = None
    bit_depth: Optional[int] = None
    color_space: Optional[str] = None
    camera_make: Optional[str] = None
    camera_model: Optional[str] = None
    focal_length: Optional[str] = None

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

def calculate_aspect_ratio_str(width: Optional[int], height: Optional[int]) -> Optional[str]:
    """Calculate aspect ratio as a string (e.g., '16:9')."""
    if not width or not height or width <= 0 or height <= 0:
        return None
    common_divisor = math.gcd(width, height)
    return f"{width // common_divisor}:{height // common_divisor}"

def calculate_checksum(file_path: str) -> str:
    """
    Calculate MD5 checksum of a file.
    
    Args:
        file_path: Path to the file
        
    Returns:
        str: Hex digest of MD5 checksum
    """
    logger.info("Calculating checksum", path=file_path)
    hash_md5 = hashlib.md5()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_md5.update(chunk)
    checksum = hash_md5.hexdigest()
    logger.info("Checksum calculated", path=file_path, checksum=checksum)
    return checksum

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
        # Use polyfile for file type detection
        with open(file_path, 'rb') as f:
            # Read a small chunk, as PolyFile can work with partial data
            # and some files might be very large.
            file_bytes = f.read(2048) # Read first 2KB for type detection
            for match in MagicMatcher.DEFAULT_INSTANCE.match(file_bytes):
                for mime_type in match.mimetypes:
                    if mime_type.startswith('video/'):
                        logger.info("File type detected (polyfile)", path=file_path, mime_type=mime_type)
                        return True
        # Fallback if polyfile doesn't find a video MIME type
        mime_type, _ = mimetypes.guess_type(file_path)
        if mime_type and mime_type.startswith('video/'):
            logger.info("File type detected (mimetypes)", path=file_path, mime_type=mime_type)
            return True
        return False
    except Exception as e:
        logger.error("Error detecting file type", path=file_path, error=str(e))
        # Ultimate fallback to mimetypes if PolyFile errors out
        mime_type, _ = mimetypes.guess_type(file_path)
        return bool(mime_type and mime_type.startswith('video/'))

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

# Functions for Technical Metadata Extraction
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

def analyze_exposure(thumbnail_path: str) -> Dict[str, float]:
    """
    Analyze exposure in an image.
    
    Args:
        thumbnail_path: Path to the thumbnail image
        
    Returns:
        Dict: Exposure analysis results
    """
    logger.info("Analyzing exposure", path=thumbnail_path)
    try:
        image = cv2.imread(thumbnail_path)
        
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        
        hist = cv2.calcHist([gray], [0], None, [256], [0, 256])
        hist = hist.flatten() / (gray.shape[0] * gray.shape[1])
        
        overexposed = sum(hist[240:])
        underexposed = sum(hist[:16])
        
        result = {
            'overexposed_percentage': float(overexposed * 100),
            'underexposed_percentage': float(underexposed * 100)
        }
        
        logger.info("Exposure analysis complete", path=thumbnail_path, result=result)
        return result
    
    except Exception as e:
        logger.error("Exposure analysis failed", path=thumbnail_path, error=str(e))
        return {
            'overexposed_percentage': 0.0,
            'underexposed_percentage': 0.0
        }

def estimate_quality_score(metadata: Dict[str, Any], exposure_data: Dict[str, float]) -> float:
    """
    Estimate video quality score based on technical parameters.
    
    Args:
        metadata: Technical metadata
        exposure_data: Exposure analysis results
        
    Returns:
        float: Quality score (0-10)
    """
    score = 5.0
    
    width = metadata.get('width', 0)
    height = metadata.get('height', 0)
    if width and height:
        resolution = width * height
        if resolution >= 1920 * 1080:
            score += 2.0
        elif resolution >= 1280 * 720:
            score += 1.0
        else:
            score -= 1.0
    
    frame_rate = metadata.get('frame_rate', 0)
    if frame_rate >= 30:
        score += 1.0
    elif frame_rate >= 24:
        score += 0.5
    
    overexposed = exposure_data.get('overexposed_percentage', 0)
    underexposed = exposure_data.get('underexposed_percentage', 0)
    if overexposed > 10 or underexposed > 10:
        score -= 1.5
    elif overexposed > 5 or underexposed > 5:
        score -= 0.5
    
    return max(0.0, min(10.0, score))

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
    
    aspect_ratio_str = calculate_aspect_ratio_str(metadata.get('width'), metadata.get('height'))
    
    quality_score = estimate_quality_score(metadata, exposure_data)
    
    technical_metadata = TechnicalMetadata(
        codec=metadata.get('codec'),
        container=metadata.get('container'),
        resolution_width=metadata.get('width'),
        resolution_height=metadata.get('height'),
        aspect_ratio=aspect_ratio_str,
        frame_rate=metadata.get('frame_rate'),
        bit_rate_kbps=int(metadata.get('overall_bit_rate') / 1000) if metadata.get('overall_bit_rate') else None,
        duration_seconds=metadata.get('duration_seconds'),
        quality_score=quality_score,
        overexposed_percentage=exposure_data.get('overexposed_percentage'),
        underexposed_percentage=exposure_data.get('underexposed_percentage'),
        bit_depth=metadata.get('bit_depth'),
        color_space=metadata.get('color_space'),
        camera_make=metadata.get('camera_make'),
        camera_model=metadata.get('camera_model'),
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
    
    logger.info("Starting ingestion process", 
                directory=directory, 
                recursive=recursive,
                output_dir=output_dir,
                limit=limit)
    
    os.makedirs(output_dir, exist_ok=True)
    thumbnails_dir = os.path.join(output_dir, "thumbnails")
    os.makedirs(thumbnails_dir, exist_ok=True)
    
    console.print(Panel.fit(
        "[bold blue]AI-Powered Video Ingest & Catalog Tool[/bold blue]\n"
        f"[cyan]Directory:[/cyan] {directory}\n"
        f"[cyan]Recursive:[/cyan] {recursive}\n"
        f"[cyan]Output Directory:[/cyan] {output_dir}\n"
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
                
                individual_json_path = os.path.join(json_dir, f"{video_file.id}.json")
                save_to_json(video_file, individual_json_path)
                
            except Exception as e:
                logger.error("Error processing video file", path=file_path, error=str(e))
            
            progress.update(task, advance=1)
    
    all_data_json_path = os.path.join(json_dir, f"all_videos_{timestamp}.json")
    save_to_json(processed_files, all_data_json_path)
    
    end_time = time.time()
    processing_time = end_time - start_time
    
    summary_table = Table(title="Processing Summary")
    summary_table.add_column("Metric", style="cyan")
    summary_table.add_column("Value", style="green")
    
    summary_table.add_row("Total files processed", str(len(processed_files)))
    summary_table.add_row("Processing time", f"{processing_time:.2f} seconds")
    summary_table.add_row("Average time per file", f"{processing_time / len(processed_files):.2f} seconds" if processed_files else "N/A")
    summary_table.add_row("Summary JSON", all_data_json_path)
    summary_table.add_row("Log file", log_file)
    
    console.print(summary_table)
    
    logger.info("Ingestion process completed", 
                files_processed=len(processed_files),
                processing_time=processing_time)

if __name__ == "__main__":
    app()
