"""
Thumbnail upload task for storing thumbnail file paths in local mode.

This task handles organizing and cataloging thumbnails without requiring
external storage authentication since we're using local DuckDB.
"""

import os
import shutil
import mimetypes
from pathlib import Path
from typing import Any, Dict, List
from prefect import task

@task
def upload_thumbnails_step(data: Dict[str, Any], logger=None) -> Dict[str, Any]:
    """
    Process thumbnails for local storage (no upload required).
    
    Since we're using local DuckDB mode, this task organizes thumbnails
    locally and returns file paths for database storage.
    
    Args:
        data: Pipeline data containing thumbnail_paths, ai_thumbnail_paths, and clip_id
        logger: Optional logger
        
    Returns:
        Dict with local thumbnail URLs/paths
    """
    # Check if we have the required data
    thumbnail_paths = data.get('thumbnail_paths', [])
    ai_thumbnail_paths = data.get('ai_thumbnail_paths', [])
    ai_thumbnail_metadata = data.get('ai_thumbnail_metadata', [])
    clip_id = data.get('clip_id')
    
    has_thumbnails = bool(thumbnail_paths) or bool(ai_thumbnail_paths)
    
    if not has_thumbnails:
        if logger:
            logger.warning("No thumbnails available for processing")
        return {
            'thumbnail_upload_skipped': True,
            'reason': 'no_thumbnails'
        }
    
    if not clip_id:
        if logger:
            logger.warning("No clip_id available, thumbnails cannot be processed")
        return {
            'thumbnail_upload_skipped': True,
            'reason': 'no_clip_id'
        }
    
    try:
        # Create local thumbnails directory structure
        thumbnails_base_dir = Path("output/thumbnails")
        clip_thumbnails_dir = thumbnails_base_dir / str(clip_id)
        clip_thumbnails_dir.mkdir(parents=True, exist_ok=True)
        
        if logger:
            logger.info(f"Processing thumbnails for clip {clip_id} in local mode")
        
        # Process regular thumbnails
        thumbnail_urls = []
        for thumbnail_path in thumbnail_paths:
            if not os.path.exists(thumbnail_path):
                if logger:
                    logger.warning(f"Thumbnail file not found: {thumbnail_path}")
                continue
            
            # Get the filename from the path
            filename = os.path.basename(thumbnail_path)
            local_path = clip_thumbnails_dir / filename
            
            # Copy thumbnail to organized location if not already there
            if str(local_path) != thumbnail_path:
                shutil.copy2(thumbnail_path, local_path)
                if logger:
                    logger.info(f"Copied thumbnail to: {local_path}")
            
            # Store relative path for database
            relative_path = str(local_path.relative_to(Path.cwd()))
            thumbnail_urls.append({
                "url": f"file://{local_path.absolute()}",  # Local file URL
                "local_path": relative_path,
                "filename": filename,
                "is_ai_selected": False
            })
        
        # Process AI thumbnails
        ai_thumbnail_urls = []
        
        # Create a mapping from path to metadata
        ai_thumbnail_map = {}
        for metadata in ai_thumbnail_metadata:
            if 'path' in metadata and 'rank' in metadata:
                ai_thumbnail_map[metadata['path']] = metadata
        
        for thumbnail_path in ai_thumbnail_paths:
            if not os.path.exists(thumbnail_path):
                if logger:
                    logger.warning(f"AI thumbnail file not found: {thumbnail_path}")
                continue
            
            # Get the filename from the path
            filename = os.path.basename(thumbnail_path)
            
            # Get metadata for this thumbnail
            metadata = ai_thumbnail_map.get(thumbnail_path, {})
            rank = metadata.get('rank')
            timestamp = metadata.get('timestamp')
            description = metadata.get('description', '')
            reason = metadata.get('reason', '')
            
            if not rank:
                if logger:
                    logger.warning(f"Missing rank for AI thumbnail: {thumbnail_path}")
                continue
            
            local_path = clip_thumbnails_dir / filename
            
            # Copy thumbnail to organized location if not already there
            if str(local_path) != thumbnail_path:
                shutil.copy2(thumbnail_path, local_path)
                if logger:
                    logger.info(f"Copied AI thumbnail to: {local_path}")
            
            # Store relative path for database
            relative_path = str(local_path.relative_to(Path.cwd()))
            ai_thumbnail_urls.append({
                "url": f"file://{local_path.absolute()}",  # Local file URL
                "local_path": relative_path,
                "filename": filename,
                "is_ai_selected": True,
                "rank": rank,
                "timestamp": timestamp,
                "description": description,
                "reason": reason
            })
        
        # Combine all thumbnail URLs
        all_thumbnail_urls = thumbnail_urls + ai_thumbnail_urls
        
        if logger:
            logger.info(f"Processed {len(all_thumbnail_urls)} thumbnails for clip {clip_id}")
        
        return {
            'thumbnail_urls': thumbnail_urls,
            'ai_thumbnail_urls': ai_thumbnail_urls,
            'all_thumbnail_urls': all_thumbnail_urls,
            'thumbnails_directory': str(clip_thumbnails_dir),
            'thumbnail_upload_success': True
        }
        
    except Exception as e:
        if logger:
            logger.error(f"Error processing thumbnails: {str(e)}")
        return {
            'thumbnail_upload_failed': True,
            'error': str(e)
        } 