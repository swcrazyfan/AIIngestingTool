"""
Special extractors for the video ingest tool.

Contains functions for extracting specialized metadata like HDR information and subtitles.
"""

import pymediainfo
import av
from typing import Any, Dict, List, Optional

def extract_subtitle_tracks(file_path: str, logger=None) -> List[Dict[str, Any]]:
    """
    Extract subtitle track information from video files.
    
    Args:
        file_path: Path to the video file
        logger: Logger instance
        
    Returns:
        List[Dict]: List of subtitle track metadata
    """
    if logger:
        logger.info("Extracting subtitle tracks", path=file_path)
    
    subtitle_tracks = []
    
    try:
        media_info = pymediainfo.MediaInfo.parse(file_path)
        
        for track in media_info.tracks:
            if track.track_type == 'Text':
                subtitle_track = {
                    'track_id': str(track.track_id) if hasattr(track, 'track_id') and track.track_id is not None else None,
                    'format': track.format if hasattr(track, 'format') else None,
                    'codec_id': track.codec_id if hasattr(track, 'codec_id') else None,
                    'language': track.language if hasattr(track, 'language') else None,
                    'embedded': True if hasattr(track, 'muxing_mode') and track.muxing_mode == 'muxed' else None
                }
                
                # Filter out None values
                subtitle_track = {k: v for k, v in subtitle_track.items() if v is not None}
                
                subtitle_tracks.append(subtitle_track)
        
        if logger:
            logger.info("Subtitle track extraction successful", path=file_path, track_count=len(subtitle_tracks))
        
        return subtitle_tracks
    
    except Exception as e:
        if logger:
            logger.error("Subtitle track extraction failed", path=file_path, error=str(e))
        return []

def extract_codec_parameters(file_path: str, logger=None) -> Dict[str, Any]:
    """
    Extract detailed codec parameters from video files.
    
    Args:
        file_path: Path to the video file
        logger: Logger instance
        
    Returns:
        Dict: Detailed codec parameters
    """
    if logger:
        logger.info("Extracting codec parameters", path=file_path)
    
    try:
        # Try MediaInfo first for more detailed codec parameters
        media_info = pymediainfo.MediaInfo.parse(file_path)
        video_track = next((track for track in media_info.tracks if track.track_type == 'Video'), None)
        
        codec_params = {}
        
        if video_track:
            # Extract profile info
            if hasattr(video_track, 'format_profile') and video_track.format_profile:
                parts = str(video_track.format_profile).split('@')
                if len(parts) > 0:
                    codec_params['profile'] = parts[0].strip()
                    if len(parts) > 1 and 'L' in parts[1]:
                        level_part = parts[1].strip()
                        codec_params['level'] = level_part.replace('L', '')
            
            # Extract pixel format
            if hasattr(video_track, 'pixel_format'):
                codec_params['pixel_format'] = video_track.pixel_format
            
            # Extract chroma subsampling
            if hasattr(video_track, 'chroma_subsampling'):
                codec_params['chroma_subsampling'] = video_track.chroma_subsampling
            
            # Extract bitrate mode
            if hasattr(video_track, 'bit_rate_mode'):
                codec_params['bitrate_mode'] = video_track.bit_rate_mode
            
            # Extract scan type and field order
            if hasattr(video_track, 'scan_type'):
                codec_params['scan_type'] = video_track.scan_type
                
            if hasattr(video_track, 'scan_order'):
                codec_params['field_order'] = video_track.scan_order
        
        # Try PyAV for additional codec parameters if MediaInfo doesn't provide enough
        if not codec_params or len(codec_params) < 3:
            try:
                with av.open(file_path) as container:
                    for stream in container.streams.video:
                        if not 'profile' in codec_params and hasattr(stream.codec_context, 'profile'):
                            codec_params['profile'] = stream.codec_context.profile
                            
                        if not 'pixel_format' in codec_params and hasattr(stream.codec_context, 'pix_fmt'):
                            codec_params['pixel_format'] = stream.codec_context.pix_fmt
                            
                        # Get GOP size if available
                        if hasattr(stream.codec_context, 'gop_size'):
                            codec_params['gop_size'] = stream.codec_context.gop_size
                            
                        # Get reference frames if available
                        if hasattr(stream.codec_context, 'refs'):
                            codec_params['ref_frames'] = stream.codec_context.refs
                            
                        # Check for CABAC (H.264 specific)
                        if hasattr(stream.codec_context, 'flags') and \
                           hasattr(stream.codec_context.flags, 'CABAC'):
                            codec_params['cabac'] = bool(stream.codec_context.flags.CABAC)
                        
                        break  # Only process the first video stream
            except Exception as av_error:
                if logger:
                    logger.warning("PyAV codec parameter extraction failed", path=file_path, error=str(av_error))
                
        if logger:
            logger.info("Codec parameter extraction successful", path=file_path, params_count=len(codec_params))
        
        return codec_params
    
    except Exception as e:
        if logger:
            logger.error("Codec parameter extraction failed", path=file_path, error=str(e))
        return {}

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
