"""
MediaInfo extraction step for the video ingest tool.

Extracts metadata using MediaInfo library.
"""

from typing import Any, Dict
from ...extractors.media import extract_mediainfo
from prefect import task

@task
def extract_mediainfo_step(data: Dict[str, Any], logger=None) -> Dict[str, Any]:
    """
    Extract metadata using MediaInfo.
    
    Args:
        data: Pipeline data containing file_path
        logger: Optional logger
        
    Returns:
        Dict with mediainfo data
    """
    file_path = data.get('file_path')
    if not file_path:
        raise ValueError("Missing file_path in data")
        
    mediainfo_data = extract_mediainfo(file_path, logger)
    
    return {
        'mediainfo_data': mediainfo_data
    } 