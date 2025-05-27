"""
Command-line interface for the video ingest tool.

Contains the CLI application built with Typer.
"""

import os
import time
import json
import typer
import requests
from typing import List, Dict, Optional
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeRemainingColumn
from rich.panel import Panel
from rich.table import Table
from rich.progress import BarColumn, Progress

from .config import setup_logging, console, DEFAULT_COMPRESSION_CONFIG
from .discovery import scan_directory
from .pipeline.registry import get_available_pipeline_steps, get_default_pipeline
from .steps import process_video_file
from .config.settings import get_default_pipeline_config
from .output import save_to_json, save_run_outputs
from .utils import calculate_checksum

# Create Typer app
app = typer.Typer(help="AI-Powered Video Ingest & Catalog Tool")

# API server URL
API_SERVER_URL = "http://localhost:8000/api"

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
    compression_bitrate: str = typer.Option(DEFAULT_COMPRESSION_CONFIG['video_bitrate'], "--bitrate", help=f"Video bitrate for compression (default: {DEFAULT_COMPRESSION_CONFIG['video_bitrate']})"),
    store_database: bool = typer.Option(False, "--store-database", help="Store results in Supabase database (requires authentication)"),
    generate_embeddings: bool = typer.Option(False, "--generate-embeddings", help="Generate vector embeddings for semantic search (requires authentication)"),
    upload_thumbnails: bool = typer.Option(False, "--upload-thumbnails", help="Upload thumbnails to Supabase storage (requires authentication)"),
    force_reprocess: bool = typer.Option(False, "--force-reprocess", "-f", help="Force reprocessing of files even if they already exist in database")
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
    
    # Handle database storage, embeddings, and thumbnail uploads
    if store_database or generate_embeddings or upload_thumbnails:
        from .auth import AuthManager
        from .supabase_config import verify_connection
        
        # Check Supabase connection
        if not verify_connection():
            console.print("[bold red]Error:[/bold red] Cannot connect to Supabase database")
            console.print("Please check your .env file and Supabase configuration")
            raise typer.Exit(1)
        
        # Check authentication
        auth_manager = AuthManager()
        if not auth_manager.get_current_session():
            console.print("[bold red]Error:[/bold red] Database storage requires authentication")
            console.print("Please run: [cyan]python -m video_ingest_tool auth login[/cyan]")
            raise typer.Exit(1)
        
        # Enable database storage if requested
        if store_database:
            pipeline_config['database_storage'] = True
            logger.info("Enabled database storage")
            console.print("[green]✓[/green] Database storage enabled")
        
        # Enable embeddings if requested (also requires database storage)
        if generate_embeddings:
            pipeline_config['generate_embeddings'] = True
            pipeline_config['database_storage'] = True  # Embeddings require database
            logger.info("Enabled vector embeddings generation")
            console.print("[green]✓[/green] Vector embeddings enabled")
        
        # Enable thumbnail uploads if requested (also requires database storage)
        if upload_thumbnails:
            pipeline_config['thumbnail_upload'] = True
            pipeline_config['database_storage'] = True  # Thumbnail uploads require database storage for clip_id
            logger.info("Enabled thumbnail uploads")
            console.print("[green]✓[/green] Thumbnail uploads enabled")
    
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
    skipped_files = []
    
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
                result = process_video_file(
                    file_path, 
                    thumbnails_dir, 
                    logger,
                    config=pipeline_config,
                    compression_fps=compression_fps,
                    compression_bitrate=compression_bitrate,
                    force_reprocess=force_reprocess
                )
                
                # Handle skipped files (duplicates)
                if isinstance(result, dict) and result.get('skipped'):
                    skipped_files.append({
                        'file_path': file_path,
                        'reason': result.get('reason'),
                        'existing_clip_id': result.get('existing_clip_id'),
                        'existing_file_name': result.get('existing_file_name'),
                        'existing_processed_at': result.get('existing_processed_at')
                    })
                    logger.info("Skipped duplicate file", 
                               file=file_path, 
                               existing_id=result.get('existing_clip_id'))
                else:
                    # Normal processing result
                    video_file = result
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
    
    # Check if we had skipped files and inform the user
    if skipped_files:
        console.print(f"[bold yellow]Info:[/bold yellow] Skipped {len(skipped_files)} duplicate file(s):", style="yellow")
        for skipped in skipped_files:
            console.print(f"  - {os.path.basename(skipped['file_path'])} (exists as {skipped['existing_file_name']})", style="yellow")
        if not force_reprocess:
            console.print(f"[dim]Use --force-reprocess to reprocess these files[/dim]")
    
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
    if skipped_files:
        summary_table.add_row("Skipped files (duplicates)", str(len(skipped_files)))
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
                skipped_files=len(skipped_files),
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

