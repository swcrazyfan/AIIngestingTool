#!/usr/bin/env python
"""
Test script for AI thumbnail selection step.
"""

import os
import sys
import json
import logging
from typing import Dict, Any, List, Optional
from dotenv import load_dotenv

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("test_ai_thumbnail")

# Load environment variables
load_dotenv()

# Import the AI thumbnail selection step
from video_ingest_tool.steps.analysis.ai_thumbnail_selection import ai_thumbnail_selection_step

def load_test_data(json_path: str) -> Dict[str, Any]:
    """Load test data from a JSON file."""
    with open(json_path, 'r') as f:
        return json.load(f)

def main():
    """Run the AI thumbnail selection test."""
    # Find all run directories with AI analysis files
    run_dirs = []
    for root, dirs, files in os.walk("./output/runs"):
        if "ai_analysis" in dirs:
            ai_dir = os.path.join(root, "ai_analysis")
            json_files = [f for f in os.listdir(ai_dir) if f.endswith("_AI_analysis.json")]
            if json_files:
                run_dirs.append((root, ai_dir, json_files))
    
    if not run_dirs:
        logger.error("No AI analysis files found in any run directory")
        return
    
    # Sort to get the newest first
    run_dirs.sort(reverse=True, key=lambda x: os.path.basename(x[0]))
    
    # Take the first one with AI analysis
    latest_run, ai_analysis_dir, json_files = run_dirs[0]
    
    json_path = os.path.join(ai_analysis_dir, json_files[0])
    logger.info(f"Using AI analysis file: {json_path}")
    logger.info(f"From run directory: {latest_run}")
    
    # Load AI analysis data
    analysis_data = load_test_data(json_path)
    
    # Debug info
    logger.info("JSON structure debug info:")
    logger.info(f"Keys at root level: {list(analysis_data.keys())}")
    if 'visual_analysis' in analysis_data:
        logger.info(f"Keys in visual_analysis: {list(analysis_data['visual_analysis'].keys())}")
        if 'keyframe_analysis' in analysis_data['visual_analysis']:
            logger.info(f"Keys in keyframe_analysis: {list(analysis_data['visual_analysis']['keyframe_analysis'].keys())}")
            if 'recommended_thumbnails' in analysis_data['visual_analysis']['keyframe_analysis']:
                logger.info(f"Found recommended_thumbnails with {len(analysis_data['visual_analysis']['keyframe_analysis']['recommended_thumbnails'])} items")
            else:
                logger.info("No recommended_thumbnails found in keyframe_analysis")
        else:
            logger.info("No keyframe_analysis key found in visual_analysis")
    else:
        logger.info("No visual_analysis key found at root level")
    
    # Find the original video file from the run directory
    input_file = None
    for file in os.listdir("./test_new_vid"):
        if file.endswith(".mp4"):
            input_file = os.path.join("./test_new_vid", file)
            break
    
    if not input_file:
        logger.error("No video file found in ./test_new_vid")
        return
    
    # Create test data
    test_data = {
        "file_path": input_file,
        "checksum": os.path.basename(json_path).split("_AI_analysis.json")[0],
        "analysis_results": analysis_data
    }
    
    # Run the AI thumbnail selection step
    thumbnails_dir = os.path.join(latest_run, "thumbnails")
    logger.info(f"Using thumbnails directory: {thumbnails_dir}")
    
    try:
        result = ai_thumbnail_selection_step(test_data, thumbnails_dir, logger)
        
        # Display results
        paths = result.get("ai_thumbnail_paths", [])
        metadata = result.get("ai_thumbnail_metadata", [])
        
        logger.info(f"Generated {len(paths)} AI thumbnails")
        for i, (path, meta) in enumerate(zip(paths, metadata)):
            logger.info(f"AI Thumbnail {i+1}:")
            logger.info(f"  Path: {path}")
            logger.info(f"  Timestamp: {meta.get('timestamp')}")
            logger.info(f"  Rank: {meta.get('rank')}")
            logger.info(f"  Description: {meta.get('description')}")
            logger.info(f"  Reason: {meta.get('reason')}")
            logger.info("")
        
    except Exception as e:
        logger.error(f"Error testing AI thumbnail selection: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main() 