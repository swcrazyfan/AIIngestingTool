"""
Test script to verify refactored pipeline steps are properly registered.
"""

import structlog
from video_ingest_tool.pipeline.registry import get_all_steps
from video_ingest_tool.steps.extraction import (
    extract_mediainfo_step, 
    extract_ffprobe_step,
    extract_exiftool_step,
    extract_extended_exif_step,
    extract_codec_step,
    extract_hdr_step,
    extract_audio_step,
    extract_subtitle_step
)
from video_ingest_tool.steps.analysis import (
    generate_thumbnails_step,
    analyze_exposure_step,
    detect_focal_length_step,
    ai_video_analysis_step,
    ai_thumbnail_selection_step
)
from video_ingest_tool.steps.processing import (
    generate_checksum_step,
    check_duplicate_step,
    consolidate_metadata_step
)

# Import the steps to make sure they get registered
print("Importing extraction steps...")
print(f"MediaInfo step: {extract_mediainfo_step.__name__}")
print(f"FFprobe step: {extract_ffprobe_step.__name__}")
print(f"ExifTool step: {extract_exiftool_step.__name__}")
print(f"Extended EXIF step: {extract_extended_exif_step.__name__}")
print(f"Codec step: {extract_codec_step.__name__}")
print(f"HDR step: {extract_hdr_step.__name__}")
print(f"Audio step: {extract_audio_step.__name__}")
print(f"Subtitle step: {extract_subtitle_step.__name__}")

print("\nImporting analysis steps...")
print(f"Thumbnails step: {generate_thumbnails_step.__name__}")
print(f"Exposure analysis step: {analyze_exposure_step.__name__}")
print(f"Focal length detection step: {detect_focal_length_step.__name__}")
print(f"AI video analysis step: {ai_video_analysis_step.__name__}")
print(f"AI thumbnail selection step: {ai_thumbnail_selection_step.__name__}")

print("\nImporting processing steps...")
print(f"Checksum step: {generate_checksum_step.__name__}")
print(f"Duplicate check step: {check_duplicate_step.__name__}")
print(f"Metadata consolidation step: {consolidate_metadata_step.__name__}")

# Get all registered steps
steps = get_all_steps()
print("\nRegistered steps:")
for step in steps:
    print(f"- {step['name']}: {step['description']} (enabled: {step['enabled']})")

print(f"\nTotal steps registered: {len(steps)}") 