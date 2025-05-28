"""
ExifTool extraction step for the video ingest pipeline.

Extracts basic EXIF metadata using ExifTool.
"""

from typing import Any, Dict

from ...pipeline.registry import register_step
from ...extractors.exif import extract_exiftool_info
from prefect import task

@register_step(
    name="exiftool_extraction", 
    enabled=True,
    description="Extract EXIF metadata"
)
@task
def extract_exiftool_step(data: Dict[str, Any], logger=None) -> Dict[str, Any]:
    """
    Extract metadata using ExifTool.
    
    Args:
        data: Pipeline data containing file_path
        logger: Optional logger
        
    Returns:
        Dict with exiftool data
    """
    file_path = data.get('file_path')
    if not file_path:
        raise ValueError("Missing file_path in data")
        
    exiftool_data = extract_exiftool_info(file_path, logger)
    
    return {
        'exiftool_data': exiftool_data
    } 