# Search commands
search_app = typer.Typer(help="Search video catalog")
app.add_typer(search_app, name="search")

@search_app.command("recent")
def list_recent_videos(
    limit: int = typer.Option(10, "--limit", "-l", help="Maximum number of results"),
    output_format: str = typer.Option("table", "--format", help="Output format: table, json")
):
    """List recent videos from your catalog."""
    from .search import VideoSearcher, format_search_results # Import here to avoid circular deps
    from .auth import AuthManager # Import AuthManager

    auth_manager = AuthManager()
    if not auth_manager.get_current_session():
        console.print("[red]Authentication required. Please login using 'ait auth login'.[/red]")
        raise typer.Exit(code=1)

    try:
        video_searcher = VideoSearcher()
        # Call the new list_videos method, default sort is 'processed_at' descending
        results = video_searcher.list_videos(limit=limit) 

        if not results:
            console.print("No recent videos found.")
            return

        if output_format == "json":
            # For JSON, we might not need the 'format_search_results' if list_videos returns sufficient data
            # Or, adapt format_search_results if specific formatting is still needed
            console.print_json(data=results)
        else:
            # Assuming 'list_videos' returns data in a structure that format_search_results can handle
            # or that we can adapt. For now, let's assume it's compatible or we'll adjust format_search_results later.
            # We pass a generic search_type like 'recent' or None if format_search_results needs it.
            # For now, let's try to display raw fields if format_search_results is not directly applicable.
            
            table = Table(title=f"Recent Videos (Top {limit})")
            if results:
                # Dynamically create columns from the keys of the first result
                # This makes it flexible if list_videos returns different fields than search
                headers = results[0].keys()
                for header in headers:
                    table.add_column(header.replace("_", " ").title())
                
                for item in results:
                    table.add_row(*[str(item.get(header, "N/A")) for header in headers])
            
            console.print(table)

    except ValueError as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(code=1)
    except Exception as e:
        console.print(f"[red]An unexpected error occurred: {e}[/red]")
        logger.exception("Error listing recent videos in CLI") # Make sure logger is defined
        raise typer.Exit(code=1)


