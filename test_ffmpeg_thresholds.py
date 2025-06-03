#!/usr/bin/env python3
"""
Test different FFmpeg scene detection thresholds to find optimal settings.
"""

import subprocess
import time
import os
from pathlib import Path

def test_ffmpeg_threshold(video_path, threshold, output_dir):
    """Test a specific FFmpeg scene detection threshold."""
    print(f"Testing threshold: {threshold}")
    
    # FFmpeg command for scene detection
    cmd = [
        'ffmpeg', '-i', video_path,
        '-vf', f'select=gt(scene\\,{threshold}),scale=854:480',
        '-fps_mode', 'vfr',
        '-frame_pts', '1',
        os.path.join(output_dir, f'scene_t{threshold}_%d.jpg'),
        '-y'  # Overwrite existing files
    ]
    
    start_time = time.time()
    
    try:
        # Run FFmpeg and capture output
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        processing_time = time.time() - start_time
        
        if result.returncode != 0:
            print(f"  FFmpeg error: {result.stderr}")
            return 0, processing_time
        
        # Count extracted frames
        frame_files = list(Path(output_dir).glob(f'scene_t{threshold}_*.jpg'))
        frame_count = len(frame_files)
        
        print(f"  Threshold {threshold}: {frame_count} frames in {processing_time:.2f}s")
        return frame_count, processing_time
        
    except subprocess.TimeoutExpired:
        print(f"  Threshold {threshold}: Timed out!")
        return 0, 30.0
    except Exception as e:
        print(f"  Threshold {threshold}: Error - {e}")
        return 0, time.time() - start_time

def main():
    import sys
    if len(sys.argv) < 2:
        print("Usage: python test_ffmpeg_thresholds.py video_path")
        return
    
    video_path = sys.argv[1]
    if not os.path.exists(video_path):
        print(f"Video not found: {video_path}")
        return
    
    video_name = os.path.splitext(os.path.basename(video_path))[0]
    output_dir = f"{video_name}_threshold_test"
    os.makedirs(output_dir, exist_ok=True)
    
    print(f"Testing FFmpeg scene detection thresholds on: {os.path.basename(video_path)}")
    print("=" * 60)
    
    # Test different thresholds
    thresholds = [0.01, 0.02, 0.05, 0.1, 0.15, 0.2]
    results = []
    
    for threshold in thresholds:
        frames, time_taken = test_ffmpeg_threshold(video_path, threshold, output_dir)
        results.append((threshold, frames, time_taken))
    
    print("\n" + "=" * 60)
    print("THRESHOLD COMPARISON RESULTS:")
    print("=" * 60)
    print(f"{'Threshold':<12} {'Frames':<8} {'Time(s)':<8} {'Recommendation':<20}")
    print("-" * 60)
    
    for threshold, frames, time_taken in results:
        rec = ""
        if frames > 0:
            rec = "✓ Found frames"
        else:
            rec = "✗ No frames"
        
        print(f"{threshold:<12} {frames:<8} {time_taken:<8.1f} {rec:<20}")
    
    print(f"\nFrames saved to: ./{output_dir}/")

if __name__ == "__main__":
    main() 