#!/usr/bin/env python3
"""
Entry point for running the video ingest tool as a module.
Example: python -m video_ingest_tool /path/to/videos
"""

import sys
from .video_ingestor import app

if __name__ == "__main__":
    # Forward command line arguments to the Typer app
    app()
