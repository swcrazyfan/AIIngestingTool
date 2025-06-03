#!/usr/bin/env python3
"""
Enhanced motion-based frame extractor using OpenCV optical flow.

This script uses OpenCV's Farneback optical flow algorithm for more
accurate motion detection, particularly for subtle movements like head turns.
"""

import cv2
import os
import numpy as np
import argparse
from pathlib import Path
import time


def create_output_directory(video_path: str, method: str = "opencv") -> str:
    """Create output directory for extracted frames."""
    video_name = Path(video_path).stem
    output_dir = f"{video_name}_motion_frames_{method}"
    os.makedirs(output_dir, exist_ok=True)
    return output_dir


def calculate_optical_flow_motion(frame1: np.ndarray, frame2: np.ndarray) -> tuple[float, float]:
    """
    Calculate motion using Farneback optical flow.
    
    Returns:
        tuple: (overall_motion_score, directional_motion_score)
    """
    # Convert to grayscale
    gray1 = cv2.cvtColor(frame1, cv2.COLOR_BGR2GRAY)
    gray2 = cv2.cvtColor(frame2, cv2.COLOR_BGR2GRAY)
    
    # Use dense optical flow (Farneback)
    flow = cv2.calcOpticalFlowFarneback(
        gray1, gray2, None, 
        pyr_scale=0.5,      # Pyramid scale
        levels=3,           # Number of pyramid levels
        winsize=15,         # Window size
        iterations=3,       # Number of iterations
        poly_n=5,          # Polynomial neighborhood size
        poly_sigma=1.2,    # Gaussian standard deviation
        flags=0
    )
    
    # Calculate magnitude and angle of flow vectors
    magnitude, angle = cv2.cartToPolar(flow[..., 0], flow[..., 1])
    
    # Overall motion score (mean magnitude)
    overall_motion = np.mean(magnitude)
    
    # Directional motion score (variance in angles - indicates turning/rotation)
    angle_variance = np.var(angle[magnitude > 0.5])  # Only consider significant motion
    directional_motion = angle_variance if not np.isnan(angle_variance) else 0
    
    return overall_motion, directional_motion


def calculate_background_subtraction_motion(frame: np.ndarray, bg_subtractor) -> float:
    """Calculate motion using background subtraction."""
    # Apply background subtraction
    fg_mask = bg_subtractor.apply(frame)
    
    # Calculate percentage of foreground pixels
    fg_pixels = cv2.countNonZero(fg_mask)
    total_pixels = fg_mask.shape[0] * fg_mask.shape[1]
    motion_score = fg_pixels / total_pixels
    
    return motion_score


def calculate_feature_tracking_motion(frame1: np.ndarray, frame2: np.ndarray, 
                                    prev_features=None) -> tuple[float, np.ndarray]:
    """Calculate motion using feature tracking."""
    gray1 = cv2.cvtColor(frame1, cv2.COLOR_BGR2GRAY)
    gray2 = cv2.cvtColor(frame2, cv2.COLOR_BGR2GRAY)
    
    # Detect features in first frame if not provided
    if prev_features is None or len(prev_features) < 10:
        # Parameters for corner detection
        feature_params = dict(
            maxCorners=100,
            qualityLevel=0.3,
            minDistance=7,
            blockSize=7
        )
        prev_features = cv2.goodFeaturesToTrack(gray1, mask=None, **feature_params)
    
    if prev_features is None or len(prev_features) == 0:
        return 0.0, np.array([])
    
    # Parameters for Lucas-Kanade optical flow
    lk_params = dict(
        winSize=(15, 15),
        maxLevel=2,
        criteria=(cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 10, 0.03)
    )
    
    # Calculate optical flow
    next_features, status, error = cv2.calcOpticalFlowPyrLK(
        gray1, gray2, prev_features, None, **lk_params
    )
    
    # Select good points
    if next_features is not None:
        good_new = next_features[status == 1]
        good_old = prev_features[status == 1]
        
        if len(good_new) > 0:
            # Calculate motion vectors
            motion_vectors = good_new - good_old
            motion_magnitudes = np.sqrt(motion_vectors[:, 0]**2 + motion_vectors[:, 1]**2)
            avg_motion = np.mean(motion_magnitudes)
            
            return avg_motion, good_new.reshape(-1, 1, 2)
    
    return 0.0, np.array([])


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


