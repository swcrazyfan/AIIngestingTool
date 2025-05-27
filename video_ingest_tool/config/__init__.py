"""
Configuration package for the video ingest tool.

Re-exports all configuration components.
"""

from .constants import (
    FOCAL_LENGTH_RANGES,
    HAS_POLYFILE,
    HAS_TRANSFORMERS,
    DEFAULT_COMPRESSION_CONFIG
)
from .settings import Config
from .logging import setup_logging, console

__all__ = [
    # Constants
    'FOCAL_LENGTH_RANGES',
    'HAS_POLYFILE',
    'HAS_TRANSFORMERS',
    'DEFAULT_COMPRESSION_CONFIG',
    
    # Classes
    'Config',
    
    # Functions and objects
    'setup_logging',
    'console',
]
