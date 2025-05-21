#!/usr/bin/env python3
"""
Task Queue System for Video Ingestor Tool

This module provides a PostgreSQL-based task queue system for the Video Ingestor Tool 
using Procrastinate. All tasks are stored in the database for reliable processing
and persistence between application restarts.

Tasks are properly registered from the video_processor module, eliminating circular imports.
"""

import os
import logging
import sys
from typing import Dict, Any, Optional, List, Union
from pathlib import Path
import uuid
import importlib
import traceback

# Missing dependencies tracking
missing_deps = []

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    # Load from .env file if it exists
    load_dotenv()
    print("DEBUG: Loaded environment variables from .env file")
except ImportError:
    missing_deps.append("python-dotenv")
    print("DEBUG: python-dotenv not installed, using environment variables directly")

# Try to import structlog for structured logging
try:
    import structlog
    HAS_STRUCTLOG = True
except ImportError:
    HAS_STRUCTLOG = False
    print("WARNING: structlog package not found. Install with 'pip install structlog' for enhanced logging.")

# Configure logging
if HAS_STRUCTLOG:
    logger = structlog.get_logger(__name__)
else:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)-5.5s] [%(name)s] %(message)s"
    )
    logger = logging.getLogger(__name__)

# Try to import psycopg for database connectivity
try:
    import psycopg
except ImportError:
    missing_deps.append("psycopg")
    print("WARNING: psycopg not installed. Install with 'pip install psycopg' for PostgreSQL connectivity.")

# Import Procrastinate with PostgreSQL connector
try:
    print("DEBUG: Attempting to import procrastinate...")
    import procrastinate
    print(f"DEBUG: procrastinate imported successfully. Version: {getattr(procrastinate, '__version__', 'N/A')}")
    print("DEBUG: Attempting to import procrastinate.App and procrastinate.PsycopgConnector...")
    from procrastinate import App, PsycopgConnector
    print("DEBUG: procrastinate.App and procrastinate.PsycopgConnector imported successfully.")
    PROCRASTINATE_AVAILABLE = True
except ImportError as e:
    missing_deps.append("procrastinate")
    print(f"DEBUG: ImportError occurred: {e}")
    logger.error("Procrastinate not available. Install with 'pip install procrastinate psycopg2-binary'")
    PROCRASTINATE_AVAILABLE = False
    # Create dummy App class for type checking
    class App: # type: ignore
        pass
except Exception as e:
    print(f"DEBUG: An unexpected error occurred during import: {e}")
    logger.error(f"Unexpected error importing Procrastinate: {e}")
    PROCRASTINATE_AVAILABLE = False
    class App: # type: ignore
        pass

# Display missing dependencies
if missing_deps:
    print("\nMISSING DEPENDENCIES: Please install these packages for full functionality:")
    print(f"pip install {' '.join(missing_deps)}\n")

def get_db_config() -> Dict[str, Any]:
    """
    Get database configuration from environment variables.
    Environment variables are loaded from .env file if available.
    
    Returns:
        Dict[str, Any]: Database configuration dictionary
    """
    raw_host = os.environ.get("VIDEOINGESTOR_DB_HOST", "localhost")
    resolved_host = "127.0.0.1" if raw_host == "localhost" else raw_host
    return {
        "host": resolved_host,
        "user": os.environ.get("VIDEOINGESTOR_DB_USER", "postgres"),
        "password": os.environ.get("VIDEOINGESTOR_DB_PASSWORD", "password"),
        "dbname": os.environ.get("VIDEOINGESTOR_DB_NAME", "videoingestor"),
        "port": int(os.environ.get("VIDEOINGESTOR_DB_PORT", "5432")),
    }

# Database configuration
DB_CONFIG = get_db_config()

def create_app(db_config: Optional[Dict[str, Any]] = None) -> App:
    """
    Create a Procrastinate App instance with PostgreSQL connector.
    
    Args:
        db_config: Database configuration dictionary
        
    Returns:
        App: Configured Procrastinate App
    """
    if not PROCRASTINATE_AVAILABLE:
        logger.error("Cannot create app: Procrastinate is not installed")
        sys.exit(1)
        
    try:
        logger.info("Creating Procrastinate App with PostgreSQL")
        config = db_config or DB_CONFIG
        
        # Check if psycopg2 is available
        try:
            import psycopg2
            print(f"DEBUG: psycopg2 version: {psycopg2.__version__}")
        except ImportError:
            print("DEBUG: psycopg2 is not installed. Trying to use psycopg instead.")
        
        # Create the connector with improved connection pool settings
        connector = PsycopgConnector(
            kwargs={
                "host": config["host"],
                "user": config["user"],
                "password": config["password"],
                "dbname": config["dbname"],
                "port": config["port"],
            }
        )
        logger.info(f"Connected to PostgreSQL database: {config['dbname']} on {config['host']}:{config['port']}")
    except Exception as e:
        logger.error(f"Failed to connect to PostgreSQL: {str(e)}")
        print(f"\nDEBUG: Detailed connection error: {repr(e)}")
        print("\nPlease ensure PostgreSQL is running and accessible with the following settings:")
        config_display = DB_CONFIG.copy()
        config_display['password'] = '********'  # Hide password
        for key, value in config_display.items():
            print(f"  {key}: {value}")
        print("\nYou can set these values using environment variables:")
        print("  VIDEOINGESTOR_DB_HOST, VIDEOINGESTOR_DB_PORT, VIDEOINGESTOR_DB_USER,")
        print("  VIDEOINGESTOR_DB_PASSWORD, VIDEOINGESTOR_DB_NAME\n")
        sys.exit(1)
    
    app = App(connector=connector)
    return app


