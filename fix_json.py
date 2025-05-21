#!/usr/bin/env python3
"""
Quick fix script to view and fix JSON output in video ingestor
"""

import json
import os
import sys

# Look in the last few JSON files in the json_output directory
json_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "json_output")
json_files = sorted([f for f in os.listdir(json_dir) if f.startswith('all_videos_')], reverse=True)

if not json_files:
    print("No JSON files found")
    sys.exit(1)

latest_json = os.path.join(json_dir, json_files[0])
print(f"Examining: {latest_json}")

# Read the current content
with open(latest_json, 'r') as f:
    content = f.read()
    print(f"Current content length: {len(content)} bytes")
    if len(content) <= 2:
        print("Content is empty: []")
    else:
        data = json.loads(content)
        print(f"Found {len(data)} items")

# Fix for Pydantic validation error
# Look at other JSON files to see if they have video objects
individual_jsons = [f for f in os.listdir(json_dir) if not f.startswith('all_videos_') and f.endswith('.json')]

print(f"Found {len(individual_jsons)} individual JSON files")

# Create a fixed file with dummy data
fixed_data = []

print("Creating dummy data for example...")

# Create a sample entry
sample_entry = {
    "id": "12345678-1234-5678-1234-567812345678",
    "file_path": "/path/to/video/sample.mp4",
    "file_name": "sample.mp4",
    "file_checksum": "abcdef123456789",
    "file_size_bytes": 1000000,
    "processed_at": "2025-05-21T19:20:00",
    "duration_seconds": 120.5,
    "technical_metadata": {
        "codec": "h264",
        "container": "mp4",
        "resolution_width": 1920,
        "resolution_height": 1080,
        "aspect_ratio": "16:9",
        "frame_rate": 30.0,
        "bit_rate_kbps": 5000,
        "duration_seconds": 120.5,
        "exposure_warning": False,
        "exposure_stops": 0.0,
        "overexposed_percentage": 0.0,
        "underexposed_percentage": 0.2,
        "bit_depth": 8,
        "color_space": "YUV",
        "camera_make": "Canon",
        "camera_model": "EOS 5D",
        "focal_length": "MEDIUM"  # Using string value for focal_length category
    },
    "thumbnail_paths": [
        "/path/to/thumbnails/sample1.jpg",
        "/path/to/thumbnails/sample2.jpg"
    ]
}

fixed_data.append(sample_entry)

output_file = os.path.join(json_dir, "sample_fixed.json")
with open(output_file, 'w') as f:
    json.dump(fixed_data, f, indent=2)

print(f"Created example file at: {output_file}")
print("\nYou can use this as a guide to fix the focal_length validation error in video_ingestor.py")
print("The exact error is that focal_length should be a string category not a number")
print("\nCheck the TechnicalMetadata class in video_ingestor.py and modify it to either:")
print("1. Accept integers for focal_length (change the field type to Optional[Union[str, int]])")
print("2. Convert the focal_length value to a string before assigning it to the model")
print("3. Map numeric focal lengths to category strings (ULTRA-WIDE, WIDE, etc.)")
