"""
AI-Powered Video Ingest & Catalog Tool

This package provides tools for video ingestion, metadata extraction, and cataloging.
It consists of three main components:
- video_processor.py: Core video processing functions
- task_queue.py: Task queuing system backed by Procrastinate and PostgreSQL
- video_ingestor.py: CLI interface for the tool

The system can operate either with direct processing or asynchronously via the task queue.
"""

__version__ = "0.1.0"

# Make key components available at package level
try:
    from .video_ingestor import ingest, worker, schema, db_status, run
    
    # Try to import task_queue components, but don't fail if not available
    try:
        from .task_queue import enqueue_video_processing, run_worker
        HAS_TASK_QUEUE = True
    except (ImportError, AttributeError):
        HAS_TASK_QUEUE = False
except ImportError:
    # These will be imported when used directly, not through package import
    pass
