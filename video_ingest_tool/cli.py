"""
Command-line interface for the video ingest tool.

Contains the CLI application built with Typer.
"""

import os
import time
import json
import typer
from typing import List, Dict, Optional
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeRemainingColumn
from rich.panel import Panel
from rich.table import Table

from .config import setup_logging, console
from .discovery import scan_directory
from .processor import (
    process_video_file, 
    get_default_pipeline_config, 
    get_available_pipeline_steps
)
from .output import save_to_json, save_run_outputs
from .video_processor import DEFAULT_COMPRESSION_CONFIG
from .utils import calculate_checksum

# Create Typer app
app = typer.Typer(help="AI-Powered Video Ingest & Catalog Tool")

@app.command()
def ingest(
    directory: str = typer.Argument(..., help="Directory to scan for video files"),
    recursive: bool = typer.Option(True, "--recursive/--no-recursive", "-r/-nr", help="Scan subdirectories"),
    output_dir: str = typer.Option("output", "--output-dir", "-o", help="Base output directory for all processing runs"),
    limit: int = typer.Option(0, "--limit", "-l", help="Limit number of files to process (0 = no limit)"),
    disable_steps: List[str] = typer.Option(None, "--disable", "-d", help="Steps to disable in the pipeline"),
    enable_steps: List[str] = typer.Option(None, "--enable", "-e", help="Steps to enable in the pipeline"),
    config_file: Optional[str] = typer.Option(None, "--config", "-c", help="JSON configuration file for pipeline steps"),
    compression_fps: int = typer.Option(DEFAULT_COMPRESSION_CONFIG['fps'], "--fps", help=f"Frame rate for compressed videos (default: {DEFAULT_COMPRESSION_CONFIG['fps']})"),
    compression_bitrate: str = typer.Option(DEFAULT_COMPRESSION_CONFIG['video_bitrate'], "--bitrate", help=f"Video bitrate for compression (default: {DEFAULT_COMPRESSION_CONFIG['video_bitrate']})")
):
    """
    Scan a directory for video files and extract metadata.
    """
    start_time = time.time()
    
    # Setup logging and get paths - this creates the run directory structure
    logger, timestamp, json_dir, log_file = setup_logging()
    
    # The run directory is already created by setup_logging
    # Extract run directory from json_dir path
    run_dir = os.path.dirname(json_dir)  # json_dir is run_dir/json, so get parent
    
    # Create subdirectories for this run (json directory already created by setup_logging)
    thumbnails_dir = os.path.join(run_dir, "thumbnails")
    os.makedirs(thumbnails_dir, exist_ok=True)
    
    # JSON directory already exists from setup_logging
    # json_dir is already set to run_dir/json
    
    # Create identifiable summary filename with timestamp
    summary_filename = f"all_videos_{os.path.basename(directory)}_{timestamp}.json"
    
    logger.info("Starting ingestion process", 
                directory=directory, 
                recursive=recursive,
                run_dir=run_dir,
                limit=limit,
                compression_fps=compression_fps,
                compression_bitrate=compression_bitrate)
    
    # Set up pipeline configuration
    pipeline_config = get_default_pipeline_config()
    
    # Load config from file if specified
    if config_file:
        try:
            with open(config_file, 'r') as f:
                file_config = json.load(f)
                pipeline_config.update(file_config)
                logger.info(f"Loaded pipeline configuration from {config_file}")
        except Exception as e:
            logger.error(f"Error loading config file: {str(e)}")
            console.print(f"[bold red]Error loading config file:[/bold red] {str(e)}")
    
    # Apply command-line overrides
    if disable_steps:
        for step in disable_steps:
            if step in pipeline_config:
                pipeline_config[step] = False
                logger.info(f"Disabled step: {step}")
            else:
                logger.warning(f"Unknown step to disable: {step}")
                console.print(f"[yellow]Warning:[/yellow] Unknown step '{step}'")
    
    if enable_steps:
        for step in enable_steps:
            if step in pipeline_config:
                pipeline_config[step] = True
                logger.info(f"Enabled step: {step}")
            else:
                logger.warning(f"Unknown step to enable: {step}")
                console.print(f"[yellow]Warning:[/yellow] Unknown step '{step}'")
    
    # Save the active configuration to the run directory
    config_path = os.path.join(run_dir, "pipeline_config.json")
    with open(config_path, 'w') as f:
        json.dump(pipeline_config, f, indent=2)
    
    console.print(Panel.fit(
        "[bold blue]AI-Powered Video Ingest & Catalog Tool[/bold blue]\n"
        f"[cyan]Directory:[/cyan] {directory}\n"
        f"[cyan]Recursive:[/cyan] {recursive}\n"
        f"[cyan]Output Directory:[/cyan] {run_dir}\n"
        f"[cyan]File Limit:[/cyan] {limit if limit > 0 else 'No limit'}\n"
        f"[cyan]Log File:[/cyan] {log_file}\n"
        f"[cyan]Pipeline Config:[/cyan] {config_path}",
        title="Alpha Test",
        border_style="green"
    ))
    
    # Display active pipeline steps
    steps_table = Table(title="Active Pipeline Steps")
    steps_table.add_column("Step", style="cyan")
    steps_table.add_column("Status", style="green")
    steps_table.add_column("Description", style="yellow")
    
    for step in get_available_pipeline_steps():
        status = "[green]Enabled" if pipeline_config.get(step['name'], step['enabled']) else "[red]Disabled"
        steps_table.add_row(step['name'], status, step['description'])
    
    console.print(steps_table)
    
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
                video_file = process_video_file(
                    file_path, 
                    thumbnails_dir, 
                    logger,
                    config=pipeline_config,
                    compression_fps=compression_fps,
                    compression_bitrate=compression_bitrate
                )
                processed_files.append(video_file)
                
                # Create filename with original name and UUID
                base_name = os.path.splitext(os.path.basename(file_path))[0]
                json_filename = f"{base_name}_{video_file.id}.json"
                
                # Save individual JSON to run directory
                individual_json_path = os.path.join(json_dir, json_filename)
                save_to_json(video_file, individual_json_path, logger)
                
            except Exception as e:
                failed_files.append(file_path)
                logger.error("Error processing video file", path=file_path, error=str(e))
            
            progress.update(task, advance=1)
    
    # Save run outputs with directory name in the summary filename
    output_paths = save_run_outputs(
        processed_files,
        run_dir,
        summary_filename,
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

@app.command()
def list_steps():
    """
    List all available processing steps.
    """
    steps_table = Table(title="Available Pipeline Steps")
    steps_table.add_column("Step", style="cyan")
    steps_table.add_column("Default Status", style="green")
    steps_table.add_column("Description", style="yellow")
    
    for step in get_available_pipeline_steps():
        status = "[green]Enabled" if step['enabled'] else "[red]Disabled"
        steps_table.add_row(step['name'], status, step['description'])
    
    console.print(steps_table)
    
    console.print("\n[cyan]Example usage:[/cyan]")
    console.print("  python -m video_ingest_tool ingest /path/to/videos/ --disable=hdr_extraction,ai_focal_length")
    console.print("  python -m video_ingest_tool ingest /path/to/videos/ --enable=thumbnail_generation --disable=exposure_analysis")
    console.print("  python -m video_ingest_tool ingest /path/to/videos/ --config=my_config.json")

if __name__ == "__main__":
    app()

# Authentication commands
auth_app = typer.Typer(help="Authentication commands")
app.add_typer(auth_app, name="auth")

@auth_app.command("login")
def auth_login():
    """Login to Supabase with email and password."""
    from .auth import AuthManager
    from .supabase_config import verify_connection
    
    # Check connection first
    if not verify_connection():
        console.print("[red]Unable to connect to Supabase. Please check your configuration.[/red]")
        raise typer.Exit(1)
    
    email = typer.prompt("Email")
    password = typer.prompt("Password", hide_input=True)
    
    auth_manager = AuthManager()
    if auth_manager.login(email, password):
        console.print(f"[green]Successfully logged in as {email}[/green]")
        
        # Get user profile
        profile = auth_manager.get_user_profile()
        if profile:
            console.print(f"Profile: {profile.get('display_name', 'Unknown')} ({profile.get('profile_type', 'user')})")
    else:
        console.print("[red]Login failed. Please check your credentials.[/red]")
        raise typer.Exit(1)

@auth_app.command("signup")
def auth_signup():
    """Sign up for a new account."""
    from .auth import AuthManager
    from .supabase_config import verify_connection
    
    # Check connection first
    if not verify_connection():
        console.print("[red]Unable to connect to Supabase. Please check your configuration.[/red]")
        raise typer.Exit(1)
    
    email = typer.prompt("Email")
    password = typer.prompt("Password", hide_input=True)
    confirm_password = typer.prompt("Confirm Password", hide_input=True)
    
    if password != confirm_password:
        console.print("[red]Passwords do not match.[/red]")
        raise typer.Exit(1)
    
    auth_manager = AuthManager()
    if auth_manager.signup(email, password):
        console.print(f"[green]Successfully signed up as {email}[/green]")
        console.print("[yellow]Please check your email for verification link.[/yellow]")
    else:
        console.print("[red]Sign up failed. Please try again.[/red]")
        raise typer.Exit(1)

@auth_app.command("logout")
def auth_logout():
    """Logout from current session."""
    from .auth import AuthManager
    
    auth_manager = AuthManager()
    if auth_manager.logout():
        console.print("[green]Successfully logged out.[/green]")
    else:
        console.print("[red]Logout failed.[/red]")
        raise typer.Exit(1)

@auth_app.command("status")
def auth_status():
    """Show current authentication status."""
    from .auth import AuthManager
    from .supabase_config import get_database_status
    
    auth_manager = AuthManager()
    session = auth_manager.get_current_session()
    
    status_table = Table(title="Authentication Status")
    status_table.add_column("Item", style="cyan")
    status_table.add_column("Status", style="green")
    
    if session:
        status_table.add_row("Logged in", "[green]Yes[/green]")
        status_table.add_row("Email", session.get('email', 'Unknown'))
        status_table.add_row("User ID", session.get('user_id', 'Unknown'))
        
        # Get profile info
        profile = auth_manager.get_user_profile()
        if profile:
            status_table.add_row("Display Name", profile.get('display_name', 'Not set'))
            status_table.add_row("Profile Type", profile.get('profile_type', 'user'))
    else:
        status_table.add_row("Logged in", "[red]No[/red]")
    
    console.print(status_table)
    
    # Database status
    db_status = get_database_status()
    
    db_table = Table(title="Database Status")
    db_table.add_column("Component", style="cyan")
    db_table.add_column("Status", style="green")
    
    db_table.add_row("Connection", "[green]Success[/green]" if db_status['connection'] == 'success' else "[red]Failed[/red]")
    db_table.add_row("URL", db_status['url'] or 'Not configured')
    
    if 'tables' in db_status:
        for table, status in db_status['tables'].items():
            db_table.add_row(f"Table: {table}", "[green]Exists[/green]" if status == 'exists' else "[red]Missing[/red]")
    
    console.print(db_table)
