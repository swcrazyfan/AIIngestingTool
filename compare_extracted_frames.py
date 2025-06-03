#!/usr/bin/env python3
"""
Compare the actual extracted frames between FFmpeg and OpenCV methods.
Analyze which method captures more meaningful motion events.
"""

import cv2
import numpy as np
import os
from pathlib import Path
import matplotlib.pyplot as plt
from datetime import datetime

def analyze_frame_timestamps(opencv_dir, ffmpeg_dir, video_duration):
    """Analyze the distribution of extracted frames across the video timeline."""
    
    print("FRAME TIMESTAMP ANALYSIS")
    print("=" * 60)
    
    # Get OpenCV frames and timestamps
    opencv_files = sorted(list(Path(opencv_dir).glob('motion_*.jpg')))
    opencv_timestamps = []
    
    for f in opencv_files:
        # Extract timestamp from filename like "motion_0001_0.083s.jpg"
        parts = f.stem.split('_')
        if len(parts) >= 3:
            timestamp_str = parts[2].replace('s', '')
            try:
                timestamp = float(timestamp_str)
                opencv_timestamps.append(timestamp)
            except ValueError:
                continue
    
    # Get FFmpeg frames (frame numbers, convert to approximate timestamps)
    ffmpeg_files = sorted(list(Path(ffmpeg_dir).glob('scene_*.jpg')))
    ffmpeg_timestamps = []
    
    # For FFmpeg, we need to estimate timestamps from frame numbers
    # Assume 24 FPS for rough estimation
    for f in ffmpeg_files:
        parts = f.stem.split('_')
        if len(parts) >= 2:
            try:
                frame_num = int(parts[1])
                # Rough timestamp estimation (24 FPS)
                timestamp = frame_num / 24.0
                ffmpeg_timestamps.append(timestamp)
            except ValueError:
                continue
    
    print(f"Video Duration: {video_duration:.2f}s")
    print(f"OpenCV Frames: {len(opencv_timestamps)} at timestamps:")
    print(f"  {[f'{t:.2f}s' for t in opencv_timestamps[:10]]}{'...' if len(opencv_timestamps) > 10 else ''}")
    print(f"FFmpeg Frames: {len(ffmpeg_timestamps)} at estimated timestamps:")
    print(f"  {[f'{t:.2f}s' for t in ffmpeg_timestamps[:10]]}{'...' if len(ffmpeg_timestamps) > 10 else ''}")
    
    # Calculate temporal distribution
    if opencv_timestamps:
        opencv_span = max(opencv_timestamps) - min(opencv_timestamps)
        opencv_density = len(opencv_timestamps) / video_duration
    else:
        opencv_span = 0
        opencv_density = 0
        
    if ffmpeg_timestamps:
        ffmpeg_span = max(ffmpeg_timestamps) - min(ffmpeg_timestamps)
        ffmpeg_density = len(ffmpeg_timestamps) / video_duration
    else:
        ffmpeg_span = 0
        ffmpeg_density = 0
    
    print(f"\nTEMPORAL COVERAGE:")
    print(f"OpenCV: {opencv_span:.2f}s span, {opencv_density:.2f} frames/sec")
    print(f"FFmpeg: {ffmpeg_span:.2f}s span, {ffmpeg_density:.2f} frames/sec")
    
    return opencv_timestamps, ffmpeg_timestamps

def analyze_frame_differences(opencv_dir, ffmpeg_dir):
    """Analyze visual differences between consecutive frames to assess motion capture."""
    
    print("\nFRAME MOTION ANALYSIS")
    print("=" * 60)
    
    def calculate_frame_differences(frame_dir, method_name):
        """Calculate visual differences between consecutive frames."""
        frame_files = sorted(list(Path(frame_dir).glob('*.jpg')))
        if len(frame_files) < 2:
            print(f"{method_name}: Not enough frames for analysis")
            return []
        
        differences = []
        prev_frame = None
        
        for i, frame_file in enumerate(frame_files[:10]):  # Analyze first 10 frames
            frame = cv2.imread(str(frame_file), cv2.IMREAD_GRAYSCALE)
            if frame is None:
                continue
                
            if prev_frame is not None:
                # Calculate frame difference
                diff = cv2.absdiff(prev_frame, frame)
                mean_diff = np.mean(diff)
                differences.append(mean_diff)
            
            prev_frame = frame
        
        return differences
    
    opencv_diffs = calculate_frame_differences(opencv_dir, "OpenCV")
    ffmpeg_diffs = calculate_frame_differences(ffmpeg_dir, "FFmpeg")
    
    print(f"OpenCV frame differences (mean): {np.mean(opencv_diffs) if opencv_diffs else 0:.2f}")
    print(f"FFmpeg frame differences (mean): {np.mean(ffmpeg_diffs) if ffmpeg_diffs else 0:.2f}")
    
    if opencv_diffs and ffmpeg_diffs:
        opencv_avg = np.mean(opencv_diffs)
        ffmpeg_avg = np.mean(ffmpeg_diffs)
        
        if opencv_avg > ffmpeg_avg:
            print("→ OpenCV captures more visual change between frames")
        else:
            print("→ FFmpeg captures more visual change between frames")
    
    return opencv_diffs, ffmpeg_diffs

