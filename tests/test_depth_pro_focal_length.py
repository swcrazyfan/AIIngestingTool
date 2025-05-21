#!/usr/bin/env python3
"""
Script for estimating depth and focal length from images or video frames using Apple's DepthPro.

This script can process:
1. Individual image files
2. Directories of images
3. Video files (either first frame or multiple frames)

It uses Apple's DepthPro model to estimate both depth maps and focal length information
and saves the results for analysis.

Requirements:
- depth_pro package (ml-depth-pro)
- torch, pillow, numpy, matplotlib, tqdm
- av (for video processing)
- huggingface_hub (for downloading model checkpoints if needed)
"""

import os
import argparse
import numpy as np
from PIL import Image
import torch
import time
import sys
import json
from pathlib import Path
import matplotlib.pyplot as plt
from tqdm import tqdm
import cv2
from datetime import datetime
import glob
import csv
import shutil

# Import depth_pro package
import depth_pro

# Check if PyAV is installed (for video processing)
try:
    import av
    HAS_AV = True
except ImportError:
    print("Warning: PyAV is not installed. Using OpenCV for video processing instead.")
    print("To enable better video processing, install PyAV: pip install av")
    HAS_AV = False

# Check if PyAV is installed (for video processing)
try:
    import av
    HAS_AV = True
except ImportError:
    print("Warning: PyAV is not installed. Video processing will not be available.")
    print("To enable video processing, install PyAV: pip install av")
    HAS_AV = False

def find_model_file():
    """Find an existing model file in the standard locations."""
    # Get the ml-depth-pro root directory
    depth_pro_file = os.path.dirname(os.path.dirname(depth_pro.__file__))
    ml_depth_pro_root = os.path.dirname(depth_pro_file)
    
    # List of potential locations to check
    potential_locations = [
        os.path.join(ml_depth_pro_root, "checkpoints", "depth_pro.pt"),  # Root/checkpoints/depth_pro.pt
        os.path.join(ml_depth_pro_root, "checkpoints", "model.pth"),     # Root/checkpoints/model.pth
        os.path.join(depth_pro_file, "checkpoints", "depth_pro.pt"),     # src/checkpoints/depth_pro.pt
        os.path.join(depth_pro_file, "checkpoints", "model.pth"),        # src/checkpoints/model.pth
        os.path.join("./checkpoints", "depth_pro.pt"),                   # ./checkpoints/depth_pro.pt
        os.path.join("./checkpoints", "model.pth"),                      # ./checkpoints/model.pth
    ]
    
    # Check each potential location
    for location in potential_locations:
        print(f"Checking for model at: {location}")
        if os.path.exists(location):
            print(f"Found model at: {location}")
            return location
    
    # If no specific model found, look for any .pt or .pth file in checkpoints directories
    checkpoints_dirs = [
        os.path.join(ml_depth_pro_root, "checkpoints"),
        os.path.join(depth_pro_file, "checkpoints"),
        "./checkpoints"
    ]
    
    for checkpoints_dir in checkpoints_dirs:
        if os.path.exists(checkpoints_dir):
            print(f"Searching for model files in: {checkpoints_dir}")
            model_files = []
            for ext in [".pt", ".pth"]:
                model_files.extend(glob.glob(os.path.join(checkpoints_dir, f"*{ext}")))
            
            if model_files:
                print(f"Found model file: {model_files[0]}")
                return model_files[0]
    
    # No model found
    return None




def colorize_depth(depth, min_depth=None, max_depth=None, cmap="viridis"):
    """Convert depth map to colored visualization using matplotlib colormap."""
    import matplotlib.cm as cm
    
    if min_depth is None:
        min_depth = np.min(depth)
    if max_depth is None:
        max_depth = np.max(depth)
    
    depth_normalized = np.clip((depth - min_depth) / (max_depth - min_depth), 0, 1)
    colormap = cm.get_cmap(cmap)
    colored = colormap(depth_normalized)
    
    # Convert to uint8 RGB
    colored_rgb = (colored[:, :, :3] * 255).astype(np.uint8)
    return colored_rgb

