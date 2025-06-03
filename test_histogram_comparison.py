#!/usr/bin/env python3
"""
Test histogram comparison vs frame differencing for motion detection.
"""

import cv2
import numpy as np
import time

def motion_with_frame_diff(frame1, frame2):
    """Our current frame differencing method."""
    gray1 = cv2.cvtColor(frame1, cv2.COLOR_BGR2GRAY)
    gray2 = cv2.cvtColor(frame2, cv2.COLOR_BGR2GRAY)
    
    gray1 = cv2.boxFilter(gray1, -1, (5, 5))
    gray2 = cv2.boxFilter(gray2, -1, (5, 5))
    
    diff = cv2.absdiff(gray1, gray2)
    _, thresh = cv2.threshold(diff, 20, 255, cv2.THRESH_BINARY)
    
    changed_pixels = cv2.countNonZero(thresh)
    total_pixels = thresh.shape[0] * thresh.shape[1]
    return changed_pixels / total_pixels

def motion_with_histogram(frame1, frame2):
    """Motion detection using histogram comparison."""
    # Convert to HSV for better color representation
    hsv1 = cv2.cvtColor(frame1, cv2.COLOR_BGR2HSV)
    hsv2 = cv2.cvtColor(frame2, cv2.COLOR_BGR2HSV)
    
    # Calculate histograms for each channel
    hist1_h = cv2.calcHist([hsv1], [0], None, [50], [0, 180])
    hist1_s = cv2.calcHist([hsv1], [1], None, [60], [0, 256])
    hist1_v = cv2.calcHist([hsv1], [2], None, [60], [0, 256])
    
    hist2_h = cv2.calcHist([hsv2], [0], None, [50], [0, 180])
    hist2_s = cv2.calcHist([hsv2], [1], None, [60], [0, 256])
    hist2_v = cv2.calcHist([hsv2], [2], None, [60], [0, 256])
    
    # Compare histograms using correlation
    corr_h = cv2.compareHist(hist1_h, hist2_h, cv2.HISTCMP_CORREL)
    corr_s = cv2.compareHist(hist1_s, hist2_s, cv2.HISTCMP_CORREL)
    corr_v = cv2.compareHist(hist1_v, hist2_v, cv2.HISTCMP_CORREL)
    
    # Average correlation (1.0 = identical, lower = more different)
    avg_correlation = (corr_h + corr_s + corr_v) / 3.0
    
    # Return difference (higher = more motion)
    return 1.0 - avg_correlation

def test_comparison(video_path, num_frames=30):
    """Compare both methods."""
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        return
    
    ret, prev_frame = cap.read()
    if not ret:
        return
    
    print("Testing Histogram vs Frame Differencing")
    print(f"{'Frame':<6} {'FrameDiff':<12} {'Histogram':<12} {'Time(ms)':<15}")
    print("-" * 50)
    
    frame_diff_times = []
    histogram_times = []
    
    for frame_num in range(num_frames):
        ret, current_frame = cap.read()
        if not ret:
            break
        
        # Test frame differencing
        start = time.time()
        frame_diff_score = motion_with_frame_diff(prev_frame, current_frame)
        frame_diff_time = (time.time() - start) * 1000
        frame_diff_times.append(frame_diff_time)
        
        # Test histogram
        start = time.time()
        histogram_score = motion_with_histogram(prev_frame, current_frame)
        histogram_time = (time.time() - start) * 1000
        histogram_times.append(histogram_time)
        
        print(f"{frame_num:<6} {frame_diff_score:<12.4f} {histogram_score:<12.4f} {frame_diff_time:.1f}/{histogram_time:.1f}")
        
        prev_frame = current_frame
    
    cap.release()
    
    # Summary
    avg_frame_diff = np.mean(frame_diff_times)
    avg_histogram = np.mean(histogram_times)
    
    print(f"\nSUMMARY:")
    print(f"Frame Differencing: {avg_frame_diff:.1f}ms avg ({1000/avg_frame_diff:.1f} FPS)")
    print(f"Histogram Method:   {avg_histogram:.1f}ms avg ({1000/avg_histogram:.1f} FPS)")
    print(f"Speed difference:   Histogram is {avg_frame_diff/avg_histogram:.1f}x {'faster' if avg_histogram < avg_frame_diff else 'slower'}")

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        test_comparison(sys.argv[1])
    else:
        print("Usage: python test_histogram_comparison.py video_path") 