#!/usr/bin/env python3
"""
Compare FFmpeg scene detection vs Fast OpenCV motion detection.
Shows the fundamental differences in their detection capabilities.
"""

import cv2
import numpy as np
import subprocess
import time
import os
import tempfile
import json
from pathlib import Path

def ffmpeg_scene_detection(video_path, threshold=0.3, output_dir=None):
    """
    Use FFmpeg scene detection to extract frames.
    
    Args:
        video_path: Path to video file
        threshold: Scene detection threshold (0.0-1.0)
        output_dir: Directory to save extracted frames
    
    Returns:
        List of timestamps where scenes change
    """
    print(f"Running FFmpeg scene detection (threshold={threshold})...")
    
    if output_dir is None:
        output_dir = tempfile.mkdtemp()
    
    # FFmpeg command for scene detection
    cmd = [
        'ffmpeg', '-i', video_path,
        '-vf', f'select=gt(scene\\,{threshold}),scale=854:480',
        '-fps_mode', 'vfr',
        '-frame_pts', '1',
        os.path.join(output_dir, 'scene_%d.jpg'),
        '-y'  # Overwrite existing files
    ]
    
    start_time = time.time()
    
    try:
        # Run FFmpeg and capture output
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        processing_time = time.time() - start_time
        
        if result.returncode != 0:
            print(f"FFmpeg error: {result.stderr}")
            return [], processing_time, []
        
        # Count extracted frames
        frame_files = list(Path(output_dir).glob('scene_*.jpg'))
        frame_count = len(frame_files)
        
        print(f"FFmpeg extracted {frame_count} frames in {processing_time:.2f}s")
        
        # Extract timestamps from filenames (FFmpeg frame_pts naming)
        timestamps = []
        for frame_file in sorted(frame_files):
            # Try to extract timestamp from filename or file modification time
            # This is approximate since FFmpeg scene detection doesn't give precise timestamps
            frame_num = int(frame_file.stem.split('_')[1])
            timestamps.append(frame_num)  # Frame numbers, not precise timestamps
        
        return timestamps, processing_time, frame_files
        
    except subprocess.TimeoutExpired:
        print("FFmpeg timed out after 30 seconds")
        return [], 30.0, []
    except Exception as e:
        print(f"FFmpeg error: {e}")
        return [], time.time() - start_time, []

