"""
FFprobe extraction step for the video ingest pipeline.

Extracts metadata using FFprobe/PyAV library.
"""

from typing import Any, Dict

from ...pipeline.registry import register_step
from ...extractors.media import extract_ffprobe_info

@register_step(
    name="ffprobe_extraction", 
    enabled=True,
    description="Extract metadata using FFprobe/PyAV"
)
def extract_ffprobe_step(data: Dict[str, Any], logger=None) -> Dict[str, Any]:
    """
    Extract metadata using FFprobe/PyAV.
    
    Args:
        data: Pipeline data containing file_path
        logger: Optional logger
        
    Returns:
        Dict with ffprobe data
    """
    file_path = data.get('file_path')
    if not file_path:
        raise ValueError("Missing file_path in data")
        
    ffprobe_data = extract_ffprobe_info(file_path, logger)
    
    return {
        'ffprobe_data': ffprobe_data
    } 