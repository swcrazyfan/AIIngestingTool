"""
Video processing package for compressing and analyzing videos.

Re-exports all video processor components.
"""

try:
    from .analysis import VideoAnalyzer
    from .compression import VideoCompressor, DEFAULT_COMPRESSION_CONFIG
    from .processor import VideoProcessor
except ImportError as e:
    # Fail gracefully if dependencies are missing
    import logging
    logging.getLogger(__name__).warning(f"Could not import some video processor components: {str(e)}")

__all__ = [
    'VideoAnalyzer',
    'VideoCompressor',
    'VideoProcessor',
    'DEFAULT_COMPRESSION_CONFIG',
]
