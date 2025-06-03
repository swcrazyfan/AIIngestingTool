#!/usr/bin/env python3
"""
Compare FFmpeg scene detection vs OpenCV motion detection.
"""

import subprocess
import os
import time
from pathlib import Path

def test_ffmpeg_scene_detection(video_path: str, threshold: float = 0.1):
    """Test FFmpeg scene detection."""
    video_name = Path(video_path).stem
    output_dir = f"{video_name}_ffmpeg_scenes"
    os.makedirs(output_dir, exist_ok=True)
    
    print(f"Testing FFmpeg scene detection on: {video_path}")
    print(f"Scene threshold: {threshold}")
    
    start_time = time.time()
    
    # FFmpeg command for scene detection and frame extraction
    cmd = [
        'ffmpeg',
        '-i', video_path,
        '-vf', f'select=gt(scene,{threshold}),scale=854:480',
        '-vsync', 'vfr',
        '-q:v', '5',  # Quality setting ~equivalent to our JPEG 85
        f'{output_dir}/scene_%04d.jpg',
        '-y'  # Overwrite without asking
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        processing_time = time.time() - start_time
        
        # Count output files
        jpg_files = list(Path(output_dir).glob('*.jpg'))
        frame_count = len(jpg_files)
        
        print(f"FFmpeg completed in {processing_time:.2f}s")
        print(f"Extracted {frame_count} scene changes")
        
        if result.stderr:
            # Parse FFmpeg output for video info
            lines = result.stderr.split('\n')
            for line in lines:
                if 'fps' in line and 'Duration' in line:
                    print(f"FFmpeg info: {line.strip()}")
                    break
        
        return frame_count, processing_time
        
    except subprocess.TimeoutExpired:
        print("FFmpeg timed out!")
        return 0, 60
    except FileNotFoundError:
        print("FFmpeg not found! Please install FFmpeg.")
        return 0, 0

def test_opencv_motion_detection(video_path: str):
    """Test our OpenCV motion detection."""
    print(f"\nTesting OpenCV motion detection on: {video_path}")
    
    start_time = time.time()
    
    # Run our fast OpenCV script
    cmd = [
        'python', 'motion_frame_extractor_fast.py',
        video_path
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        processing_time = time.time() - start_time
        
        # Parse output for frame count
        frame_count = 0
        lines = result.stdout.split('\n')
        for line in lines:
            if 'Extracted' in line and 'frames from' in line:
                # Extract number from "Extracted X frames from Y total frames"
                parts = line.split()
                frame_count = int(parts[1])
                break
        
        print(f"OpenCV completed in {processing_time:.2f}s")
        print(f"Extracted {frame_count} motion frames")
        
        return frame_count, processing_time
        
    except subprocess.TimeoutExpired:
        print("OpenCV timed out!")
        return 0, 60

def compare_methods(video_path: str):
    """Compare both methods on the same video."""
    if not os.path.exists(video_path):
        print(f"Video file not found: {video_path}")
        return
    
    print("=" * 60)
    print("COMPARISON: FFmpeg Scene Detection vs OpenCV Motion Detection")
    print("=" * 60)
    
    # Test FFmpeg scene detection
    ffmpeg_frames, ffmpeg_time = test_ffmpeg_scene_detection(video_path, 0.1)
    
    # Test OpenCV motion detection  
    opencv_frames, opencv_time = test_opencv_motion_detection(video_path)
    
    # Results summary
    print("\n" + "=" * 60)
    print("RESULTS SUMMARY:")
    print("=" * 60)
    print(f"{'Method':<20} {'Frames':<10} {'Time(s)':<10} {'Speed':<15}")
    print("-" * 60)
    print(f"{'FFmpeg Scene':<20} {ffmpeg_frames:<10} {ffmpeg_time:<10.2f} {'N/A':<15}")
    print(f"{'OpenCV Motion':<20} {opencv_frames:<10} {opencv_time:<10.2f} {'N/A':<15}")
    
    if ffmpeg_time > 0 and opencv_time > 0:
        speed_ratio = ffmpeg_time / opencv_time
        print(f"\nSpeed comparison: FFmpeg is {speed_ratio:.1f}x {'slower' if speed_ratio > 1 else 'faster'} than OpenCV")
    
    print(f"\nFrame detection comparison:")
    print(f"- FFmpeg detected {ffmpeg_frames} scene changes")
    print(f"- OpenCV detected {opencv_frames} motion events")
    
    print(f"\nWhat this means:")
    print(f"- FFmpeg: Detects cuts/scene changes (good for editing)")
    print(f"- OpenCV: Detects movement within scenes (good for action/gestures)")

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        compare_methods(sys.argv[1])
    else:
        print("Usage: python compare_ffmpeg_vs_opencv.py video_path") 