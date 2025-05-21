#!/usr/bin/env python3
"""
Video Processor Module

This module contains the core video processing functions that will be registered as tasks.
Separating these functions from task_queue.py solves circular dependency issues and allows
for better code organization.
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
import structlog

# Import necessary libraries
try:
    import av
    import pymediainfo
    import exiftool
    import cv2
    from PIL import Image
    from dateutil import parser as dateutil_parser
except ImportError as e:
    print(f"Error importing required library: {e}")
    sys.exit(1)

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
        raise

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
        raise

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
                'camera