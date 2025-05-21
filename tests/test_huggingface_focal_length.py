#!/usr/bin/env python3
"""
Script for estimating focal length category from images or video frames using a Hugging Face model.

This script can process:
1. Individual image files
2. Directories of images
3. The first frame of a video file

It uses the tonyassi/camera-lens-focal-length model to classify each image into a focal length 
category (ULTRA-WIDE, WIDE, MEDIUM, LONG-LENS, TELEPHOTO), and saves the results.

Requirements:
- transformers
- torch
- pillow
- matplotlib
- tqdm
- av (for video processing)
"""

import os
import argparse
import numpy as np
from tqdm import tqdm
import matplotlib.pyplot as plt
from PIL import Image
import time
import sys
import json
from collections import Counter
import glob

# Check if transformers is installed, if not provide instructions
try:
    from transformers import pipeline
except ImportError:
    print("Error: transformers package is not installed.")
    print("Please install it using: pip install transformers torch")
    sys.exit(1)

# Check if PyAV is installed (for video processing)
try:
    import av
except ImportError:
    print("Warning: PyAV is not installed. Video processing will not be available.")
    print("To enable video processing, install PyAV: pip install av")
    HAS_AV = False
else:
    HAS_AV = True

# Focal length category approximate ranges (in mm, for full-frame equivalent)
FOCAL_LENGTH_RANGES = {
    "ULTRA-WIDE": (8, 18),    # Ultra wide-angle: 8-18mm
    "WIDE": (18, 35),         # Wide-angle: 18-35mm
    "MEDIUM": (35, 70),       # Standard/Normal: 35-70mm
    "LONG-LENS": (70, 200),   # Short telephoto: 70-200mm
    "TELEPHOTO": (200, 800)   # Telephoto: 200-800mm
}

def get_approx_focal_length(category):
    """Get the approximate middle focal length value for a category."""
    if category in FOCAL_LENGTH_RANGES:
        min_val, max_val = FOCAL_LENGTH_RANGES[category]
        return (min_val + max_val) / 2
    return None

def extract_first_frame(video_path):
    """Extract only the first frame from a video using PyAV."""
    if not HAS_AV:
        raise ImportError("PyAV is required for video processing but is not installed.")
    
    try:
        container = av.open(video_path)
        container.streams.video[0].thread_type = "AUTO"  # Use threading for faster decoding
        
        for frame in container.decode(video=0):
            # Convert the frame to RGB PIL Image
            img = frame.to_image()
            # Only need the first frame
            return img
            
    except Exception as e:
        raise RuntimeError(f"Error extracting frame from video: {e}")

