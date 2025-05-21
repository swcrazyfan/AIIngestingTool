#!/usr/bin/env python3
"""
Script for estimating depth and focal length from images or video frames using the
Hugging Face version of Apple's DepthPro.

This script can process:
1. Individual image files
2. Directories of images
3. Video files (either first frame or multiple frames)

Requirements:
- transformers
- torch, pillow, matplotlib, tqdm
- av (for video processing, optional)
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
import requests

# Try importing transformers
try:
    from transformers import DepthProImageProcessorFast, DepthProForDepthEstimation
except ImportError:
    print("Error: transformers package is not installed or doesn't have DepthPro models.")
    print("Please install it using: pip install transformers")
    sys.exit(1)

# Check if PyAV is installed (for video processing)
try:
    import av
    HAS_AV = True
except ImportError:
    print("Warning: PyAV is not installed. Using OpenCV for video processing instead.")
    print("To enable better video processing, install PyAV: pip install av")
    HAS_AV = False

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
            return img
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
    # Convert to PIL Image
    pil_image = Image.fromarray(frame)
    return pil_image

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

def load_model(device=None):
    """Load DepthPro model from Hugging Face."""
    if device is None:
        device = torch.device("cuda" if torch.cuda.is_available() else 
                             "mps" if torch.backends.mps.is_available() else 
                             "cpu")
    
    print(f"Loading DepthPro model from Hugging Face to {device}...")
    start_time = time.time()
    
    # Load model and processor
    processor = DepthProImageProcessorFast.from_pretrained("apple/DepthPro-hf")
    model = DepthProForDepthEstimation.from_pretrained("apple/DepthPro-hf").to(device)
    
    load_time = time.time() - start_time
    print(f"Model loaded in {load_time:.2f} seconds")
    
    return model, processor, device

def process_image(img_path, model, processor, device, output_dir, run_dir=None):
    """Process a single image file to estimate depth and focal length."""
    start_time = time.time()
    
    # Create subdirectory for this run if not provided
    if run_dir is None:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        image_name = os.path.splitext(os.path.basename(img_path))[0]
        run_dir = os.path.join(output_dir, f"{image_name}_{timestamp}")
        os.makedirs(run_dir, exist_ok=True)
    
    try:
        # Load image
        print(f"Processing image: {img_path}")
        if img_path.startswith(('http://', 'https://')):
            # Download image from URL
            image = Image.open(requests.get(img_path, stream=True).raw)
        else:
            # Load image from file
            image = Image.open(img_path)
        
        # Save a copy of the original image
        original_output_path = os.path.join(run_dir, os.path.basename(img_path) if not img_path.startswith(('http://', 'https://')) else "original.jpg")
        image.save(original_output_path)
        
        # Process image
        inputs = processor(images=image, return_tensors="pt").to(device)
        
        # Run inference
        with torch.no_grad():
            outputs = model(**inputs)
        
        # Post-process outputs
        post_processed = processor.post_process_depth_estimation(
            outputs, target_sizes=[(image.height, image.width)]
        )
        
        # Extract results
        field_of_view = post_processed[0]["field_of_view"].item()
        focal_length_px = post_processed[0]["focal_length"].item()
        depth = post_processed[0]["predicted_depth"]
        
        # Convert depth to numpy for visualization
        depth_np = depth.cpu().numpy()
        
        # Calculate approximate focal length in mm (assuming a typical sensor size)
        img_width = image.width
        sensor_width_mm = 5.7  # Approximate for modern cameras
        focal_length_mm = (focal_length_px / img_width) * sensor_width_mm
        
        # Create depth visualization (normalize 0-1 for better visualization)
        depth_normalized = (depth_np - depth_np.min()) / (depth_np.max() - depth_np.min())
        depth_colored = colorize_depth(depth_normalized)
        depth_output_path = os.path.join(run_dir, f"depth_{os.path.basename(img_path)}" if not img_path.startswith(('http://', 'https://')) else "depth.jpg")
        Image.fromarray(depth_colored).save(depth_output_path)
        
        # Create depth heatmap with matplotlib for better visualization
        plt.figure(figsize=(10, 8))
        plt.imshow(depth_np, cmap='plasma')
        plt.colorbar(label='Depth (arbitrary units)')
        plt.title(f'Depth Map - Min: {depth_np.min():.2f}, Max: {depth_np.max():.2f}')
        plt.savefig(os.path.join(run_dir, f"depth_heatmap_{os.path.basename(img_path)}" if not img_path.startswith(('http://', 'https://')) else "depth_heatmap.jpg"))
        plt.close()
        
        # Create histogram of depth values
        plt.figure(figsize=(10, 6))
        plt.hist(depth_np.flatten(), bins=100, alpha=0.7)
        plt.title(f'Depth Distribution - Mean: {np.mean(depth_np):.2f}, Std: {np.std(depth_np):.2f}')
        plt.xlabel('Depth')
        plt.ylabel('Pixel Count')
        plt.savefig(os.path.join(run_dir, f"depth_histogram_{os.path.basename(img_path)}" if not img_path.startswith(('http://', 'https://')) else "depth_histogram.jpg"))
        plt.close()
        
        # Save 8-bit depth map for easier viewing
        depth_8bit = (depth_normalized * 255).astype(np.uint8)
        depth_8bit_path = os.path.join(run_dir, f"depth_8bit_{os.path.basename(img_path)}" if not img_path.startswith(('http://', 'https://')) else "depth_8bit.jpg")
        Image.fromarray(depth_8bit).save(depth_8bit_path)
        
        # Save JSON with detailed information
        processing_time = time.time() - start_time
        result = {
            "image_path": img_path,
            "processing_time_seconds": processing_time,
            "field_of_view_degrees": field_of_view,
            "focal_length_px": focal_length_px,
            "focal_length_mm_approx": focal_length_mm,
            "depth_stats": {
                "min_depth": float(depth_np.min()),
                "max_depth": float(depth_np.max()),
                "mean_depth": float(np.mean(depth_np)),
                "median_depth": float(np.median(depth_np)),
                "std_depth": float(np.std(depth_np))
            },
            "image_dimensions": {
                "width_px": image.width,
                "height_px": image.height,
            }
        }
        
        info_filename = os.path.splitext(os.path.basename(img_path))[0] if not img_path.startswith(('http://', 'https://')) else "result"
        with open(os.path.join(run_dir, f"{info_filename}_info.json"), 'w') as f:
            json.dump(result, f, indent=2)
        
        print(f"Image processed in {processing_time:.2f} seconds")
        print(f"Field of view: {field_of_view:.2f} degrees")
        print(f"Focal length: {focal_length_px:.2f} pixels ({focal_length_mm:.2f}mm approx)")
        print(f"Results saved to: {run_dir}")
        print("-" * 50)
        
        return result, run_dir
        
    except Exception as e:
        print(f"Error processing image {img_path}: {e}")
        import traceback
        traceback.print_exc()
        return None, run_dir

def process_images(image_paths, model, processor, device, output_dir):
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
        result, _ = process_image(img_path, model, processor, device, batch_dir)
        if result:
            results.append(result)
    
    # Save batch summary
    if results:
        # Aggregate focal length statistics
        focal_lengths_px = [r["focal_length_px"] for r in results]
        focal_lengths_mm = [r["focal_length_mm_approx"] for r in results]
        fov_degrees = [r["field_of_view_degrees"] for r in results]
        
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
            "field_of_view_statistics": {
                "mean_degrees": float(np.mean(fov_degrees)),
                "median_degrees": float(np.median(fov_degrees)),
                "std_degrees": float(np.std(fov_degrees)),
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
        
        # Create field of view histogram
        plt.figure(figsize=(12, 6))
        plt.hist(fov_degrees, bins=20, alpha=0.7)
        plt.title('Field of View Distribution')
        plt.xlabel('Field of View (degrees)')
        plt.ylabel('Count')
        plt.savefig(os.path.join(batch_dir, "fov_histogram.png"))
        plt.close()
        
        # Save CSV with all results
        with open(os.path.join(batch_dir, "results.csv"), 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([
                "image_name", 
                "focal_length_px", 
                "focal_length_mm", 
                "field_of_view_degrees",
                "min_depth",
                "max_depth",
                "mean_depth", 
                "processing_time_s"
            ])
            
            for r in results:
                writer.writerow([
                    os.path.basename(r["image_path"]),
                    r["focal_length_px"],
                    r["focal_length_mm_approx"],
                    r["field_of_view_degrees"],
                    r["depth_stats"]["min_depth"],
                    r["depth_stats"]["max_depth"],
                    r["depth_stats"]["mean_depth"],
                    r["processing_time_seconds"]
                ])
        
        print(f"Batch processing complete. Results saved to: {batch_dir}")
        print(f"Mean focal length: {summary['focal_length_statistics']['mean_mm_approx']:.2f}mm (approx)")
        print(f"Mean field of view: {summary['field_of_view_statistics']['mean_degrees']:.2f} degrees")
        print(f"Total processing time: {summary['processing_times']['total_seconds']:.2f} seconds")
    
    return results, batch_dir

def process_video(video_path, model, processor, device, output_dir, sample_rate=30, max_frames=None):
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
        log.write(f"=== DEPTH PRO HF VIDEO PROCESSING LOG ===\n")
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
            "field_of_view_degrees": [],
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
            pil_image = extract_frame(video_path, frame_idx)
            
            # Save original frame
            frame_filename = os.path.join(run_dir, f"frame_{frame_idx:06d}.jpg")
            pil_image.save(frame_filename)
            
            # Process the frame
            inputs = processor(images=pil_image, return_tensors="pt").to(device)
            
            # Run inference
            with torch.no_grad():
                outputs = model(**inputs)
            
            # Post-process outputs
            post_processed = processor.post_process_depth_estimation(
                outputs, target_sizes=[(pil_image.height, pil_image.width)]
            )
            
            # Extract results
            field_of_view = post_processed[0]["field_of_view"].item()
            focal_length_px = post_processed[0]["focal_length"].item()
            depth = post_processed[0]["predicted_depth"]
            
            # Convert depth to numpy for visualization
            depth_np = depth.cpu().numpy()
            
            # Calculate approximate focal length in mm (assuming a typical sensor size)
            img_width = pil_image.width
            sensor_width_mm = 5.7  # Approximate for modern cameras
            focal_length_mm = (focal_length_px / img_width) * sensor_width_mm
            
            # Create depth visualization (normalize 0-1 for better visualization)
            depth_normalized = (depth_np - depth_np.min()) / (depth_np.max() - depth_np.min())
            depth_colored = colorize_depth(depth_normalized)
            depth_filename = os.path.join(run_dir, f"depth_{frame_idx:06d}.jpg")
            Image.fromarray(depth_colored).save(depth_filename)
            
            # Save 8-bit depth map for easier viewing
            depth_8bit = (depth_normalized * 255).astype(np.uint8)
            depth_8bit_path = os.path.join(run_dir, f"depth_8bit_{frame_idx:06d}.jpg")
            Image.fromarray(depth_8bit).save(depth_8bit_path)
            
            # Calculate processing time
            frame_time = time.time() - frame_start_time
            
            # Store results
            results["frame_idx"].append(frame_idx)
            results["focal_length_px"].append(focal_length_px)
            results["focal_length_mm"].append(focal_length_mm)
            results["field_of_view_degrees"].append(field_of_view)
            results["depth_min"].append(float(depth_np.min()))
            results["depth_max"].append(float(depth_np.max()))
            results["depth_mean"].append(float(np.mean(depth_np)))
            results["depth_median"].append(float(np.median(depth_np)))
            results["processing_time"].append(frame_time)
            
            # Save detailed results for this frame
            with open(os.path.join(run_dir, f"frame_{frame_idx:06d}_info.json"), 'w') as f:
                frame_data = {
                    "frame_idx": frame_idx,
                    "processing_time_seconds": frame_time,
                    "focal_length_px": focal_length_px,
                    "focal_length_mm_approx": focal_length_mm,
                    "field_of_view_degrees": field_of_view,
                    "depth_stats": {
                        "min_depth": float(depth_np.min()),
                        "max_depth": float(depth_np.max()),
                        "mean_depth": float(np.mean(depth_np)),
                        "median_depth": float(np.median(depth_np)),
                        "std_depth": float(np.std(depth_np))
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
        
        # Plot field of view over time
        plt.figure(figsize=(12, 6))
        plt.plot(results["frame_idx"], results["field_of_view_degrees"], 'g-', marker='o', label='Field of View (degrees)')
        plt.xlabel('Frame Index')
        plt.ylabel('Field of View (degrees)')
        plt.title('Estimated Field of View Over Time')
        plt.grid(True)
        plt.legend()
        plt.savefig(os.path.join(run_dir, 'fov_over_time.png'))
        plt.close()
        
        # Plot depth statistics over time
        plt.figure(figsize=(12, 6))
        plt.plot(results["frame_idx"], results["depth_mean"], 'r-', marker='o', label='Mean Depth')
        plt.plot(results["frame_idx"], results["depth_min"], 'g--', marker='x', label='Min Depth')
        plt.plot(results["frame_idx"], results["depth_max"], 'b--', marker='s', label='Max Depth')
        plt.xlabel('Frame Index')
        plt.ylabel('Depth')
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
                "field_of_view_degrees",
                "depth_min",
                "depth_max",
                "depth_mean",
                "depth_median", 
                "processing_time_s"
            ])
            
            for i in range(len(results["frame_idx"])):
                writer.writerow([
                    results["frame_idx"][i],
                    results["focal_length_px"][i],
                    results["focal_length_mm"][i],
                    results["field_of_view_degrees"][i],
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
            "field_of_view_statistics": {
                "mean_degrees": float(np.mean(results["field_of_view_degrees"])),
                "median_degrees": float(np.median(results["field_of_view_degrees"])),
                "std_degrees": float(np.std(results["field_of_view_degrees"])),
            },
            "depth_statistics": {
                "mean_min_depth": float(np.mean(results["depth_min"])),
                "mean_max_depth": float(np.mean(results["depth_max"])),
                "overall_mean_depth": float(np.mean(results["depth_mean"])),
            }
        }
        
        with open(os.path.join(run_dir, 'video_summary.json'), 'w') as f:
            json.dump(summary, f, indent=2)
        
        log_message(f"\nProcessing complete. Results saved to: {run_dir}")
        log_message(f"Total frames processed: {len(frame_indices)}")
        log_message(f"Total processing time: {total_time:.2f} seconds")
        log_message(f"Average time per frame: {total_time / len(frame_indices):.2f} seconds")
        log_message(f"Mean focal length: {summary['focal_length_statistics']['mean_mm']:.2f}mm (approx)")
        log_message(f"Mean field of view: {summary['field_of_view_statistics']['mean_degrees']:.2f} degrees")
        
        return results, run_dir
        
    except Exception as e:
        error_msg = f"Error processing video: {e}"
        log_message(error_msg)
        import traceback
        log_message(traceback.format_exc())
        
        return None, run_dir

def process_video_first_frame(video_path, model, processor, device, output_dir):
    """Process just the first frame of a video to estimate depth and focal length."""
    # Extract the first frame
    try:
        first_frame = extract_frame(video_path, 0)
        
        # Create a temporary file for the first frame
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        temp_dir = os.path.join(output_dir, "temp")
        os.makedirs(temp_dir, exist_ok=True)
        
        first_frame_path = os.path.join(temp_dir, f"first_frame_{timestamp}.jpg")
        first_frame.save(first_frame_path)
        
        # Process the image
        result, run_dir = process_image(first_frame_path, model, processor, device, output_dir)
        
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
    parser = argparse.ArgumentParser(description='Estimate depth and focal length using Hugging Face DepthPro')
    
    # Input source options (mutually exclusive)
    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument('--image', '-i', type=str, help='Path to a single image file or URL')
    input_group.add_argument('--directory', '-d', type=str, help='Path to a directory containing images')
    input_group.add_argument('--video', '-v', type=str, help='Path to a video file')
    input_group.add_argument('--video-first-frame', '-vf', type=str, help='Process only the first frame of a video')
    
    # Output options
    parser.add_argument('--output', '-o', type=str, default='output_depthpro_hf', help='Output directory')
    
    # Video processing options
    parser.add_argument('--sample-rate', '-s', type=int, default=30, 
                       help='Process one frame every N frames (default: 30)')
    parser.add_argument('--max-frames', '-m', type=int, default=5,
                       help='Maximum number of frames to process (default: 5)')
    
    # Image directory options
    parser.add_argument('--extensions', '-e', type=str, default='.jpg,.jpeg,.png', 
                       help='Comma-separated list of image file extensions (default: .jpg,.jpeg,.png)')
    
    # Device option
    parser.add_argument('--device', type=str, choices=['cuda', 'mps', 'cpu'], 
                       help='Device to use for inference (default: best available)')
    
    args = parser.parse_args()
    
    try:
        # Set device
        if args.device:
            if args.device == 'cuda' and not torch.cuda.is_available():
                print("CUDA requested but not available. Falling back to CPU.")
                device = torch.device("cpu")
            elif args.device == 'mps' and not (hasattr(torch, 'backends') and hasattr(torch.backends, 'mps') and torch.backends.mps.is_available()):
                print("MPS requested but not available. Falling back to CPU.")
                device = torch.device("cpu")
            else:
                device = torch.device(args.device)
        else:
            # Auto-select best device
            device = torch.device("cuda" if torch.cuda.is_available() else 
                                 "mps" if hasattr(torch, 'backends') and hasattr(torch.backends, 'mps') and torch.backends.mps.is_available() else 
                                 "cpu")
        
        # Load model
        model, processor, device = load_model(device)
        
        # Process according to the input type
        if args.image:
            # Check if it's a URL or a local file
            if args.image.startswith(('http://', 'https://')):
                print(f"Processing image from URL: {args.image}")
                process_image(args.image, model, processor, device, args.output)
            elif not os.path.isfile(args.image):
                print(f"Error: Image file not found: {args.image}")
                sys.exit(1)
            else:
                process_image(args.image, model, processor, device, args.output)
        
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
            process_images(image_paths, model, processor, device, args.output)
        
        elif args.video:
            if not os.path.isfile(args.video):
                print(f"Error: Video file not found: {args.video}")
                sys.exit(1)
            
            process_video(args.video, model, processor, device, args.output, args.sample_rate, args.max_frames)
        
        elif args.video_first_frame:
            if not os.path.isfile(args.video_first_frame):
                print(f"Error: Video file not found: {args.video_first_frame}")
                sys.exit(1)
            
            process_video_first_frame(args.video_first_frame, model, processor, device, args.output)
    
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
