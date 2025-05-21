#!/usr/bin/env python3
"""
AI-Powered Video Ingest & Catalog Tool - Alpha Test Implementation

This script provides the CLI interface for the video ingestion and cataloging process:
1. Content Discovery Phase - Scan directories for video files and create checksums
2. Technical Metadata Extraction - Extract detailed information about video files
3. Task Queue System - Asynchronous processing with Procrastinate

Videos can be processed either directly or asynchronously through a task queue.
All processing steps are logged to the terminal and to timestamped log files,
and data is saved to JSON while the DB integration is pending.
"""

import os
import sys
import json
import time
import datetime
import uuid
import pathlib
from typing import Any, Dict, List, Optional, Tuple, Union
import mimetypes
import logging
from logging import FileHandler
import typer

# Try to import rich for enhanced terminal output
try:
    from rich.console import Console
    from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeRemainingColumn
    from rich.panel import Panel
    from rich.table import Table
    from rich.logging import RichHandler
    HAS_RICH = True
except ImportError:
    HAS_RICH = False
    print("WARNING: rich package not found. Install with 'pip install rich' for enhanced terminal output.")

# Try to import structlog for structured logging
try:
    import structlog
    HAS_STRUCTLOG = True
except ImportError:
    HAS_STRUCTLOG = False
    print("WARNING: structlog package not found. Install with 'pip install structlog' for enhanced logging.")

# Try to import polyfile for file type detection
try:
    from polyfile.magic import MagicMatcher
    HAS_POLYFILE = True
except ImportError:
    HAS_POLYFILE = False
    print("WARNING: polyfile package not found. Install with 'pip install polyfile' for enhanced file type detection.")

# Configure the base application
cli = typer.Typer(help="AI-Powered Video Ingest & Catalog Tool - Alpha Test")

# Initialize console
if HAS_RICH:
    console = Console()
else:
    # Define a simple console.print alternative
    class SimpleConsole:
        def print(self, text, **kwargs):
            print(text)
    console = SimpleConsole()

# Configure logging
log_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs")
os.makedirs(log_dir, exist_ok=True)

# Create a timestamp for current run
timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
log_file = os.path.join(log_dir, f"ingestor_{timestamp}.log")
json_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "json_output")
os.makedirs(json_dir, exist_ok=True)

# Configure logging based on available packages
if HAS_STRUCTLOG and HAS_RICH:
    # Configure structlog to integrate with standard logging
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.stdlib.add_logger_name,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="%Y-%m-%d %H:%M:%S.%f", utc=False),
            structlog.processors.StackInfoRenderer(),
            structlog.dev.set_exc_info,
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.make_filtering_bound_logger(min_level=logging.INFO),
        context_class=dict,
        cache_logger_on_first_use=True,
    )

    # Configure standard Python logging handlers
    log_format = "%(message)s"

    # Console Handler (using Rich for pretty output)
    rich_console_handler = RichHandler(console=console, rich_tracebacks=True, markup=True, show_path=False)
    rich_console_handler.setFormatter(logging.Formatter(log_format))
    rich_console_handler.setLevel(logging.INFO)

    # File Handler (plain text)
    file_log_handler = FileHandler(log_file, mode='w', encoding='utf-8')
    file_log_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)-5.5s] [%(name)s] %(message)s"))
    file_log_handler.setLevel(logging.INFO)

    # Get the root logger and add handlers
    std_root_logger = logging.getLogger()
    std_root_logger.addHandler(rich_console_handler)
    std_root_logger.addHandler(file_log_handler)
    std_root_logger.setLevel(logging.INFO)

    # Set Procrastinate's own loggers to DEBUG for more verbose output
    logging.getLogger("procrastinate").setLevel(logging.DEBUG)

    # Create a logger instance using structlog
    logger = structlog.get_logger(__name__)
    logger.info("Logging configured successfully for console and file.")
else:
    # Basic logging configuration if structlog or rich is not available
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)-5.5s] [%(name)s] %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(log_file, mode='w', encoding='utf-8')
        ]
    )
    logger = logging.getLogger(__name__)
    logger.info("Basic logging configured. Install structlog and rich for enhanced logging.")

# Show missing dependencies message
missing_deps = []
if not HAS_RICH:
    missing_deps.append("rich")
