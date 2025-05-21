#!/usr/bin/env python3
"""
Task Queue Worker for AI-Powered Video Ingest & Catalog Tool

This script runs a worker process to handle tasks in the Procrastinate queue.
Run this in a separate terminal or process to process queued video files.

Compatible with Procrastinate 3.2.2
"""

import argparse
import os
import sys
import logging
import psycopg2
import json
import structlog
from typing import List, Optional, Dict, Any
from rich.console import Console
from rich.panel import Panel

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = structlog.get_logger(__name__)
console = Console()

# Database configuration
DB_CONFIG = {
    "host": os.environ.get("VIDEOINGESTOR_DB_HOST", "localhost"),
    "user": os.environ.get("VIDEOINGESTOR_DB_USER", "postgres"),
    "password": os.environ.get("VIDEOINGESTOR_DB_PASSWORD", "password"),
    "dbname": os.environ.get("VIDEOINGESTOR_DB_NAME", "videoingestor"),
    "port": int(os.environ.get("VIDEOINGESTOR_DB_PORT", "5432")),
}

# Import procrastinate
try:
    import procrastinate
    from procrastinate import App, PsycopgConnector
    PROCRASTINATE_AVAILABLE = True
    console.print(f"[green]Procrastinate version: {procrastinate.__version__}[/green]")
    
    # Import task_queue module
    try:
        from task_queue import app
        APP_AVAILABLE = True
    except ImportError:
        console.print("[yellow]Warning:[/yellow] Could not import app from task_queue module. Will create a new app instance.")
        APP_AVAILABLE = False
except ImportError:
    console.print("[bold red]Error:[/bold red] Could not import procrastinate. Make sure it's installed.")
    sys.exit(1)

def create_app():
    """Create a Procrastinate App instance with PostgreSQL connector."""
    try:
        console.print("[green]Creating Procrastinate App with PostgreSQL...[/green]")
        
        # Create the connector
        connector = PsycopgConnector(
            kwargs={
                "host": DB_CONFIG["host"],
                "user": DB_CONFIG["user"],
                "password": DB_CONFIG["password"],
                "dbname": DB_CONFIG["dbname"],
                "port": DB_CONFIG["port"],
            }
        )
        console.print(f"[green]Connected to PostgreSQL database: {DB_CONFIG['dbname']} on {DB_CONFIG['host']}:{DB_CONFIG['port']}[/green]")
    except Exception as e:
        console.print(f"[bold red]Failed to connect to PostgreSQL:[/bold red] {str(e)}")
        console.print("\nPlease ensure PostgreSQL is running and accessible with the following settings:")
        config_display = DB_CONFIG.copy()
        config_display['password'] = '********'  # Hide password
        for key, value in config_display.items():
            console.print(f"  [cyan]{key}:[/cyan] {value}")
        sys.exit(1)
    
    return App(connector=connector)