@search_app.command("query") 
# Renamed from 'search' to 'query' to avoid conflict with the 'search' subcommand group
# and to be more descriptive of its action (querying with text)
def search_videos(
    query: str = typer.Argument(..., help="Search query"),
    search_type: str = typer.Option("hybrid", "--type", "-t", help="Search type: semantic, fulltext, hybrid, transcripts"),
    limit: int = typer.Option(10, "--limit", "-l", help="Maximum number of results"),
    show_scores: bool = typer.Option(True, "--scores/--no-scores", help="Show similarity/ranking scores"),
    summary_weight: float = typer.Option(1.0, "--summary-weight", help="Weight for summary embeddings (hybrid/semantic)"),
    keyword_weight: float = typer.Option(0.8, "--keyword-weight", help="Weight for keyword embeddings (hybrid/semantic)"),
    fulltext_weight: float = typer.Option(1.0, "--fulltext-weight", help="Weight for full-text search (hybrid)"),
    output_format: str = typer.Option("table", "--format", help="Output format: table, json")
):
    """Search the video catalog using various search methods."""
    from .search import VideoSearcher, format_search_results, format_duration
    
    # Validate search type
    valid_types = ["semantic", "fulltext", "hybrid", "transcripts", "similar", "recent"]
    if search_type not in valid_types:
        console.print(f"[red]Error:[/red] Invalid search type. Must be one of: {', '.join(valid_types)}")
        raise typer.Exit(1)
        
    # Handle special search types
    if search_type == "recent":
        # Redirect to the recent command
        console.print("[yellow]Redirecting to 'recent' command...[/yellow]")
        list_recent_videos(limit=limit, output_format=output_format)
        return
    elif search_type == "similar":
        console.print("[red]Error:[/red] For similar search, use: python -m video_ingest_tool search similar <clip_id>")
        raise typer.Exit(1)
    
    try:
        searcher = VideoSearcher()
        
        # Set weights for search
        weights = {
            'summary_weight': summary_weight,
            'keyword_weight': keyword_weight,
            'fulltext_weight': fulltext_weight
        }
        
        console.print(f"[cyan]Searching for:[/cyan] '{query}' [dim]({search_type} search)[/dim]")
        
        # Perform search
        results = searcher.search(
            query=query,
            search_type=search_type,
            match_count=limit,
            weights=weights
        )
        
        if not results:
            console.print("[yellow]No results found.[/yellow]")
            return
        
        # Format results
        formatted_results = format_search_results(results, search_type, show_scores)
        
        if output_format == "json":
            import json
            console.print(json.dumps(formatted_results, indent=2, default=str))
        else:
            # Display as table
            results_table = Table(title=f"Search Results ({len(results)} found)")
            results_table.add_column("File", style="cyan", max_width=30)
            results_table.add_column("Summary", style="green", max_width=50)
            results_table.add_column("Duration", style="blue")
            results_table.add_column("Category", style="magenta")
            
            if show_scores:
                if search_type == "hybrid":
                    results_table.add_column("Score", style="yellow")
                    results_table.add_column("Type", style="dim")
                elif search_type == "semantic":
                    results_table.add_column("Similarity", style="yellow")
                elif search_type in ["fulltext", "transcripts"]:
                    results_table.add_column("Rank", style="yellow")
            
            for result in formatted_results:
                row = [
                    result.get('file_name', 'Unknown'),
                    result.get('content_summary', 'No summary')[:100] + "..." if result.get('content_summary') else "No summary",
                    format_duration(result.get('duration_seconds', 0)),
                    result.get('content_category', 'Unknown')
                ]
                
                if show_scores:
                    if search_type == "hybrid":
                        search_rank_val = result.get('search_rank')
                        search_rank_str = f"{search_rank_val:.3f}" if search_rank_val is not None else "N/A"
                        row.extend([
                            search_rank_str,
                            result.get('match_type', 'unknown')
                        ])
                    elif search_type == "semantic":
                        combined_similarity_val = result.get('combined_similarity')
                        combined_similarity_str = f"{combined_similarity_val:.3f}" if combined_similarity_val is not None else "N/A"
                        row.append(combined_similarity_str)
                    elif search_type in ["fulltext", "transcripts"]:
                        fts_rank_val = result.get('fts_rank')
                        fts_rank_str = f"{fts_rank_val:.3f}" if fts_rank_val is not None else "N/A"
                        row.append(fts_rank_str)
                
                results_table.add_row(*row)
            
            console.print(results_table)
            
            # Show example commands
            console.print(f"\n[dim]💡 To view details: python -m video_ingest_tool search show <clip_id>[/dim]")
            
    except ValueError as e:
        console.print(f"[red]Error:[/red] {str(e)}")
        console.print("Please run: [cyan]python -m video_ingest_tool auth login[/cyan]")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Search failed:[/red] {str(e)}")
        raise typer.Exit(1)

@search_app.command("similar")
def find_similar_videos(
    clip_id: str = typer.Argument(..., help="ID of the source clip"),
    limit: int = typer.Option(5, "--limit", "-l", help="Maximum number of similar clips"),
    threshold: float = typer.Option(0.5, "--threshold", "-t", help="Minimum similarity threshold"),
    output_format: str = typer.Option("table", "--format", help="Output format: table, json")
):
    """Find videos similar to a given clip."""
    from .search import VideoSearcher, format_search_results, format_duration
    
    try:
        searcher = VideoSearcher()
        
        console.print(f"[cyan]Finding clips similar to:[/cyan] {clip_id}")
        
        results = searcher.find_similar(
            clip_id=clip_id,
            match_count=limit,
            similarity_threshold=threshold
        )
        
        if not results:
            console.print("[yellow]No similar clips found.[/yellow]")
            return
        
        formatted_results = format_search_results(results, "similar", True)
        
        if output_format == "json":
            import json
            console.print(json.dumps(formatted_results, indent=2, default=str))
        else:
            results_table = Table(title=f"Similar Clips ({len(results)} found)")
            results_table.add_column("File", style="cyan", max_width=30)
            results_table.add_column("Summary", style="green", max_width=50)
            results_table.add_column("Duration", style="blue")
            results_table.add_column("Category", style="magenta")
            results_table.add_column("Similarity", style="yellow")
            
            for result in formatted_results:
                results_table.add_row(
                    result.get('file_name', 'Unknown'),
                    result.get('content_summary', 'No summary')[:100] + "..." if result.get('content_summary') else "No summary",
                    format_duration(result.get('duration_seconds', 0)),
                    result.get('content_category', 'Unknown'),
                    f"{result.get('similarity_score', 0):.3f}"
                )
            
            console.print(results_table)
            
    except Exception as e:
        console.print(f"[red]Similar search failed:[/red] {str(e)}")
        raise typer.Exit(1)