def extract_frame_av(video_path, frame_idx):
    """Extract a specific frame from the video using PyAV."""
    if not HAS_AV:
        raise ImportError("PyAV is required for this function but is not installed.")
    
    container = av.open(video_path)
    container.streams.video[0].thread_type = "AUTO"  # Use threading for faster decoding
    
    stream = container.streams.video[0]
    container.seek(int(frame_idx * stream.time_base * stream.duration / stream.frames))
    
    for frame in container.decode(video=0):
        if frame.index == frame_idx:
            img = frame.to_image()
            return np.array(img)
        if frame.index > frame_idx:
            break
    
    raise ValueError(f"Could not extract frame {frame_idx} from video")

def extract_frame_cv2(video_path, frame_idx):
    """Extract a specific frame from the video using OpenCV."""
    cap = cv2.VideoCapture(video_path)
    cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
    ret, frame = cap.read()
    cap.release()
    
    if not ret:
        raise ValueError(f"Could not extract frame {frame_idx} from video")
    
    # Convert BGR to RGB
    frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    return frame

def extract_frame(video_path, frame_idx):
    """Extract a specific frame from the video using the best available method."""
    if HAS_AV:
        try:
            return extract_frame_av(video_path, frame_idx)
        except Exception as e:
            print(f"PyAV extraction failed: {e}. Falling back to OpenCV.")
            return extract_frame_cv2(video_path, frame_idx)
    else:
        return extract_frame_cv2(video_path, frame_idx)

def get_video_info(video_path):
    """Get basic information about the video."""
    if HAS_AV:
        try:
            container = av.open(video_path)
            stream = container.streams.video[0]
            fps = float(stream.average_rate)
            frame_count = stream.frames
            width = stream.width
            height = stream.height
            container.close()
            
            return {
                "fps": fps,
                "frame_count": frame_count,
                "width": width,
                "height": height
            }
        except Exception as e:
            print(f"PyAV info extraction failed: {e}. Falling back to OpenCV.")
    
    # Fallback to OpenCV
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

