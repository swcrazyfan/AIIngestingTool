"""
Thumbnail generation step for the video ingest pipeline.

Generates thumbnails from a video file.
"""

import os
from typing import Any, Dict, Optional
from ...processors import generate_thumbnails
from prefect import task

@task
def generate_thumbnails_step(
    data: Dict[str, Any], 
    data_base_dir: Optional[str] = None,  # Base data directory (e.g., /path/to/data)
    logger=None
) -> Dict[str, Any]:
    """
    Generate thumbnails for a video file.
    
    Args:
        data: Pipeline data containing file_path, checksum, clip_id, and file_name
        data_base_dir: Base data directory for organized output structure
        logger: Optional logger
        
    Returns:
        Dict with thumbnail paths
    """
    file_path = data.get('file_path')
    checksum = data.get('checksum')
    clip_id = data.get('clip_id')
    file_name = data.get('file_name', os.path.basename(file_path) if file_path else 'unknown')
    
    if not file_path or not checksum:
        raise ValueError("Missing file_path or checksum in data")
        
    if not data_base_dir:
        raise ValueError("Missing data_base_dir parameter")
    
    # Determine output directory structure: data/clips/{filename}_{clip_id}/thumbnails/
    if clip_id:
        # New organized structure
        base_filename = os.path.splitext(file_name)[0]
        clip_dir_name = f"{base_filename}_{clip_id}"
        clip_base_dir = os.path.join(data_base_dir, "clips", clip_dir_name)
        thumbnail_dir_for_file = os.path.join(clip_base_dir, "thumbnails")
    else:
        # Fallback to data/thumbnails if no clip_id
        thumbnail_dir_for_file = os.path.join(data_base_dir, "thumbnails", checksum)
    
    thumbnail_paths = generate_thumbnails(file_path, thumbnail_dir_for_file, logger=logger)
    
    return {
        'thumbnail_paths': thumbnail_paths
    } 