"""
Command-line interface for the video ingest tool.

Contains the CLI application built with Typer.
"""

import os
import time
import typer
from typing import List
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeRemainingColumn
from rich.panel import Panel
from rich.table import Table

from .config import setup_logging, console
from .discovery import scan_directory
from .processor import process_video_file
from .output import save_to_json, save_run_outputs
from .utils import calculate_checksum

# Create Typer app
app = typer.Typer(help="AI-Powered Video Ingest & Catalog Tool")

@app.command()
def ingest(
    directory: str = typer.Argument(..., help="Directory to scan for video files"),
    recursive: bool = typer.Option(True, "--recursive/--no-recursive", "-r/-nr", help="Scan subdirectories"),
    output_dir: str = typer.Option("output", "--output-dir", "-o", help="Output directory for thumbnails and JSON"),
    limit: int = typer.Option(0, "--limit", "-l", help="Limit number of files to process (0 = no limit)")
):
    """
    Scan a directory for video files and extract metadata.
    """
    start_time = time.time()
    
    # Setup logging and get paths
    logger, timestamp, json_dir, log_file = setup_logging()
    
    # Create a timestamped run directory
    run_dir = os.path.join(output_dir, f"run_{timestamp}")
    os.makedirs(run_dir, exist_ok=True)
    
    # Create subdirectories for this run
    thumbnails_dir = os.path.join(run_dir, "thumbnails")
    os.makedirs(thumbnails_dir, exist_ok=True)
    
    # Create a run-specific JSON directory
    run_json_dir = os.path.join(run_dir, "json")
    os.makedirs(run_json_dir, exist_ok=True)
    
    logger.info("Starting ingestion process", 
                directory=directory, 
                recursive=recursive,
                output_dir=run_dir,
                limit=limit)
    
    console.print(Panel.fit(
        "[bold blue]AI-Powered Video Ingest & Catalog Tool[/bold blue]\n"
        f"[cyan]Directory:[/cyan] {directory}\n"
        f"[cyan]Recursive:[/cyan] {recursive}\n"
        f"[cyan]Output Directory:[/cyan] {run_dir}\n"
        f"[cyan]File Limit:[/cyan] {limit if limit > 0 else 'No limit'}\n"
        f"[cyan]Log File:[/cyan] {log_file}",
        title="Alpha Test",
        border_style="green"
    ))
    
    console.print(f"[bold yellow]Step 1:[/bold yellow] Scanning directory for video files...")
    video_files = scan_directory(directory, recursive, logger)
    
    if limit > 0 and len(video_files) > limit:
        video_files = video_files[:limit]
        logger.info("Applied file limit", limit=limit)
    
    console.print(f"[green]Found {len(video_files)} video files[/green]")
    
    console.print(f"[bold yellow]Step 2:[/bold yellow] Processing video files...")
    processed_files = []
    failed_files = []
    
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
                video_file = process_video_file(file_path, thumbnails_dir, logger)
                processed_files.append(video_file)
                
                # Save individual JSON to run-specific directory
                individual_json_path = os.path.join(run_json_dir, f"{video_file.id}.json")
                save_to_json(video_file, individual_json_path, logger)
                
                # Also save a copy to the global JSON directory for backward compatibility
                global_json_path = os.path.join(json_dir, f"{video_file.id}.json")
                save_to_json(video_file, global_json_path, logger)
                
            except Exception as e:
                failed_files.append(file_path)
                logger.error("Error processing video file", path=file_path, error=str(e))
            
            progress.update(task, advance=1)
    
    # Save run outputs
    output_paths = save_run_outputs(
        processed_files, 
        run_dir, 
        timestamp, 
        json_dir, 
        log_file,
        logger
    )
    
    # Check if we had failed files and warn the user
    if failed_files:
        console.print(f"[bold red]Warning:[/bold red] Failed to process {len(failed_files)} file(s):", style="red")
        for f in failed_files:
            console.print(f"  - {f}", style="red")
    
    end_time = time.time()
    processing_time = end_time - start_time
    
    summary_table = Table(title="Processing Summary")
    summary_table.add_column("Metric", style="cyan")
    summary_table.add_column("Value", style="green")
    
    summary_table.add_row("Total files processed", str(len(processed_files)))
    if failed_files:
        summary_table.add_row("Failed files", str(len(failed_files)))
    summary_table.add_row("Processing time", f"{processing_time:.2f} seconds")
    summary_table.add_row("Average time per file", f"{processing_time / len(processed_files):.2f} seconds" if processed_files else "N/A")
    summary_table.add_row("Run directory", run_dir)
    summary_table.add_row("Summary JSON", output_paths.get('run_summary', 'N/A'))
    summary_table.add_row("Log file", output_paths.get('run_log', 'N/A'))
    
    console.print(summary_table)
    
    logger.info("Ingestion process completed", 
                files_processed=len(processed_files),
                failed_files=len(failed_files),
                processing_time=processing_time,
                run_directory=run_dir)

if __name__ == "__main__":
    app()
