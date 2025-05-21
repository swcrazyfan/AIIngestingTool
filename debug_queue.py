#!/usr/bin/env python3
"""
Debug Queue Script

This script helps debug the Procrastinate task queue by examining the database
directly and listing pending jobs.
"""

import os
import sys
import psycopg2
from pprint import pprint

# Add the parent directory to the path so we can import video_ingest_tool
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from video_ingest_tool.task_queue import get_db_config, app, init_app

def main():
    print("Creating app and connecting to database...")
    init_app()
    
    if not app:
        print("ERROR: Failed to create Procrastinate app")
        return
    
    # Get database configuration
    db_config = get_db_config()
    
    try:
        print("Opening connection...")
        # Connect directly with psycopg2 to examine the database
        conn = psycopg2.connect(
            host=db_config['host'],
            dbname=db_config['dbname'],
            user=db_config['user'],
            password=db_config['password'],
            port=db_config['port']
        )
        
        # Create a cursor
        cur = conn.cursor()
        
        # Check if tables exist
        print("\nChecking if procrastinate_jobs table exists...")
        cur.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_name = 'procrastinate_jobs'
            );
        """)
        table_exists = cur.fetchone()[0]
        
        if not table_exists:
            print("ERROR: procrastinate_jobs table does not exist!")
            print("Try running: python -m video_ingest_tool schema")
        else:
            print("procrastinate_jobs table exists!")
            
            # Count jobs by status
            cur.execute("""
                SELECT status, COUNT(*) 
                FROM procrastinate_jobs 
                GROUP BY status
            """)
            job_counts = cur.fetchall()
            
            print("\nJob counts by status:")
            if not job_counts:
                print("No jobs found in the database.")
            else:
                for status, count in job_counts:
                    print(f"  {status}: {count}")
            
            # Check for pending jobs
            print("\nPending jobs:")
            cur.execute("""
                SELECT id, queue_name, task_name, lock, args, status, scheduled_at
                FROM procrastinate_jobs
                WHERE status = 'todo'
                ORDER BY id
                LIMIT 5
            """)
            pending_jobs = cur.fetchall()
            
            if not pending_jobs:
                print("No pending jobs found.")
            else:
                for job in pending_jobs:
                    job_id, queue, task, lock, args, status, scheduled = job
                    print(f"Job #{job_id}:")
                    print(f"  Queue: {queue}")
                    print(f"  Task: {task}")
                    print(f"  Lock: {lock}")
                    print(f"  Args: {args}")
                    print(f"  Status: {status}")
                    print(f"  Scheduled: {scheduled}")
                    print()
        
        # Close the cursor and connection
        cur.close()
        conn.close()
        
        # Try to use Procrastinate's built-in schema application
        if table_exists:
            print("\nApplying schema via Procrastinate (if needed)...")
            try:
                with app.open():
                    app.schema_manager.apply_schema()
                print("Schema applied successfully.")
            except Exception as e:
                print(f"Error applying schema: {e}")
                
    except Exception as e:
        print(f"Database error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
