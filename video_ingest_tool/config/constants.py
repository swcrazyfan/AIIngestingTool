"""
Constants for the video ingest tool.

Contains all constant values used throughout the application.
"""

# Focal length category ranges (in mm, for full-frame equivalent)
FOCAL_LENGTH_RANGES = {
    "ULTRA-WIDE": (8, 18),    # Ultra wide-angle: 8-18mm
    "WIDE": (18, 35),         # Wide-angle: 18-35mm
    "MEDIUM": (35, 70),       # Standard/Normal: 35-70mm
    "LONG-LENS": (70, 200),   # Short telephoto: 70-200mm
    "TELEPHOTO": (200, 800)   # Telephoto: 200-800mm
}

# Default compression configuration - single source of truth
DEFAULT_COMPRESSION_CONFIG = {
    'max_dimension': 1280,  # Scale longest dimension to this size
    'fps': 5,
    'video_bitrate': '1000k',
    'audio_bitrate': '32k',
    'audio_channels': 1,
    'use_hardware_accel': True,
    'codec_priority': ['hevc_videotoolbox', 'h264_videotoolbox', 'libx265', 'libx264'],
    'crf_value': '25',
}

# Check if required modules are available
try:
    from polyfile.magic import MagicMatcher
    HAS_POLYFILE = True
except ImportError:
    HAS_POLYFILE = False

try:
    from transformers import pipeline
    import torch
    HAS_TRANSFORMERS = True
except ImportError:
    HAS_TRANSFORMERS = False 