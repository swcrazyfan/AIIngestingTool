"""
Metadata extractors for the video ingest tool.

Contains functions for extracting metadata from video files using various tools.
"""

import os
import av
import pymediainfo
import exiftool
from typing import Any, Dict, List, Optional, Tuple, Union

from .config import HAS_TRANSFORMERS, FOCAL_LENGTH_RANGES
from .utils import parse_datetime_string, map_exposure_mode, map_white_balance, categorize_focal_length

def extract_mediainfo(file_path: str, logger=None) -> Dict[str, Any]:
    """
    Extract technical metadata using pymediainfo.
    
    Args:
        file_path: Path to the video file
        logger: Logger instance
        
    Returns:
        Dict: Technical metadata
    """
    if logger:
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
                    if logger:
                        logger.info(f"MediaInfo bit rate (general): {metadata['bit_rate_kbps']} kbps", path=file_path)
                except (ValueError, TypeError):
                    if logger:
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
                        if logger:
                            logger.info(f"MediaInfo bit rate (video): {metadata['bit_rate_kbps']} kbps", path=file_path)
                except (ValueError, TypeError):
                    if logger:
                        logger.warning("Could not parse video track bit rate", path=file_path)
            
            metadata.update({
                'codec': video_track.codec_id or video_track.format,
                'width': video_track.width,
                'height': video_track.height,
                'frame_rate': float(video_track.frame_rate) if video_track.frame_rate else None,
                'bit_depth': video_track.bit_depth,
                'color_space': video_track.color_space
            })
        
        if logger:
            logger.info("MediaInfo extraction successful", path=file_path)
        
        return metadata
    
    except Exception as e:
        if logger:
            logger.error("MediaInfo extraction failed", path=file_path, error=str(e))
        return {}

def extract_ffprobe_info(file_path: str, logger=None) -> Dict[str, Any]:
    """
    Extract technical metadata using PyAV (which uses FFmpeg libraries).
    
    Args:
        file_path: Path to the video file
        logger: Logger instance
        
    Returns:
        Dict: Technical metadata
    """
    if logger:
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
                if logger:
                    logger.info(f"Calculated bit rate: {metadata['bit_rate_kbps']} kbps", path=file_path)
            
            video_streams = [s for s in container.streams.video if s.type == 'video']
            if video_streams:
                video_stream = video_streams[0]
                
                # Try to get bit rate from stream if available
                if hasattr(video_stream, 'bit_rate') and video_stream.bit_rate:
                    metadata['bit_rate_kbps'] = int(video_stream.bit_rate / 1000)
                    if logger:
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
                        if logger:
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
            
            if logger:
                logger.info("PyAV extraction successful", path=file_path)
            
            return metadata
    
    except Exception as e:
        if logger:
            logger.error("PyAV extraction failed", path=file_path, error=str(e))
        return {}
