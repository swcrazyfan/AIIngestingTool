"""
Processors for the video ingest tool.

Contains functions for thumbnail generation, exposure analysis, and AI detection.
"""

import os
import cv2
import math
import numpy as np
import av
from PIL import Image
import torch
from typing import Any, Dict, List, Optional, Tuple, Union

def generate_thumbnails(file_path: str, output_dir: str, count: int = 5, logger=None) -> List[str]:
    """
    Generate thumbnails from video file using PyAV.
    
    Args:
        file_path: Path to the video file
        output_dir: Directory to save thumbnails
        count: Number of thumbnails to generate
        logger: Logger instance
        
    Returns:
        List[str]: Paths to generated thumbnails
    """
    if logger:
        logger.info("Generating thumbnails", path=file_path, count=count)
    
    thumbnail_paths = []
    
    try:
        os.makedirs(output_dir, exist_ok=True)
        
        with av.open(file_path) as container:
            duration = float(container.duration / 1000000) if container.duration else 0
            
            if duration <= 0:
                if logger:
                    logger.error("Could not determine video duration", path=file_path)
                return []
            
            positions = [duration * i / (count + 1) for i in range(1, count + 1)]
            
            if not container.streams.video:
                if logger:
                    logger.error("No video stream found", path=file_path)
                return []
                
            stream = container.streams.video[0]
            
            for i, position in enumerate(positions):
                # Format the position as seconds_milliseconds
                position_seconds = int(position)
                position_milliseconds = int((position - position_seconds) * 1000)
                timestamp_str = f"{position_seconds}s{position_milliseconds:03d}ms"
                
                # Include the timestamp in the filename
                base_filename = os.path.basename(file_path)
                output_path = os.path.join(output_dir, f"{base_filename}_{timestamp_str}_{i}.jpg")
                
                container.seek(int(position * 1000000), stream=stream)
                
                for frame in container.decode(video=0):
                    img = frame.to_image()
                    
                    width, height = img.size
                    new_width = 640
                    new_height = int(height * new_width / width)
                    img = img.resize((new_width, new_height), Image.LANCZOS)
                    
                    img.save(output_path, quality=95)
                    
                    thumbnail_paths.append(output_path)
                    if logger:
                        logger.info("Generated thumbnail", path=output_path, position=position)
                    break
        
        if logger:
            logger.info("Thumbnail generation complete", path=file_path, count=len(thumbnail_paths))
        
        return thumbnail_paths
    
    except Exception as e:
        if logger:
            logger.error("Thumbnail generation failed", path=file_path, error=str(e))
        return []

def analyze_exposure(thumbnail_path: str, logger=None) -> Dict[str, Any]:
    """
    Analyze exposure in an image.
    
    Args:
        thumbnail_path: Path to the thumbnail image
        logger: Logger instance
        
    Returns:
        Dict: Exposure analysis results including warning flag and exposure deviation in stops
    """
    if logger:
        logger.info("Analyzing exposure", path=thumbnail_path)
    
    try:
        image = cv2.imread(thumbnail_path)
        
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        
        hist = cv2.calcHist([gray], [0], None, [256], [0, 256])
        hist = hist.flatten() / (gray.shape[0] * gray.shape[1])
        
        overexposed = sum(hist[240:])
        underexposed = sum(hist[:16])
        
        # Calculate exposure warning flag
        exposure_warning = overexposed > 0.05 or underexposed > 0.05
        
        # Estimate exposure deviation in stops
        exposure_stops = 0.0
        if overexposed > underexposed and overexposed > 0.05:
            # Rough approximation of stops overexposed
            exposure_stops = math.log2(overexposed * 20)
        elif underexposed > 0.05:
            # Rough approximation of stops underexposed (negative value)
            exposure_stops = -math.log2(underexposed * 20)
        
        result = {
            'exposure_warning': exposure_warning,
            'exposure_stops': exposure_stops,
            'overexposed_percentage': float(overexposed * 100),
            'underexposed_percentage': float(underexposed * 100)
        }
        
        if logger:
            logger.info("Exposure analysis complete", path=thumbnail_path, result=result)
        
        return result
    
    except Exception as e:
        if logger:
            logger.error("Exposure analysis failed", path=thumbnail_path, error=str(e))
        return {
            'exposure_warning': False,
            'exposure_stops': 0.0,
            'overexposed_percentage': 0.0,
            'underexposed_percentage': 0.0
        }

def detect_focal_length_with_ai(image_path: str, focal_length_ranges: dict, has_transformers: bool = False, logger=None) -> Optional[str]:
    """
    Use AI to detect the focal length category from an image when EXIF data is not available.
    
    Args:
        image_path: Path to the image file
        focal_length_ranges: Dictionary of focal length ranges
        has_transformers: Whether transformers library is available
        logger: Logger instance
        
    Returns:
        Optional[str]: Focal length category (e.g., 'ULTRA-WIDE', 'WIDE', etc.)
    """
    if not has_transformers:
        if logger:
            logger.warning("AI-based focal length detection requested but transformers library is not available",
                        path=image_path)
        return None
    
    try:
        if logger:
            logger.info("Using AI to detect focal length", path=image_path)
        
        # Import here to avoid errors if module is not available
        from transformers import pipeline
        
        # Device selection logic - prioritize MPS, then CUDA, then CPU
        if hasattr(torch, 'backends') and hasattr(torch.backends, 'mps') and torch.backends.mps.is_available():
            device = "mps"
        elif torch.cuda.is_available():
            device = "cuda"
        else:
            device = "cpu"
        
        if logger:
            logger.info(f"Using device for AI model: {device}")
        
        # Create a pipeline using the Hugging Face model
        pipe = pipeline("image-classification", model="tonyassi/camera-lens-focal-length", device=device)
        
        # Load the image
        pil_image = Image.open(image_path)
        
        # Run the model to estimate focal length category
        prediction_result = pipe(pil_image)
        
        # Extract the top prediction
        if prediction_result and len(prediction_result) > 0:
            top_prediction = prediction_result[0]
            category = top_prediction["label"]
            confidence = top_prediction["score"]
            
            if logger:
                logger.info(f"AI detected focal length category: {category} (confidence: {confidence:.4f})",
                          path=image_path, category=category, confidence=confidence)
            
            return category
        else:
            if logger:
                logger.warning("AI model did not return predictions for focal length", path=image_path)
            return None
            
    except Exception as e:
        if logger:
            logger.error("Error using AI to detect focal length", path=image_path, error=str(e))
        return None