def process_images(image_paths, output_dir):
    """Process a list of image files to estimate focal length using the Hugging Face model."""
    # Record the start time
    start_time = time.time()
    
    # Create a timestamped subdirectory for this run if not processing within video_first_frame
    if not os.path.basename(output_dir).startswith(os.path.basename(os.path.dirname(image_paths[0]))):
        timestamp = time.strftime('%Y%m%d_%H%M%S')
        run_dir = os.path.join(output_dir, f"images_{timestamp}")
        os.makedirs(run_dir, exist_ok=True)
        print(f"Results will be saved to: {run_dir}")
        output_dir = run_dir
    
    # Create output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)
    
    # Load the focal length estimation model
    print("Loading focal length classification model...")
    model_load_start = time.time()
    
    # Device selection logic - prioritize MPS, then CUDA, then CPU
    import torch
    
    if hasattr(torch, 'backends') and hasattr(torch.backends, 'mps') and torch.backends.mps.is_available():
        device = "mps"
    elif torch.cuda.is_available():
        device = "cuda"
    else:
        device = "cpu"
    
    print(f"Using device: {device}")
    pipe = pipeline("image-classification", model="tonyassi/camera-lens-focal-length", device=device)
    model_load_time = time.time() - model_load_start
    print(f"Model loaded in {model_load_time:.2f} seconds")
    
    # Prepare results storage
    results = {
        "image_path": [],
        "focal_length_category": [],
        "approx_focal_length_mm": [],
        "confidence": [],
        "all_predictions": []
    }
    
    # Process images
    print(f"Processing {len(image_paths)} images...")
    total_processing_time = 0
    
    for i, img_path in enumerate(tqdm(image_paths)):
        frame_start_time = time.time()
        
        # Load image
        try:
            pil_image = Image.open(img_path)
            
            # Save a copy of the image to the output directory
            base_name = os.path.basename(img_path)
            output_image_path = os.path.join(output_dir, base_name)
            pil_image.save(output_image_path)
            
            # Run the model to estimate focal length category
            prediction_result = pipe(pil_image)
            
            # Extract the top prediction
            top_prediction = prediction_result[0] if prediction_result else None
            
            if top_prediction:
                category = top_prediction["label"]
                confidence = top_prediction["score"]
                approx_focal_length = get_approx_focal_length(category)
            else:
                category = None
                confidence = 0
                approx_focal_length = None
            
            # Store detailed results for this image
            info_filename = os.path.splitext(base_name)[0] + "_info.json"
            with open(os.path.join(output_dir, info_filename), 'w') as f:
                frame_data = {
                    "image_path": img_path,
                    "processing_time": time.time() - frame_start_time,
                    "focal_length_category": category,
                    "approx_focal_length_mm": approx_focal_length,
                    "confidence": confidence,
                    "all_predictions": [
                        {"label": pred["label"], "confidence": pred["score"]} 
                        for pred in prediction_result
                    ]
                }
                json.dump(frame_data, f, indent=2)
            
            # Calculate processing time
            frame_time = time.time() - frame_start_time
            total_processing_time += frame_time
            
            # Store results
            results["image_path"].append(img_path)
            results["focal_length_category"].append(category)
            results["approx_focal_length_mm"].append(approx_focal_length)
            results["confidence"].append(confidence)
            results["all_predictions"].append(prediction_result)
            
        except Exception as e:
            print(f"Error processing image {img_path}: {e}")
    
    # Calculate the most common category
    categories = [cat for cat in results["focal_length_category"] if cat is not None]
    if categories:
        category_counts = Counter(categories)
        most_common_category = category_counts.most_common(1)[0][0]
        approx_focal_length = get_approx_focal_length(most_common_category)
    else:
        most_common_category = "Unknown"
        approx_focal_length = None
    
    # Valid approximate focal lengths
    valid_focal_lengths = [fl for fl in results["approx_focal_length_mm"] if fl is not None]
    
    if valid_focal_lengths:
        # Calculate average of approximate focal lengths
        avg_focal_length = sum(valid_focal_lengths) / len(valid_focal_lengths)
        
        # Plot categories as a pie chart
        plt.figure(figsize=(10, 8))
        plt.pie(
            [count for _, count in category_counts.most_common()],
            labels=[f"{cat} ({count})" for cat, count in category_counts.most_common()],
            autopct='%1.1f%%',
            startangle=90,
            shadow=True,
        )
        plt.axis('equal')
        plt.title('Focal Length Categories Distribution')
        plt.tight_layout()
        plt.savefig(os.path.join(output_dir, 'category_distribution.png'))
        
        # Plot confidence scores
        plt.figure(figsize=(12, 6))
        plt.bar(range(len(results["confidence"])), results["confidence"])
        plt.xticks(range(len(results["image_path"])), [os.path.basename(path) for path in results["image_path"]], rotation=90)
        plt.xlabel('Image')
        plt.ylabel('Confidence')
        plt.title('Model Confidence for Focal Length Categories')
        plt.tight_layout()
        plt.savefig(os.path.join(output_dir, 'confidence_scores.png'))
        
        # Save results to CSV
        with open(os.path.join(output_dir, 'results.csv'), 'w') as f:
            f.write("image_path,focal_length_category,approx_focal_length_mm,confidence\n")
            for i in range(len(results["image_path"])):
                image_filename = os.path.basename(results["image_path"][i])
                f.write(f"{image_filename},{results['focal_length_category'][i]},{results['approx_focal_length_mm'][i]},{results['confidence'][i]}\n")
        
        # Save summary
        end_time = time.time()
        total_time = end_time - start_time
        
        summary = {
            "most_common_category": most_common_category,
            "category_distribution": {cat: count for cat, count in category_counts.most_common()},
            "approximate_focal_length_mm": approx_focal_length,
            "average_approximate_focal_length_mm": avg_focal_length,
            "total_images_processed": len(image_paths),
            "valid_estimations": len(valid_focal_lengths),
            "total_processing_time_seconds": total_time,
            "average_time_per_image_seconds": total_time / len(image_paths) if image_paths else 0,
            "model_load_time_seconds": model_load_time
        }
        
        with open(os.path.join(output_dir, 'summary.json'), 'w') as f:
            json.dump(summary, f, indent=2)
        
        print(f"Most common focal length category: {most_common_category}")
        print(f"Approximate focal length: {approx_focal_length}mm (based on category)")
        print(f"Average approximate focal length: {avg_focal_length:.2f}mm")
        print(f"Category distribution: {dict(category_counts)}")
        print(f"Total processing time: {total_time:.2f} seconds")
        print(f"Average time per image: {total_time / len(image_paths):.2f} seconds")
    else:
        print("No valid focal length categories were obtained.")
    
    return results

