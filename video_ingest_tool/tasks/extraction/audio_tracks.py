"""
Audio track extraction step for the video ingest pipeline.

Extracts audio track information from video files.
"""

from typing import Any, Dict

from ...pipeline.registry import register_step
from ...extractors.tracks import extract_audio_tracks
from prefect import task

@register_step(
    name="audio_extraction", 
    enabled=True,
    description="Extract audio track information"
)
@task
def extract_audio_step(data: Dict[str, Any], logger=None) -> Dict[str, Any]:
    """
    Extract audio track information.
    
    Args:
        data: Pipeline data containing file_path
        logger: Optional logger
        
    Returns:
        Dict with audio track data
    """
    file_path = data.get('file_path')
    if not file_path:
        raise ValueError("Missing file_path in data")
        
    audio_tracks = extract_audio_tracks(file_path, logger)
    
    return {
        'audio_tracks': audio_tracks
    } 