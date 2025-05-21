"""
Core processor for the video ingest tool.

Handles the primary processing logic for video ingestion using the pipeline system.
"""

import os
import datetime
import uuid
from typing import Any, Dict, List, Optional, Tuple, Union

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
from .pipeline import ProcessingPipeline, ProcessingStep

# Create a global pipeline instance
pipeline = ProcessingPipeline()

# Define pipeline steps using decorators
@pipeline.register_step(
    name="checksum_generation", 
    enabled=True,
    description="Calculate file checksum for deduplication"
)
def generate_checksum(data: Dict[str, Any], logger=None) -> Dict[str, Any]:
    """
    Generate checksum for a video file.
    
    Args:
        data: Pipeline data containing file_path
        logger: Optional logger
        
    Returns:
        Dict with checksum information
    """
    file_path = data.get('file_path')
    if not file_path:
        raise ValueError("Missing file_path in data")
        
    if logger:
        logger.info("Generating checksum", path=file_path)
        
    checksum = calculate_checksum(file_path)
    file_size_bytes = os.path.getsize(file_path)
    file_name = os.path.basename(file_path)
    
    return {
        'checksum': checksum,
        'file_size_bytes': file_size_bytes,
        'file_name': file_name
    }

@pipeline.register_step(
    name="mediainfo_extraction", 
    enabled=True,
    description="Extract metadata using MediaInfo"
)
def extract_mediainfo_step(data: Dict[str, Any], logger=None) -> Dict[str, Any]:
    """
    Extract metadata using MediaInfo.
    
    Args:
        data: Pipeline data containing file_path
        logger: Optional logger
        
    Returns:
        Dict with mediainfo data
    """
    file_path = data.get('file_path')
    if not file_path:
        raise ValueError("Missing file_path in data")
        
    mediainfo_data = extract_mediainfo(file_path, logger)
    
    return {
        'mediainfo_data': mediainfo_data
    }

@pipeline.register_step(
    name="ffprobe_extraction", 
    enabled=True,
    description="Extract metadata using FFprobe/PyAV"
)
def extract_ffprobe_step(data: Dict[str, Any], logger=None) -> Dict[str, Any]:
    """
    Extract metadata using FFprobe/PyAV.
    
    Args:
        data: Pipeline data containing file_path
        logger: Optional logger
        
    Returns:
        Dict with ffprobe data
    """
    file_path = data.get('file_path')
    if not file_path:
        raise ValueError("Missing file_path in data")
        
    ffprobe_data = extract_ffprobe_info(file_path, logger)
    
    return {
        'ffprobe_data': ffprobe_data
    }

@pipeline.register_step(
    name="exiftool_extraction", 
    enabled=True,
    description="Extract EXIF metadata"
)
def extract_exiftool_step(data: Dict[str, Any], logger=None) -> Dict[str, Any]:
    """
    Extract metadata using ExifTool.
    
    Args:
        data: Pipeline data containing file_path
        logger: Optional logger
        
    Returns:
        Dict with exiftool data
    """
    file_path = data.get('file_path')
    if not file_path:
        raise ValueError("Missing file_path in data")
        
    exiftool_data = extract_exiftool_info(file_path, logger)
    
    return {
        'exiftool_data': exiftool_data
    }

@pipeline.register_step(
    name="extended_exif_extraction", 
    enabled=True,
    description="Extract extended EXIF metadata"
)
def extract_extended_exif_step(data: Dict[str, Any], logger=None) -> Dict[str, Any]:
    """
    Extract extended EXIF metadata.
    
    Args:
        data: Pipeline data containing file_path
        logger: Optional logger
        
    Returns:
        Dict with extended EXIF data
    """
    file_path = data.get('file_path')
    if not file_path:
        raise ValueError("Missing file_path in data")
        
    extended_exif_data = extract_extended_exif_metadata(file_path, logger)
    
    return {
        'extended_exif_data': extended_exif_data
    }

@pipeline.register_step(
    name="codec_extraction", 
    enabled=True,
    description="Extract detailed codec parameters"
)
def extract_codec_step(data: Dict[str, Any], logger=None) -> Dict[str, Any]:
    """
    Extract codec parameters.
    
    Args:
        data: Pipeline data containing file_path
        logger: Optional logger
        
    Returns:
        Dict with codec data
    """
    file_path = data.get('file_path')
    if not file_path:
        raise ValueError("Missing file_path in data")
        
    codec_params = extract_codec_parameters(file_path, logger)
    
    return {
        'codec_params': codec_params
    }

