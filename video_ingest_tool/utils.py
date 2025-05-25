"""
Utility functions for the video ingest tool.

Contains helper functions for checksum calculation, parsing dates, etc.
"""

import os
import math
import hashlib
import datetime
from typing import Optional, Union
from dateutil import parser as dateutil_parser

def calculate_checksum(file_path: str, block_size: int = 65536) -> str:
    """
    Calculate MD5 checksum of a file.
    
    Args:
        file_path: Path to the file
        block_size: Block size for reading the file
        
    Returns:
        str: Hex digest of MD5 checksum
    """
    hash_md5 = hashlib.md5()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(block_size), b""):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()

def parse_datetime_string(date_str: Optional[str]) -> Optional[datetime.datetime]:
    """Parse a date string into a datetime object, handling various formats and UTC."""
    if not date_str:
        return None
    try:
        # Clean up string first
        cleaned_date_str = date_str
        
        # Handle common date formats with timezone info
        if 'UTC' in cleaned_date_str:
            # Try to handle formats like "2026-04-18 04:54:32 UTC" or "2026-04-18 04-54-32 UTC"
            cleaned_date_str = cleaned_date_str.replace(' UTC', 'Z')
            # Replace all hyphens in time part with colons
            if ' ' in cleaned_date_str:
                date_part, time_part = cleaned_date_str.split(' ', 1)
                time_part = time_part.replace('-', ':')
                cleaned_date_str = f"{date_part} {time_part}"
                
        # Handle formats with colons in date part (2022:01:01 12:30:00)
        elif cleaned_date_str.count(':') > 2:
            parts = cleaned_date_str.split(' ', 1)
            date_part = parts[0].replace(':', '-')
            
            if len(parts) > 1:
                time_part = parts[1]
                cleaned_date_str = f"{date_part} {time_part}"
            else:
                cleaned_date_str = date_part
            
        # Parse the cleaned string
        dt = dateutil_parser.parse(cleaned_date_str)
        return dt
    except (ValueError, TypeError):
        return None

def calculate_aspect_ratio_str(width: Optional[int], height: Optional[int]) -> Optional[str]:
    """Calculate aspect ratio as a string (e.g., '16:9')."""
    if not width or not height or width <= 0 or height <= 0:
        return None
    common_divisor = math.gcd(width, height)
    return f"{width // common_divisor}:{height // common_divisor}"

def map_exposure_mode(mode_val: Optional[Union[str, int]]) -> Optional[str]:
    """Map EXIF ExposureMode numerical value to a human-readable string."""
    if mode_val is None:
        return None
    try:
        val = int(str(mode_val).strip())
        if val == 0:
            return "AUTO_EXPOSURE"
        elif val == 1:
            return "MANUAL_EXPOSURE"
        elif val == 2:
            return "AUTO_BRACKET"
        else:
            return str(mode_val) # Return original value if unknown
    except ValueError:
        return str(mode_val) # Return original string if not an int

def map_white_balance(wb_val: Optional[Union[str, int]]) -> Optional[str]:
    """Map EXIF WhiteBalance numerical value to a human-readable string."""
    if wb_val is None:
        return None
    try:
        val = int(str(wb_val).strip())
        if val == 0:
            return "AUTO_WHITE_BALANCE"
        elif val == 1:
            return "MANUAL_WHITE_BALANCE"
        else:
            # Many more values exist for white balance, but these are the most common.
            return str(wb_val) # Return original value if unknown or unmapped
    except ValueError:
        return str(wb_val) # Return original string if not an int

def is_video_file(file_path: str, has_polyfile: bool = False) -> bool:
    """
    Check if a file is a video file based on MIME type.
    
    Args:
        file_path: Path to the file to check
        has_polyfile: Whether polyfile module is available
        
    Returns:
        bool: True if the file is a video, False otherwise
    """
    import mimetypes
    
    try:
        # Use polyfile for file type detection if available
        if has_polyfile:
            from polyfile.magic import MagicMatcher
            with open(file_path, 'rb') as f:
                # Read a small chunk, as PolyFile can work with partial data
                file_bytes = f.read(2048) # Read first 2KB for type detection
                for match in MagicMatcher.DEFAULT_INSTANCE.match(file_bytes):
                    for mime_type in match.mimetypes:
                        if mime_type.startswith('video/'):
                            return True
        
        # Fallback to mimetypes if polyfile is not available or doesn't find a video
        mime_type, _ = mimetypes.guess_type(file_path)
        if mime_type and mime_type.startswith('video/'):
            return True
            
        # Additional fallback: check extensions
        file_ext = os.path.splitext(file_path.lower())[1]
        video_extensions = ['.mp4', '.mov', '.avi', '.wmv', '.flv', '.mkv', '.webm', '.m4v', '.mpg', '.mpeg']
        if file_ext in video_extensions:
            return True
            
        return False
    except Exception:
        # Ultimate fallback to mimetypes if everything else errors out
        try:
            mime_type, _ = mimetypes.guess_type(file_path)
            return bool(mime_type and mime_type.startswith('video/'))
        except:
            return False

def categorize_focal_length(focal_length: Optional[Union[str, int, float]], ranges: dict) -> Optional[str]:
    """
    Categorize a focal length value into a standard category.
    
    Args:
        focal_length: The focal length value (can be string, int, or float)
        ranges: Dictionary of focal length ranges by category
        
    Returns:
        str: The focal length category (ULTRA-WIDE, WIDE, MEDIUM, LONG-LENS, TELEPHOTO) or None if not determinable
    """
    if focal_length is None:
        return None
    
    try:
        # Convert focal length to float if it's a string or other type
        if isinstance(focal_length, str):
            # Clean up string - remove 'mm' suffix and any spaces
            focal_length = focal_length.lower().replace('mm', '').strip()
        
        focal_mm = float(focal_length)
        
        # Determine category based on range
        for category, (min_val, max_val) in ranges.items():
            if min_val <= focal_mm <= max_val:
                return category
        
        # Handle extreme values
        if focal_mm < 8:
            return "ULTRA-WIDE"
        elif focal_mm > 800:
            return "TELEPHOTO"
        
        return None
    except (ValueError, TypeError):
        return None
