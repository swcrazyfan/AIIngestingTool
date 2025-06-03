#!/usr/bin/env python3
"""
Test SIFT, ORB, and absdiff methods for motion detection.
"""

import cv2
import numpy as np
import time
import argparse
from pathlib import Path

def motion_with_absdiff(frame1, frame2):
    """Our current method using cv2.absdiff (baseline)."""
    gray1 = cv2.cvtColor(frame1, cv2.COLOR_BGR2GRAY)
    gray2 = cv2.cvtColor(frame2, cv2.COLOR_BGR2GRAY)
    
    # Box filter blur
    gray1 = cv2.boxFilter(gray1, -1, (5, 5))
    gray2 = cv2.boxFilter(gray2, -1, (5, 5))
    
    # Absolute difference
    diff = cv2.absdiff(gray1, gray2)
    _, thresh = cv2.threshold(diff, 20, 255, cv2.THRESH_BINARY)
    
    # Morphological operations
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    thresh = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, kernel)
    thresh = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)
    
    changed_pixels = cv2.countNonZero(thresh)
    total_pixels = thresh.shape[0] * thresh.shape[1]
    return changed_pixels / total_pixels

def motion_with_sift(frame1, frame2):
    """Motion detection using SIFT features."""
    gray1 = cv2.cvtColor(frame1, cv2.COLOR_BGR2GRAY)
    gray2 = cv2.cvtColor(frame2, cv2.COLOR_BGR2GRAY)
    
    # Create SIFT detector
    sift = cv2.SIFT_create(nfeatures=500)  # Limit features for speed
    
    # Detect keypoints and descriptors
    kp1, des1 = sift.detectAndCompute(gray1, None)
    kp2, des2 = sift.detectAndCompute(gray2, None)
    
    if des1 is None or des2 is None or len(des1) < 10 or len(des2) < 10:
        return 0.0
    
    # Match features using FLANN
    FLANN_INDEX_KDTREE = 1
    index_params = dict(algorithm=FLANN_INDEX_KDTREE, trees=5)
    search_params = dict(checks=50)
    flann = cv2.FlannBasedMatcher(index_params, search_params)
    
    try:
        matches = flann.knnMatch(des1, des2, k=2)
        
        # Apply Lowe's ratio test
        good_matches = []
        for match_pair in matches:
            if len(match_pair) == 2:
                m, n = match_pair
                if m.distance < 0.7 * n.distance:
                    good_matches.append(m)
        
        if len(good_matches) < 10:
            return 0.0
        
        # Calculate motion from good matches
        src_pts = np.float32([kp1[m.queryIdx].pt for m in good_matches]).reshape(-1, 1, 2)
        dst_pts = np.float32([kp2[m.trainIdx].pt for m in good_matches]).reshape(-1, 1, 2)
        
        # Calculate displacement vectors
        displacements = dst_pts - src_pts
        displacement_magnitudes = np.sqrt(displacements[:, 0, 0]**2 + displacements[:, 0, 1]**2)
        
        # Return average displacement as motion score
        return np.mean(displacement_magnitudes) / 100.0  # Scale down for comparison
        
    except Exception:
        return 0.0