@pipeline.register_step(
    name="hdr_extraction", 
    enabled=True,
    description="Extract HDR metadata"
)
def extract_hdr_step(data: Dict[str, Any], logger=None) -> Dict[str, Any]:
    """
    Extract HDR metadata.
    
    Args:
        data: Pipeline data containing file_path
        logger: Optional logger
        
    Returns:
        Dict with HDR data
    """
    file_path = data.get('file_path')
    if not file_path:
        raise ValueError("Missing file_path in data")
        
    hdr_data = extract_hdr_metadata(file_path, logger)
    
    return {
        'hdr_data': hdr_data
    }

@pipeline.register_step(
    name="audio_extraction", 
    enabled=True,
    description="Extract audio track information"
)
def extract_audio_step(data: Dict[str, Any], logger=None) -> Dict[str, Any]:
    """
    Extract audio track information.
    
    Args:
        data: Pipeline data containing file_path
        logger: Optional logger
        
    Returns:
        Dict with audio track data
    """
    file_path = data.get('file_path')
    if not file_path:
        raise ValueError("Missing file_path in data")
        
    audio_tracks = extract_audio_tracks(file_path, logger)
    
    return {
        'audio_tracks': audio_tracks
    }

@pipeline.register_step(
    name="subtitle_extraction", 
    enabled=True,
    description="Extract subtitle track information"
)
def extract_subtitle_step(data: Dict[str, Any], logger=None) -> Dict[str, Any]:
    """
    Extract subtitle track information.
    
    Args:
        data: Pipeline data containing file_path
        logger: Optional logger
        
    Returns:
        Dict with subtitle track data
    """
    file_path = data.get('file_path')
    if not file_path:
        raise ValueError("Missing file_path in data")
        
    subtitle_tracks = extract_subtitle_tracks(file_path, logger)
    
    return {
        'subtitle_tracks': subtitle_tracks
    }

@pipeline.register_step(
    name="thumbnail_generation", 
    enabled=True,
    description="Generate thumbnails from video"
)
def generate_thumbnails_step(data: Dict[str, Any], thumbnails_dir=None, logger=None) -> Dict[str, Any]:
    """
    Generate thumbnails for a video file.
    
    Args:
        data: Pipeline data containing file_path and checksum
        thumbnails_dir: Directory to save thumbnails
        logger: Optional logger
        
    Returns:
        Dict with thumbnail paths
    """
    file_path = data.get('file_path')
    checksum = data.get('checksum')
    
    if not file_path or not checksum:
        raise ValueError("Missing file_path or checksum in data")
        
    if not thumbnails_dir:
        raise ValueError("Missing thumbnails_dir parameter")
        
    thumbnail_dir_for_file = os.path.join(thumbnails_dir, checksum)
    thumbnail_paths = generate_thumbnails(file_path, thumbnail_dir_for_file, logger=logger)
    
    return {
        'thumbnail_paths': thumbnail_paths
    }

@pipeline.register_step(
    name="exposure_analysis", 
    enabled=True,
    description="Analyze exposure in thumbnails"
)
def analyze_exposure_step(data: Dict[str, Any], logger=None) -> Dict[str, Any]:
    """
    Analyze exposure in thumbnails.
    
    Args:
        data: Pipeline data containing thumbnail_paths
        logger: Optional logger
        
    Returns:
        Dict with exposure analysis results
    """
    thumbnail_paths = data.get('thumbnail_paths', [])
    
    if not thumbnail_paths:
        if logger:
            logger.warning("No thumbnails available for exposure analysis")
        return {
            'exposure_data': {}
        }
        
    exposure_data = analyze_exposure(thumbnail_paths[0], logger)
    
    return {
        'exposure_data': exposure_data
    }

