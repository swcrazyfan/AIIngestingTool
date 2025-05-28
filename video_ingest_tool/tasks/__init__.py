"""
Pipeline steps for the video ingest tool.

Re-exports all pipeline steps from the tasks directory.
"""

from .extraction import (
    extract_mediainfo_step, extract_ffprobe_step, extract_exiftool_step,
    extract_extended_exif_step, extract_codec_step, extract_hdr_step,
    extract_audio_step, extract_subtitle_step
)
from .analysis import (
    generate_thumbnails_step, analyze_exposure_step, detect_focal_length_step,
    ai_video_analysis_step, ai_thumbnail_selection_step
)
from .processing import (
    generate_checksum_step, check_duplicate_step, consolidate_metadata_step, video_compression_step
)
from .storage import (
    create_model_step, database_storage_step, generate_embeddings_step,
    upload_thumbnails_step
)

__all__ = [
    # Extraction steps
    'extract_mediainfo_step',
    'extract_ffprobe_step',
    'extract_exiftool_step',
    'extract_extended_exif_step',
    'extract_codec_step',
    'extract_hdr_step',
    'extract_audio_step',
    'extract_subtitle_step',
    
    # Analysis steps
    'generate_thumbnails_step',
    'analyze_exposure_step',
    'detect_focal_length_step',
    'ai_video_analysis_step',
    'ai_thumbnail_selection_step',
    
    # Processing steps
    'generate_checksum_step',
    'check_duplicate_step',
    'consolidate_metadata_step',
    'video_compression_step',
    
    # Storage steps
    'create_model_step',
    'database_storage_step',
    'generate_embeddings_step',
    'upload_thumbnails_step'
]
