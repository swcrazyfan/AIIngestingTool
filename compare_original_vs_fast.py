#!/usr/bin/env python3
"""
Compare original motion_frame_extractor.py vs fast version.
"""

import cv2
import numpy as np
import time

def motion_original(frame1, frame2):
    """Original method with Gaussian blur."""
    # Convert to grayscale
    gray1 = cv2.cvtColor(frame1, cv2.COLOR_BGR2GRAY)
    gray2 = cv2.cvtColor(frame2, cv2.COLOR_BGR2GRAY)
    
    # Apply Gaussian blur (EXPENSIVE)
    gray1 = cv2.GaussianBlur(gray1, (21, 21), 0)
    gray2 = cv2.GaussianBlur(gray2, (21, 21), 0)
    
    # Calculate absolute difference
    diff = cv2.absdiff(gray1, gray2)
    
    # Apply threshold
    _, thresh = cv2.threshold(diff, 25, 255, cv2.THRESH_BINARY)
    
    # Calculate percentage
    changed_pixels = cv2.countNonZero(thresh)
    total_pixels = thresh.shape[0] * thresh.shape[1]
    return changed_pixels / total_pixels

def motion_fast(frame1, frame2):
    """Fast method with box filter + morphology."""
    # Convert to grayscale
    gray1 = cv2.cvtColor(frame1, cv2.COLOR_BGR2GRAY)
    gray2 = cv2.cvtColor(frame2, cv2.COLOR_BGR2GRAY)
    
    # Use box filter (FAST)
    gray1 = cv2.boxFilter(gray1, -1, (5, 5))
    gray2 = cv2.boxFilter(gray2, -1, (5, 5))
    
    # Calculate absolute difference
    diff = cv2.absdiff(gray1, gray2)
    
    # Apply threshold
    _, thresh = cv2.threshold(diff, 20, 255, cv2.THRESH_BINARY)
    
    # Morphological operations (NOISE REDUCTION)
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    thresh = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, kernel)
    thresh = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)
    
    # Calculate percentage
    changed_pixels = cv2.countNonZero(thresh)
    total_pixels = thresh.shape[0] * thresh.shape[1]
    return changed_pixels / total_pixels

def compare_methods(video_path, num_frames=50):
    """Compare both methods side by side."""
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        print(f"Error: Could not open {video_path}")
        return
    
    fps = cap.get(cv2.CAP_PROP_FPS)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    
    print(f"Comparing Original vs Fast Motion Detection")
    print(f"Video: {total_frames} frames, {fps:.1f} FPS")
    print(f"Testing first {num_frames} frames")
    print()
    
    ret, prev_frame = cap.read()
    if not ret:
        return
    
    # Track results
    original_times = []
    fast_times = []
    original_scores = []
    fast_scores = []
    
    print(f"{'Frame':<6} {'Original':<12} {'Fast':<12} {'Time(ms)':<20} {'Difference':<12}")
    print("-" * 70)
    
    for frame_num in range(num_frames):
        ret, current_frame = cap.read()
        if not ret:
            break
        
        # Test original method
        start = time.time()
        original_score = motion_original(prev_frame, current_frame)
        original_time = (time.time() - start) * 1000
        original_times.append(original_time)
        original_scores.append(original_score)
        
        # Test fast method
        start = time.time()
        fast_score = motion_fast(prev_frame, current_frame)
        fast_time = (time.time() - start) * 1000
        fast_times.append(fast_time)
        fast_scores.append(fast_score)
        
        # Calculate score difference
        score_diff = abs(original_score - fast_score)
        
        print(f"{frame_num:<6} {original_score:<12.4f} {fast_score:<12.4f} {original_time:.1f}/{fast_time:.1f}{'':<8} {score_diff:<12.4f}")
        
        prev_frame = current_frame
    
    cap.release()
    
    # Calculate statistics
    avg_original_time = np.mean(original_times)
    avg_fast_time = np.mean(fast_times)
    avg_score_diff = np.mean([abs(o - f) for o, f in zip(original_scores, fast_scores)])
    
    original_fps = 1000 / avg_original_time
    fast_fps = 1000 / avg_fast_time
    speedup = avg_original_time / avg_fast_time
    
    print("\n" + "="*70)
    print("PERFORMANCE COMPARISON:")
    print("="*70)
    print(f"{'Method':<12} {'Avg Time(ms)':<15} {'FPS':<10} {'Speedup':<10}")
    print("-" * 50)
    print(f"{'Original':<12} {avg_original_time:<15.1f} {original_fps:<10.1f} {'1.0x':<10}")
    print(f"{'Fast':<12} {avg_fast_time:<15.1f} {fast_fps:<10.1f} {speedup:<10.1f}x")
    
    print(f"\nACCURACY COMPARISON:")
    print(f"Average score difference: {avg_score_diff:.4f}")
    print(f"Score correlation: {np.corrcoef(original_scores, fast_scores)[0,1]:.3f}")
    
    # Check how many frames would be detected at different thresholds
    thresholds = [0.01, 0.015, 0.02, 0.025, 0.03]
    print(f"\nFRAME DETECTION AT DIFFERENT THRESHOLDS:")
    print(f"{'Threshold':<12} {'Original':<10} {'Fast':<10} {'Difference':<12}")
    print("-" * 50)
    
    for thresh in thresholds:
        orig_detections = sum(1 for score in original_scores if score > thresh)
        fast_detections = sum(1 for score in fast_scores if score > thresh)
        diff = abs(orig_detections - fast_detections)
        print(f"{thresh:<12} {orig_detections:<10} {fast_detections:<10} {diff:<12}")

def main():
    import sys
    if len(sys.argv) > 1:
        compare_methods(sys.argv[1])
    else:
        print("Usage: python compare_original_vs_fast.py video_path")

if __name__ == "__main__":
    main() 