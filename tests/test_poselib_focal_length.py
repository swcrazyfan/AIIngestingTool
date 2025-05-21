#!/usr/bin/env python3
"""
Test script for estimating camera pose and focal length using PoseLib.

This script extracts frames from a video file, uses PoseLib to estimate
camera pose and focal length based on matched feature points.

Requirements:
- pip install poselib opencv-python numpy matplotlib tqdm
"""

import os
import argparse
import cv2
import numpy as np
from tqdm import tqdm
import matplotlib.pyplot as plt
import poselib
import time

def extract_frame(video_path, frame_idx):
    """Extract a specific frame from the video."""
    cap = cv2.VideoCapture(video_path)
    cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
    ret, frame = cap.read()
    cap.release()
    if not ret:
        raise ValueError(f"Could not extract frame {frame_idx} from video")
    return frame

def get_video_info(video_path):
    """Get basic information about the video."""
    cap = cv2.VideoCapture(video_path)
    fps = cap.get(cv2.CAP_PROP_FPS)
    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    cap.release()
    
    return {
        "fps": fps,
        "frame_count": frame_count,
        "width": width,
        "height": height
    }

def detect_features(frame):
    """Detect features in a frame."""
    # Convert to grayscale for feature detection
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    
    # Use SIFT for feature detection
    sift = cv2.SIFT_create()
    keypoints, descriptors = sift.detectAndCompute(gray, None)
    
    # Extract the 2D points
    p2d = np.array([kp.pt for kp in keypoints], dtype=np.float32)
    
    return {
        "keypoints": keypoints,
        "descriptors": descriptors,
        "points_2d": p2d
    }

def match_features(features1, features2):
    """Match features between two frames."""
    # Use FLANN for fast feature matching
    FLANN_INDEX_KDTREE = 1
    index_params = dict(algorithm=FLANN_INDEX_KDTREE, trees=5)
    search_params = dict(checks=50)
    flann = cv2.FlannBasedMatcher(index_params, search_params)
    
    # Match descriptors
    matches = flann.knnMatch(
        features1["descriptors"], 
        features2["descriptors"], 
        k=2
    )
    
    # Apply ratio test
    good_matches = []
    for m, n in matches:
        if m.distance < 0.7 * n.distance:
            good_matches.append(m)
    
    # Get corresponding points
    pts1 = np.float32([features1["keypoints"][m.queryIdx].pt for m in good_matches])
    pts2 = np.float32([features2["keypoints"][m.trainIdx].pt for m in good_matches])
    
    return {
        "matches": good_matches,
        "points_2d_1": pts1,
        "points_2d_2": pts2
    }

