"""
API package for the video ingest tool.

This package provides a streamlined Flask API server that wraps the CLI command
classes, providing a thin HTTP layer over the standardized command interface.
"""

from .server import create_app
from .progress_tracker import get_progress_tracker

__all__ = ['create_app', 'get_progress_tracker'] 