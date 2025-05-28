"""
EXIF information extractors for the video ingest tool.

Contains functions for extracting EXIF metadata using ExifTool.
"""

import exiftool
from typing import Any, Dict

from ..utils import categorize_focal_length, parse_datetime_string, map_exposure_mode, map_white_balance
from ..config import FOCAL_LENGTH_RANGES

def extract_exiftool_info(file_path: str, logger=None) -> Dict[str, Any]:
    """
    Extract metadata using ExifTool.
    
    Args:
        file_path: Path to the video file
        logger: Logger instance
        
    Returns:
        Dict: Technical metadata
    """
    if logger:
        logger.info("Extracting ExifTool metadata", path=file_path)
    
    try:
        with exiftool.ExifToolHelper() as et:
            metadata = et.get_metadata(file_path)[0]
            
            # Get the raw focal length
            focal_length_raw = metadata.get('EXIF:FocalLength')
            
            # Map numeric focal length to categories using the utility function
            focal_length_category = None
            if focal_length_raw is not None:
                focal_length_category = categorize_focal_length(focal_length_raw, FOCAL_LENGTH_RANGES)
            
            exif_data = {
                'camera_make': metadata.get('EXIF:Make'),
                'camera_model': metadata.get('EXIF:Model'),
                'focal_length_mm': focal_length_raw if isinstance(focal_length_raw, (int, float)) else None,
                'focal_length_category': focal_length_category,
                # Keep focal_length for backward compatibility
                'focal_length': focal_length_category,
                'created_at': parse_datetime_string(metadata.get('EXIF:CreateDate') or metadata.get('QuickTime:CreateDate') or metadata.get('QuickTime:CreationDate')),
                'gps_latitude': metadata.get('EXIF:GPSLatitude'),
                'gps_longitude': metadata.get('EXIF:GPSLongitude'),
            }
            
            exif_data = {k: v for k, v in exif_data.items() if v is not None}
            
            if logger:
                logger.info("ExifTool extraction successful", path=file_path)
            
            return exif_data
            
    except Exception as e:
        if logger:
            logger.error("ExifTool extraction failed", path=file_path, error=str(e))
        return {}

def extract_extended_exif_metadata(file_path: str, logger=None) -> Dict[str, Any]:
    """
    Extract extended EXIF metadata from video files.
    
    Args:
        file_path: Path to the video file
        logger: Logger instance
        
    Returns:
        Dict: Extended EXIF metadata including GPS and advanced camera settings
    """
    if logger:
        logger.info("Extracting extended EXIF metadata", path=file_path)
    
    try:
        with exiftool.ExifToolHelper() as et:
            metadata = et.get_metadata(file_path)[0]
            
            # Initialize the result dict
            extended_metadata = {}
            
            # Extract GPS coordinates
            if 'EXIF:GPSLatitude' in metadata and 'EXIF:GPSLongitude' in metadata:
                try:
                    extended_metadata['gps_latitude'] = float(metadata['EXIF:GPSLatitude'])
                    extended_metadata['gps_longitude'] = float(metadata['EXIF:GPSLongitude'])
                    
                    # Add altitude if available
                    if 'EXIF:GPSAltitude' in metadata:
                        extended_metadata['gps_altitude'] = float(metadata['EXIF:GPSAltitude'])
                        
                    # Try to get location name if available
                    if 'XMP:Location' in metadata:
                        extended_metadata['location_name'] = metadata['XMP:Location']
                    elif 'IPTC:City' in metadata:
                        city = metadata['IPTC:City']
                        country = metadata.get('IPTC:Country', '')
                        if country:
                            extended_metadata['location_name'] = f"{city}, {country}"
                        else:
                            extended_metadata['location_name'] = city
                except (ValueError, TypeError) as e:
                    if logger:
                        logger.warning(f"Error parsing GPS coordinates: {e}", path=file_path)
            
            # Advanced camera metadata
            # Camera serial number
            if 'EXIF:SerialNumber' in metadata:
                extended_metadata['camera_serial_number'] = str(metadata['EXIF:SerialNumber'])
                
            # Lens model
            if 'EXIF:LensModel' in metadata:
                extended_metadata['lens_model'] = metadata['EXIF:LensModel']
                
            # ISO
            if 'EXIF:ISO' in metadata:
                try:
                    extended_metadata['iso'] = int(metadata['EXIF:ISO'])
                except (ValueError, TypeError):
                    pass
                    
            # Shutter speed
            if 'EXIF:ShutterSpeedValue' in metadata:
                extended_metadata['shutter_speed'] = str(metadata['EXIF:ShutterSpeedValue'])
                
            # Aperture (f-stop)
            if 'EXIF:FNumber' in metadata:
                try:
                    extended_metadata['f_stop'] = float(metadata['EXIF:FNumber'])
                except (ValueError, TypeError):
                    pass
                    
            # Exposure mode
            if 'EXIF:ExposureMode' in metadata:
                extended_metadata['exposure_mode'] = map_exposure_mode(metadata.get('EXIF:ExposureMode'))
                
            # White balance
            if 'EXIF:WhiteBalance' in metadata:
                extended_metadata['white_balance'] = map_white_balance(metadata.get('EXIF:WhiteBalance'))
                
            if logger:
                logger.info("Extended EXIF metadata extraction successful", path=file_path)
            
            return extended_metadata
            
    except Exception as e:
        if logger:
            logger.error("Extended EXIF metadata extraction failed", path=file_path, error=str(e))
        return {} 