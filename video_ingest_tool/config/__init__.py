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

# Analysis consistency configuration
ANALYSIS_CONSISTENCY_CONFIG = {
    'vocabulary_version': '1.0',
    'enable_reference_examples': True,
    'max_reference_examples': 3,
    'require_vocabulary_compliance': True,
    'enable_re_analysis_detection': True,
    'similarity_threshold_for_re_analysis': 0.8,  # If existing similar clips have very different descriptions
}

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