def ensure_schema(app_instance):
    """Ensure the database schema exists."""
    try:
        console.print("[green]Checking database schema...[/green]")
        
        # Connect directly to create schema if needed
        conn = psycopg2.connect(
            host=DB_CONFIG['host'],
            port=DB_CONFIG['port'],
            user=DB_CONFIG['user'],
            password=DB_CONFIG['password'],
            dbname=DB_CONFIG['dbname']
        )
        
        with conn.cursor() as cursor:
            # Check if the table exists
            cursor.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_name = 'procrastinate_jobs'
                );
            """)
            table_exists = cursor.fetchone()[0]
            
            if not table_exists:
                console.print("[yellow]Creating procrastinate_jobs table...[/yellow]")
                # Create the tables and indexes for Procrastinate 3.2.2
                cursor.execute("""
                    CREATE TABLE procrastinate_jobs (
                        id SERIAL PRIMARY KEY,
                        queue_name TEXT NOT NULL,
                        task_name TEXT NOT NULL,
                        lock TEXT,
                        queueing_lock TEXT,
                        args JSONB NOT NULL,
                        status TEXT NOT NULL,
                        scheduled_at TIMESTAMP WITH TIME ZONE NOT NULL,
                        attempts INT NOT NULL DEFAULT 0,
                        priority INT NOT NULL DEFAULT 0,
                        events JSONB,
                        worker_name TEXT
                    );
                    
                    CREATE INDEX procrastinate_jobs_queue_name_idx ON procrastinate_jobs (queue_name);
                    CREATE INDEX procrastinate_jobs_status_idx ON procrastinate_jobs (status);
                    CREATE INDEX procrastinate_jobs_lock_idx ON procrastinate_jobs (lock) WHERE lock IS NOT NULL;
                    CREATE INDEX procrastinate_jobs_queueing_lock_idx ON procrastinate_jobs (queueing_lock) WHERE queueing_lock IS NOT NULL;
                """)
                conn.commit()
                console.print("[green]Schema created successfully![/green]")
            else:
                console.print("[green]procrastinate_jobs table already exists.[/green]")
                
                # Check if the table has the required columns for Procrastinate 3.2.2
                cursor.execute("""
                    SELECT column_name FROM information_schema.columns 
                    WHERE table_name = 'procrastinate_jobs' 
                    ORDER BY ordinal_position;
                """)
                columns = [col[0] for col in cursor.fetchall()]
                
                # Check for missing columns
                required_columns = [
                    "id", "queue_name", "task_name", "lock", "queueing_lock", 
                    "args", "status", "scheduled_at", "attempts", "priority", 
                    "events", "worker_name"
                ]
                
                missing_columns = [col for col in required_columns if col not in columns]
                if missing_columns:
                    console.print(f"[yellow]Missing columns in procrastinate_jobs table: {', '.join(missing_columns)}[/yellow]")
                    console.print("[yellow]Attempting to add missing columns...[/yellow]")
                    
                    for col in missing_columns:
                        try:
                            if col == "queueing_lock":
                                cursor.execute("ALTER TABLE procrastinate_jobs ADD COLUMN queueing_lock TEXT;")
                                cursor.execute("CREATE INDEX IF NOT EXISTS procrastinate_jobs_queueing_lock_idx ON procrastinate_jobs (queueing_lock) WHERE queueing_lock IS NOT NULL;")
                            elif col == "priority":
                                cursor.execute("ALTER TABLE procrastinate_jobs ADD COLUMN priority INT NOT NULL DEFAULT 0;")
                            elif col == "events":
                                cursor.execute("ALTER TABLE procrastinate_jobs ADD COLUMN events JSONB;")
                            elif col == "worker_name":
                                cursor.execute("ALTER TABLE procrastinate_jobs ADD COLUMN worker_name TEXT;")
                            conn.commit()
                            console.print(f"[green]Added column: {col}[/green]")
                        except Exception as e:
                            console.print(f"[red]Error adding column {col}: {str(e)}[/red]")
        
        conn.close()
        console.print("[green]Schema verification complete.[/green]")
        
    except Exception as e:
        console.print(f"[bold red]Error ensuring schema:[/bold red] {str(e)}")
        raise

def run_worker(app_instance, queues: Optional[List[str]] = None, concurrency: int = 1):
    """Run a worker to process tasks."""
    try:
        console.print(f"[green]Starting worker with concurrency={concurrency}...[/green]")
        console.print(f"[green]Listening on queues: {queues or 'all'}[/green]")
        
        with app_instance.open():
            # Run the worker
            app_instance.run_worker(
                queues=queues, 
                concurrency=concurrency,
                delete_jobs="never"  # Keep jobs for debugging
            )
    except Exception as e:
        console.print(f"[bold red]Worker error:[/bold red] {str(e)}")
        if hasattr(e, '__cause__') and e.__cause__:
            console.print(f"[red]Caused by: {e.__cause__}[/red]")
        raise

def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Worker for AI-Powered Video Ingest & Catalog Tool")
    parser.add_argument(
        "-q", "--queue", 
        action="append", 
        help="Queue name to process (can be specified multiple times, default: all queues)"
    )
    parser.add_argument(
        "-c", "--concurrency", 
        type=int, 
        default=1, 
        help="Number of concurrent jobs to process (default: 1)"
    )
    parser.add_argument(
        "--schema", 
        action="store_true", 
        help="Apply database schema and exit"
    )
    return parser.parse_args()

def main():
    """Main entry point."""
    args = parse_args()
    
    # Use existing app or create a new one
    if APP_AVAILABLE:
        app_instance = app
    else:
        app_instance = create_app()
    
    if args.schema:
        console.print("[green]Applying database schema...[/green]")
        try:
            ensure_schema(app_instance)
            console.print("[green]Schema applied successfully![/green]")
            return
        except Exception as e:
            console.print(f"[bold red]Error applying schema:[/bold red] {str(e)}")
            return
    
    # Display worker info
    console.print(Panel.fit(
        "[bold blue]AI-Powered Video Ingest & Catalog Tool - Worker[/bold blue]\n"
        f"[cyan]Queues:[/cyan] {', '.join(args.queue) if args.queue else 'All'}\n"
        f"[cyan]Concurrency:[/cyan] {args.concurrency}",
        title="Worker",
        border_style="green"
    ))
    
    # Ensure schema exists before starting worker
    try:
        ensure_schema(app_instance)
    except Exception as e:
        console.print(f"[bold red]Error ensuring schema:[/bold red] {str(e)}")
        return
    
    # Start the worker
    try:
        run_worker(app_instance, queues=args.queue, concurrency=args.concurrency)
    except KeyboardInterrupt:
        console.print("[yellow]Worker stopped by user[/yellow]")
    except Exception as e:
        console.print(f"[bold red]Worker error:[/bold red] {str(e)}")
        console.print("\n[yellow]Possible solutions:[/yellow]")
        console.print("1. Ensure PostgreSQL is running")
        console.print("2. Check that the database 'videoingestor' exists")
        console.print("3. Verify the user 'postgres' has permission to access the database")
        console.print("4. Check that all required tables and columns exist")

if __name__ == "__main__":
    main()
