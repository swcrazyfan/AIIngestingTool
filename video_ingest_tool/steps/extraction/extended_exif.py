"""
Extended EXIF extraction step for the video ingest pipeline.

Extracts extended EXIF metadata using ExifTool.
"""

from typing import Any, Dict

from ...pipeline.registry import register_step
from ...extractors.exif import extract_extended_exif_metadata

@register_step(
    name="extended_exif_extraction", 
    enabled=True,
    description="Extract extended EXIF metadata"
)
def extract_extended_exif_step(data: Dict[str, Any], logger=None) -> Dict[str, Any]:
    """
    Extract extended EXIF metadata.
    
    Args:
        data: Pipeline data containing file_path
        logger: Optional logger
        
    Returns:
        Dict with extended EXIF data
    """
    file_path = data.get('file_path')
    if not file_path:
        raise ValueError("Missing file_path in data")
        
    extended_exif_data = extract_extended_exif_metadata(file_path, logger)
    
    return {
        'extended_exif_data': extended_exif_data
    } 