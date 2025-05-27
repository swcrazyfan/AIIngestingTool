"""
HDR information extractors for the video ingest tool.

Contains functions for extracting HDR metadata from video files.
"""

import pymediainfo
from typing import Any, Dict

def extract_hdr_metadata(file_path: str, logger=None) -> Dict[str, Any]:
    """
    Extract HDR-related metadata from video files.
    
    Args:
        file_path: Path to the video file
        logger: Logger instance
        
    Returns:
        Dict: HDR metadata including format, mastering display info, and light levels
    """
    if logger:
        logger.info("Extracting HDR metadata", path=file_path)
    
    try:
        media_info = pymediainfo.MediaInfo.parse(file_path)
        
        video_track = next((track for track in media_info.tracks if track.track_type == 'Video'), None)
        
        hdr_metadata = {}
        
        if video_track:
            # Check for HDR format based on transfer characteristics
            if hasattr(video_track, 'transfer_characteristics') and video_track.transfer_characteristics:
                transfer = str(video_track.transfer_characteristics).lower()
                hdr_metadata['transfer_characteristics'] = video_track.transfer_characteristics
                
                if 'pq' in transfer or 'smpte st 2084' in transfer or 'smpte2084' in transfer:
                    hdr_metadata['hdr_format'] = 'HDR10'
                elif 'hlg' in transfer or 'hybrid log' in transfer or 'arib std b67' in transfer:
                    hdr_metadata['hdr_format'] = 'HLG'
            
            # Check for HDR10+ and Dolby Vision
            commercial_id = ''
            if hasattr(video_track, 'hdr_format_commercial') and video_track.hdr_format_commercial:
                commercial_id = str(video_track.hdr_format_commercial).lower()
                if 'dolby vision' in commercial_id:
                    hdr_metadata['hdr_format'] = 'Dolby Vision'
                elif 'hdr10+' in commercial_id:
                    hdr_metadata['hdr_format'] = 'HDR10+'
            
            # Store color info
            if hasattr(video_track, 'color_primaries'):
                hdr_metadata['color_primaries'] = video_track.color_primaries
                
            if hasattr(video_track, 'matrix_coefficients'):
                hdr_metadata['matrix_coefficients'] = video_track.matrix_coefficients
                
            if hasattr(video_track, 'color_range'):
                hdr_metadata['color_range'] = video_track.color_range
                
            # Get master display information (typically for HDR10)
            if hasattr(video_track, 'mastering_display_color_primaries'):
                hdr_metadata['master_display'] = video_track.mastering_display_color_primaries
                
            # Get content light level
            if hasattr(video_track, 'maximum_content_light_level'):
                try:
                    hdr_metadata['max_cll'] = int(video_track.maximum_content_light_level)
                except (ValueError, TypeError):
                    pass
                    
            if hasattr(video_track, 'maximum_frame_light_level'):
                try:
                    hdr_metadata['max_fall'] = int(video_track.maximum_frame_light_level)
                except (ValueError, TypeError):
                    pass
        
        if hdr_metadata and logger:
            logger.info("HDR metadata extraction successful", path=file_path, 
                     format=hdr_metadata.get('hdr_format', 'unknown'))
        elif logger:
            logger.info("No HDR metadata found", path=file_path)
            
        return hdr_metadata
    
    except Exception as e:
        if logger:
            logger.error("HDR metadata extraction failed", path=file_path, error=str(e))
        return {} 