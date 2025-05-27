"""
Metadata extractors for the video ingest tool.

Re-exports metadata extraction functions from modules.
"""

from .media import extract_mediainfo, extract_ffprobe_info
from .exif import extract_exiftool_info, extract_extended_exif_metadata
from .tracks import extract_audio_tracks, extract_subtitle_tracks
from .codec import extract_codec_parameters
from .hdr import extract_hdr_metadata

__all__ = [
    # Media extraction
    'extract_mediainfo',
    'extract_ffprobe_info',
    
    # EXIF extraction
    'extract_exiftool_info',
    'extract_extended_exif_metadata',
    
    # Track extraction
    'extract_audio_tracks',
    'extract_subtitle_tracks',
    
    # Codec and HDR extraction
    'extract_codec_parameters',
    'extract_hdr_metadata',
]
