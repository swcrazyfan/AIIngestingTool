"""
Focal length detection step for the video ingest pipeline.

Detects focal length using AI when EXIF data is not available.
"""

from typing import Any, Dict

from ...pipeline.registry import register_step
from ...processors import detect_focal_length_with_ai
from ...config.constants import FOCAL_LENGTH_RANGES, HAS_TRANSFORMERS

@register_step(
    name="ai_focal_length", 
    enabled=True,
    description="Detect focal length using AI when EXIF data is not available"
)
def detect_focal_length_step(data: Dict[str, Any], logger=None) -> Dict[str, Any]:
    """
    Detect focal length using AI when EXIF data is not available.
    
    Args:
        data: Pipeline data containing thumbnail_paths and metadata
        logger: Optional logger
        
    Returns:
        Dict with focal length data
    """
    # Check if we already have focal length information
    exiftool_data = data.get('exiftool_data', {})
    extended_exif_data = data.get('extended_exif_data', {})
    
    # Check if we have valid focal length data from EXIF (not None/null)
    has_exif_focal_length = (
        exiftool_data.get('focal_length_mm') is not None or
        exiftool_data.get('focal_length_category') is not None or
        extended_exif_data.get('focal_length_mm') is not None or
        extended_exif_data.get('focal_length_category') is not None
    )
    
    if has_exif_focal_length:
        if logger:
            logger.info("Valid focal length available from EXIF, skipping AI detection")
        return {
            'focal_length_source': 'EXIF'
        }
    
    thumbnail_paths = data.get('thumbnail_paths', [])
    
    if not thumbnail_paths:
        if logger:
            logger.warning("No thumbnails available for focal length detection")
        return {
            'focal_length_source': None  # Source is unknown if no thumbnails and no EXIF
        }
    
    if logger:
        logger.info("Focal length not found, attempting AI detection.")
        
    category = detect_focal_length_with_ai(
        thumbnail_paths[0],
        FOCAL_LENGTH_RANGES,
        has_transformers=HAS_TRANSFORMERS,
        logger=logger
    )
    
    if category:
        if logger:
            logger.info(f"AI detected focal length category: {category}")
        return {
            'focal_length_category': category,    # The AI-detected category
            'focal_length_mm': None,              # AI never provides mm value
            'focal_length_source': 'AI'           # Mark as AI-sourced
        }
    
    if logger:
        logger.warning("AI detection failed to determine focal length")
    return {
        'focal_length_category': None,
        'focal_length_mm': None,
        'focal_length_source': None
    } 