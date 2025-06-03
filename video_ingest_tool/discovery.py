"""
File discovery module for the video ingest tool.

Contains functions for scanning directories and identifying video files.
"""

import os
from typing import List
from rich.progress import Progress
import magic
import logging

from .config import console
from .utils import is_video_file
# from .models import VideoFile, IngestConfig # Removed unused import
# from .config import SUPPORTED_EXTENSIONS, EXCLUDED_SUBSTRINGS # Removed unused import

def scan_directory(directory: str, recursive: bool = True, logger=None, has_polyfile: bool = False) -> List[str]:
    """
    Scan directory for video files.
    
    Args:
        directory: Directory to scan
        recursive: Whether to scan subdirectories
        logger: Logger instance
        has_polyfile: Whether polyfile module is available
        
    Returns:
        List[str]: List of video file paths
    """
    if logger:
        logger.info("Scanning directory", directory=directory, recursive=recursive)
    
    video_files = []
    
    with Progress(console=console, transient=True) as progress:
        task = progress.add_task("[cyan]Scanning directory...", total=None)
        
        for root, dirs, files in os.walk(directory):
            progress.update(task, advance=1, description=f"[cyan]Scanning {root}")
            
            for file in files:
                file_path = os.path.join(root, file)
                if is_video_file(file_path, has_polyfile):
                    video_files.append(file_path)
                    if logger:
                        logger.info("Found video file", path=file_path)
            
            if not recursive:
                dirs.clear()
    
    if logger:
        logger.info("Directory scan complete", video_count=len(video_files))
    
    return video_files
