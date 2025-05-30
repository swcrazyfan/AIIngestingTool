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
    'max_dimension': 854,  # Scale longest dimension to this size
    'fps': 5,
    'video_bitrate': '1000k', # Target bitrate for hardware encoding (e.g., h264_videotoolbox)
    'audio_bitrate': '32k',
    'audio_channels': 1,
    'use_hardware_accel': True,  # Enable hardware acceleration
    # Prioritize VideoToolbox, then software fallbacks
    'codec_priority': ['h264_videotoolbox', 'hevc_videotoolbox', 'libx265', 'libx264'], 
    'crf_value': '23',  # Retain for software fallback (libx264/libx265)
    'preset': 'ultrafast',  # Retain for software fallback (libx264/libx265), may not apply to all HW encoders
    'audio_copy': True,     # Use -c:a copy
    # Note: The VideoCompressor class in compression.py already adds '-allow_sw 1' 
    # for videotoolbox codecs.
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