def show_frame_samples(opencv_dir, ffmpeg_dir, max_samples=5):
    """Display sample frames from both methods for visual comparison."""
    
    print(f"\nFRAME SAMPLES COMPARISON")
    print("=" * 60)
    
    opencv_files = sorted(list(Path(opencv_dir).glob('motion_*.jpg')))[:max_samples]
    ffmpeg_files = sorted(list(Path(ffmpeg_dir).glob('scene_*.jpg')))[:max_samples]
    
    print(f"OpenCV Sample Frames ({len(opencv_files)}):")
    for f in opencv_files:
        # Get file size
        size_kb = f.stat().st_size / 1024
        print(f"  {f.name} ({size_kb:.1f}KB)")
    
    print(f"\nFFmpeg Sample Frames ({len(ffmpeg_files)}):")
    for f in ffmpeg_files:
        size_kb = f.stat().st_size / 1024
        print(f"  {f.name} ({size_kb:.1f}KB)")

def analyze_frame_quality_metrics(opencv_dir, ffmpeg_dir):
    """Analyze image quality metrics of extracted frames."""
    
    print(f"\nFRAME QUALITY ANALYSIS")
    print("=" * 60)
    
    def get_quality_metrics(frame_dir, method_name):
        """Calculate quality metrics for frames in a directory."""
        frame_files = sorted(list(Path(frame_dir).glob('*.jpg')))
        
        total_size = 0
        sharpness_scores = []
        
        for frame_file in frame_files:
            # File size
            total_size += frame_file.stat().st_size
            
            # Sharpness (Laplacian variance)
            frame = cv2.imread(str(frame_file), cv2.IMREAD_GRAYSCALE)
            if frame is not None:
                laplacian_var = cv2.Laplacian(frame, cv2.CV_64F).var()
                sharpness_scores.append(laplacian_var)
        
        avg_size = total_size / len(frame_files) / 1024 if frame_files else 0
        avg_sharpness = np.mean(sharpness_scores) if sharpness_scores else 0
        
        return avg_size, avg_sharpness, len(frame_files)
    
    opencv_size, opencv_sharp, opencv_count = get_quality_metrics(opencv_dir, "OpenCV")
    ffmpeg_size, ffmpeg_sharp, ffmpeg_count = get_quality_metrics(ffmpeg_dir, "FFmpeg")
    
    print(f"{'Method':<10} {'Frames':<8} {'Avg Size(KB)':<12} {'Avg Sharpness':<12} {'Efficiency':<12}")
    print("-" * 60)
    print(f"{'OpenCV':<10} {opencv_count:<8} {opencv_size:<12.1f} {opencv_sharp:<12.1f} {'Baseline':<12}")
    
    if ffmpeg_count > 0:
        size_ratio = opencv_size / ffmpeg_size if ffmpeg_size > 0 else float('inf')
        sharp_ratio = opencv_sharp / ffmpeg_sharp if ffmpeg_sharp > 0 else float('inf')
        print(f"{'FFmpeg':<10} {ffmpeg_count:<8} {ffmpeg_size:<12.1f} {ffmpeg_sharp:<12.1f} {size_ratio:.1f}x size")
    else:
        print(f"{'FFmpeg':<10} {ffmpeg_count:<8} {'N/A':<12} {'N/A':<12} {'No frames':<12}")

def main():
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python compare_extracted_frames.py video_name")
        print("Example: python compare_extracted_frames.py MVI_0484")
        return
    
    video_name = sys.argv[1]
    opencv_dir = f"{video_name}_opencv_comparison"
    ffmpeg_dir = f"{video_name}_ffmpeg_comparison"
    
    # Check if directories exist
    if not os.path.exists(opencv_dir):
        print(f"OpenCV directory not found: {opencv_dir}")
        print("Run the comparison script first!")
        return
        
    if not os.path.exists(ffmpeg_dir):
        print(f"FFmpeg directory not found: {ffmpeg_dir}")
        print("Run the comparison script first!")
        return
    
    print("FRAME EXTRACTION ACCURACY COMPARISON")
    print("=" * 80)
    print(f"Comparing: {opencv_dir} vs {ffmpeg_dir}")
    print()
    
    # Estimate video duration (you might want to pass this as parameter)
    video_duration = 15.85 if 'MVI_0484' in video_name else 6.01  # Rough estimates
    
    # Analyze timestamps and distribution
    opencv_timestamps, ffmpeg_timestamps = analyze_frame_timestamps(
        opencv_dir, ffmpeg_dir, video_duration
    )
    
    # Analyze frame differences (motion detection quality)
    opencv_diffs, ffmpeg_diffs = analyze_frame_differences(opencv_dir, ffmpeg_dir)
    
    # Show frame samples
    show_frame_samples(opencv_dir, ffmpeg_dir)
    
    # Analyze quality metrics
    analyze_frame_quality_metrics(opencv_dir, ffmpeg_dir)
    
    # Final recommendation
    print(f"\nFINAL RECOMMENDATION FOR MOTION CAPTURE:")
    print("=" * 60)
    
    opencv_count = len(list(Path(opencv_dir).glob('*.jpg')))
    ffmpeg_count = len(list(Path(ffmpeg_dir).glob('*.jpg')))
    
    if opencv_count > ffmpeg_count * 2:
        print("✓ OpenCV is BETTER for motion capture:")
        print("  - Captures more motion events")
        print("  - Better temporal coverage")
        print("  - More suitable for head turns and gestures")
    elif ffmpeg_count > opencv_count:
        print("? FFmpeg found more significant changes:")
        print("  - May be better for scene transitions")
        print("  - Consider if you need scene changes vs motion")
    else:
        print("≈ Methods are comparable:")
        print("  - Consider your specific use case")
        print("  - OpenCV better for within-scene motion")
        print("  - FFmpeg better for scene changes")

if __name__ == "__main__":
    main() 