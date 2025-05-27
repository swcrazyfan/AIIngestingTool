"""
Codec information extractors for the video ingest tool.

Contains functions for extracting detailed codec parameters.
"""

import pymediainfo
import av
from typing import Any, Dict

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