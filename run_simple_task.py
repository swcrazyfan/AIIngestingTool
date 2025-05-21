#!/usr/bin/env python3
"""
Run a Simple Task

This script demonstrates a simple task execution with proper queue handling.
"""

import os
import sys
import time

# Add the parent directory to the path so we can import video_ingest_tool
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def simple_task(a: int, b: int) -> int:
    """A simple addition task"""
    print(f"Executing simple_task with {a} + {b}")
    time.sleep(2)  # Simulate some work
    result = a + b
    print(f"Result: {result}")
    return result

def main():
    print("Setting up task queue")
    from video_ingest_tool.task_queue import app, init_app, ensure_schema

    print("Initializing app...")
    init_app()
    if not app:
        print("ERROR: Failed to initialize Procrastinate app")
        return

    print("Ensuring schema is applied...")
    ensure_schema(app)
    
    # Register the task
    print("Registering simple task...")
    simple_task_registered = app.task(queue="math")(simple_task)
    
    # Queue 5 simple tasks
    print("Queueing 5 addition tasks...")
    with app.open():
        for i in range(5):
            a = i
            b = i * 10
            simple_task_registered.defer(a=a, b=b)
            print(f"Queued task: {a} + {b}")
    
    print("\nTasks queued successfully! Now run the worker:")
    print("\n    python -m video_ingest_tool worker -q math\n")
    print("Or check the queue status:")
    print("\n    python debug_queue.py\n")

if __name__ == "__main__":
    main()