def process_video(video_path, output_dir, sample_rate=30, max_frames=None):
    """Process a video file to estimate camera poses and focal length."""
    # Record the start time
    start_time = time.time()
    
    # Create output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)
    
    # Get video information
    video_info = get_video_info(video_path)
    print(f"Video info: {video_info}")
    
    # Determine frames to process
    frame_indices = list(range(0, video_info["frame_count"], sample_rate))
    if max_frames is not None and len(frame_indices) > max_frames:
        frame_indices = frame_indices[:max_frames]
    
    # Extract all frames and their features
    print(f"Extracting features from {len(frame_indices)} frames...")
    frames = []
    features = []
    for frame_idx in tqdm(frame_indices):
        frame = extract_frame(video_path, frame_idx)
        frame_features = detect_features(frame)
        
        frames.append(frame)
        features.append(frame_features)
        
        # Save frame with keypoints
        vis_frame = cv2.drawKeypoints(
            frame, 
            frame_features["keypoints"], 
            None, 
            flags=cv2.DRAW_MATCHES_FLAGS_DRAW_RICH_KEYPOINTS
        )
        cv2.imwrite(
            os.path.join(output_dir, f"frame_{frame_idx:06d}_keypoints.jpg"), 
            vis_frame
        )
    
    # Set up results storage
    results = {
        "frame_idx": frame_indices,
        "focal_length_px": [],
        "fundamental_matrix": [],
        "essential_matrix": [],
        "num_inliers": []
    }
    
    # Process consecutive frame pairs
    print("Estimating camera parameters from frame pairs...")
    for i in tqdm(range(len(frames) - 1)):
        frame_idx1 = frame_indices[i]
        frame_idx2 = frame_indices[i+1]
        
        # Match features between consecutive frames
        matches = match_features(features[i], features[i+1])
        
        if len(matches["points_2d_1"]) < 8:
            print(f"Not enough matches between frames {frame_idx1} and {frame_idx2}")
            continue
        
        # Set options for RANSAC as a dictionary
        ransac_options = {
            'max_iterations': 1000,
            'success_prob': 0.9999,
            'max_epipolar_error': 0.75,
            'progressive_sampling': True
        }
        
        # Create bundle options as a dictionary
        bundle_options = {}
        
        try:
            # Estimate the fundamental matrix using PoseLib
            F, info = poselib.estimate_fundamental(
                matches["points_2d_1"], 
                matches["points_2d_2"], 
                ransac_options, 
                bundle_options
            )
            
            # Convert F to numpy array for easier handling
            F_np = np.array(F).reshape(3, 3)
            
            # Save match visualization
            h, w = frames[i].shape[:2]
            
            # Estimate the focal length using OpenCV
            try:
                # Use OpenCV to estimate the essential matrix from F
                # For this we need a camera matrix with a focal length
                # We'll try different focal lengths and pick the one with the best inliers
                best_focal = 0
                best_inliers = 0
                
                for test_focal in np.linspace(800, 2000, 20):
                    # Create a camera matrix
                    K = np.array([
                        [test_focal, 0, w/2],
                        [0, test_focal, h/2],
                        [0, 0, 1]
                    ])
                    
                    # Calculate the essential matrix E = K'.T * F * K
                    E = K.T @ F_np @ K
                    
                    # Decompose the essential matrix
                    retval, R1, R2, t = cv2.recoverPose(E, 
                                                     matches["points_2d_1"],
                                                     matches["points_2d_2"],
                                                     K)
                    
                    if retval > best_inliers:
                        best_inliers = retval
                        best_focal = test_focal
                
                focal_length = best_focal
                
            except Exception as e:
                print(f"Focal length estimation failed: {e}")
                # Fall back to a default value based on field of view
                focal_length = max(w, h) * 1.2  # Rough estimate
            
            # Store the results
            results["focal_length_px"].append(focal_length)
            results["fundamental_matrix"].append(F_np.tolist())
            results["essential_matrix"].append(None)  # We don't calculate E directly
            results["num_inliers"].append(info.get('num_inliers', 0))
            
            # Save the F matrix and estimated focal length
            with open(os.path.join(output_dir, f"pair_{frame_idx1}_{frame_idx2}_info.txt"), 'w') as f:
                f.write(f"Frame pair: {frame_idx1} - {frame_idx2}\n")
                f.write(f"Number of matches: {len(matches['points_2d_1'])}\n")
                f.write(f"Number of inliers: {info.get('num_inliers', 0)}\n")
                f.write(f"Estimated focal length: {focal_length:.2f} pixels\n")
                f.write("Fundamental matrix:\n")
                for row in F_np:
                    f.write(f"  {row[0]:.6f}, {row[1]:.6f}, {row[2]:.6f}\n")
            
        except Exception as e:
            print(f"Error processing frames {frame_idx1} and {frame_idx2}: {e}")
            # Add placeholder values
            results["focal_length_px"].append(None)
            results["fundamental_matrix"].append(None)
            results["essential_matrix"].append(None)
            results["num_inliers"].append(0)
    
    # Plot focal length estimates
    valid_indices = [i for i, fl in enumerate(results["focal_length_px"]) if fl is not None]
    if valid_indices:
        focal_lengths = [results["focal_length_px"][i] for i in valid_indices]
        frame_pairs = [f"{frame_indices[i]}-{frame_indices[i+1]}" for i in valid_indices]
        
        plt.figure(figsize=(12, 6))
        plt.bar(range(len(valid_indices)), focal_lengths)
        plt.xticks(range(len(valid_indices)), frame_pairs, rotation=90)
        plt.xlabel('Frame Pairs')
        plt.ylabel('Estimated Focal Length (pixels)')
        plt.title('Focal Length Estimates from PoseLib')
        plt.tight_layout()
        plt.savefig(os.path.join(output_dir, 'focal_length_estimates.png'))
        
        # Calculate and print average focal length
        avg_focal_length = np.mean(focal_lengths)
        print(f"Average estimated focal length: {avg_focal_length:.2f} pixels")
        
        # Calculate total processing time
        end_time = time.time()
        processing_time = end_time - start_time
        
        # Save to summary file
        with open(os.path.join(output_dir, 'summary.txt'), 'w') as f:
            f.write(f"Average estimated focal length: {avg_focal_length:.2f} pixels\n")
            f.write(f"Number of valid estimates: {len(valid_indices)}\n")
            f.write(f"Total frames processed: {len(frame_indices)}\n")
            f.write(f"Total processing time: {processing_time:.2f} seconds\n")
            f.write(f"Average time per frame: {processing_time/len(frame_indices):.2f} seconds\n")
            
        # Also print processing time
        print(f"Total processing time: {processing_time:.2f} seconds")
        print(f"Average time per frame: {processing_time/len(frame_indices):.2f} seconds")
    else:
        print("No valid focal length estimates were obtained.")
    
    return results

def main():
    parser = argparse.ArgumentParser(description='Estimate focal length from a video using PoseLib')
    parser.add_argument('video_path', type=str, help='Path to the input video file')
    parser.add_argument('--output', '-o', type=str, default='output_poselib', help='Output directory')
    parser.add_argument('--sample-rate', '-s', type=int, default=30, 
                        help='Process one frame every N frames (default: 30)')
    parser.add_argument('--max-frames', '-m', type=int, default=10,
                        help='Maximum number of frames to process (default: 10)')
    
    args = parser.parse_args()
    
    # Process the video
    process_video(args.video_path, args.output, args.sample_rate, args.max_frames)

if __name__ == "__main__":
    main()
