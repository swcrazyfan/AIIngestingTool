"""
Track extractors for the video ingest tool.

Contains functions for extracting audio and subtitle track information.
"""

import pymediainfo
from typing import Any, Dict, List

def extract_audio_tracks(file_path: str, logger=None) -> List[Dict[str, Any]]:
    """
    Extract audio track information from video files.
    
    Args:
        file_path: Path to the video file
        logger: Logger instance
        
    Returns:
        List[Dict]: List of audio track metadata
    """
    if logger:
        logger.info("Extracting audio tracks", path=file_path)
    
    audio_tracks = []
    
    try:
        media_info = pymediainfo.MediaInfo.parse(file_path)
        
        for track in media_info.tracks:
            if track.track_type == 'Audio':
                audio_track = {
                    'track_id': str(track.track_id) if hasattr(track, 'track_id') and track.track_id is not None else None,
                    'codec': track.format if hasattr(track, 'format') else None,
                    'codec_id': track.codec_id if hasattr(track, 'codec_id') else None,
                    'duration_seconds': float(track.duration) / 1000 if hasattr(track, 'duration') and track.duration else None,
                    'bit_rate_kbps': int(float(str(track.bit_rate).replace('kb/s', '').strip())) if hasattr(track, 'bit_rate') and track.bit_rate else None,
                    'channels': int(track.channel_s) if hasattr(track, 'channel_s') and track.channel_s else None,
                    'channel_layout': track.channel_layout if hasattr(track, 'channel_layout') else None,
                    'sample_rate': int(float(str(track.sampling_rate).replace('Hz', '').strip())) if hasattr(track, 'sampling_rate') and track.sampling_rate else None,
                    'bit_depth': int(track.bit_depth) if hasattr(track, 'bit_depth') and track.bit_depth else None,
                    'language': track.language if hasattr(track, 'language') else None
                }
                
                # Filter out None values
                audio_track = {k: v for k, v in audio_track.items() if v is not None}
                
                audio_tracks.append(audio_track)
        
        if logger:
            logger.info("Audio track extraction successful", path=file_path, track_count=len(audio_tracks))
        
        return audio_tracks
    
    except Exception as e:
        if logger:
            logger.error("Audio track extraction failed", path=file_path, error=str(e))
        return []

def extract_subtitle_tracks(file_path: str, logger=None) -> List[Dict[str, Any]]:
    """
    Extract subtitle track information from video files.
    
    Args:
        file_path: Path to the video file
        logger: Logger instance
        
    Returns:
        List[Dict]: List of subtitle track metadata
    """
    if logger:
        logger.info("Extracting subtitle tracks", path=file_path)
    
    subtitle_tracks = []
    
    try:
        media_info = pymediainfo.MediaInfo.parse(file_path)
        
        for track in media_info.tracks:
            if track.track_type == 'Text':
                subtitle_track = {
                    'track_id': str(track.track_id) if hasattr(track, 'track_id') and track.track_id is not None else None,
                    'format': track.format if hasattr(track, 'format') else None,
                    'codec_id': track.codec_id if hasattr(track, 'codec_id') else None,
                    'language': track.language if hasattr(track, 'language') else None,
                    'embedded': True if hasattr(track, 'muxing_mode') and track.muxing_mode == 'muxed' else None
                }
                
                # Filter out None values
                subtitle_track = {k: v for k, v in subtitle_track.items() if v is not None}
                
                subtitle_tracks.append(subtitle_track)
        
        if logger:
            logger.info("Subtitle track extraction successful", path=file_path, track_count=len(subtitle_tracks))
        
        return subtitle_tracks
    
    except Exception as e:
        if logger:
            logger.error("Subtitle track extraction failed", path=file_path, error=str(e))
        return [] 