if not HAS_STRUCTLOG:
    missing_deps.append("structlog")
if not HAS_POLYFILE:
    missing_deps.append("polyfile")

if missing_deps:
    print("\nMISSING DEPENDENCIES: Please install these packages for full functionality:")
    print(f"pip install {' '.join(missing_deps)}\n")

# Import video_processor and task_queue
try:
    # Direct imports without relative path notation since we're running as a package
    import video_ingest_tool.video_processor as video_processor
    # Attempt to import task_queue conditionally
    try:
        import video_ingest_tool.task_queue as task_queue
        HAS_TASK_QUEUE = task_queue.PROCRASTINATE_AVAILABLE
        logger.info(f"Task queue imported, available: {HAS_TASK_QUEUE}")
        
        # Define 'app' for Procrastinate CLI
        # This 'app' will be picked up by 'procrastinate --app video_ingest_tool.video_ingestor.app'
        app = task_queue.app if HAS_TASK_QUEUE else None
    except ImportError as e:
        logger.error(f"Error importing task_queue: {e}")
        HAS_TASK_QUEUE = False
        app = None
except ImportError as e:
    logger.error(f"Error importing video_processor: {e}")
    print(f"ERROR: {e}")
    print("Make sure you're running from the project root using 'python -m video_ingest_tool'")
    sys.exit(1)

def is_video_file(file_path: str) -> bool:
    """
    Check if a file is a video file based on MIME type.
    
    Args:
        file_path: Path to the file to check
        
    Returns:
        bool: True if the file is a video, False otherwise
    """
    try:
        if HAS_POLYFILE:
            # Use polyfile for file type detection
            with open(file_path, 'rb') as f:
                # Read a small chunk for type detection
                file_bytes = f.read(2048)
                for match in MagicMatcher.DEFAULT_INSTANCE.match(file_bytes):
                    for mime_type in match.mimetypes:
                        if mime_type.startswith('video/'):
                            logger.info(f"File type detected (polyfile): {file_path} - {mime_type}")
                            return True
                            
        # Fallback to mimetypes
        mime_type, _ = mimetypes.guess_type(file_path)
        if mime_type and mime_type.startswith('video/'):
            logger.info(f"File type detected (mimetypes): {file_path} - {mime_type}")
            return True
        return False
    except Exception as e:
        logger.error(f"Error detecting file type for {file_path}: {e}")
        # Ultimate fallback to mimetypes if errors occur
        mime_type, _ = mimetypes.guess_type(file_path)
        return bool(mime_type and mime_type.startswith('video/'))

def scan_directory(directory: str, recursive: bool = True) -> List[str]:
    """
    Scan directory for video files.
    
    Args:
        directory: Directory to scan
        recursive: Whether to scan subdirectories
        
    Returns:
        List[str]: List of video file paths
    """
    logger.info(f"Scanning directory: {directory}, recursive: {recursive}")
    video_files = []
    
    if HAS_RICH:
        with Progress(console=console, transient=True) as progress:
            task = progress.add_task("[cyan]Scanning directory...", total=None)
            
            for root, dirs, files in os.walk(directory):
                progress.update(task, advance=1, description=f"[cyan]Scanning {root}")
                
                for file in files:
                    file_path = os.path.join(root, file)
                    if is_video_file(file_path):
                        video_files.append(file_path)
                        logger.info(f"Found video file: {file_path}")
                
                if not recursive:
                    dirs.clear()  # Don't recurse into subdirectories
    else:
        # Simple version without rich progress bar
        print(f"Scanning directory: {directory}")
        for root, dirs, files in os.walk(directory):
            print(f"Scanning: {root}")
            
            for file in files:
                file_path = os.path.join(root, file)
                if is_video_file(file_path):
                    video_files.append(file_path)
                    logger.info(f"Found video file: {file_path}")
            
            if not recursive:
                dirs.clear()  # Don't recurse into subdirectories
    
    logger.info(f"Directory scan complete. Found {len(video_files)} video files.")
    return video_files