@pipeline.register_step(
    name="ai_focal_length", 
    enabled=True,
    description="Detect focal length using AI when EXIF data is not available"
)
def detect_focal_length_step(data: Dict[str, Any], logger=None) -> Dict[str, Any]:
    """
    Detect focal length using AI when EXIF data is not available.
    
    Args:
        data: Pipeline data containing thumbnail_paths and metadata
        logger: Optional logger
        
    Returns:
        Dict with focal length data
    """
    # Check if we already have focal length information
    exiftool_data = data.get('exiftool_data', {})
    extended_exif_data = data.get('extended_exif_data', {})
    
    if exiftool_data.get('focal_length_mm') or exiftool_data.get('focal_length_category') or \
       extended_exif_data.get('focal_length_mm') or extended_exif_data.get('focal_length_category'):
        # We already have focal length data, no need for AI detection
        if logger:
            logger.info("Focal length already available, skipping AI detection")
        return {}
    
    thumbnail_paths = data.get('thumbnail_paths', [])
    
    if not thumbnail_paths:
        if logger:
            logger.warning("No thumbnails available for focal length detection")
        return {}
    
    if logger:
        logger.info("Focal length not found, attempting AI detection.")
        
    category, approx_value = detect_focal_length_with_ai(
        thumbnail_paths[0], 
        FOCAL_LENGTH_RANGES, 
        has_transformers=HAS_TRANSFORMERS,
        logger=logger
    )
    
    if category and approx_value:
        return {
            'ai_focal_length_category': category,
            'ai_focal_length_mm': approx_value,
            'focal_length_source': 'AI'
        }
    
    return {}

@pipeline.register_step(
    name="metadata_consolidation", 
    enabled=True,
    description="Consolidate metadata from all sources"
)
def consolidate_metadata_step(data: Dict[str, Any], logger=None) -> Dict[str, Any]:
    """
    Consolidate metadata from all sources.
    
    Args:
        data: Pipeline data containing all extracted metadata
        logger: Optional logger
        
    Returns:
        Dict with consolidated metadata
    """
    mediainfo_data = data.get('mediainfo_data', {})
    ffprobe_data = data.get('ffprobe_data', {})
    exiftool_data = data.get('exiftool_data', {})
    extended_exif_data = data.get('extended_exif_data', {})
    codec_params = data.get('codec_params', {})
    hdr_data = data.get('hdr_data', {})
    
    # AI-detected focal length
    ai_focal_length_category = data.get('ai_focal_length_category')
    ai_focal_length_mm = data.get('ai_focal_length_mm')
    focal_length_source = data.get('focal_length_source')
    
    # Initialize the master metadata dictionary
    master_metadata = {}

    # Prioritize sources for technical video properties
    tech_keys = ['codec', 'width', 'height', 'frame_rate', 'bit_rate_kbps', 'bit_depth', 'color_space', 'container', 'duration_seconds', 'profile', 'level', 'chroma_subsampling', 'pixel_format', 'bitrate_mode', 'scan_type', 'field_order', 'cabac', 'ref_frames', 'gop_size']
    for key in tech_keys:
        master_metadata[key] = mediainfo_data.get(key, ffprobe_data.get(key, exiftool_data.get(key, codec_params.get(key))))

    # Prioritize sources for camera/lens info
    camera_keys = ['camera_make', 'camera_model', 'focal_length_mm', 'focal_length_category', 'lens_model', 'iso', 'shutter_speed', 'f_stop', 'exposure_mode', 'white_balance', 'gps_latitude', 'gps_longitude', 'gps_altitude', 'location_name']
    for key in camera_keys:
        master_metadata[key] = exiftool_data.get(key, extended_exif_data.get(key, mediainfo_data.get(key, ffprobe_data.get(key))))

    # Prioritize sources for dates
    master_metadata['created_at'] = exiftool_data.get('created_at', mediainfo_data.get('created_at', ffprobe_data.get('created_at')))

    # Merge remaining from specific extractions if not already set or to overwrite with more specific data
    for key, value in codec_params.items():
        if master_metadata.get(key) is None or key in ['profile', 'level', 'pixel_format', 'chroma_subsampling', 'bitrate_mode', 'scan_type', 'field_order', 'cabac', 'ref_frames', 'gop_size']:
            if value is not None: master_metadata[key] = value
    
    for key, value in hdr_data.items():
        if master_metadata.get(key) is None or key in ['hdr_format', 'master_display', 'max_cll', 'max_fall', 'color_primaries', 'transfer_characteristics', 'matrix_coefficients', 'color_range']:
            if value is not None: master_metadata[key] = value

    for key, value in extended_exif_data.items():
        if master_metadata.get(key) is None or key in ['lens_model', 'iso', 'shutter_speed', 'f_stop', 'exposure_mode', 'white_balance', 'gps_latitude', 'gps_longitude', 'gps_altitude', 'location_name', 'camera_serial_number']:
            if value is not None: master_metadata[key] = value
    
    # Add AI-detected focal length if available and no other focal length data exists
    if ai_focal_length_category and ai_focal_length_mm and not master_metadata.get('focal_length_category') and not master_metadata.get('focal_length_mm'):
        master_metadata['focal_length_category'] = ai_focal_length_category
        master_metadata['focal_length_mm'] = ai_focal_length_mm
        master_metadata['focal_length_source'] = focal_length_source
        if logger:
            logger.info("Using AI-detected focal length", category=ai_focal_length_category, value=ai_focal_length_mm)
    
    return {
        'master_metadata': master_metadata
    }