def extract_motion_frames_opencv(video_path: str, motion_threshold: float = 2.0, 
                                min_interval: float = 0.5, method: str = "optical_flow"):
    """
    Extract frames using OpenCV's advanced motion detection.
    
    Args:
        video_path: Path to input video file
        motion_threshold: Motion threshold (adjusted for optical flow scale)
        min_interval: Minimum seconds between extracted frames
        method: 'optical_flow', 'background_subtraction', or 'feature_tracking'
    """
    print(f"Processing video with OpenCV {method}: {video_path}")
    
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
    print(f"Motion threshold: {motion_threshold:.3f}")
    print(f"Method: {method}")
    print(f"Minimum interval between frames: {min_interval}s")
    
    # Create output directory
    output_dir = create_output_directory(video_path, method)
    print(f"Output directory: {output_dir}")
    
    # Initialize background subtractor if needed
    bg_subtractor = None
    if method == "background_subtraction":
        bg_subtractor = cv2.createBackgroundSubtractorMOG2(detectShadows=True)
    
    # Initialize variables
    ret, prev_frame = cap.read()
    if not ret:
        print("Error: Could not read first frame")
        return
    
    frame_count = 0
    extracted_count = 0
    last_extracted_time = -min_interval
    features = None
    
    # JPEG quality for ~1000kbps equivalent
    jpeg_quality = 85
    
    print(f"\nExtracting frames using {method}...")
    start_time = time.time()
    
    while True:
        ret, current_frame = cap.read()
        if not ret:
            break
        
        frame_count += 1
        current_time = frame_count / fps
        
        # Calculate motion score based on method
        if method == "optical_flow":
            overall_motion, directional_motion = calculate_optical_flow_motion(prev_frame, current_frame)
            motion_score = overall_motion
            motion_info = f"overall:{overall_motion:.3f}, directional:{directional_motion:.3f}"
        elif method == "background_subtraction":
            motion_score = calculate_background_subtraction_motion(current_frame, bg_subtractor)
            motion_info = f"fg_ratio:{motion_score:.4f}"
        elif method == "feature_tracking":
            motion_score, features = calculate_feature_tracking_motion(prev_frame, current_frame, features)
            motion_info = f"avg_displacement:{motion_score:.3f}, features:{len(features) if features is not None else 0}"
        else:
            print(f"Unknown method: {method}")
            return
        
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
            
            print(f"  Extracted: {filename} ({motion_info})")
        
        # Update previous frame
        prev_frame = current_frame.copy()
        
        # Progress indicator
        if frame_count % int(fps * 10) == 0:  # Every 10 seconds
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
    parser = argparse.ArgumentParser(description="Extract motion-based frames using OpenCV")
    parser.add_argument("video_path", help="Path to input video file")
    parser.add_argument("--threshold", type=float, default=2.0, 
                       help="Motion threshold (scale varies by method)")
    parser.add_argument("--interval", type=float, default=0.5,
                       help="Minimum seconds between extracted frames")
    parser.add_argument("--method", choices=["optical_flow", "background_subtraction", "feature_tracking"],
                       default="optical_flow", help="Motion detection method")
    
    args = parser.parse_args()
    
    if not os.path.exists(args.video_path):
        print(f"Error: Video file not found: {args.video_path}")
        return
    
    extract_motion_frames_opencv(args.video_path, args.threshold, args.interval, args.method)


if __name__ == "__main__":
    main() 