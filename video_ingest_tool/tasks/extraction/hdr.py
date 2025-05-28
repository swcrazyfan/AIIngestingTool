"""
HDR metadata extraction step for the video ingest pipeline.

Extracts HDR metadata from video files.
"""

from typing import Any, Dict
from ...extractors.hdr import extract_hdr_metadata
from prefect import task

@task
def extract_hdr_step(data: Dict[str, Any], logger=None) -> Dict[str, Any]:
    """
    Extract HDR metadata.
    
    Args:
        data: Pipeline data containing file_path
        logger: Optional logger
        
    Returns:
        Dict with HDR data
    """
    file_path = data.get('file_path')
    if not file_path:
        raise ValueError("Missing file_path in data")
        
    hdr_data = extract_hdr_metadata(file_path, logger)
    
    return {
        'hdr_data': hdr_data
    } 