def process_video_first_frame(video_path, output_dir):
    """Process just the first frame of a video file to estimate focal length."""
    if not HAS_AV:
        print("Error: PyAV is required for video processing but is not installed.")
        print("Please install it with: pip install av")
        sys.exit(1)
    
    # Create a timestamped subdirectory for this run
    timestamp = time.strftime('%Y%m%d_%H%M%S')
    video_name = os.path.splitext(os.path.basename(video_path))[0]
    run_dir = os.path.join(output_dir, f"{video_name}_{timestamp}")
    os.makedirs(run_dir, exist_ok=True)
    
    print(f"Results will be saved to: {run_dir}")
    
    # Set up logging
    log_file = os.path.join(run_dir, 'processing_log.txt')
    with open(log_file, 'w') as log:
        log.write(f"=== VIDEO FOCAL LENGTH PROCESSING LOG ===\n")
        log.write(f"Video: {video_path}\n")
        log.write(f"Timestamp: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        log.write(f"Output directory: {run_dir}\n\n")
    
    def log_message(message):
        """Log a message to both console and log file"""
        print(message)
        with open(log_file, 'a') as log:
            log.write(f"{message}\n")
    
    try:
        log_message(f"Extracting first frame from video: {video_path}")
        first_frame = extract_first_frame(video_path)
        
        # Save the frame
        frame_filename = f"first_frame.jpg"
        frame_path = os.path.join(run_dir, frame_filename)
        first_frame.save(frame_path)
        log_message(f"Saved first frame to: {frame_path}")
        
        # Process the extracted frame as an image
        log_message("Processing first frame with focal length model...")
        image_paths = [frame_path]
        
        # Modified process_images function call for direct model output
        # Load the focal length estimation model
        log_message("Loading focal length classification model...")
        model_load_start = time.time()
        
        # Device selection logic - prioritize MPS, then CUDA, then CPU
        import torch
        
        if hasattr(torch, 'backends') and hasattr(torch.backends, 'mps') and torch.backends.mps.is_available():
            device = "mps"
        elif torch.cuda.is_available():
            device = "cuda"
        else:
            device = "cpu"
        
        log_message(f"Using device: {device}")
        pipe = pipeline("image-classification", model="tonyassi/camera-lens-focal-length", device=device)
        model_load_time = time.time() - model_load_start
        log_message(f"Model loaded in {model_load_time:.2f} seconds")
        
        # Process the image with the model
        pil_image = Image.open(frame_path)
        prediction_result = pipe(pil_image)
        
        # Log raw model output
        log_message("\nRAW MODEL OUTPUT:")
        log_message(json.dumps(prediction_result, indent=2))
        
        # Extract and process predictions
        # The model returns categories (ULTRA-WIDE, WIDE, MEDIUM, LONG-LENS, TELEPHOTO)
        # We convert these to approximate mm values based on standard ranges
        
        if prediction_result:
            log_message("\nPREDICTIONS RANKED BY CONFIDENCE:")
            for i, pred in enumerate(prediction_result):
                category = pred["label"]
                confidence = pred["score"]
                approx_focal_length = get_approx_focal_length(category)
                log_message(f"{i+1}. {category} ({confidence:.4f} confidence)")
                log_message(f"   Approximate focal length: {approx_focal_length}mm")
                
                # Explanation of the estimation
                min_val, max_val = FOCAL_LENGTH_RANGES[category]
                log_message(f"   Range: {min_val}-{max_val}mm (taking midpoint as estimate)")
            
            # Process top prediction
            top_prediction = prediction_result[0]
            category = top_prediction["label"]
            confidence = top_prediction["score"]
            approx_focal_length = get_approx_focal_length(category)
            
            # Border for clear visibility in terminal
            border = "=" * 60
            log_message(f"\n{border}")
            log_message(f"FOCAL LENGTH ESTIMATION FOR VIDEO: {video_path}")
            log_message(f"Category: {category}")
            log_message(f"Approximate focal length: {approx_focal_length}mm")
            log_message(f"Confidence: {confidence:.4f}")
            log_message(f"{border}")
            
            # Explain how the focal length was calculated
            log_message("\nNOTE ON FOCAL LENGTH CALCULATION:")
            log_message(f"The model classifies the image into one of five categories:")
            for cat, (min_val, max_val) in FOCAL_LENGTH_RANGES.items():
                log_message(f"- {cat}: {min_val}-{max_val}mm")
            log_message("The approximate focal length is calculated as the midpoint of the range.")
            log_message("This is an ESTIMATE based on visual characteristics, not EXIF data.")
            
            # Save video-specific summary
            summary = {
                "video_path": video_path,
                "focal_length_category": category,
                "approx_focal_length_mm": approx_focal_length,
                "confidence": confidence,
                "all_predictions": [
                    {
                        "category": pred["label"],
                        "confidence": pred["score"],
                        "approx_focal_length_mm": get_approx_focal_length(pred["label"]),
                        "range_mm": FOCAL_LENGTH_RANGES[pred["label"]]
                    }
                    for pred in prediction_result
                ],
                "model_info": {
                    "name": "tonyassi/camera-lens-focal-length",
                    "device": device,
                    "load_time_seconds": model_load_time
                },
                "processing_info": {
                    "timestamp": time.strftime('%Y-%m-%d %H:%M:%S'),
                    "log_file": log_file
                }
            }
            
            with open(os.path.join(run_dir, 'video_summary.json'), 'w') as f:
                json.dump(summary, f, indent=2)
                
            log_message(f"\nSummary saved to: {os.path.join(run_dir, 'video_summary.json')}")
            log_message(f"Full log saved to: {log_file}")
            
            # Also save a copy of the summary to the main output directory with timestamp
            summary_filename = f"{video_name}_summary_{timestamp}.json"
            with open(os.path.join(output_dir, summary_filename), 'w') as f:
                json.dump(summary, f, indent=2)
            log_message(f"Copy of summary saved to: {os.path.join(output_dir, summary_filename)}")
            
            return prediction_result
        else:
            log_message("Could not determine focal length for the video - no predictions returned.")
            return None
    
    except Exception as e:
        error_msg = f"Error processing video: {e}"
        print(error_msg)
        with open(log_file, 'a') as log:
            log.write(f"{error_msg}\n")
            import traceback
            log.write(traceback.format_exc())
            
        # Save the error to a file in the main output directory
        error_file = os.path.join(output_dir, f"{video_name}_error_{timestamp}.txt")
        with open(error_file, 'w') as f:
            f.write(f"Error processing {video_path} at {time.strftime('%Y-%m-%d %H:%M:%S')}:\n")
            f.write(f"{error_msg}\n")
            f.write(traceback.format_exc())
        print(f"Error details saved to: {error_file}")
        
        return None

def main():
    parser = argparse.ArgumentParser(description='Classify focal length from images/videos using a Hugging Face model')
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--image', '-i', type=str, help='Path to a single image file')
    group.add_argument('--directory', '-d', type=str, help='Path to a directory containing images')
    group.add_argument('--files', '-f', type=str, nargs='+', help='List of image file paths')
    group.add_argument('--video', '-v', type=str, help='Path to a video file (only first frame will be processed)')
    
    parser.add_argument('--output', '-o', type=str, default='output_huggingface', help='Output directory')
    parser.add_argument('--extensions', '-e', type=str, default='.jpg,.jpeg,.png', 
                        help='Comma-separated list of image file extensions (default: .jpg,.jpeg,.png)')
    
    args = parser.parse_args()
    
    # Process video (first frame only)
    if args.video:
        if not os.path.isfile(args.video):
            print(f"Error: Video file not found: {args.video}")
            sys.exit(1)
        
        process_video_first_frame(args.video, args.output)
        return
    
    # Collect image paths
    image_paths = []
    
    if args.image:
        if os.path.isfile(args.image):
            image_paths = [args.image]
        else:
            print(f"Error: Image file not found: {args.image}")
            sys.exit(1)
    
    elif args.directory:
        if not os.path.isdir(args.directory):
            print(f"Error: Directory not found: {args.directory}")
            sys.exit(1)
        
        # Get list of valid extensions
        extensions = args.extensions.split(',')
        
        # Find all image files in the directory
        for ext in extensions:
            ext_pattern = os.path.join(args.directory, f"*{ext}")
            image_paths.extend(glob.glob(ext_pattern))
        
        if not image_paths:
            print(f"Error: No images with extensions {extensions} found in {args.directory}")
            sys.exit(1)
    
    elif args.files:
        # Validate that all specified files exist
        for file_path in args.files:
            if os.path.isfile(file_path):
                image_paths.append(file_path)
            else:
                print(f"Warning: File not found: {file_path}")
        
        if not image_paths:
            print("Error: None of the specified files were found")
            sys.exit(1)
    
    # Process the images
    print(f"Found {len(image_paths)} images to process")
    process_images(image_paths, args.output)

if __name__ == "__main__":
    main()