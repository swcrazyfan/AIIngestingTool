#!/usr/bin/env python3
"""
Test Queue Script

This script tests the Procrastinate task queue by queueing a simple test task
and verifying that it works.
"""

import os
import sys
import time
import uuid

# Add the parent directory to the path so we can import video_ingest_tool
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import task queue
from video_ingest_tool.task_queue import app, init_app, ensure_schema

def test_task(message: str, job_id: str):
    """A simple test task for Procrastinate"""
    print(f"Test task executed with message: {message}")
    print(f"Job ID: {job_id}")
    return {"status": "success", "message": message, "job_id": job_id}

def main():
    print("Initializing app...")
    init_app()
    
    # Ensure app is available
    if not app:
        print("ERROR: Failed to initialize Procrastinate app")
        return
    
    # Ensure schema is applied
    print("Ensuring schema is applied...")
    if not ensure_schema(app):
        print("ERROR: Failed to apply schema")
        return
    
    # Register the test task
    print("Registering test task...")
    test_task_registered = app.task(queue="test")(test_task)
    
    # Generate a unique job ID
    job_id = str(uuid.uuid4())
    
    # Queue the test task
    print(f"Queueing test task with job ID: {job_id}")
    with app.open():
        test_task_registered.defer(message="Hello, Procrastinate!", job_id=job_id)
    
    # Wait a moment
    print("Task queued successfully! Now run a worker to process it:")
    print("\n    python -m video_ingest_tool worker -q test\n")
    print("Or run the debug script to view pending jobs:")
    print("\n    python debug_queue.py\n")

if __name__ == "__main__":
    main()