# Create the app instance
app = create_app() if PROCRASTINATE_AVAILABLE else None

# Import the task functions from video_processor
# We'll register them with Procrastinate in the init_app function
video_processor = None

def init_app():
    """
    Initialize the Procrastinate app and register tasks.
    This avoids circular import issues by importing video_processor functions here.
    """
    global app, video_processor
    print("DEBUG: Initializing Procrastinate app and registering tasks")
    
    if app is None and PROCRASTINATE_AVAILABLE:
        app = create_app()
    
    if app is not None and video_processor is None:
        try:
            # Import the video_processor module
            import video_ingest_tool.video_processor as vp
            video_processor = vp
            
            # Register task functions with proper queue assignments and locks
            global validate_video_file, extract_metadata, generate_thumbnails
            global analyze_exposure, save_results
            
            # Register tasks with appropriate configurations
            # Use only parameters supported in Procrastinate 3.2.2
            validate_video_file = app.task(
                queue="validation",
                lock="file:{file_path}"
            )(video_processor.validate_video_file)
            
            extract_metadata = app.task(
                queue="metadata",
                lock="file:{file_path}"
            )(video_processor.extract_metadata_task)
            
            generate_thumbnails = app.task(
                queue="thumbnails",
                lock="file:{file_path}"
            )(video_processor.generate_thumbnails_task)
            
            analyze_exposure = app.task(
                queue="analysis",
                lock="file:{file_path}"
            )(video_processor.analyze_exposure_task)
            
            save_results = app.task(
                queue="results",
                lock="file:{file_path}"
            )(video_processor.save_results_task)
            
            logger.info("Successfully registered all tasks with Procrastinate")
        except ImportError as e:
            logger.error(f"Failed to import video_processor: {e}")
            traceback.print_exc()
        except Exception as e:
            logger.error(f"Unexpected error during task registration: {e}")
            traceback.print_exc()
    
    return app


def ensure_schema(app: App) -> bool:
    """
    Ensures that the database schema is properly set up using Procrastinate's
    programmatic schema applier. This is typically called at worker startup.
    Procrastinate's apply_schema is designed to be idempotent.

    Args:
        app: The initialized Procrastinate App instance.

    Returns:
        bool: True if schema application was successful, False otherwise.
    """
    if not app:
        print("ERROR: Procrastinate app instance is not provided or not initialized for ensure_schema.")
        logger.error("Procrastinate app instance is None in ensure_schema.")
        return False

    try:
        print("Attempting to apply/verify Procrastinate schema...")
        with app.open():  # Ensures DB connection is available
            app.schema_manager.apply_schema()
        print("Procrastinate schema applied/verified successfully programmatically.")
        return True
    except procrastinate.exceptions.ConnectorException as e:
        err_msg = f"Database ConnectorException during schema application: {type(e).__name__} - {e}"
        # Check if the underlying psycopg error is about a duplicate object/type
        # This can happen if the schema is already correctly applied by the CLI
        is_duplicate_object_error = False
        # Ensure psycopg.errors is accessible
        if hasattr(psycopg, 'errors') and e.__cause__ and isinstance(e.__cause__, psycopg.errors.DuplicateObject):
            is_duplicate_object_error = True
        
        if is_duplicate_object_error:
            warn_msg = f"Warning during schema apply/verify: {err_msg}. Assuming schema is OK as this often means objects already exist."
            print(f"WARNING: {warn_msg}")
            logger.warning(warn_msg, exc_info=False) # Log as warning, traceback might be too noisy if it's expected
            return True # Proceed, assuming CLI handled actual schema issues
        else:
            print(f"ERROR: {err_msg}")
            import traceback
            traceback.print_exc() # Print traceback to stdout for immediate visibility
            logger.error(err_msg, exc_info=True)
            return False
    except Exception as e:
        err_msg = f"Unexpected error during schema application: {type(e).__name__} - {e}"
        print(f"ERROR: {err_msg}")
        import traceback
        traceback.print_exc() # Print traceback to stdout for immediate visibility
        logger.error(err_msg, exc_info=True)
        return False

