#!/usr/bin/env python3
"""
Apply Procrastinate Schema

This script uses Procrastinate's CLI capabilities to fully apply the schema.
"""

import sys
import os
import subprocess

# Ensure we can access the video_ingest_tool package
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import the necessary modules
from video_ingest_tool.task_queue import get_db_config

def main():
    """Apply the Procrastinate schema using CLI"""
    # Get database configuration
    db_config = get_db_config()
    
    # Build the connection string
    conn_string = (
        f"postgresql://{db_config['user']}:{db_config['password']}@"
        f"{db_config['host']}:{db_config['port']}/{db_config['dbname']}"
    )
    
    # Set environment variables for procrastinate
    env = os.environ.copy()
    env["PROCRASTINATE_APP"] = "video_ingest_tool.video_ingestor.app"
    env["PROCRASTINATE_URL"] = conn_string
    
    # Check if procrastinate CLI is available
    try:
        # Run procrastinate healthchecks
        print("Running Procrastinate healthchecks...")
        result = subprocess.run(
            ["procrastinate", "healthchecks"], 
            env=env,
            capture_output=True,
            text=True
        )
        print(result.stdout)
        if result.returncode != 0:
            print(f"Error running healthchecks: {result.stderr}")
    except FileNotFoundError:
        print("Procrastinate CLI not found. Please install it with:")
        print("pip install procrastinate")
        return
    
    # Apply the schema
    print("\nApplying Procrastinate schema...")
    try:
        # Using --apply to force schema creation
        result = subprocess.run(
            ["procrastinate", "schema", "--apply"], 
            env=env,
            capture_output=True,
            text=True
        )
        print(result.stdout)
        if result.returncode != 0:
            print(f"Error applying schema: {result.stderr}")
        else:
            print("Schema applied successfully!")
    except Exception as e:
        print(f"Error: {e}")
    
    # Show schema information
    print("\nSchema information:")
    try:
        result = subprocess.run(
            ["procrastinate", "schema", "--info"], 
            env=env,
            capture_output=True,
            text=True
        )
        print(result.stdout)
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