def motion_with_orb(frame1, frame2):
    """Motion detection using ORB features."""
    gray1 = cv2.cvtColor(frame1, cv2.COLOR_BGR2GRAY)
    gray2 = cv2.cvtColor(frame2, cv2.COLOR_BGR2GRAY)
    
    # Create ORB detector
    orb = cv2.ORB_create(nfeatures=1000)
    
    # Detect keypoints and descriptors
    kp1, des1 = orb.detectAndCompute(gray1, None)
    kp2, des2 = orb.detectAndCompute(gray2, None)
    
    if des1 is None or des2 is None or len(des1) < 10 or len(des2) < 10:
        return 0.0
    
    # Match features using BFMatcher (better for ORB)
    bf = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True)
    matches = bf.match(des1, des2)
    
    # Sort matches by distance
    matches = sorted(matches, key=lambda x: x.distance)
    
    # Take only good matches (top 50% or max 100)
    good_matches = matches[:min(len(matches)//2, 100)]
    
    if len(good_matches) < 10:
        return 0.0
    
    # Calculate motion from good matches
    src_pts = np.float32([kp1[m.queryIdx].pt for m in good_matches]).reshape(-1, 1, 2)
    dst_pts = np.float32([kp2[m.trainIdx].pt for m in good_matches]).reshape(-1, 1, 2)
    
    # Calculate displacement vectors
    displacements = dst_pts - src_pts
    displacement_magnitudes = np.sqrt(displacements[:, 0, 0]**2 + displacements[:, 0, 1]**2)
    
    # Return average displacement as motion score
    return np.mean(displacement_magnitudes) / 100.0  # Scale down for comparison

def test_all_methods(video_path, num_frames=50):
    """Test all three methods on a video."""
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        print(f"Error: Could not open {video_path}")
        return
    
    fps = cap.get(cv2.CAP_PROP_FPS)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    
    print(f"Testing methods on: {Path(video_path).name}")
    print(f"Video: {total_frames} frames, {fps:.1f} FPS")
    print(f"Testing first {num_frames} frames")
    print()
    
    ret, prev_frame = cap.read()
    if not ret:
        return
    
    # Track results
    results = {
        'absdiff': {'scores': [], 'time': 0},
        'sift': {'scores': [], 'time': 0},
        'orb': {'scores': [], 'time': 0}
    }
    
    frame_count = 0
    
    print(f"{'Frame':<6} {'AbsDiff':<10} {'SIFT':<10} {'ORB':<10} {'Times (ms)':<20}")
    print("-" * 60)
    
    while frame_count < num_frames:
        ret, current_frame = cap.read()
        if not ret:
            break
        
        # Test absdiff method
        start_time = time.time()
        absdiff_score = motion_with_absdiff(prev_frame, current_frame)
        absdiff_time = (time.time() - start_time) * 1000
        results['absdiff']['scores'].append(absdiff_score)
        results['absdiff']['time'] += absdiff_time
        
        # Test SIFT method
        start_time = time.time()
        sift_score = motion_with_sift(prev_frame, current_frame)
        sift_time = (time.time() - start_time) * 1000
        results['sift']['scores'].append(sift_score)
        results['sift']['time'] += sift_time
        
        # Test ORB method
        start_time = time.time()
        orb_score = motion_with_orb(prev_frame, current_frame)
        orb_time = (time.time() - start_time) * 1000
        results['orb']['scores'].append(orb_score)
        results['orb']['time'] += orb_time
        
        print(f"{frame_count:<6} {absdiff_score:<10.4f} {sift_score:<10.4f} {orb_score:<10.4f} {absdiff_time:.1f}/{sift_time:.1f}/{orb_time:.1f}")
        
        prev_frame = current_frame
        frame_count += 1
    
    cap.release()
    
    # Print summary
    print("\n" + "="*60)
    print("PERFORMANCE SUMMARY:")
    print("="*60)
    
    for method, data in results.items():
        avg_score = np.mean(data['scores']) if data['scores'] else 0
        avg_time = data['time'] / len(data['scores']) if data['scores'] else 0
        max_score = np.max(data['scores']) if data['scores'] else 0
        
        print(f"{method.upper():<8} | Avg Score: {avg_score:.4f} | Max Score: {max_score:.4f} | Avg Time: {avg_time:.1f}ms")
    
    # Speed comparison
    absdiff_fps = 1000 / (results['absdiff']['time'] / len(results['absdiff']['scores']))
    sift_fps = 1000 / (results['sift']['time'] / len(results['sift']['scores']))
    orb_fps = 1000 / (results['orb']['time'] / len(results['orb']['scores']))
    
    print(f"\nProcessing Speed:")
    print(f"AbsDiff: {absdiff_fps:.1f} FPS")
    print(f"SIFT:    {sift_fps:.1f} FPS ({absdiff_fps/sift_fps:.1f}x slower)")
    print(f"ORB:     {orb_fps:.1f} FPS ({absdiff_fps/orb_fps:.1f}x slower)")

def main():
    parser = argparse.ArgumentParser(description="Compare motion detection methods")
    parser.add_argument("video_path", help="Path to input video file")
    parser.add_argument("--frames", type=int, default=50, help="Number of frames to test")
    
    args = parser.parse_args()
    
    if not Path(args.video_path).exists():
        print(f"Video file not found: {args.video_path}")
        return
    
    test_all_methods(args.video_path, args.frames)

if __name__ == "__main__":
    main() 