@search_app.command("show")
def show_clip_details(
    clip_id: str = typer.Argument(..., help="ID of the clip to show"),
    show_transcript: bool = typer.Option(False, "--transcript", help="Show full transcript if available"),
    show_analysis: bool = typer.Option(False, "--analysis", help="Show AI analysis details")
):
    """Show detailed information about a specific clip."""
    from .auth import AuthManager
    from .search import format_duration, format_file_size
    
    try:
        auth_manager = AuthManager()
        client = auth_manager.get_authenticated_client()
        
        if not client:
            console.print("[red]Error:[/red] Authentication required")
            console.print("Please run: [cyan]python -m video_ingest_tool auth login[/cyan]")
            raise typer.Exit(1)
        
        # Get clip details
        clip_result = client.table('clips').select('*').eq('id', clip_id).execute()
        
        if not clip_result.data:
            console.print(f"[red]Error:[/red] Clip with ID {clip_id} not found")
            raise typer.Exit(1)
        
        clip = clip_result.data[0]
        
        # Display clip information
        info_table = Table(title=f"Clip Details: {clip.get('file_name')}")
        info_table.add_column("Property", style="cyan")
        info_table.add_column("Value", style="green")
        
        info_table.add_row("ID", clip.get('id'))
        info_table.add_row("File Name", clip.get('file_name'))
        info_table.add_row("Local Path", clip.get('local_path'))
        info_table.add_row("Duration", format_duration(clip.get('duration_seconds', 0)))
        info_table.add_row("File Size", format_file_size(clip.get('file_size_bytes', 0)))
        info_table.add_row("Content Category", clip.get('content_category') or 'Unknown')
        info_table.add_row("Camera", f"{clip.get('camera_make', 'Unknown')} {clip.get('camera_model', '')}")
        info_table.add_row("Resolution", f"{clip.get('width')}x{clip.get('height')}" if clip.get('width') else 'Unknown')
        info_table.add_row("Frame Rate", f"{clip.get('frame_rate')} fps" if clip.get('frame_rate') else 'Unknown')
        info_table.add_row("Processed At", clip.get('processed_at'))
        
        console.print(info_table)
        
        # Show content summary
        if clip.get('content_summary'):
            console.print(f"\n[bold]Content Summary:[/bold]")
            console.print(clip['content_summary'])
        
        # Show content tags
        if clip.get('content_tags'):
            console.print(f"\n[bold]Content Tags:[/bold]")
            console.print(", ".join(clip['content_tags']))
        
        # Show transcript if requested
        if show_transcript:
            transcript_result = client.table('transcripts').select('full_text').eq('clip_id', clip_id).execute()
            if transcript_result.data and transcript_result.data[0].get('full_text'):
                console.print(f"\n[bold]Transcript:[/bold]")
                console.print(transcript_result.data[0]['full_text'])
            else:
                console.print(f"\n[dim]No transcript available[/dim]")
        
        # Show AI analysis if requested
        if show_analysis:
            analysis_result = client.table('analysis').select('*').eq('clip_id', clip_id).execute()
            if analysis_result.data:
                console.print(f"\n[bold]AI Analysis:[/bold]")
                for analysis in analysis_result.data:
                    console.print(f"Type: {analysis.get('analysis_type')}")
                    console.print(f"Model: {analysis.get('ai_model')}")
                    console.print(f"Usability Rating: {analysis.get('usability_rating')}")
                    console.print(f"Speaker Count: {analysis.get('speaker_count')}")
            else:
                console.print(f"\n[dim]No AI analysis available[/dim]")
                
    except Exception as e:
        console.print(f"[red]Failed to show clip details:[/red] {str(e)}")
        raise typer.Exit(1)

