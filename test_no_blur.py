#!/usr/bin/env python3
"""
Test script to demonstrate the effect of blur on motion detection.
"""

import cv2
import numpy as np

def motion_without_blur(frame1, frame2):
    """Calculate motion without any blur."""
    gray1 = cv2.cvtColor(frame1, cv2.COLOR_BGR2GRAY)
    gray2 = cv2.cvtColor(frame2, cv2.COLOR_BGR2GRAY)
    
    diff = cv2.absdiff(gray1, gray2)
    _, thresh = cv2.threshold(diff, 20, 255, cv2.THRESH_BINARY)
    
    changed_pixels = cv2.countNonZero(thresh)
    total_pixels = thresh.shape[0] * thresh.shape[1]
    return changed_pixels / total_pixels

def motion_with_blur(frame1, frame2):
    """Calculate motion with box filter blur."""
    gray1 = cv2.cvtColor(frame1, cv2.COLOR_BGR2GRAY)
    gray2 = cv2.cvtColor(frame2, cv2.COLOR_BGR2GRAY)
    
    # Apply box filter blur
    gray1 = cv2.boxFilter(gray1, -1, (5, 5))
    gray2 = cv2.boxFilter(gray2, -1, (5, 5))
    
    diff = cv2.absdiff(gray1, gray2)
    _, thresh = cv2.threshold(diff, 20, 255, cv2.THRESH_BINARY)
    
    changed_pixels = cv2.countNonZero(thresh)
    total_pixels = thresh.shape[0] * thresh.shape[1]
    return changed_pixels / total_pixels

def compare_methods(video_path):
    """Compare motion detection with and without blur."""
    cap = cv2.VideoCapture(video_path)
    
    ret, prev_frame = cap.read()
    if not ret:
        return
    
    frame_count = 0
    
    print("Frame | No Blur Motion | With Blur Motion | Difference")
    print("-" * 55)
    
    while frame_count < 20:  # Test first 20 frames
        ret, current_frame = cap.read()
        if not ret:
            break
        
        motion_no_blur = motion_without_blur(prev_frame, current_frame)
        motion_with_blur_val = motion_with_blur(prev_frame, current_frame)
        
        difference = motion_no_blur - motion_with_blur_val
        
        print(f"{frame_count:5d} | {motion_no_blur:12.4f} | {motion_with_blur_val:14.4f} | {difference:+10.4f}")
        
        prev_frame = current_frame
        frame_count += 1
    
    cap.release()

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        compare_methods(sys.argv[1])
    else:
        print("Usage: python test_no_blur.py video_path") 