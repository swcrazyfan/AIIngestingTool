"""
Codec parameter extraction step for the video ingest tool.

Registered as a step in the flows registry.

Extracts detailed codec parameters.
"""

from typing import Any, Dict

from ...flows.registry import register_step
from ...extractors.codec import extract_codec_parameters
from prefect import task

@register_step(
    name="codec_extraction", 
    enabled=True,
    description="Extract detailed codec parameters"
)
@task
def extract_codec_step(data: Dict[str, Any], logger=None) -> Dict[str, Any]:
    """
    Extract codec parameters.
    
    Args:
        data: Pipeline data containing file_path
        logger: Optional logger
        
    Returns:
        Dict with codec data
    """
    file_path = data.get('file_path')
    if not file_path:
        raise ValueError("Missing file_path in data")
        
    codec_params = extract_codec_parameters(file_path, logger)
    
    return {
        'codec_params': codec_params
    } 