def process_image(img_path, model, transform, output_dir, run_dir=None):
    """Process a single image file to estimate depth and focal length."""
    start_time = time.time()
    
    # Create subdirectory for this run if not provided
    if run_dir is None:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        image_name = os.path.splitext(os.path.basename(img_path))[0]
        run_dir = os.path.join(output_dir, f"{image_name}_{timestamp}")
        os.makedirs(run_dir, exist_ok=True)
    
    try:
        # Load and preprocess image
        print(f"Processing image: {img_path}")
        image, icc_profile, f_px = depth_pro.load_rgb(img_path)
        
        # Save a copy of the original image
        original_img = Image.fromarray(image)
        original_output_path = os.path.join(run_dir, os.path.basename(img_path))
        original_img.save(original_output_path)
        
        # Transform image for model
        image_tensor = transform(Image.fromarray(image))
        
        # Run inference
        prediction = model.infer(image_tensor, f_px=f_px)
        
        depth = prediction["depth"].cpu().numpy()  # Depth in [m]
        focallength_px = prediction["focallength_px"].cpu().numpy()
        
        # Approximate focal length in mm (assuming a typical sensor size)
        img_width = image.shape[1]
        sensor_width_mm = 5.7  # Approximate for modern cameras
        focallength_mm = (focallength_px / img_width) * sensor_width_mm
        
        # Create depth visualization
        colored_depth = colorize_depth(depth)
        depth_output_path = os.path.join(run_dir, f"depth_{os.path.basename(img_path)}")
        Image.fromarray(colored_depth).save(depth_output_path)
        
        # Create depth heatmap with matplotlib for better visualization
        plt.figure(figsize=(10, 8))
        plt.imshow(depth, cmap='plasma')
        plt.colorbar(label='Depth (meters)')
        plt.title(f'Depth Map - Min: {np.min(depth):.2f}m, Max: {np.max(depth):.2f}m')
        plt.savefig(os.path.join(run_dir, f"depth_heatmap_{os.path.basename(img_path)}"))
        plt.close()
        
        # Create histogram of depth values
        plt.figure(figsize=(10, 6))
        plt.hist(depth.flatten(), bins=100, alpha=0.7)
        plt.title(f'Depth Distribution - Mean: {np.mean(depth):.2f}m, Std: {np.std(depth):.2f}m')
        plt.xlabel('Depth (meters)')
        plt.ylabel('Pixel Count')
        plt.savefig(os.path.join(run_dir, f"depth_histogram_{os.path.basename(img_path)}"))
        plt.close()
        
        # Save JSON with detailed information
        processing_time = time.time() - start_time
        result = {
            "image_path": img_path,
            "processing_time_seconds": processing_time,
            "focallength_px": float(focallength_px),
            "focallength_mm_approx": float(focallength_mm),
            "exif_focallength_px": float(f_px) if f_px is not None else None,
            "depth_stats": {
                "min_depth_meters": float(np.min(depth)),
                "max_depth_meters": float(np.max(depth)),
                "mean_depth_meters": float(np.mean(depth)),
                "median_depth_meters": float(np.median(depth)),
                "std_depth_meters": float(np.std(depth))
            },
            "image_dimensions": {
                "width_px": image.shape[1],
                "height_px": image.shape[0],
            }
        }
        
        with open(os.path.join(run_dir, f"{os.path.splitext(os.path.basename(img_path))[0]}_info.json"), 'w') as f:
            json.dump(result, f, indent=2)
        
        print(f"Image processed in {processing_time:.2f} seconds")
        print(f"Focal length: {focallength_px:.2f} pixels ({focallength_mm:.2f}mm approx)")
        print(f"Depth range: {np.min(depth):.2f}m to {np.max(depth):.2f}m (mean: {np.mean(depth):.2f}m)")
        print(f"Results saved to: {run_dir}")
        print("-" * 50)
        
        return result, run_dir
        
    except Exception as e:
        print(f"Error processing image {img_path}: {e}")
        import traceback
        traceback.print_exc()
        return None, run_dir