@search_app.command("stats")
def show_catalog_stats():
    """Show statistics about your video catalog."""
    from .search import VideoSearcher
    
    try:
        searcher = VideoSearcher()
        stats = searcher.get_user_stats()
        
        if not stats:
            console.print("[yellow]No statistics available.[/yellow]")
            return
        
        stats_table = Table(title="Video Catalog Statistics")
        stats_table.add_column("Metric", style="cyan")
        stats_table.add_column("Value", style="green")
        
        stats_table.add_row("Total Clips", str(stats.get('total_clips', 0)))
        stats_table.add_row("Total Duration", f"{stats.get('total_duration_hours', 0)} hours")
        stats_table.add_row("Total Storage", f"{stats.get('total_storage_gb', 0)} GB")
        stats_table.add_row("Clips with Transcripts", str(stats.get('clips_with_transcripts', 0)))
        stats_table.add_row("Clips with AI Analysis", str(stats.get('clips_with_ai_analysis', 0)))
        
        console.print(stats_table)
        
    except Exception as e:
        console.print(f"[red]Failed to get statistics:[/red] {str(e)}")
        raise typer.Exit(1)

@app.command("check-progress")
def check_ingest_progress():
    """Check the progress of the current ingest job running on the API server.
    
    This command connects to the API server (http://localhost:8000) and retrieves
    the current status of any running ingest job. If no job is running, it will
    show an idle status.
    """
    try:
        console.print("[bold]Checking ingest progress on API server...[/bold]")
        response = requests.get(f"{API_SERVER_URL}/ingest/progress")
        
        if response.status_code != 200:
            console.print(f"[red]Error: API server returned status code {response.status_code}[/red]")
            if response.status_code == 404:
                console.print("[yellow]Endpoint not found. Make sure the API server is running and up to date.[/yellow]")
            return
            
        progress_data = response.json()
        
        # Create a styled status indicator
        status = progress_data.get("status", "unknown")
        status_color = {
            "idle": "white",
            "running": "blue",
            "scanning": "cyan",
            "processing": "green",
            "completed": "green",
            "failed": "red"
        }.get(status, "yellow")
        
        # Create a progress bar
        progress_value = progress_data.get("progress", 0)
        progress = Progress(
            "[progress.description]{task.description}",
            BarColumn(bar_width=40),
            "[progress.percentage]{task.percentage:>3.0f}%",
            console=console
        )
        
        # Display the progress information in a panel
        console.print(Panel.fit(
            f"[bold]Status:[/bold] [{status_color}]{status.upper()}[/{status_color}]\n"
            f"[bold]Message:[/bold] {progress_data.get('message', 'No message')}\n",
            title="Ingest Progress"
        ))
        
        # Show the progress bar
        with progress:
            task = progress.add_task("Progress", total=100, completed=progress_value)
            progress.update(task, completed=progress_value)
        
        # Show additional statistics if available
        if "processed_count" in progress_data or "results_count" in progress_data:
            stats_table = Table(title="Processing Statistics")
            stats_table.add_column("Metric", style="cyan")
            stats_table.add_column("Value", style="green")
            
            processed = progress_data.get("processed_count", progress_data.get("results_count", 0))
            stats_table.add_row("Processed Files", str(processed))
            
            if "total_count" in progress_data:
                stats_table.add_row("Total Files", str(progress_data["total_count"]))
                
            if "failed_count" in progress_data:
                failed_color = "red" if progress_data["failed_count"] > 0 else "green"
                stats_table.add_row("Failed Files", f"[{failed_color}]{progress_data['failed_count']}[/{failed_color}]")
                
            console.print(stats_table)
            
        # Show next steps based on status
        if status == "idle":
            console.print("\n[yellow]No active ingest job. Use 'ingest' command or the API to start processing.[/yellow]")
        elif status == "completed":
            console.print("\n[green]Processing completed successfully![/green]")
        elif status == "failed":
            console.print("\n[red]Processing failed. Check the API server logs for details.[/red]")
                
    except requests.exceptions.ConnectionError:
        console.print("[red]Error: Could not connect to the API server[/red]")
        console.print("[yellow]Make sure the API server is running on http://localhost:8000[/yellow]")
        console.print("[yellow]Start it with 'python api_server.py' from the project root[/yellow]")
    except Exception as e:
        console.print(f"[red]Error checking progress: {str(e)}[/red]")

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
