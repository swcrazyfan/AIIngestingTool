#!/usr/bin/env python3
"""
AI-Powered Video Ingest & Catalog Tool - Main Entry Point

This file allows the package to be run directly with:
python -m video_ingest_tool

It simply imports and runs the CLI from video_ingestor.py
"""

from .video_ingestor import run

if __name__ == "__main__":
    run()