def process_images(image_paths, model, transform, output_dir):
    """Process multiple image files to estimate depth and focal length."""
    # Create main output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)
    
    # Create a timestamped subdirectory for this batch run
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    batch_dir = os.path.join(output_dir, f"batch_{timestamp}")
    os.makedirs(batch_dir, exist_ok=True)
    
    results = []
    
    print(f"Processing {len(image_paths)} images...")
    for img_path in tqdm(image_paths):
        result, _ = process_image(img_path, model, transform, batch_dir)
        if result:
            results.append(result)
    
    # Save batch summary
    if results:
        # Aggregate focal length statistics
        focal_lengths_px = [r["focallength_px"] for r in results]
        focal_lengths_mm = [r["focallength_mm_approx"] for r in results]
        
        summary = {
            "total_images": len(results),
            "timestamp": timestamp,
            "focal_length_statistics": {
                "mean_px": float(np.mean(focal_lengths_px)),
                "median_px": float(np.median(focal_lengths_px)),
                "std_px": float(np.std(focal_lengths_px)),
                "mean_mm_approx": float(np.mean(focal_lengths_mm)),
                "median_mm_approx": float(np.median(focal_lengths_mm)),
                "std_mm_approx": float(np.std(focal_lengths_mm)),
            },
            "processing_times": {
                "total_seconds": sum(r["processing_time_seconds"] for r in results),
                "mean_seconds_per_image": float(np.mean([r["processing_time_seconds"] for r in results])),
            }
        }
        
        with open(os.path.join(batch_dir, "batch_summary.json"), 'w') as f:
            json.dump(summary, f, indent=2)
        
        # Create focal length histogram
        plt.figure(figsize=(12, 6))
        plt.hist(focal_lengths_mm, bins=20, alpha=0.7)
        plt.title('Estimated Focal Lengths Distribution')
        plt.xlabel('Focal Length (mm)')
        plt.ylabel('Count')
        plt.savefig(os.path.join(batch_dir, "focal_length_histogram.png"))
        plt.close()
        
        # Save CSV with all results
        with open(os.path.join(batch_dir, "results.csv"), 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([
                "image_name", 
                "focallength_px", 
                "focallength_mm", 
                "min_depth_m",
                "max_depth_m",
                "mean_depth_m", 
                "processing_time_s"
            ])
            
            for r in results:
                writer.writerow([
                    os.path.basename(r["image_path"]),
                    r["focallength_px"],
                    r["focallength_mm_approx"],
                    r["depth_stats"]["min_depth_meters"],
                    r["depth_stats"]["max_depth_meters"],
                    r["depth_stats"]["mean_depth_meters"],
                    r["processing_time_seconds"]
                ])
        
        print(f"Batch processing complete. Results saved to: {batch_dir}")
        print(f"Mean focal length: {summary['focal_length_statistics']['mean_mm_approx']:.2f}mm (approx)")
        print(f"Total processing time: {summary['processing_times']['total_seconds']:.2f} seconds")
    
    return results, batch_dir

def process_video(video_path, model, transform, output_dir, sample_rate=30, max_frames=None):
    """Process video frames to estimate depth and focal length."""
    # Create output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)
    
    # Create a timestamped subdirectory for this video
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    video_name = os.path.splitext(os.path.basename(video_path))[0]
    run_dir = os.path.join(output_dir, f"{video_name}_{timestamp}")
    os.makedirs(run_dir, exist_ok=True)
    
    # Set up logging
    log_file = os.path.join(run_dir, 'processing_log.txt')
    with open(log_file, 'w') as log:
        log.write(f"=== DEPTH PRO VIDEO PROCESSING LOG ===\n")
        log.write(f"Video: {video_path}\n")
        log.write(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        log.write(f"Output directory: {run_dir}\n\n")
    
    def log_message(message):
        """Log a message to both console and log file"""
        print(message)
        with open(log_file, 'a') as log:
            log.write(f"{message}\n")
    
    start_time = time.time()
    
    try:
        # Get video information
        video_info = get_video_info(video_path)
        log_message(f"Video info: {video_info}")
        
        # Determine frames to process
        frame_indices = list(range(0, video_info["frame_count"], sample_rate))
        if max_frames is not None and len(frame_indices) > max_frames:
            frame_indices = frame_indices[:max_frames]
        
        log_message(f"Processing {len(frame_indices)} frames with sample rate {sample_rate}")
        
        # Prepare results storage
        results = {
            "frame_idx": [],
            "focal_length_px": [],
            "focal_length_mm": [],
            "depth_min": [],
            "depth_max": [],
            "depth_mean": [],
            "depth_median": [],
            "processing_time": []
        }
        
        # Process frames
        for i, frame_idx in enumerate(tqdm(frame_indices)):
            frame_start_time = time.time()
            
            # Extract frame
            log_message(f"Processing frame {frame_idx}")
            frame = extract_frame(video_path, frame_idx)
            
            # Save original frame
            frame_filename = os.path.join(run_dir, f"frame_{frame_idx:06d}.jpg")
            Image.fromarray(frame).save(frame_filename)
            
            # Preprocess image for model
            frame_tensor = transform(Image.fromarray(frame))
            
            # Run inference
            prediction = model.infer(frame_tensor)
            
            # Extract results
            depth = prediction["depth"].cpu().numpy()
            focallength_px = prediction["focallength_px"].cpu().numpy()
            
            # Approximate focal length in mm (assuming a typical sensor size)
            img_width = frame.shape[1]
            sensor_width_mm = 5.7  # Approximate for modern cameras
            focallength_mm = (focallength_px / img_width) * sensor_width_mm
            
            # Create depth visualization
            colored_depth = colorize_depth(depth)
            depth_filename = os.path.join(run_dir, f"depth_{frame_idx:06d}.jpg")
            Image.fromarray(colored_depth).save(depth_filename)
            
            # Calculate processing time
            frame_time = time.time() - frame_start_time
            
            # Store results
            results["frame_idx"].append(frame_idx)
            results["focal_length_px"].append(float(focallength_px))
            results["focal_length_mm"].append(float(focallength_mm))
            results["depth_min"].append(float(np.min(depth)))
            results["depth_max"].append(float(np.max(depth)))
            results["depth_mean"].append(float(np.mean(depth)))
            results["depth_median"].append(float(np.median(depth)))
            results["processing_time"].append(frame_time)
            
            # Save detailed results for this frame
            with open(os.path.join(run_dir, f"frame_{frame_idx:06d}_info.json"), 'w') as f:
                frame_data = {
                    "frame_idx": frame_idx,
                    "processing_time_seconds": frame_time,
                    "focallength_px": float(focallength_px),
                    "focallength_mm_approx": float(focallength_mm),
                    "depth_stats": {
                        "min_depth_meters": float(np.min(depth)),
                        "max_depth_meters": float(np.max(depth)),
                        "mean_depth_meters": float(np.mean(depth)),
                        "median_depth_meters": float(np.median(depth)),
                        "std_depth_meters": float(np.std(depth))
                    }
                }
                json.dump(frame_data, f, indent=2)
        
        # Plot focal length over time
        plt.figure(figsize=(12, 6))
        plt.plot(results["frame_idx"], results["focal_length_mm"], 'b-', marker='o', label='Focal Length (mm)')
        plt.xlabel('Frame Index')
        plt.ylabel('Focal Length (mm)')
        plt.title('Estimated Focal Length Over Time')
        plt.grid(True)
        plt.legend()
        plt.savefig(os.path.join(run_dir, 'focal_length_over_time.png'))
        plt.close()
        
        # Plot depth statistics over time
        plt.figure(figsize=(12, 6))
        plt.plot(results["frame_idx"], results["depth_mean"], 'r-', marker='o', label='Mean Depth (m)')
        plt.plot(results["frame_idx"], results["depth_min"], 'g--', marker='x', label='Min Depth (m)')
        plt.plot(results["frame_idx"], results["depth_max"], 'b--', marker='s', label='Max Depth (m)')
        plt.xlabel('Frame Index')
        plt.ylabel('Depth (meters)')
        plt.title('Depth Statistics Over Time')
        plt.grid(True)
        plt.legend()
        plt.savefig(os.path.join(run_dir, 'depth_stats_over_time.png'))
        plt.close()
        
        # Plot processing time per frame
        plt.figure(figsize=(12, 6))
        plt.plot(results["frame_idx"], results["processing_time"], 'g-', marker='o')
        plt.xlabel('Frame Index')
        plt.ylabel('Processing Time (seconds)')
        plt.title('Processing Time per Frame')
        plt.grid(True)
        plt.savefig(os.path.join(run_dir, 'processing_time_per_frame.png'))
        plt.close()
        
        # Save all results to CSV
        with open(os.path.join(run_dir, 'results.csv'), 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([
                "frame_idx", 
                "focal_length_px", 
                "focal_length_mm", 
                "depth_min_m",
                "depth_max_m",
                "depth_mean_m",
                "depth_median_m", 
                "processing_time_s"
            ])
            
            for i in range(len(results["frame_idx"])):
                writer.writerow([
                    results["frame_idx"][i],
                    results["focal_length_px"][i],
                    results["focal_length_mm"][i],
                    results["depth_min"][i],
                    results["depth_max"][i],
                    results["depth_mean"][i],
                    results["depth_median"][i],
                    results["processing_time"][i]
                ])
        
        # Calculate total processing time
        total_time = time.time() - start_time
        
        # Save summary
        summary = {
            "video_path": video_path,
            "frames_processed": len(frame_indices),
            "total_processing_time_seconds": total_time,
            "average_time_per_frame_seconds": total_time / len(frame_indices) if frame_indices else 0,
            "focal_length_statistics": {
                "mean_px": float(np.mean(results["focal_length_px"])),
                "median_px": float(np.median(results["focal_length_px"])),
                "std_px": float(np.std(results["focal_length_px"])),
                "mean_mm": float(np.mean(results["focal_length_mm"])),
                "median_mm": float(np.median(results["focal_length_mm"])),
                "std_mm": float(np.std(results["focal_length_mm"])),
            },
            "depth_statistics": {
                "mean_min_depth_m": float(np.mean(results["depth_min"])),
                "mean_max_depth_m": float(np.mean(results["depth_max"])),
                "overall_mean_depth_m": float(np.mean(results["depth_mean"])),
            }
        }
        
        with open(os.path.join(run_dir, 'video_summary.json'), 'w') as f:
            json.dump(summary, f, indent=2)
        
        log_message(f"\nProcessing complete. Results saved to: {run_dir}")
        log_message(f"Total frames processed: {len(frame_indices)}")
        log_message(f"Total processing time: {total_time:.2f} seconds")
        log_message(f"Average time per frame: {total_time / len(frame_indices):.2f} seconds")
        log_message(f"Mean focal length: {summary['focal_length_statistics']['mean_mm']:.2f}mm (approx)")
        
        return results, run_dir
        
    except Exception as e:
        error_msg = f"Error processing video: {e}"
        log_message(error_msg)
        import traceback
        log_message(traceback.format_exc())
        
        return None, run_dir

def process_video_first_frame(video_path, model, transform, output_dir):
    """Process just the first frame of a video to estimate depth and focal length."""
    # Extract the first frame
    try:
        first_frame = extract_frame(video_path, 0)
        
        # Create a temporary file for the first frame
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        temp_dir = os.path.join(output_dir, "temp")
        os.makedirs(temp_dir, exist_ok=True)
        
        first_frame_path = os.path.join(temp_dir, f"first_frame_{timestamp}.jpg")
        Image.fromarray(first_frame).save(first_frame_path)
        
        # Process the image
        result, run_dir = process_image(first_frame_path, model, transform, output_dir)
        
        # Rename the output directory to indicate it's a video first frame
        video_name = os.path.splitext(os.path.basename(video_path))[0]
        new_dir = os.path.join(output_dir, f"{video_name}_first_frame_{timestamp}")
        os.rename(run_dir, new_dir)
        
        # Cleanup temporary file
        os.remove(first_frame_path)
        
        return result, new_dir
        
    except Exception as e:
        print(f"Error processing video first frame: {e}")
        import traceback
        traceback.print_exc()
        return None, None

def main():
    parser = argparse.ArgumentParser(description='Estimate depth and focal length using Apple DepthPro')
    
    # Input source options (mutually exclusive)
    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument('--image', '-i', type=str, help='Path to a single image file')
    input_group.add_argument('--directory', '-d', type=str, help='Path to a directory containing images')
    input_group.add_argument('--video', '-v', type=str, help='Path to a video file')
    input_group.add_argument('--video-first-frame', '-vf', type=str, help='Process only the first frame of a video')
    
    # Output options
    parser.add_argument('--output', '-o', type=str, default='output_depthpro', help='Output directory')
    
    # Video processing options
    parser.add_argument('--sample-rate', '-s', type=int, default=30, 
                       help='Process one frame every N frames (default: 30)')
    parser.add_argument('--max-frames', '-m', type=int, default=5,
                       help='Maximum number of frames to process (default: 5)')
    
    # Image directory options
    parser.add_argument('--extensions', '-e', type=str, default='.jpg,.jpeg,.png', 
                       help='Comma-separated list of image file extensions (default: .jpg,.jpeg,.png)')
    
    args = parser.parse_args()
    
    try:
        # Load DepthPro model following the example from README.md
        print("Loading Apple DepthPro model...")
        start_time = time.time()
        
        # Import necessary modules to override the default config
        from depth_pro.depth_pro import DEFAULT_MONODEPTH_CONFIG_DICT, DepthProConfig
        
        # Explicitly set the model path to the existing file
        model_path = "/Users/developer/Development/GitHub/AIIngestingTool/ml-depth-pro/checkpoints/depth_pro.pt"
        
        if not os.path.exists(model_path):
            print(f"Error: Model file not found at {model_path}")
            print("Please follow the instructions in the README to download the model:")
            print("1. Run 'cd /Users/developer/Development/GitHub/AIIngestingTool/ml-depth-pro'")
            print("2. Run 'source get_pretrained_models.sh'")
            print("3. Wait for the download to complete (1.8GB file)")
            sys.exit(1)
        
        print(f"Using model file: {model_path}")
        
        # Create a custom config with the explicit model path
        custom_config = DepthProConfig(
            patch_encoder_preset=DEFAULT_MONODEPTH_CONFIG_DICT.patch_encoder_preset,
            image_encoder_preset=DEFAULT_MONODEPTH_CONFIG_DICT.image_encoder_preset,
            decoder_features=DEFAULT_MONODEPTH_CONFIG_DICT.decoder_features,
            checkpoint_uri=model_path,
            use_fov_head=DEFAULT_MONODEPTH_CONFIG_DICT.use_fov_head,
            fov_encoder_preset=DEFAULT_MONODEPTH_CONFIG_DICT.fov_encoder_preset
        )
        
        # Device selection logic
        if torch.cuda.is_available():
            device = torch.device("cuda")
            precision = torch.float16  # Use half precision for faster processing on CUDA
        elif hasattr(torch, 'backends') and hasattr(torch.backends, 'mps') and torch.backends.mps.is_available():
            device = torch.device("mps")
            precision = torch.float32
        else:
            device = torch.device("cpu")
            precision = torch.float32
        
        print(f"Using device: {device}, precision: {precision}")
        
        # Create model and transforms with custom config
        model, transform = depth_pro.create_model_and_transforms(
            config=custom_config, 
            device=device,
            precision=precision
        )
        model.eval()
        
        load_time = time.time() - start_time
        print(f"Model loaded in {load_time:.2f} seconds")
        
        # Process according to the input type
        if args.image:
            if not os.path.isfile(args.image):
                print(f"Error: Image file not found: {args.image}")
                sys.exit(1)
            
            process_image(args.image, model, transform, args.output)
        
        elif args.directory:
            if not os.path.isdir(args.directory):
                print(f"Error: Directory not found: {args.directory}")
                sys.exit(1)
            
            # Get list of valid extensions
            extensions = args.extensions.split(',')
            
            # Find all image files in the directory
            image_paths = []
            for ext in extensions:
                ext_pattern = os.path.join(args.directory, f"*{ext}")
                image_paths.extend(glob.glob(ext_pattern))
            
            if not image_paths:
                print(f"Error: No images with extensions {extensions} found in {args.directory}")
                sys.exit(1)
            
            print(f"Found {len(image_paths)} images to process")
            process_images(image_paths, model, transform, args.output)
        
        elif args.video:
            if not os.path.isfile(args.video):
                print(f"Error: Video file not found: {args.video}")
                sys.exit(1)
            
            process_video(args.video, model, transform, args.output, args.sample_rate, args.max_frames)
        
        elif args.video_first_frame:
            if not os.path.isfile(args.video_first_frame):
                print(f"Error: Video file not found: {args.video_first_frame}")
                sys.exit(1)
            
            process_video_first_frame(args.video_first_frame, model, transform, args.output)
    
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
