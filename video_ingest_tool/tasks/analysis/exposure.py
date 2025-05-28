"""
Exposure analysis step for the video ingest pipeline.

Analyzes exposure in thumbnails.
"""

from typing import Any, Dict
from ...processors import analyze_exposure
from prefect import task

@task
def analyze_exposure_step(data: Dict[str, Any], logger=None) -> Dict[str, Any]:
    """
    Analyze exposure in thumbnails.
    
    Args:
        data: Pipeline data containing thumbnail_paths
        logger: Optional logger
        
    Returns:
        Dict with exposure analysis results
    """
    thumbnail_paths = data.get('thumbnail_paths', [])
    
    if not thumbnail_paths:
        if logger:
            logger.warning("No thumbnails available for exposure analysis")
        return {
            'exposure_data': {}
        }
        
    exposure_data = analyze_exposure(thumbnail_paths[0], logger)
    
    return {
        'exposure_data': exposure_data
    } 