def save_to_json(data: Any, filename: str) -> None:
    """
    Save data to JSON file.
    
    Args:
        data: Data to save
        filename: Output filename
    """
    logger.info(f"Saving data to JSON: {filename}")
    
    # Handle datetime objects
    def json_serial(obj):
        """JSON serializer for objects not serializable by default json code"""
        if isinstance(obj, (datetime.datetime, datetime.date)):
            return obj.isoformat()
        raise TypeError(f"Type {type(obj)} not serializable")
    
    with open(filename, 'w') as f:
        json.dump(data, f, indent=2, default=json_serial)
    
    logger.info(f"Data saved to JSON: {filename}")

@cli.command()
def ingest(
    directory: str = typer.Argument(..., help="Directory to scan for video files"),
    recursive: bool = typer.Option(True, "--recursive/--no-recursive", "-r/-nr", help="Scan subdirectories"),
    output_dir: str = typer.Option("output", "--output-dir", "-o", help="Output directory for thumbnails and JSON"),
    limit: int = typer.Option(0, "--limit", "-l", help="Limit number of files to process (0 = no limit)"),
    use_queue: bool = typer.Option(False, "--queue/--no-queue", "-q/-nq", help="Use task queue for processing")
):
    """
    Scan a directory for video files and extract metadata.
    """
    start_time = time.time()
    
    logger.info(f"Starting ingestion process: directory={directory}, recursive={recursive}, output_dir={output_dir}, limit={limit}, use_queue={use_queue}")
    
    os.makedirs(output_dir, exist_ok=True)
    thumbnails_dir = os.path.join(output_dir, "thumbnails")
    os.makedirs(thumbnails_dir, exist_ok=True)
    
    if HAS_RICH:
        console.print(Panel.fit(
            "[bold blue]AI-Powered Video Ingest & Catalog Tool[/bold blue]\n"
            f"[cyan]Directory:[/cyan] {directory}\n"
            f"[cyan]Recursive:[/cyan] {recursive}\n"
            f"[cyan]Output Directory:[/cyan] {output_dir}\n"
            f"[cyan]File Limit:[/cyan] {limit if limit > 0 else 'No limit'}\n"
            f"[cyan]Use Task Queue:[/cyan] {use_queue}\n"
            f"[cyan]Log File:[/cyan] {log_file}",
            title="Alpha Test",
            border_style="green"
        ))
        console.print(f"[bold yellow]Step 1:[/bold yellow] Scanning directory for video files...")
    else:
        print("\n=== AI-Powered Video Ingest & Catalog Tool - Alpha Test ===")
        print(f"Directory: {directory}")
        print(f"Recursive: {recursive}")
        print(f"Output Directory: {output_dir}")
        print(f"File Limit: {limit if limit > 0 else 'No limit'}")
        print(f"Use Task Queue: {use_queue}")
        print(f"Log File: {log_file}")
        print("\nStep 1: Scanning directory for video files...")
    
    video_files = scan_directory(directory, recursive)
    
    if limit > 0 and len(video_files) > limit:
        video_files = video_files[:limit]
        logger.info(f"Applied file limit: {limit}")
    
    if HAS_RICH:
        console.print(f"[green]Found {len(video_files)} video files[/green]")
    else:
        print(f"Found {len(video_files)} video files")
    
    if use_queue and HAS_TASK_QUEUE:
        if HAS_RICH:
            console.print(f"[bold yellow]Step 2:[/bold yellow] Queueing video files for processing...")
        else:
            print("\nStep 2: Queueing video files for processing...")
        
        processed_files = []
        
        if HAS_RICH:
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
                TimeRemainingColumn(),
                console=console,
                transient=True
            ) as progress:
                task = progress.add_task("[green]Queueing videos...", total=len(video_files))
                
                for file_path in video_files:
                    progress.update(task, advance=0, description=f"[cyan]Queueing {os.path.basename(file_path)}")
                    
                    try:
                        # Queue the video processing task
                        job_id = task_queue.enqueue_video_processing(file_path)
                        
                        processed_files.append({
                            "file_path": file_path,
                            "job_id": job_id
                        })
                        
                        logger.info(f"Video queued for processing: {file_path}, job_id: {job_id}")
                    except Exception as e:
                        logger.error(f"Error queueing video file {file_path}: {e}")
                    
                    progress.update(task, advance=1)
        else:
            # Simple version without rich progress
            for i, file_path in enumerate(video_files, 1):
                print(f"Queueing [{i}/{len(video_files)}]: {os.path.basename(file_path)}")
                
                try:
                    # Queue the video processing task
                    job_id = task_queue.enqueue_video_processing(file_path)
                    
                    processed_files.append({
                        "file_path": file_path,
                        "job_id": job_id
                    })
                    
                    logger.info(f"Video queued for processing: {file_path}, job_id: {job_id}")
                except Exception as e:
                    logger.error(f"Error queueing video file {file_path}: {e}")
        
        if HAS_RICH:
            console.print(f"[green]Queued {len(processed_files)} videos for processing[/green]")
            console.print(f"[cyan]To process queued videos, run:[/cyan] python run_video_ingest.py worker")
        else:
            print(f"\nQueued {len(processed_files)} videos for processing")
            print(f"To process queued videos, run: python run_video_ingest.py worker")
    else:
        # Direct processing without queue
        if HAS_RICH:
            console.print(f"[bold yellow]Step 2:[/bold yellow] Processing video files...")
        else:
            print("\nStep 2: Processing video files...")
        
        processed_files = []
        
        if HAS_RICH:
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
                TimeRemainingColumn(),
                console=console,  
                transient=True    
            ) as progress:
                task = progress.add_task("[green]Processing videos...", total=len(video_files))
                
                for file_path in video_files:
                    progress.update(task, advance=0, description=f"[cyan]Processing {os.path.basename(file_path)}")
                    
                    try:
                        # Direct processing without queuing
                        result = video_processor.process_video_file(file_path, thumbnails_dir)
                        processed_files.append(result)
                        
                        # Save individual JSON file
                        individual_json_path = os.path.join(json_dir, f"{result['id']}.json")
                        save_to_json(result, individual_json_path)
                        
                    except Exception as e:
                        logger.error(f"Error processing video file {file_path}: {e}")
                    
                    progress.update(task, advance=1)
        else:
            # Simple version without rich progress
            for i, file_path in enumerate(video_files, 1):
                print(f"Processing [{i}/{len(video_files)}]: {os.path.basename(file_path)}")
                
                try:
                    # Direct processing without queuing
                    result = video_processor.process_video_file(file_path, thumbnails_dir)
                    processed_files.append(result)
                    
                    # Save individual JSON file
                    individual_json_path = os.path.join(json_dir, f"{result['id']}.json")
                    save_to_json(result, individual_json_path)
                    
                except Exception as e:
                    logger.error(f"Error processing video file {file_path}: {e}")
        
        # Save all data to a single JSON file
        all_data_json_path = os.path.join(json_dir, f"all_videos_{timestamp}.json")
        save_to_json(processed_files, all_data_json_path)
    
    end_time = time.time()
    processing_time = end_time - start_time
    
    if HAS_RICH:
        summary_table = Table(title="Processing Summary")
        summary_table.add_column("Metric", style="cyan")
        summary_table.add_column("Value", style="green")
        
        summary_table.add_row("Total files", str(len(video_files)))
        
        if use_queue and HAS_TASK_QUEUE:
            summary_table.add_row("Files queued", str(len(processed_files)))
            summary_table.add_row("Queue time", f"{processing_time:.2f} seconds")
            summary_table.add_row("Average time per file", f"{processing_time / len(processed_files):.2f} seconds" if processed_files else "N/A")
        else:
            summary_table.add_row("Files processed", str(len(processed_files)))
            summary_table.add_row("Processing time", f"{processing_time:.2f} seconds")
            summary_table.add_row("Average time per file", f"{processing_time / len(processed_files):.2f} seconds" if processed_files else "N/A")
            summary_table.add_row("Summary JSON", all_data_json_path if 'all_data_json_path' in locals() else "None")
        
        summary_table.add_row("Log file", log_file)
        
        console.print(summary_table)
    else:
        print("\n=== Processing Summary ===")
        print(f"Total files: {len(video_files)}")
        
        if use_queue and HAS_TASK_QUEUE:
            print(f"Files queued: {len(processed_files)}")
            print(f"Queue time: {processing_time:.2f} seconds")
            print(f"Average time per file: {processing_time / len(processed_files):.2f} seconds" if processed_files else "N/A")
        else:
            print(f"Files processed: {len(processed_files)}")
            print(f"Processing time: {processing_time:.2f} seconds")
            print(f"Average time per file: {processing_time / len(processed_files):.2f} seconds" if processed_files else "N/A")
            print(f"Summary JSON: {all_data_json_path if 'all_data_json_path' in locals() else 'None'}")
        
        print(f"Log file: {log_file}")
    
    logger.info(f"Ingestion process completed: files_processed={len(processed_files)}, processing_time={processing_time:.2f}s")