def fast_opencv_motion_detection(video_path, threshold=0.02, output_dir=None):
    """
    Use fast OpenCV motion detection to extract frames.
    
    Args:
        video_path: Path to video file
        threshold: Motion detection threshold
        output_dir: Directory to save extracted frames
    
    Returns:
        List of timestamps where motion is detected
    """
    print(f"Running Fast OpenCV motion detection (threshold={threshold})...")
    
    if output_dir is None:
        output_dir = tempfile.mkdtemp()
    
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        print(f"Error: Could not open {video_path}")
        return [], 0, []
    
    fps = cap.get(cv2.CAP_PROP_FPS)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    
    start_time = time.time()
    
    ret, prev_frame = cap.read()
    if not ret:
        return [], 0, []
    
    # Resize to 480p for consistency with FFmpeg
    height, width = prev_frame.shape[:2]
    new_width = 854
    new_height = 480
    prev_frame = cv2.resize(prev_frame, (new_width, new_height))
    
    motion_timestamps = []
    frame_files = []
    frame_count = 0
    
    for frame_num in range(1, total_frames):
        ret, current_frame = cap.read()
        if not ret:
            break
        
        # Resize current frame
        current_frame = cv2.resize(current_frame, (new_width, new_height))
        
        # Fast motion detection
        gray1 = cv2.cvtColor(prev_frame, cv2.COLOR_BGR2GRAY)
        gray2 = cv2.cvtColor(current_frame, cv2.COLOR_BGR2GRAY)
        
        # Use box filter (fast)
        gray1 = cv2.boxFilter(gray1, -1, (5, 5))
        gray2 = cv2.boxFilter(gray2, -1, (5, 5))
        
        # Calculate difference
        diff = cv2.absdiff(gray1, gray2)
        _, thresh = cv2.threshold(diff, 20, 255, cv2.THRESH_BINARY)
        
        # Morphological operations
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
        thresh = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, kernel)
        thresh = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)
        
        # Calculate motion percentage
        changed_pixels = cv2.countNonZero(thresh)
        total_pixels = thresh.shape[0] * thresh.shape[1]
        motion_percentage = changed_pixels / total_pixels
        
        # Check if motion exceeds threshold
        if motion_percentage > threshold:
            timestamp = frame_num / fps
            motion_timestamps.append(timestamp)
            
            # Save frame
            frame_filename = os.path.join(output_dir, f'motion_{frame_count:04d}_{timestamp:.3f}s.jpg')
            cv2.imwrite(frame_filename, current_frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
            frame_files.append(frame_filename)
            frame_count += 1
        
        prev_frame = current_frame
    
    cap.release()
    processing_time = time.time() - start_time
    
    print(f"OpenCV extracted {len(motion_timestamps)} frames in {processing_time:.2f}s")
    
    return motion_timestamps, processing_time, frame_files

def analyze_video_properties(video_path):
    """Get basic video properties."""
    cap = cv2.VideoCapture(video_path)
    fps = cap.get(cv2.CAP_PROP_FPS)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    duration = total_frames / fps
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    cap.release()
    
    return {
        'fps': fps,
        'total_frames': total_frames,
        'duration': duration,
        'resolution': f"{width}x{height}"
    }

def compare_methods(video_path):
    """Compare FFmpeg vs Fast OpenCV motion detection."""
    print("="*80)
    print("FFMPEG vs FAST OPENCV MOTION DETECTION COMPARISON")
    print("="*80)
    
    # Analyze video properties
    props = analyze_video_properties(video_path)
    print(f"Video: {os.path.basename(video_path)}")
    print(f"Duration: {props['duration']:.2f}s")
    print(f"FPS: {props['fps']:.1f}")
    print(f"Total Frames: {props['total_frames']}")
    print(f"Resolution: {props['resolution']}")
    print()
    
    # Create local output directories based on video name
    video_name = os.path.splitext(os.path.basename(video_path))[0]
    ffmpeg_dir = f"{video_name}_ffmpeg_comparison"
    opencv_dir = f"{video_name}_opencv_comparison"
    
    # Create directories if they don't exist
    os.makedirs(ffmpeg_dir, exist_ok=True)
    os.makedirs(opencv_dir, exist_ok=True)
    
    try:
        # Test FFmpeg scene detection
        print("1. FFMPEG SCENE DETECTION")
        print("-" * 40)
        ffmpeg_timestamps, ffmpeg_time, ffmpeg_files = ffmpeg_scene_detection(
            video_path, threshold=0.01, output_dir=ffmpeg_dir
        )
        ffmpeg_fps = props['total_frames'] / ffmpeg_time if ffmpeg_time > 0 else 0
        
        # Test Fast OpenCV motion detection
        print("\n2. FAST OPENCV MOTION DETECTION")
        print("-" * 40)
        opencv_timestamps, opencv_time, opencv_files = fast_opencv_motion_detection(
            video_path, threshold=0.02, output_dir=opencv_dir
        )
        opencv_fps = props['total_frames'] / opencv_time if opencv_time > 0 else 0
        
        # Compare results
        print("\n3. COMPARISON RESULTS")
        print("="*80)
        
        print(f"{'Method':<20} {'Frames Found':<15} {'Time (s)':<12} {'Processing FPS':<15} {'Efficiency':<12}")
        print("-" * 80)
        print(f"{'FFmpeg Scene':<20} {len(ffmpeg_timestamps):<15} {ffmpeg_time:<12.2f} {ffmpeg_fps:<15.1f} {'1.0x':<12}")
        
        speedup = ffmpeg_time / opencv_time if opencv_time > 0 else float('inf')
        print(f"{'OpenCV Motion':<20} {len(opencv_timestamps):<15} {opencv_time:<12.2f} {opencv_fps:<15.1f} {speedup:<12.1f}x")
        
        print(f"\nDETECTION ANALYSIS:")
        print("-" * 40)
        print(f"FFmpeg found {len(ffmpeg_timestamps)} scene changes")
        print(f"OpenCV found {len(opencv_timestamps)} motion events")
        
        if len(ffmpeg_timestamps) > 0:
            print(f"\nFFmpeg timestamps: {ffmpeg_timestamps[:10]}{'...' if len(ffmpeg_timestamps) > 10 else ''}")
        else:
            print("\nFFmpeg: No scene changes detected (typical for single-scene videos)")
        
        if len(opencv_timestamps) > 0:
            print(f"OpenCV timestamps: {[f'{t:.2f}s' for t in opencv_timestamps[:10]]}{'...' if len(opencv_timestamps) > 10 else ''}")
        else:
            print("OpenCV: No motion detected")
        
        print(f"\nKEY DIFFERENCES:")
        print("-" * 40)
        print("• FFmpeg Scene Detection:")
        print("  - Detects scene CHANGES (cuts, transitions)")
        print("  - Poor for within-scene motion (head turns, gestures)")
        print("  - Good for editing/segmentation")
        print()
        print("• OpenCV Motion Detection:")
        print("  - Detects ANY motion within scenes")
        print("  - Excellent for head turns, gestures, movements")
        print("  - Better for extracting representative frames")
        
        # Analysis conclusion
        print(f"\nRECOMMENDATION:")
        print("-" * 40)
        if len(opencv_timestamps) > len(ffmpeg_timestamps):
            print("✓ OpenCV Motion Detection is BETTER for this video")
            print("  - Detected more motion events")
            print("  - Better for capturing head turns and subtle movements")
            print(f"  - {speedup:.1f}x faster processing")
        elif len(ffmpeg_timestamps) > 0:
            print("? FFmpeg Scene Detection found scene changes")
            print("  - May be useful for multi-scene videos")
            print("  - Consider OpenCV for within-scene motion")
        else:
            print("! Both methods found limited motion/scene changes")
            print("  - Video may have minimal motion")
            print("  - OpenCV still preferred for consistency")
        
        # Show sample extracted frames info
        print(f"\nEXTRACTED FRAMES SAVED TO:")
        print(f"FFmpeg: ./{ffmpeg_dir}/ ({len(ffmpeg_files)} files)")
        print(f"OpenCV: ./{opencv_dir}/ ({len(opencv_files)} files)")
        
    except Exception as e:
        print(f"Error during comparison: {e}")
        import traceback
        traceback.print_exc()
    
    return {
        'ffmpeg': {
            'frames': len(ffmpeg_timestamps),
            'time': ffmpeg_time,
            'timestamps': ffmpeg_timestamps,
            'files': ffmpeg_files,
            'directory': ffmpeg_dir
        },
        'opencv': {
            'frames': len(opencv_timestamps),
            'time': opencv_time,
            'timestamps': opencv_timestamps,
            'files': opencv_files,
            'directory': opencv_dir
        }
    }

def main():
    import sys
    if len(sys.argv) > 1:
        video_path = sys.argv[1]
        if not os.path.exists(video_path):
            print(f"Error: Video file not found: {video_path}")
            sys.exit(1)
        
        results = compare_methods(video_path)
        
        # Optional: Clean up temp directories
        # import shutil
        # shutil.rmtree(results['ffmpeg']['files'][0].parent if results['ffmpeg']['files'] else '/tmp')
        # shutil.rmtree(results['opencv']['files'][0].parent if results['opencv']['files'] else '/tmp')
        
    else:
        print("Usage: python compare_ffmpeg_vs_fast_opencv.py video_path")
        print()
        print("This script compares:")
        print("1. FFmpeg scene detection (detects scene changes/cuts)")
        print("2. Fast OpenCV motion detection (detects any motion)")
        print()
        print("Example:")
        print("python compare_ffmpeg_vs_fast_opencv.py test_videos/MVI_0484.MP4")

if __name__ == "__main__":
    main() 