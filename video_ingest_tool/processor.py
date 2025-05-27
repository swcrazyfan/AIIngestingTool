"""
Processor module for the video ingest tool.

This module re-exports processing functions from other modules to maintain compatibility
with the API server and other components that expect them in this location.
"""

from typing import Dict, Any, List

# Re-export functions from other modules
from .pipeline.registry import get_available_pipeline_steps
from .steps import process_video_file
from .config.settings import get_default_pipeline_config
from .video_processor import DEFAULT_COMPRESSION_CONFIG

__all__ = [
    'get_available_pipeline_steps',
    'process_video_file',
    'get_default_pipeline_config',
    'DEFAULT_COMPRESSION_CONFIG',
] 