"""
Thumbnail generation step for the video ingest pipeline.

Generates thumbnails from a video file.
"""

import os
from typing import Any, Dict
from ...processors import generate_thumbnails
from prefect import task

@task
def generate_thumbnails_step(data: Dict[str, Any], thumbnails_dir=None, logger=None) -> Dict[str, Any]:
    """
    Generate thumbnails for a video file.
    
    Args:
        data: Pipeline data containing file_path, checksum, and clip_id
        thumbnails_dir: Base directory for thumbnails (should be data/clips)
        logger: Optional logger
        
    Returns:
        Dict with thumbnail paths
    """
    file_path = data.get('file_path')
    checksum = data.get('checksum')
    clip_id = data.get('clip_id')
    
    if not file_path or not checksum:
        raise ValueError("Missing file_path or checksum in data")
        
    if not thumbnails_dir:
        raise ValueError("Missing thumbnails_dir parameter")
    
    # Use clip_id if available, otherwise fall back to filename_checksum pattern
    if clip_id:
        thumbnail_dir_for_file = os.path.join(thumbnails_dir, str(clip_id))
    else:
        # Fallback to old pattern if clip_id not available yet
        base_name = os.path.splitext(os.path.basename(file_path))[0]
        thumbnail_dir_name = f"{base_name}_{checksum}"
        thumbnail_dir_for_file = os.path.join(thumbnails_dir, thumbnail_dir_name)
    
    thumbnail_paths = generate_thumbnails(file_path, thumbnail_dir_for_file, logger=logger)
    
    return {
        'thumbnail_paths': thumbnail_paths
    } 