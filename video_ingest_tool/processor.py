"""
Core processor for the video ingest tool.

Handles the primary processing logic for video ingestion.
"""

import os
import datetime
import uuid

from typing import Any, Dict, List, Optional, Tuple, Union
from pydantic import BaseModel

from .models import (
    VideoIngestOutput, FileInfo, VideoCodecDetails, VideoResolution, VideoHDRDetails,
    VideoColorDetails, VideoExposureDetails, VideoDetails, CameraFocalLength,
    CameraSettings, CameraLocation, CameraDetails, AnalysisDetails,
    AudioTrack, SubtitleTrack
)
from .utils import calculate_checksum, calculate_aspect_ratio_str
from .extractors import extract_mediainfo, extract_ffprobe_info
from .extractors_extended import extract_exiftool_info, extract_extended_exif_metadata, extract_audio_tracks
from .extractors_hdr import extract_subtitle_tracks, extract_codec_parameters, extract_hdr_metadata
from .processors import generate_thumbnails, analyze_exposure, detect_focal_length_with_ai
from .config import FOCAL_LENGTH_RANGES, HAS_TRANSFORMERS

def process_video_file(file_path: str, thumbnails_dir: str, logger=None) -> VideoIngestOutput:
    """
    Process a video file to extract metadata and generate thumbnails.
    
    Args:
        file_path: Path to the video file
        thumbnails_dir: Directory to save thumbnails
        logger: Logger instance
        
    Returns:
        VideoIngestOutput: Processed video data object
    """
    if logger:
        logger.info("Processing video file", path=file_path)
    
    video_id = str(uuid.uuid4())
    checksum = calculate_checksum(file_path)
    file_size_bytes = os.path.getsize(file_path)
    file_name = os.path.basename(file_path)
    processed_at_time = datetime.datetime.now()

    # --- Metadata Extraction ---
    mediainfo_data = extract_mediainfo(file_path, logger)
    ffprobe_data = extract_ffprobe_info(file_path, logger)
    exiftool_data = extract_exiftool_info(file_path, logger)
    
    hdr_data_extracted = {}
    audio_tracks_list_data = []
    subtitle_tracks_list_data = []
    codec_params_extracted = {}
    extended_exif_data = {}

    try:
        hdr_data_extracted = extract_hdr_metadata(file_path, logger)
        audio_tracks_list_data = extract_audio_tracks(file_path, logger)
        subtitle_tracks_list_data = extract_subtitle_tracks(file_path, logger)
        codec_params_extracted = extract_codec_parameters(file_path, logger)
        extended_exif_data = extract_extended_exif_metadata(file_path, logger)
    except Exception as e:
        if logger:
            logger.error(f"Error extracting some extended metadata parts: {e}", path=file_path)

    # --- Consolidate Metadata ---
    master_metadata = {}

    # Prioritize sources for technical video properties
    tech_keys = ['codec', 'width', 'height', 'frame_rate', 'bit_rate_kbps', 'bit_depth', 'color_space', 'container', 'duration_seconds', 'profile', 'level', 'chroma_subsampling', 'pixel_format', 'bitrate_mode', 'scan_type', 'field_order', 'cabac', 'ref_frames', 'gop_size']
    for key in tech_keys:
        master_metadata[key] = mediainfo_data.get(key, ffprobe_data.get(key, exiftool_data.get(key, codec_params_extracted.get(key))))

    # Prioritize sources for camera/lens info
    camera_keys = ['camera_make', 'camera_model', 'focal_length_mm', 'focal_length_category', 'lens_model', 'iso', 'shutter_speed', 'f_stop', 'exposure_mode', 'white_balance', 'gps_latitude', 'gps_longitude', 'gps_altitude', 'location_name']
    for key in camera_keys:
        master_metadata[key] = exiftool_data.get(key, extended_exif_data.get(key, mediainfo_data.get(key, ffprobe_data.get(key))))

    # Prioritize sources for dates
    master_metadata['created_at'] = exiftool_data.get('created_at', mediainfo_data.get('created_at', ffprobe_data.get('created_at')))

    # Merge remaining from specific extractions if not already set or to overwrite with more specific data
    for key, value in codec_params_extracted.items():
        if master_metadata.get(key) is None or key in ['profile', 'level', 'pixel_format', 'chroma_subsampling', 'bitrate_mode', 'scan_type', 'field_order', 'cabac', 'ref_frames', 'gop_size']:
            if value is not None: master_metadata[key] = value
    
    for key, value in hdr_data_extracted.items():
        if master_metadata.get(key) is None or key in ['hdr_format', 'master_display', 'max_cll', 'max_fall', 'color_primaries', 'transfer_characteristics', 'matrix_coefficients', 'color_range']:
            if value is not None: master_metadata[key] = value

    for key, value in extended_exif_data.items():
        if master_metadata.get(key) is None or key in ['lens_model', 'iso', 'shutter_speed', 'f_stop', 'exposure_mode', 'white_balance', 'gps_latitude', 'gps_longitude', 'gps_altitude', 'location_name', 'camera_serial_number']:
            if value is not None: master_metadata[key] = value
            
    # --- Thumbnail Generation & Exposure Analysis ---
    thumbnail_dir_for_file = os.path.join(thumbnails_dir, checksum)
    thumbnail_paths = generate_thumbnails(file_path, thumbnail_dir_for_file, logger=logger)
    
    exposure_analysis_results = {}
    if thumbnail_paths:
        exposure_analysis_results = analyze_exposure(thumbnail_paths[0], logger=logger)

    # --- AI Focal Length Detection (if needed) ---
    if not master_metadata.get('focal_length_mm') and not master_metadata.get('focal_length_category') and thumbnail_paths:
        if logger:
            logger.info("Focal length not found, attempting AI detection.", path=file_path)
        category, approx_value = detect_focal_length_with_ai(
            thumbnail_paths[0], 
            FOCAL_LENGTH_RANGES, 
            has_transformers=HAS_TRANSFORMERS,
            logger=logger
        )
        if category and approx_value:
            master_metadata['focal_length_category'] = category
            master_metadata['focal_length_mm'] = approx_value
            master_metadata['focal_length_source'] = 'AI'
            if logger:
                logger.info("AI detected focal length", category=category, value=approx_value, path=file_path)

    # --- Populate Pydantic Models ---
    file_info_obj = FileInfo(
        file_path=file_path,
        file_name=file_name,
        file_checksum=checksum,
        file_size_bytes=file_size_bytes,
        created_at=master_metadata.get('created_at'),
        processed_at=processed_at_time
    )

    video_codec_details_obj = VideoCodecDetails(
        name=master_metadata.get('codec'),
        profile=master_metadata.get('profile'),
        level=master_metadata.get('level'),
        bitrate_kbps=master_metadata.get('bit_rate_kbps'),
        bit_depth=master_metadata.get('bit_depth'),
        chroma_subsampling=master_metadata.get('chroma_subsampling'),
        pixel_format=master_metadata.get('pixel_format'),
        bitrate_mode=master_metadata.get('bitrate_mode'),
        cabac=master_metadata.get('cabac'),
        ref_frames=master_metadata.get('ref_frames'),
        gop_size=master_metadata.get('gop_size'),
        scan_type=master_metadata.get('scan_type'),
        field_order=master_metadata.get('field_order')
    )

    video_resolution_obj = VideoResolution(
        width=master_metadata.get('width'),
        height=master_metadata.get('height'),
        aspect_ratio=calculate_aspect_ratio_str(master_metadata.get('width'), master_metadata.get('height'))
    )

    video_hdr_details_obj = VideoHDRDetails(
        is_hdr=bool(master_metadata.get('hdr_format')),
        format=master_metadata.get('hdr_format'),
        master_display=master_metadata.get('master_display'),
        max_cll=master_metadata.get('max_cll'),
        max_fall=master_metadata.get('max_fall')
    )

    video_color_details_obj = VideoColorDetails(
        color_space=master_metadata.get('color_space'),
        color_primaries=master_metadata.get('color_primaries'),
        transfer_characteristics=master_metadata.get('transfer_characteristics'),
        matrix_coefficients=master_metadata.get('matrix_coefficients'),
        color_range=master_metadata.get('color_range'),
        hdr=video_hdr_details_obj
    )

    video_exposure_details_obj = VideoExposureDetails(
        warning=exposure_analysis_results.get('exposure_warning'),
        stops=exposure_analysis_results.get('exposure_stops'),
        overexposed_percentage=exposure_analysis_results.get('overexposed_percentage'),
        underexposed_percentage=exposure_analysis_results.get('underexposed_percentage')
    )

    video_details_obj = VideoDetails(
        duration_seconds=master_metadata.get('duration_seconds'),
        codec=video_codec_details_obj,
        container=master_metadata.get('container'),
        resolution=video_resolution_obj,
        frame_rate=master_metadata.get('frame_rate'),
        color=video_color_details_obj,
        exposure=video_exposure_details_obj
    )

    audio_track_models = [AudioTrack(**track) for track in audio_tracks_list_data]
    subtitle_track_models = [SubtitleTrack(**track) for track in subtitle_tracks_list_data]

    camera_focal_length_obj = CameraFocalLength(
        value_mm=master_metadata.get('focal_length_mm'),
        category=master_metadata.get('focal_length_category')
    )

    camera_settings_obj = CameraSettings(
        iso=master_metadata.get('iso'),
        shutter_speed=master_metadata.get('shutter_speed'),
        f_stop=master_metadata.get('f_stop'),
        exposure_mode=master_metadata.get('exposure_mode'),
        white_balance=master_metadata.get('white_balance')
    )

    camera_location_obj = CameraLocation(
        gps_latitude=master_metadata.get('gps_latitude'),
        gps_longitude=master_metadata.get('gps_longitude'),
        gps_altitude=master_metadata.get('gps_altitude'),
        location_name=master_metadata.get('location_name')
    )

    camera_details_obj = CameraDetails(
        make=master_metadata.get('camera_make'),
        model=master_metadata.get('camera_model'),
        lens_model=master_metadata.get('lens_model'),
        focal_length=camera_focal_length_obj,
        settings=camera_settings_obj,
        location=camera_location_obj
    )

    analysis_details_obj = AnalysisDetails(
        scene_changes=[],  # Placeholder for future implementation
        content_tags=[],   # Placeholder for future implementation
        content_summary=None  # Placeholder for future implementation
    )

    output = VideoIngestOutput(
        id=video_id,
        file_info=file_info_obj,
        video=video_details_obj,
        audio_tracks=audio_track_models,
        subtitle_tracks=subtitle_track_models,
        camera=camera_details_obj,
        thumbnails=thumbnail_paths,
        analysis=analysis_details_obj
    )
    
    if logger:
        logger.info("Video processing complete", path=file_path, id=output.id)
    
    return output
