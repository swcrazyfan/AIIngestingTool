"""
AI thumbnail selection step for the video ingest pipeline.

Extracts frames from the video based on AI analysis recommended timestamps and processes them for thumbnail use.
"""

import os
import math
import logging
from typing import Any, Dict, List, Optional
from PIL import Image
import av
from prefect import task

def extract_frame_at_timestamp(file_path: str, timestamp: str, output_path: str, logger=None) -> Optional[str]:
    """
    Extract a specific frame from a video at the given timestamp.
    
    Args:
        file_path: Path to the video file
        timestamp: Timestamp string in format like "5s600ms", "00:00:03.800", or "00:03" 
        output_path: Path to save the extracted frame
        logger: Optional logger
        
    Returns:
        str: Path to the saved frame or None if extraction failed
    """
    try:
        # Parse the timestamp string to seconds
        seconds = 0
        
        # Handle format "5s600ms"
        if "s" in timestamp and not timestamp.startswith("00:"):
            parts = timestamp.split("s")
            seconds = int(parts[0])
            if "ms" in parts[1]:
                milliseconds = int(parts[1].split("ms")[0])
                seconds += milliseconds / 1000.0
        
        # Handle format "00:00:03.800"
        elif timestamp.startswith("00:") and "." in timestamp:
            # Format is "00:00:03.800"
            time_parts = timestamp.split(":")
            if len(time_parts) == 3:
                seconds = int(time_parts[1]) * 60 + float(time_parts[2])
            elif len(time_parts) == 2:
                seconds = float(time_parts[1])
        
        # Handle format "00:03" (minutes:seconds)
        elif ":" in timestamp:
            time_parts = timestamp.split(":")
            if len(time_parts) == 2:
                minutes = int(time_parts[0])
                seconds = int(time_parts[1])
                seconds += minutes * 60
        
        # Try to parse as float as fallback
        else:
            try:
                seconds = float(timestamp)
            except ValueError:
                if logger:
                    logger.error(f"Unable to parse timestamp: {timestamp}")
                return None
        
        if logger:
            logger.info(f"Parsed timestamp {timestamp} to {seconds} seconds")
        
        # Open the video file
        with av.open(file_path) as container:
            # Find video stream
            if not container.streams.video:
                if logger:
                    logger.error(f"No video stream found in {file_path}")
                return None
                
            stream = container.streams.video[0]
            
            # Convert timestamp to microseconds for av
            seek_position = int(seconds * 1000000)
            
            # Seek to the position
            container.seek(seek_position, stream=stream)
            
            # Get the first frame after the seek position
            for frame in container.decode(video=0):
                img = frame.to_image()
                
                # Resize to standard 256x256 while maintaining aspect ratio with padding
                width, height = img.size
                
                # Determine the target size while maintaining aspect ratio
                if width > height:
                    new_width = 256
                    new_height = int(height * 256 / width)
                else:
                    new_height = 256
                    new_width = int(width * 256 / height)
                
                # Resize the image
                img = img.resize((new_width, new_height), Image.LANCZOS)
                
                # Create a new image with white background for padding
                padded_img = Image.new("RGB", (256, 256), (255, 255, 255))
                
                # Paste the resized image centered on the padded image
                paste_x = (256 - new_width) // 2
                paste_y = (256 - new_height) // 2
                padded_img.paste(img, (paste_x, paste_y))
                
                # Save the image
                os.makedirs(os.path.dirname(output_path), exist_ok=True)
                padded_img.save(output_path, quality=95)
                
                if logger:
                    logger.info(f"Extracted frame at {timestamp} and saved to {output_path}")
                
                return output_path
                
        if logger:
            logger.warning(f"No frame found at timestamp {timestamp}")
        return None
            
    except Exception as e:
        if logger:
            logger.error(f"Frame extraction failed for timestamp {timestamp}: {str(e)}")
        return None

