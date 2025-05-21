#!/usr/bin/env python3
"""
Quick script to examine EXIF data and debug focal length issues
"""

import exiftool

# Path to a video file
video_path = "/Users/developer/Development/GitHub/AIIngestingTool/test/MVI_0476.MP4"

with exiftool.ExifToolHelper() as et:
    metadata = et.get_metadata(video_path)[0]
    
    # Print all metadata keys
    print("All metadata keys:")
    for key in sorted(metadata.keys()):
        print(f"  {key}: {metadata[key]}")
    
    # Look specifically for focal length
    print("\nFocal length related fields:")
    for key in metadata:
        if "focal" in key.lower() or "lens" in key.lower():
            print(f"  {key}: {metadata[key]}")