@cli.command()
def worker(
    queues: Optional[List[str]] = typer.Option(None, "--queue", "-q", help="Queue names to process (empty for all)"),
    concurrency: int = typer.Option(1, "--concurrency", "-c", help="Number of concurrent jobs to process")
):
    """
    Run a worker to process queued tasks from PostgreSQL.
    """
    print("DEBUG: WORKER COMMAND LAUNCHED")
    if not HAS_TASK_QUEUE:
        if HAS_RICH:
            console.print("[bold red]Error:[/bold red] Task queue is not available. Please install Procrastinate and psycopg2-binary.")
        else:
            print("ERROR: Task queue is not available. Please install Procrastinate and psycopg2-binary.")
        return
    
    # Show information about the database
    db_config = task_queue.DB_CONFIG.copy()
    db_config["password"] = "********"  # Hide password
    db_str = f"{db_config['user']}@{db_config['host']}:{db_config['port']}/{db_config['dbname']}"
    
    if HAS_RICH:
        console.print(Panel.fit(
            "[bold blue]AI-Powered Video Ingest & Catalog Tool - Worker[/bold blue]\n"
            f"[cyan]Database:[/cyan] {db_str}\n"
            f"[cyan]Queues:[/cyan] {', '.join(queues) if queues else 'All'}\n"
            f"[cyan]Concurrency:[/cyan] {concurrency}\n"
            f"[cyan]Log File:[/cyan] {log_file}",
            title="Worker",
            border_style="green"
        ))
        console.print("[green]Starting worker...[/green]")
    else:
        print("\n=== AI-Powered Video Ingest & Catalog Tool - Worker ===")
        print(f"Database: {db_str}")
        print(f"Queues: {', '.join(queues) if queues else 'All'}")
        print(f"Concurrency: {concurrency}")
        print(f"Log File: {log_file}")
        print("\nStarting worker...")
    
    try:
        task_queue.run_worker(queues=queues, concurrency=concurrency)
    except KeyboardInterrupt:
        if HAS_RICH:
            console.print("[yellow]Worker stopped by user[/yellow]")
        else:
            print("\nWorker stopped by user")
    except Exception as e:
        if HAS_RICH:
            console.print(f"[bold red]Worker error:[/bold red] {str(e)}")
        else:
            print(f"\nWORKER ERROR: {str(e)}")

