"""
Subtitle track extraction step for the video ingest pipeline.

Extracts subtitle track information from video files.
"""

from typing import Any, Dict
from ...extractors.tracks import extract_subtitle_tracks
from prefect import task

@task
def extract_subtitle_step(data: Dict[str, Any], logger=None) -> Dict[str, Any]:
    """
    Extract subtitle track information.
    
    Args:
        data: Pipeline data containing file_path
        logger: Optional logger
        
    Returns:
        Dict with subtitle track data
    """
    file_path = data.get('file_path')
    if not file_path:
        raise ValueError("Missing file_path in data")
        
    subtitle_tracks = extract_subtitle_tracks(file_path, logger)
    
    return {
        'subtitle_tracks': subtitle_tracks
    } 