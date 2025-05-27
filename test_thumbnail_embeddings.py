#!/usr/bin/env python
"""
Test script for thumbnail embedding generation.
"""

import os
import sys
import glob
from typing import Dict, Any, List, Optional
import logging
import json
from dotenv import load_dotenv

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("test_embeddings")

# Load environment variables from .env file
load_dotenv()

# Import the functions
from video_ingest_tool.embeddings_image import generate_thumbnail_embedding, batch_generate_thumbnail_embeddings

def test_single_thumbnail(image_path: str) -> None:
    """Test embedding generation for a single thumbnail."""
    description = "A person standing in front of a green screen, speaking to the camera"
    
    logger.info(f"Testing embedding generation for: {image_path}")
    
    embedding = generate_thumbnail_embedding(
        image_path=image_path,
        description=description,
        logger=logger
    )
    
    if embedding:
        logger.info(f"✅ Successfully generated embedding with dimension: {len(embedding)}")
        logger.info(f"First 5 values: {embedding[:5]}")
    else:
        logger.error("❌ Failed to generate embedding")

def test_batch_thumbnails(thumbnail_dir: str) -> None:
    """Test batch embedding generation for multiple thumbnails."""
    # Find all jpg files in the thumbnail directory
    image_files = glob.glob(f"{thumbnail_dir}/*.jpg")
    
    if not image_files:
        logger.error(f"No thumbnail images found in {thumbnail_dir}")
        return
    
    # Create thumbnail metadata
    thumbnails = []
    for i, path in enumerate(image_files[:3]):  # Limit to first 3 thumbnails
        thumbnails.append({
            'path': path,
            'description': f"Thumbnail {i+1} from test video",
            'rank': str(i+1)  # Use string rank to match schema
        })
    
    logger.info(f"Testing batch embedding generation for {len(thumbnails)} thumbnails")
    
    embeddings = batch_generate_thumbnail_embeddings(
        thumbnails=thumbnails,
        logger=logger
    )
    
    if embeddings:
        logger.info(f"✅ Successfully generated {len(embeddings)} embeddings")
        for rank, embedding in embeddings.items():
            if embedding:
                logger.info(f"  Rank {rank}: dimension {len(embedding)}")
            else:
                logger.info(f"  Rank {rank}: embedding generation failed")
    else:
        logger.error("❌ Failed to generate any embeddings")

def main():
    """Main function."""
    # Find a recent thumbnail directory to use for testing
    # Look for the most recent run
    runs_dirs = glob.glob("output/runs/run_*")
    if not runs_dirs:
        logger.error("No run directories found")
        return
    
    # Sort by modification time (newest first)
    runs_dirs.sort(key=lambda x: os.path.getmtime(x), reverse=True)
    most_recent_run = runs_dirs[0]
    
    logger.info(f"Using most recent run: {most_recent_run}")
    
    # Find thumbnail directories
    thumbnail_dirs = glob.glob(f"{most_recent_run}/thumbnails/*")
    if not thumbnail_dirs:
        logger.error("No thumbnail directories found")
        return
    
    most_recent_thumbnails = thumbnail_dirs[0]
    logger.info(f"Using thumbnail directory: {most_recent_thumbnails}")
    
    # Find thumbnail images
    thumbnail_images = glob.glob(f"{most_recent_thumbnails}/*.jpg")
    if not thumbnail_images:
        logger.error("No thumbnail images found")
        return
    
    # Test single thumbnail
    test_single_thumbnail(thumbnail_images[0])
    
    # Test batch thumbnails
    test_batch_thumbnails(most_recent_thumbnails)

if __name__ == "__main__":
    main() 