@cli.command()
def schema():
    """
    Initialize or update the database schema using Procrastinate's programmatic apply.
    For more robust schema management or troubleshooting, prefer the Procrastinate CLI:
    'conda run -n video-ingest env PYTHONPATH=. procrastinate --app=video_ingest_tool.video_ingestor.app schema --apply'
    """
    if not HAS_TASK_QUEUE:
        if HAS_RICH:
            console.print("[red]Task queue module not available. Procrastinate is required.[/red]")
        else:
            print("ERROR: Task queue module not available. Procrastinate is required.")
        return

    if app is None:
        if HAS_RICH:
            console.print("[red]Procrastinate app not initialized. Cannot apply schema.[/red]")
        else:
            print("ERROR: Procrastinate app not initialized. Cannot apply schema.")
        return

    if HAS_RICH:
        console.print("Attempting to apply/verify Procrastinate schema programmatically...")
    else:
        print("Attempting to apply/verify Procrastinate schema programmatically...")
        
    if task_queue.ensure_schema(app):
        if HAS_RICH:
            console.print("[green]Schema apply/verify command executed successfully via script.[/green]")
        else:
            print("SUCCESS: Schema apply/verify command executed successfully via script.")
    else:
        if HAS_RICH:
            console.print("[bold red]Schema apply/verify command failed via script.[/bold red]")
            console.print("This might indicate an issue with the database or schema state.")
            console.print("For robust schema management, especially if issues persist, please use the Procrastinate CLI:")
            console.print("  [blue]conda run -n video-ingest env PYTHONPATH=. procrastinate --app=video_ingest_tool.video_ingestor.app schema --apply[/blue]")
        else:
            print("ERROR: Schema apply/verify command failed via script.")
            print("This might indicate an issue with the database or schema state.")
            print("For robust schema management, especially if issues persist, please use the Procrastinate CLI:")
            print("  conda run -n video-ingest env PYTHONPATH=. procrastinate --app=video_ingest_tool.video_ingestor.app schema --apply")

