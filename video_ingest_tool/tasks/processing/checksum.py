"""
Checksum generation step for the video ingest tool.

Registered as a step in the flows registry.

Calculates file checksum for deduplication.
"""

import os
from typing import Any, Dict

from ...flows.registry import register_step
from ...utils import calculate_checksum
from prefect import task

@register_step(
    name="checksum_generation", 
    enabled=True,
    description="Calculate file checksum for deduplication"
)
@task
def generate_checksum_step(data: Dict[str, Any], logger=None) -> Dict[str, Any]:
    """
    Generate checksum for a video file.
    
    Args:
        data: Pipeline data containing file_path
        logger: Optional logger
        
    Returns:
        Dict with checksum information
    """
    file_path = data.get('file_path')
    if not file_path:
        raise ValueError("Missing file_path in data")
        
    if logger:
        logger.info("Generating checksum", path=file_path)
        
    checksum = calculate_checksum(file_path)
    file_size_bytes = os.path.getsize(file_path)
    file_name = os.path.basename(file_path)
    
    return {
        'checksum': checksum,
        'file_size_bytes': file_size_bytes,
        'file_name': file_name
    } 