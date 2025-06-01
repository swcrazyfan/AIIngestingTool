"""
Focal length detection step for the video ingest pipeline.

Detects focal length using AI when EXIF data is not available.
"""

from typing import Any, Dict
from ...processors import detect_focal_length_with_ai
from ...config.constants import FOCAL_LENGTH_RANGES, HAS_TRANSFORMERS
from prefect import task

@task
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
    
    # Debug logging to understand the data structure
    if logger:
        logger.debug(f"thumbnail_paths type: {type(thumbnail_paths)}")
        logger.debug(f"thumbnail_paths content: {thumbnail_paths}")
    
    # Handle case where thumbnail_paths might be a dictionary instead of a list
    if isinstance(thumbnail_paths, dict):
        if logger:
            logger.warning("thumbnail_paths is a dictionary, extracting list from 'thumbnail_paths' key")
        thumbnail_paths = thumbnail_paths.get('thumbnail_paths', [])
    
    # Ensure we have a list
    if not isinstance(thumbnail_paths, list):
        if logger:
            logger.error(f"thumbnail_paths is not a list: {type(thumbnail_paths)}")
        return {'focal_length_source': None}
    
    if not thumbnail_paths:
        if logger:
            logger.warning("No thumbnails available for focal length detection")
        return {'focal_length_source': None}
    
    if logger:
        logger.info("Focal length not found, attempting AI detection.")
    
    # Use only the first thumbnail for AI detection
    try:
        first_thumbnail = thumbnail_paths[0]
        category = detect_focal_length_with_ai(
            first_thumbnail, FOCAL_LENGTH_RANGES, HAS_TRANSFORMERS, logger
        )
        if category:
            return {
                'focal_length_source': 'AI',
                'focal_length_category': category
            }
        else:
            if logger:
                logger.error("AI focal length detection failed for first thumbnail.")
            return {'focal_length_source': None}
    except (IndexError, KeyError) as e:
        if logger:
            logger.error(f"Error accessing first thumbnail: {e}")
            logger.error(f"thumbnail_paths: {thumbnail_paths}")
        return {'focal_length_source': None} 