"""
Checksum generation step for the video ingest tool.

Calculates file checksum for deduplication and generates clip ID.
"""

import os
import uuid
from typing import Any, Dict
from ...utils import calculate_checksum
from prefect import task

@task
def generate_checksum_step(data: Dict[str, Any], logger=None) -> Dict[str, Any]:
    """
    Generate checksum for a video file and assign a clip ID.
    
    Args:
        data: Pipeline data containing file_path
        logger: Optional logger
        
    Returns:
        Dict with checksum information and clip_id
    """
    file_path = data.get('file_path')
    if not file_path:
        raise ValueError("Missing file_path in data")
        
    if logger:
        logger.info("Generating checksum and clip ID", path=file_path)
        
    checksum = calculate_checksum(file_path)
    file_size_bytes = os.path.getsize(file_path)
    file_name = os.path.basename(file_path)
    
    # Generate clip ID early so it can be used for thumbnail directory structure
    clip_id = str(uuid.uuid4())
    
    if logger:
        logger.info("Generated clip ID", clip_id=clip_id, checksum=checksum)
    
    return {
        'checksum': checksum,
        'file_size_bytes': file_size_bytes,
        'file_name': file_name,
        'clip_id': clip_id
    } 