@task
def ai_thumbnail_selection_step(
    data: Dict[str, Any], 
    data_base_dir: Optional[str] = None,  # Base data directory (e.g., /path/to/data)
    logger=None
) -> Dict[str, Any]:
    """
    Extract frames from the video at timestamps recommended by AI analysis.
    
    Args:
        data: Pipeline data containing file_path, checksum, clip_id, file_name, and full_ai_analysis_data
        data_base_dir: Base data directory for organized output structure
        logger: Optional logger
        
    Returns:
        Dict with AI thumbnail paths and metadata
    """
    file_path = data.get('file_path')
    checksum = data.get('checksum')
    clip_id = data.get('clip_id')
    file_name = data.get('file_name', os.path.basename(file_path) if file_path else 'unknown')
    analysis_results = data.get('full_ai_analysis_data', {})
    
    if not file_path or not checksum:
        raise ValueError("Missing file_path or checksum in data")
        
    if not data_base_dir:
        raise ValueError("Missing data_base_dir parameter")
    
    if not analysis_results:
        if logger:
            logger.warning("No analysis results available, skipping AI thumbnail selection")
        return {"ai_thumbnail_paths": [], "ai_thumbnail_metadata": []}
    
    # Create a proper logger if none provided
    if logger is None:
        logger = logging.getLogger("ai_thumbnail_selection")
    
    # Get recommended thumbnails from analysis
    recommended_thumbnails = analysis_results.get("visual_analysis", {}).get("keyframe_analysis", {}).get("recommended_thumbnails", [])
    
    if not recommended_thumbnails:
        logger.warning("No recommended thumbnails in analysis results")
        return {"ai_thumbnail_paths": [], "ai_thumbnail_metadata": []}
    
    # Determine output directory structure: data/clips/{filename}_{clip_id}/thumbnails/
    base_filename = os.path.splitext(file_name)[0]
    if clip_id:
        # New organized structure
        clip_dir_name = f"{base_filename}_{clip_id}"
        clip_base_dir = os.path.join(data_base_dir, "clips", clip_dir_name)
        thumbnail_dir_for_file = os.path.join(clip_base_dir, "thumbnails")
    else:
        # Fallback to data/thumbnails if no clip_id
        thumbnail_dir_for_file = os.path.join(data_base_dir, "thumbnails", checksum)
    
    # Extract frames for each recommended thumbnail
    ai_thumbnail_paths = []
    ai_thumbnail_metadata = []
    
    for thumbnail in recommended_thumbnails:
        timestamp = thumbnail.get("timestamp")
        rank = thumbnail.get("rank")
        description = thumbnail.get("description")
        detailed_visual_description = thumbnail.get("detailed_visual_description")
        reason = thumbnail.get("reason")
        
        if not timestamp or not rank:
            logger.warning(f"Missing timestamp or rank in thumbnail: {thumbnail}")
            continue
        
        # Generate AI thumbnail filename with rank
        ai_filename = f"AI_{base_filename}_{timestamp}_{rank}.jpg"
        ai_output_path = os.path.join(thumbnail_dir_for_file, ai_filename)
        
        # Extract the frame
        extracted_path = extract_frame_at_timestamp(file_path, timestamp, ai_output_path, logger)
        
        if extracted_path:
            ai_thumbnail_paths.append(extracted_path)
            ai_thumbnail_metadata.append({
                "path": extracted_path,
                "timestamp": timestamp,
                "rank": rank,
                "description": description,
                "detailed_visual_description": detailed_visual_description,
                "reason": reason
            })
            logger.info(f"Successfully processed AI thumbnail rank {rank} at path {extracted_path}")
        else:
            logger.error(f"Failed to extract AI thumbnail at {timestamp}")
    
    # Sort thumbnails by rank to ensure order (1, 2, 3)
    ai_thumbnail_metadata.sort(key=lambda x: int(x.get("rank", "999") if isinstance(x.get("rank"), str) else x.get("rank", 999)))
    ai_thumbnail_paths = [item["path"] for item in ai_thumbnail_metadata]
    
    logger.info(f"AI thumbnail selection complete, found {len(ai_thumbnail_paths)} thumbnails")
    
    return {
        "ai_thumbnail_paths": ai_thumbnail_paths,
        "ai_thumbnail_metadata": ai_thumbnail_metadata
    } 