"""
Metadata consolidation step for the video ingest pipeline.

Consolidates metadata from all sources.
"""

from typing import Any, Dict

from ...pipeline.registry import register_step

@register_step(
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
    
    # Get focal length info from AI or EXIF
    focal_length_source = data.get('focal_length_source')
    ai_focal_length_info = {
        'category': data.get('focal_length_category'),
        'mm': data.get('focal_length_mm')
    }
    
    # Initialize the master metadata dictionary
    master_metadata = {}

    # Prioritize sources for technical video properties
    tech_keys = ['codec', 'width', 'height', 'frame_rate', 'bit_rate_kbps', 'bit_depth', 'color_space', 'container', 'duration_seconds', 'profile', 'level', 'chroma_subsampling', 'pixel_format', 'bitrate_mode', 'scan_type', 'field_order', 'cabac', 'ref_frames', 'gop_size']
    for key in tech_keys:
        master_metadata[key] = mediainfo_data.get(key, ffprobe_data.get(key, exiftool_data.get(key, codec_params.get(key))))

    # Prioritize sources for camera/lens info
    camera_keys = ['camera_make', 'camera_model', 'focal_length_mm', 'focal_length_category', 'lens_model', 'iso', 'shutter_speed', 'f_stop', 'exposure_mode', 'white_balance', 'gps_latitude', 'gps_longitude', 'gps_altitude', 'location_name', 'camera_serial_number']
    for key in camera_keys:
        # Prioritize extended_exif_data then exiftool_data for camera specific info
        master_metadata[key] = extended_exif_data.get(key, exiftool_data.get(key, mediainfo_data.get(key, ffprobe_data.get(key))))

    # Prioritize sources for dates
    master_metadata['created_at'] = exiftool_data.get('created_at', mediainfo_data.get('created_at', ffprobe_data.get('created_at')))

    # Merge remaining from specific extractions if not already set or to overwrite with more specific data
    for key, value in codec_params.items():
        if master_metadata.get(key) is None or key in ['profile', 'level', 'pixel_format', 'chroma_subsampling', 'bitrate_mode', 'scan_type', 'field_order', 'cabac', 'ref_frames', 'gop_size']:
            if value is not None: master_metadata[key] = value
    
    for key, value in hdr_data.items():
        if master_metadata.get(key) is None or key in ['hdr_format', 'master_display', 'max_cll', 'max_fall', 'color_primaries', 'transfer_characteristics', 'matrix_coefficients', 'color_range']:
            if value is not None: master_metadata[key] = value

    for key, value in extended_exif_data.items(): # Ensure all extended_exif_data is considered
        if master_metadata.get(key) is None: # Add if not already set
             if value is not None: master_metadata[key] = value
    
    # Handle focal length data from different sources
    if focal_length_source == 'AI':
        # Use AI detected values, overriding any EXIF data
        master_metadata['focal_length_source'] = 'AI'
        master_metadata['focal_length_category'] = ai_focal_length_info['category']
        master_metadata['focal_length_mm'] = None  # AI only provides category
        if logger:
            logger.info("Using AI-detected focal length",
                       source='AI',
                       category=ai_focal_length_info['category'])
    elif focal_length_source == 'EXIF':
        # Keep EXIF values from earlier camera_keys import
        master_metadata['focal_length_source'] = 'EXIF'
        if logger:
            logger.info("Using EXIF focal length",
                       source='EXIF',
                       mm=master_metadata.get('focal_length_mm'),
                       category=master_metadata.get('focal_length_category'))
    else:
        # No focal length data available
        master_metadata['focal_length_source'] = None
        master_metadata['focal_length_category'] = None
        master_metadata['focal_length_mm'] = None
        if logger:
            logger.info("No focal length information available")
    
    return {
        'master_metadata': master_metadata
    } 