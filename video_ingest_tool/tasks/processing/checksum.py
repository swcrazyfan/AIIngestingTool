"""
Checksum generation step for the video ingest tool.

Calculates file checksum for deduplication and generates clip ID.
"""

import os
import uuid
from typing import Any, Dict
from ...utils import calculate_checksum
from ...database.duckdb import connection as duckdb_connection
from ...database.duckdb import crud as duckdb_crud
from prefect import task

@task
def generate_checksum_step(data: Dict[str, Any], logger=None, force_reprocess: bool = False) -> Dict[str, Any]:
    """
    Generate checksum for a video file and assign a clip ID.
    If a clip with the same checksum already exists and force_reprocess is False,
    skip processing and return skip status.
    
    Args:
        data: Pipeline data containing file_path
        logger: Optional logger
        force_reprocess: Whether to force reprocessing of existing files
        
    Returns:
        Dict with checksum information and clip_id, or skip status for duplicates
    """
    file_path = data.get('file_path')
    if not file_path:
        raise ValueError("Missing file_path in data")
        
    if logger:
        logger.info("Generating checksum and clip ID", path=file_path)
        
    checksum = calculate_checksum(file_path)
    file_size_bytes = os.path.getsize(file_path)
    file_name = os.path.basename(file_path)
    
    # Check if a clip with this checksum already exists in the database
    clip_id = None
    existing_clip = None
    
    try:
        with duckdb_connection.get_db_connection() as conn:
            existing_clip = duckdb_crud.find_clip_by_checksum(checksum, conn)
    except Exception as e:
        if logger:
            logger.warning("Failed to check for existing clip by checksum", 
                         checksum=checksum, error=str(e))
        # Continue with new UUID generation if database check fails
    
    if existing_clip and existing_clip.get('id'):
        # Found duplicate clip
        clip_id = str(existing_clip['id'])
        
        if not force_reprocess:
            # Skip processing this duplicate file
            if logger:
                logger.info("Skipping duplicate file - use --force to reprocess", 
                           clip_id=clip_id, checksum=checksum, 
                           existing_file_name=existing_clip.get('file_name'),
                           current_file=file_name)
            
            return {
                'status': 'skipped',
                'reason': 'duplicate_checksum',
                'checksum': checksum,
                'file_size_bytes': file_size_bytes,
                'file_name': file_name,
                'clip_id': clip_id,
                'existing_clip': existing_clip,
                'skip_remaining_steps': True  # Signal to pipeline to skip this file
            }
        else:
            # Force reprocessing - continue with existing UUID
        if logger:
                logger.info("Force reprocessing duplicate file", 
                       clip_id=clip_id, checksum=checksum, 
                       existing_file_name=existing_clip.get('file_name'))
    else:
        # Generate new UUID for new clip
        clip_id = str(uuid.uuid4())
        if logger:
            logger.info("Generated new clip ID for new file", 
                       clip_id=clip_id, checksum=checksum)
    
    return {
        'status': 'processing',
        'checksum': checksum,
        'file_size_bytes': file_size_bytes,
        'file_name': file_name,
        'clip_id': clip_id,
        'is_reprocessing': existing_clip is not None
    } 