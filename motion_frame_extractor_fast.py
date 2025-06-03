#!/usr/bin/env python3
"""
Fast motion-based frame extractor using optimized OpenCV operations.

This script uses optimized OpenCV frame differencing with morphological
operations for very fast motion detection while maintaining good accuracy.
"""

import cv2
import os
import numpy as np
import argparse
from pathlib import Path
import time


def create_output_directory(video_path: str) -> str:
    """Create output directory for extracted frames."""
    video_name = Path(video_path).stem
    output_dir = f"{video_name}_motion_frames_fast"
    os.makedirs(output_dir, exist_ok=True)
    return output_dir


def calculate_fast_motion_score(frame1: np.ndarray, frame2: np.ndarray) -> float:
    """
    Fast motion calculation using optimized OpenCV operations.
    
    This is faster than basic frame differencing due to:
    - More efficient blur operations
    - Morphological operations to reduce noise
    - Optimized thresholding
    """
    # Convert to grayscale (more efficient than our previous method)
    gray1 = cv2.cvtColor(frame1, cv2.COLOR_BGR2GRAY)
    gray2 = cv2.cvtColor(frame2, cv2.COLOR_BGR2GRAY)
    
    # Use more efficient blur (box filter is faster than Gaussian)
    gray1 = cv2.boxFilter(gray1, -1, (5, 5))
    gray2 = cv2.boxFilter(gray2, -1, (5, 5))
    
    # Calculate absolute difference
    diff = cv2.absdiff(gray1, gray2)
    
    # Apply binary threshold
    _, thresh = cv2.threshold(diff, 20, 255, cv2.THRESH_BINARY)
    
    # Apply morphological operations to reduce noise and fill gaps
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    thresh = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, kernel)
    thresh = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)
    
    # Calculate percentage of changed pixels
    changed_pixels = cv2.countNonZero(thresh)
    total_pixels = thresh.shape[0] * thresh.shape[1]
    motion_score = changed_pixels / total_pixels
    
    return motion_score


def resize_to_480p(frame: np.ndarray) -> np.ndarray:
    """Resize frame to 480p (854x480) maintaining aspect ratio."""
    height, width = frame.shape[:2]
    
    # Calculate target dimensions (480p = 854x480)
    target_height = 480
    target_width = int(width * (target_height / height))
    
    # If calculated width exceeds 854, use 854 as max width
    if target_width > 854:
        target_width = 854
        target_height = int(height * (target_width / width))
    
    resized = cv2.resize(frame, (target_width, target_height), interpolation=cv2.INTER_AREA)
    return resized


def extract_motion_frames_fast(video_path: str, motion_threshold: float = 0.015, min_interval: float = 0.5):
    """
    Extract frames using fast OpenCV motion detection.
    
    Args:
        video_path: Path to input video file
        motion_threshold: Motion threshold (slightly lower due to noise reduction)
        min_interval: Minimum seconds between extracted frames
    """
    print(f"Processing video with FAST OpenCV method: {video_path}")
    
    # Open video
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        print(f"Error: Could not open video {video_path}")
        return
    
    # Get video properties
    fps = cap.get(cv2.CAP_PROP_FPS)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    duration = total_frames / fps
    
    print(f"Video info: {total_frames} frames, {fps:.2f} FPS, {duration:.2f}s duration")
    print(f"Motion threshold: {motion_threshold:.3f} ({motion_threshold*100:.1f}% pixel change)")
    print(f"Minimum interval between frames: {min_interval}s")
    
    # Create output directory
    output_dir = create_output_directory(video_path)
    print(f"Output directory: {output_dir}")
    
    # Initialize variables
    ret, prev_frame = cap.read()
    if not ret:
        print("Error: Could not read first frame")
        return
    
    frame_count = 0
    extracted_count = 0
    last_extracted_time = -min_interval
    
    # JPEG quality for ~1000kbps equivalent
    jpeg_quality = 85
    
    print("\nExtracting frames with FAST method...")
    start_time = time.time()
    
    while True:
        ret, current_frame = cap.read()
        if not ret:
            break
        
        frame_count += 1
        current_time = frame_count / fps
        
        # Calculate motion score using fast method
        motion_score = calculate_fast_motion_score(prev_frame, current_frame)
        
        # Check if motion exceeds threshold and minimum interval has passed
        if (motion_score > motion_threshold and 
            current_time - last_extracted_time >= min_interval):
            
            # Resize to 480p
            resized_frame = resize_to_480p(current_frame)
            
            # Create timestamp string
            minutes = int(current_time // 60)
            seconds = current_time % 60
            timestamp = f"{minutes:02d}m{seconds:06.3f}s"
            
            # Save frame
            filename = f"frame_{timestamp}_motion{motion_score:.4f}.jpg"
            filepath = os.path.join(output_dir, filename)
            
            cv2.imwrite(filepath, resized_frame, [cv2.IMWRITE_JPEG_QUALITY, jpeg_quality])
            
            extracted_count += 1
            last_extracted_time = current_time
            
            print(f"  Extracted: {filename} (motion: {motion_score:.4f})")
        
        # Update previous frame
        prev_frame = current_frame.copy()
        
        # Progress indicator (every 5 seconds to avoid spam)
        if frame_count % int(fps * 5) == 0:
            progress = (frame_count / total_frames) * 100
            print(f"  Progress: {progress:.1f}% ({frame_count}/{total_frames} frames)")
    
    # Cleanup
    cap.release()
    
    processing_time = time.time() - start_time
    print(f"\nCompleted!")
    print(f"Extracted {extracted_count} frames from {total_frames} total frames")
    print(f"Processing time: {processing_time:.2f}s")
    print(f"Average FPS: {total_frames/processing_time:.2f}")
    print(f"Frames saved to: {output_dir}/")


def main():
    parser = argparse.ArgumentParser(description="Extract motion-based frames using FAST OpenCV")
    parser.add_argument("video_path", help="Path to input video file")
    parser.add_argument("--threshold", type=float, default=0.015, 
                       help="Motion threshold (0.015 = 1.5%% pixel change)")
    parser.add_argument("--interval", type=float, default=0.5,
                       help="Minimum seconds between extracted frames")
    
    args = parser.parse_args()
    
    if not os.path.exists(args.video_path):
        print(f"Error: Video file not found: {args.video_path}")
        return
    
    extract_motion_frames_fast(args.video_path, args.threshold, args.interval)


if __name__ == "__main__":
    main() 