@pipeline.register_step(
    name="model_creation", 
    enabled=True,
    description="Create Pydantic model from processed data"
)
def create_model_step(data: Dict[str, Any], logger=None) -> Dict[str, Any]:
    """
    Create Pydantic model from processed data.
    
    Args:
        data: Pipeline data containing all processed information
        logger: Optional logger
        
    Returns:
        Dict with the output model
    """
    file_path = data.get('file_path')
    file_name = data.get('file_name')
    checksum = data.get('checksum')
    file_size_bytes = data.get('file_size_bytes')
    processed_at_time = datetime.datetime.now()
    
    master_metadata = data.get('master_metadata', {})
    thumbnail_paths = data.get('thumbnail_paths', [])
    exposure_data = data.get('exposure_data', {})
    audio_tracks = data.get('audio_tracks', [])
    subtitle_tracks = data.get('subtitle_tracks', [])
    
    # Create the Pydantic models
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
        warning=exposure_data.get('exposure_warning'),
        stops=exposure_data.get('exposure_stops'),
        overexposed_percentage=exposure_data.get('overexposed_percentage'),
        underexposed_percentage=exposure_data.get('underexposed_percentage')
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

    audio_track_models = [AudioTrack(**track) for track in audio_tracks]
    subtitle_track_models = [SubtitleTrack(**track) for track in subtitle_tracks]

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
        id=str(uuid.uuid4()),
        file_info=file_info_obj,
        video=video_details_obj,
        audio_tracks=audio_track_models,
        subtitle_tracks=subtitle_track_models,
        camera=camera_details_obj,
        thumbnails=thumbnail_paths,
        analysis=analysis_details_obj
    )
    
    return {
        'output': output
    }

def process_video_file(file_path: str, thumbnails_dir: str, logger=None, config: Dict[str, bool] = None) -> VideoIngestOutput:
    """
    Process a video file using the pipeline.
    
    Args:
        file_path: Path to the video file
        thumbnails_dir: Directory to save thumbnails
        logger: Optional logger
        config: Dictionary of step configurations (enabled/disabled)
        
    Returns:
        VideoIngestOutput: Processed video data object
    """
    if logger:
        logger.info("Processing video file", path=file_path)
    
    # Configure pipeline if config is provided
    if config:
        pipeline.configure_steps(config)
    
    # Initial data
    initial_data = {
        'file_path': file_path,
        'processed_at': datetime.datetime.now()
    }
    
    # Execute pipeline
    result = pipeline.execute_pipeline(
        initial_data, 
        thumbnails_dir=thumbnails_dir,
        logger=logger
    )
    
    # Return the output model
    output = result.get('output')
    if not output:
        raise ValueError("Pipeline did not produce an output model")
    
    if logger:
        logger.info("Video processing complete", path=file_path, id=output.id)
    
    return output

# Optional: Function to get default pipeline configuration
def get_default_pipeline_config() -> Dict[str, bool]:
    """
    Get the default pipeline configuration.
    
    Returns:
        Dict[str, bool]: Dictionary mapping step names to enabled status
    """
    return {step.name: step.enabled for step in pipeline.steps}

# Optional: Function to get available pipeline steps
def get_available_pipeline_steps() -> List[Dict[str, Any]]:
    """
    Get available pipeline steps with descriptions.
    
    Returns:
        List[Dict[str, Any]]: List of dictionaries with step information
    """
    return [
        {
            'name': step.name,
            'enabled': step.enabled,
            'description': step.description
        }
        for step in pipeline.steps
    ]
