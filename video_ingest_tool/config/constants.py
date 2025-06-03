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
    'audio_bitrate': '16k',   # Compress audio to 16kbps
    'audio_channels': 1,
    'use_hardware_accel': True,  # Enable hardware acceleration
    # Prioritize libx265 software encoding, then libx264, then VideoToolbox as fallback
    'codec_priority': ['libx265', 'libx264', 'h264_videotoolbox', 'hevc_videotoolbox'], 
    'crf_value': '23',  # CRF value for software encoders (libx264/libx265)
    'preset': 'ultrafast',  # Preset for software encoders (libx264/libx265)
    'audio_copy': False,    # Compress audio instead of copying
    'use_conditional_scaling': True,  # Use if(gte(iw,ih),854,-2) scaling logic
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