def run_worker(queues: Optional[List[str]] = None, concurrency: int = 1) -> None:
    """
    Run a worker to process tasks from the queue.
    
    Args:
        queues: List of queue names to listen to. If None, listen to all queues.
        concurrency: Number of concurrent jobs to process.
    """
    try:
        app = init_app()
        if not app:
            print("ERROR: Failed to initialize Procrastinate app for worker.")
            logger.error("Failed to initialize Procrastinate app for worker.")
            return

        print("Verifying database schema before starting worker...")
        if not ensure_schema(app):
            print("ERROR: Database schema verification/application failed. Worker cannot start.")
            print("       Please ensure the schema is correctly applied. For robust schema management,")
            print("       it's recommended to use the Procrastinate CLI:")
            print("         conda run -n video-ingest env PYTHONPATH=. procrastinate --app=video_ingest_tool.video_ingestor.app schema --apply")
            logger.error("Database schema verification/application failed. Worker will not start.")
            return
        
        print(f"Starting Procrastinate worker with concurrency={concurrency}...")
        if queues:
            print(f"Listening on queues: {', '.join(queues)}")
        else:
            print("Listening on queues: all")
        
        # Start the worker with improved configuration
        with app.open():
            # Try to fetch some jobs first to see what's in the queue
            try:
                import psycopg2
                config = DB_CONFIG
                
                # Connect directly to the database
                print("\nDEBUG: Checking for pending jobs in database...")
                conn = psycopg2.connect(
                    host=config["host"],
                    port=config["port"],
                    dbname=config["dbname"],
                    user=config["user"],
                    password=config["password"]
                )
                
                cursor = conn.cursor()
                
                # Check jobs in the queue
                cursor.execute("""
                    SELECT 
                        id, queue_name, task_name, status, 
                        args, scheduled_at
                    FROM procrastinate_jobs
                    WHERE status = 'todo'
                    ORDER BY id DESC
                    LIMIT 5
                """)
                
                jobs = cursor.fetchall()
                
                if not jobs:
                    print("DEBUG: No 'todo' jobs found in the database.")
                else:
                    print(f"DEBUG: Found {len(jobs)} 'todo' jobs:")
                    for job in jobs:
                        print(f"  Job ID: {job[0]}")
                        print(f"  Queue: {job[1]}")
                        print(f"  Task: {job[2]}")
                        print(f"  Status: {job[3]}")
                        print(f"  Args: {job[4]}")
                
                # Check registered tasks
                cursor.execute("""
                    SELECT task_name FROM procrastinate_tasks
                """)
                
                tasks = cursor.fetchall()
                print("\nDEBUG: Registered tasks:")
                for task in tasks:
                    print(f"  - {task[0]}")
                    
                cursor.close()
                conn.close()
                
            except Exception as e:
                print(f"DEBUG: Error checking jobs: {e}")
            
            print("\nDEBUG: Starting worker with listen_notify=False (polling mode)")
            app.run_worker(
                queues=queues,
                concurrency=concurrency,
                wait=True,
                # Disable LISTEN/NOTIFY to use polling instead
                listen_notify=False
            )
    except KeyboardInterrupt:
        print("\nWorker stopped by user. Shutting down gracefully...")
        logger.info("Worker stopped by keyboard interrupt")
    except Exception as e:
        detailed_error = f"Worker error: {type(e).__name__}: {str(e)}\nFull repr: {repr(e)}"
        print(detailed_error)
        logger.error("Worker failed to start or encountered an error", exc_info=True)
        print("\nPossible solutions:")
        print("1. Ensure PostgreSQL is running")
        print("2. Check that the database 'videoingestor' exists")
        print("3. Verify the user 'postgres' has permission to access the database")
        print("4. Check that all required tables and columns exist")

def enqueue_video_processing(file_path: str) -> str:
    """
    Enqueue a video file for processing.
    
    Args:
        file_path: Path to the video file
        
    Returns:
        str: Job ID
    """
    # Initialize app if not already done
    app = init_app()
    if not app:
        logger.error("Failed to initialize app")
        return ""
    
    # Generate a unique job ID
    job_id = str(uuid.uuid4())
    
    # Enqueue the first task with a lock based on file path
    with app.open():
        validate_video_file.defer(file_path=file_path, job_id=job_id)
    
    logger.info("Video processing job enqueued", file_path=file_path, job_id=job_id)
    return job_id

# Note: We removed the event handlers (app.on_success) for compatibility
# Task chaining is now handled directly in the task functions

# Initialize the app upon import
init_app()