@cli.command()
def db_status():
    """Check the database connection status"""
    try:
        try:
            import psycopg2
        except ImportError:
            if HAS_RICH:
                console.print("[red]Required module 'psycopg2' not available. Cannot check database status.[/red]")
            else:
                print("ERROR: Required module 'psycopg2' not available. Cannot check database status.")
            return
        
        if not HAS_TASK_QUEUE:
            if HAS_RICH:
                console.print("[red]Task queue module not available. Cannot check database status.[/red]")
            else:
                print("ERROR: Task queue module not available. Cannot check database status.")
            return
            
        # Get database configuration
        from video_ingest_tool.task_queue import get_db_config
        db_config = get_db_config()
        
        if HAS_RICH:
            console.print("\n[bold]Database Configuration:[/bold]")
            console.print(f"Host: {db_config['host']}")
            console.print(f"Port: {db_config['port']}")
            console.print(f"Database: {db_config['dbname']}")
            console.print(f"User: {db_config['user']}")
            
            console.print("\n[bold]Testing Connection...[/bold]")
        else:
            print("\nDatabase Configuration:")
            print(f"Host: {db_config['host']}")
            print(f"Port: {db_config['port']}")
            print(f"Database: {db_config['dbname']}")
            print(f"User: {db_config['user']}")
            
            print("\nTesting Connection...")
            
        try:
            conn = psycopg2.connect(**db_config)
            cursor = conn.cursor()
            cursor.execute("SELECT version();")
            version = cursor.fetchone()[0]
            cursor.close()
            conn.close()
            
            if HAS_RICH:
                console.print(f"[green]Connection successful![/green]")
                console.print(f"PostgreSQL version: {version}")
            else:
                print("Connection successful!")
                print(f"PostgreSQL version: {version}")
        except Exception as e:
            if HAS_RICH:
                console.print(f"[red]Connection failed: {str(e)}[/red]")
                console.print("\n[bold]Troubleshooting:[/bold]")
                console.print("1. Ensure PostgreSQL is running in Docker")
                console.print("2. Check that the database exists")
                console.print("3. Verify the connection settings in .env file")
                console.print("\n[bold]Environment Variables:[/bold]")
                console.print("VIDEOINGESTOR_DB_HOST - Database hostname (default: localhost)")
                console.print("VIDEOINGESTOR_DB_PORT - Database port (default: 5432)")
                console.print("VIDEOINGESTOR_DB_NAME - Database name (default: videoingestor)")
                console.print("VIDEOINGESTOR_DB_USER - Database username (default: postgres)")
                console.print("VIDEOINGESTOR_DB_PASSWORD - Database password (default: password)")
            else:
                print(f"Connection failed: {str(e)}")
                print("\nTroubleshooting:")
                print("1. Ensure PostgreSQL is running in Docker")
                print("2. Check that the database exists")
                print("3. Verify the connection settings in .env file")
                print("\nEnvironment Variables:")
                print("VIDEOINGESTOR_DB_HOST - Database hostname (default: localhost)")
                print("VIDEOINGESTOR_DB_PORT - Database port (default: 5432)")
                print("VIDEOINGESTOR_DB_NAME - Database name (default: videoingestor)")
                print("VIDEOINGESTOR_DB_USER - Database username (default: postgres)")
                print("VIDEOINGESTOR_DB_PASSWORD - Database password (default: password)")
    except ImportError:
        if HAS_RICH:
            console.print("[red]Required modules not available. Cannot check database status.[/red]")
        else:
            print("ERROR: Required modules not available. Cannot check database status.")
    except Exception as e:
        if HAS_RICH:
            console.print(f"[red]Error checking database status: {str(e)}[/red]")
        else:
            print(f"ERROR checking database status: {str(e)}")

# Create a main CLI entry point function
def run():
    """Entry point for CLI"""
    cli()

if __name__ == "__main__":
    run()
