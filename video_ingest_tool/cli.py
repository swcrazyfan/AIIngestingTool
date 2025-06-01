"""
Modern CLI for the video ingest tool using command classes.

This CLI is built on top of standardized command classes that can also be used
by the API server, ensuring consistent behavior across interfaces.
"""

import typer
from typing import Optional, List, Dict, Any
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeRemainingColumn
import json
import uuid # Import uuid
from datetime import datetime, date # Import datetime and date
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

from .cli_commands import SearchCommand, IngestCommand, SystemCommand, ClipsCommand, ServicesCommand # Added ServicesCommand
from .config import console
from .config.settings import PIPELINE_STEP_DEFINITIONS # Import step definitions

# Helper to create a map of step default enabled states
_step_defaults: Dict[str, bool] = {
    step['name']: step['enabled_by_default']
    for step in PIPELINE_STEP_DEFINITIONS
}

# Create the main CLI app
app = typer.Typer(
    name="video-ingest",
    help="AI-powered video ingestion and analysis tool"
)

# Create subgroups
# auth_app = typer.Typer(help="Authentication commands") # Removed
search_app = typer.Typer(help="Search and discovery commands")
clip_app = typer.Typer(help="Individual clip operations")

# app.add_typer(auth_app, name="auth") # Removed
app.add_typer(search_app, name="search")
app.add_typer(clip_app, name="clip")


# ============================================================================
# MAIN COMMANDS
# ============================================================================

@app.command()
def ingest(
    directory: str = typer.Argument(..., help="Directory containing video files"),
    recursive: bool = typer.Option(True, "--recursive/--no-recursive", "-r", help="Search subdirectories"),
    limit: Optional[int] = typer.Option(None, "--limit", "-l", help="Maximum number of files to process"),
    file_types: str = typer.Option("mp4,mov,avi,mkv,m4v,wmv,flv,webm,3gp,mpg,mpeg,m2v,m4v", "--file-types", help="Comma-separated list of file extensions"),
    force_reprocess: bool = typer.Option(False, "--force", "-f", help="Force reprocess existing files"),
    save_json: bool = typer.Option(True, "--save-json/--no-save-json", help="Save results as JSON"),
    save_directory: Optional[str] = typer.Option(None, "--save-directory", "-s", help="Directory to save outputs"),
    ai_analysis_enabled: bool = typer.Option(_step_defaults.get('ai_video_analysis_step', False), "--ai-analysis/--no-ai-analysis", help="Enable AI video analysis"),
    compression_enabled: bool = typer.Option(_step_defaults.get('video_compression_step', False), "--compression/--no-compression", help="Enable video compression for AI analysis"),
    compression_fps: int = typer.Option(2, "--compression-fps", help="Frame rate for compression"),
    compression_bitrate: str = typer.Option("500k", "--compression-bitrate", help="Bitrate for compression"),
    database_storage: bool = typer.Option(_step_defaults.get('database_storage_step', True), "--database-storage/--no-database-storage", help="Store results in database"),
    upload_thumbnails: bool = typer.Option(_step_defaults.get('upload_thumbnails_step', True), "--upload-thumbnails/--no-upload-thumbnails", help="Upload thumbnails to storage"),
    generate_embeddings: bool = typer.Option(_step_defaults.get('generate_embeddings_step', False), "--generate-embeddings/--no-generate-embeddings", help="Generate vector embeddings"),
    focal_length_detection: bool = typer.Option(_step_defaults.get('detect_focal_length_step', False), "--focal-length-detection/--no-focal-length-detection", help="Enable AI focal length detection"),
    ai_thumbnail_selection: bool = typer.Option(_step_defaults.get('ai_thumbnail_selection_step', False), "--ai-thumbnail-selection/--no-ai-thumbnail-selection", help="Enable AI thumbnail selection"),
    parallel_tasks: int = typer.Option(4, "--parallel-tasks", "-p", help="Number of parallel processing tasks"),
    use_api: bool = typer.Option(False, "--use-api/--no-use-api", help="Use API server for background processing"),
    task_to_run: Optional[str] = typer.Option(None, "--task-to-run", help="Run a specific task only (e.g., 'checksum', 'create_model'). See 'list-steps' for task keys.")
):
    """Ingest and analyze video files with AI-powered metadata extraction."""
    
    cmd = IngestCommand()
    
    # Prepare arguments for the command
    ingest_args = {
        'directory': directory,
        'recursive': recursive,
        'limit': limit,
        'file_types': file_types.split(',') if file_types else [],
        'force_reprocess': force_reprocess,
        'save_json': save_json,
        'save_directory': save_directory,
        'ai_analysis_enabled': ai_analysis_enabled,
        'compression_enabled': compression_enabled,
        'compression_fps': compression_fps,
        'compression_bitrate': compression_bitrate,
        'database_storage': database_storage,
        'upload_thumbnails': upload_thumbnails,
        'generate_embeddings': generate_embeddings,
        'focal_length_detection': focal_length_detection,
        'ai_thumbnail_selection': ai_thumbnail_selection,
        'parallel_tasks': parallel_tasks,
        'use_api': use_api,
        'task_to_run': task_to_run  # Added new argument
    }
    
    console.print(f"\n[bold blue]🎬 Starting video ingest from:[/bold blue] {directory}")
    
    # Execute the ingest command
    result = cmd.execute(**ingest_args)
    
    if result.get('success'):
        data = result.get('data', {})
        
        # If a specific task was run, print its direct data output
        if ingest_args.get('task_to_run'):
            console.print(f"\n[green]✅ Task '{ingest_args['task_to_run']}' completed successfully![/green]")
            console.print("[bold blue]📊 Task Output Data:[/bold blue]")
            # Use a custom serializer for datetime/UUID if they appear in the raw data dict
            try:
                console.print(json.dumps(data, indent=2, default=_json_default_serializer))
            except TypeError as e:
                console.print(f"[yellow]Note: Some data might not be JSON serializable directly: {e}[/yellow]")
                console.print(data) # Fallback to direct print
        
        # Handle Prefect task_run_id (background processing for batch)
        elif 'task_run_id' in data: # Changed from result to data for consistency
            task_run_id = data['task_run_id']
            console.print(f"\n[green]✅ Batch ingest started successfully![/green]")
            console.print(f"[cyan]Batch Run ID:[/cyan] {task_run_id}")
            console.print("[yellow]💡 Use 'check-progress' to monitor progress (if API is used/available)[/yellow]")
            # console.print(f"[yellow]   Or visit API server for real-time updates[/yellow]") # If applicable
            
        # Handle direct batch processing result (no task_run_id if not using API/background mode)
        else:
            console.print(f"\n[green]✅ Batch ingest completed successfully![/green]")
            
            if 'files_processed' in data:
                console.print(f"Files processed: {data.get('files_processed', 0)}")
            if 'files_failed' in data:
                console.print(f"Files failed: {data.get('files_failed', 0)}")
            if 'total_files' in data:
                console.print(f"Total files considered: {data.get('total_files', 0)}")
            if data.get('message'):
                 console.print(f"Message: {data['message']}")
            if data.get('thumbnails_dir'):
                console.print(f"Thumbnails directory: {data['thumbnails_dir']}")

            # If detailed results per file are included (optional in IngestCommand)
            if 'results' in data and isinstance(data['results'], list):
                console.print(f"Detailed results for {len(data['results'])} files available in returned object (if saved).")

    else:
        console.print(f"\n[red]❌ Ingest failed: {result.get('error')}[/red]")
        
        # Provide helpful troubleshooting hints
        error_msg = result.get('error', '').lower()
        if 'directory' in error_msg:
            console.print("[yellow]💡 Check that the directory path exists and is accessible[/yellow]")
        elif 'database' in error_msg:
            console.print("[yellow]💡 Check database connection or DuckDB file permissions[/yellow]")
            
        raise typer.Exit(1)


@app.command("list-steps")
def list_steps(
    format_type: str = typer.Option("table", "--format", "-f", help="Output format (table, json, simple)")
):
    """List all available pipeline steps."""
    
    cmd = SystemCommand()
    result = cmd.execute('list_steps', format_type=format_type)
    
    if not result.get('success'):
        console.print(f"[red]❌ Failed to list steps: {result.get('error')}[/red]")
        raise typer.Exit(1)
        
    data = result.get('data', {})
    steps = data.get('steps', [])
    categories = data.get('categories', {})
    
    if format_type == "json":
        print(json.dumps(steps, indent=2)) # Changed to standard print
        return
        
    # Display as table grouped by category
    console.print(f"\n[bold blue]📋 Available Pipeline Steps[/bold blue] ({data.get('total_steps', 0)} total)\n")
    
    for category, category_steps in categories.items():
        # Create table for this category
        table = Table(title=f"{category} Steps", show_header=True, header_style="bold magenta")
        table.add_column("Step Name", style="cyan", no_wrap=True)
        table.add_column("Status", justify="center")
        table.add_column("Description", style="dim")
        
        for step in category_steps:
            status = "✅ Enabled" if step['enabled'] else "❌ Disabled"
            # Remove the category prefix from description since we're grouping by category
            desc = step['description'].replace(f"[{category}] ", "")
            table.add_row(step['name'], status, desc)
            
        console.print(table)
        console.print()  # Add spacing between categories


@app.command("check-progress")
def check_progress(
    api_url: str = typer.Option("http://localhost:8001", "--api-url", help="API server URL")
):
    """Check the progress of running ingest operations."""
    
    cmd = SystemCommand()
    result = cmd.execute('check_progress', api_url=api_url)
    
    if result.get('success'):
        data = result.get('data', {})
        progress_info = data.get('progress', {})
        
        console.print(f"\n[green]✅ Connected to API server[/green] at {api_url}")
        
        # Display progress information
        if progress_info:
            console.print("\n[bold blue]📊 Current Progress:[/bold blue]")
            console.print(json.dumps(progress_info, indent=2))
        else:
            console.print("\n[yellow]ℹ️  No active operations[/yellow]")
            
    else:
        console.print(f"\n[red]❌ {result.get('error')}[/red]")
        console.print("[yellow]💡 Make sure the API server is running on the specified port[/yellow]")
        raise typer.Exit(1)


# ============================================================================
# AUTH COMMANDS (Removed as authentication is handled by local DuckDB setup)
# All auth commands (login, signup, logout, status) and their definitions
# have been removed from this section.
# ============================================================================
# SEARCH COMMANDS
# ============================================================================

@search_app.command("recent")
def search_recent(
    limit: int = typer.Option(10, "--limit", "-l", help="Number of recent videos to show"),
    format_type: str = typer.Option("table", "--format", "-f", help="Output format (table or json)")
):
    """List recently processed videos."""
    
    cmd = SearchCommand()
    result = cmd.execute(action='recent', limit=limit, format_type=format_type)
    
    if not result.get('success'):
        console.print(f"[red]❌ Search failed: {result.get('error')}[/red]")
        raise typer.Exit(1) # Corrected indentation
        
    _display_search_results(result, format_type)


@search_app.command("query")
def search_query(
    query: str = typer.Argument(..., help="Search query text"),
    search_type: str = typer.Option("all", "--type", "-t", help="Search type (semantic, keyword, all)"),
    limit: int = typer.Option(10, "--limit", "-l", help="Maximum number of results"),
    format_type: str = typer.Option("table", "--format", "-f", help="Output format (table or json)"),
    semantic_weight: float = typer.Option(0.7, "--semantic-weight", help="Weight for semantic search (0.0-1.0)"),
    keyword_weight: float = typer.Option(0.3, "--keyword-weight", help="Weight for keyword search (0.0-1.0)")
):
    """Search videos by query text."""
    
    cmd = SearchCommand()
    result = cmd.execute(
        action='search', 
        query=query,
        search_type=search_type,
        limit=limit,
        format_type=format_type,
        semantic_weight=semantic_weight,
        keyword_weight=keyword_weight
    )
    
    if not result.get('success'):
        console.print(f"[red]❌ Search failed: {result.get('error')}[/red]")
        raise typer.Exit(1)
        
    _display_search_results(result, format_type, show_relevance=True)


@search_app.command("similar")
def search_similar(
    clip_id: str = typer.Argument(..., help="Clip ID to find similar videos for"),
    limit: int = typer.Option(10, "--limit", "-l", help="Maximum number of results"),
    format_type: str = typer.Option("table", "--format", "-f", help="Output format (table or json)")
):
    """Find videos similar to a specific clip."""
    
    cmd = SearchCommand()
    result = cmd.execute(action='similar', clip_id=clip_id, limit=limit, format_type=format_type)
    
    if not result.get('success'):
        console.print(f"[red]❌ Search failed: {result.get('error')}[/red]")
        raise typer.Exit(1)
        
    _display_search_results(result, format_type, show_similarity=True)


@search_app.command("stats")
def search_stats():
    """Show video catalog statistics."""
    
    cmd = SearchCommand()
    result = cmd.execute(action='stats')
    
    if not result.get('success'):
        console.print(f"[red]❌ Failed to get stats: {result.get('error')}[/red]")
        raise typer.Exit(1)
        
    stats = result.get('stats', {})
    
    console.print("\n[bold blue]📊 Video Catalog Statistics[/bold blue]\n")
    
    # Create stats table
    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_column("Metric", style="cyan", min_width=20)
    table.add_column("Value", style="bold white")
    
    for key, value in stats.items():
        # Format key to be more readable
        formatted_key = key.replace('_', ' ').title()
        table.add_row(formatted_key, str(value))
        
    console.print(table)
    console.print()


# ============================================================================
# HELPER FUNCTIONS FOR DISPLAY
# ============================================================================

def _json_default_serializer(obj):
    """JSON serializer for objects not serializable by default json code"""
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    if isinstance(obj, uuid.UUID):
        return str(obj)
    raise TypeError(f"Type {type(obj)} not serializable")

def _display_search_results(data: dict, format_type: str, show_relevance: bool = False, show_similarity: bool = False, is_clip_list: bool = False):
    """Display search results or a list of clips in the specified format."""
    
    results = data.get('results', []) if not is_clip_list else data.get('clips', [])
    total = data.get('total', len(results)) # Use length of results if total not provided (e.g. for simple list)
    
    if format_type == "json":
        # For clip list, the relevant data might be directly under 'data'
        if is_clip_list:
            print(json.dumps(data, indent=2, default=_json_default_serializer)) # Changed to standard print
        else:
            print(json.dumps({"results": results, "total": total}, indent=2, default=_json_default_serializer)) # Changed to standard print
        return
        
    if not results:
        console.print("\n[yellow]No results found[/yellow]")
        return
        
    if is_clip_list:
        limit = data.get('limit')
        offset = data.get('offset')
        count_display = f"{len(results)} clip(s)"
        if limit is not None and offset is not None:
            count_display += f" (limit: {limit}, offset: {offset})"
        console.print(f"\n[bold blue]📋 Displaying {count_display}[/bold blue]\n")
    else:
        console.print(f"\n[bold blue]🔍 Found {total} video(s)[/bold blue]\n")
    
    # Create results table
    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("File Name", style="cyan", no_wrap=True, max_width=40)
    table.add_column("Duration", justify="center", max_width=10)
    table.add_column("Size (MB)", justify="center", max_width=10) # Clarified unit
    table.add_column("Processed At", justify="center", max_width=12) # Clarified name
    
    if show_relevance:
        table.add_column("Relevance", justify="center", max_width=10)
    elif show_similarity:
        table.add_column("Similarity", justify="center", max_width=10)
        
    table.add_column("Clip ID", style="dim", max_width=38) # Increased width for full UUID
    
    for result in results:
        # Adapt for different data structures (search vs. direct clip list)
        file_name = result.get('file_name', 'Unknown')
        duration = result.get('duration_seconds', 0)
        
        # Size might be file_size_mb (search) or file_size_bytes (direct clip)
        size_bytes = result.get('file_size_bytes')
        if size_bytes is not None:
            size_mb = size_bytes / (1024 * 1024)
        else:
            size_mb = result.get('file_size_mb', 0)

        processed_at_val = result.get('processed_at', 'Unknown')
        processed_at_display = processed_at_val[:10] if isinstance(processed_at_val, str) else str(processed_at_val).split(" ")[0]


        duration_display = f"{duration:.1f}s" if duration is not None else "N/A"
        size_mb_display = f"{size_mb:.1f}MB" if size_mb is not None else "N/A"

        row = [
            file_name,
            duration_display,
            size_mb_display,
            processed_at_display
        ]
        
        if show_relevance:
            row.append(f"{result.get('relevance_score', 0):.3f}")
        elif show_similarity:
            row.append(f"{result.get('similarity_score', 0):.3f}")
            
        # Display full clip_id if available, otherwise truncated
        clip_id_val = result.get('id', result.get('clip_id', 'Unknown')) # 'id' from direct clip, 'clip_id' from search
        row.append(str(clip_id_val))
        
        table.add_row(*row)
        
    console.print(table)
    console.print()


def _display_clip_details(data: dict):
    """Display detailed information about a video clip."""
    
    clip = data.get('clip', {})
    if not clip:
        console.print("[yellow]No clip details available[/yellow]")
        return
        
    console.print(f"\n[bold blue]🎬 Video Details[/bold blue]\n")
    
    # Basic information panel
    basic_info = []
    basic_info.append(f"[cyan]File Name:[/cyan] {clip.get('file_name', 'Unknown')}")
    basic_info.append(f"[cyan]Duration:[/cyan] {clip.get('duration_seconds', 0):.1f} seconds")
    basic_info.append(f"[cyan]File Size:[/cyan] {clip.get('file_size_mb', 0):.1f} MB")
    basic_info.append(f"[cyan]Resolution:[/cyan] {clip.get('width', 0)}x{clip.get('height', 0)}")
    basic_info.append(f"[cyan]Frame Rate:[/cyan] {clip.get('frame_rate', 0)} fps")
    basic_info.append(f"[cyan]Processed:[/cyan] {clip.get('processed_at', 'Unknown')}")
    
    console.print(Panel("\n".join(basic_info), title="Basic Information", border_style="blue"))
    
    # Show transcript if available
    transcript = data.get('transcript')
    if transcript:
        console.print(Panel(transcript, title="Transcript", border_style="green"))
        
    # Show AI analysis if available  
    analysis = data.get('analysis')
    if analysis:
        console.print(Panel(json.dumps(analysis, indent=2, default=_json_default_serializer), title="AI Analysis", border_style="magenta"))
        
    console.print()


# ============================================================================
# CLIP COMMANDS (RESTful resource operations)
# ============================================================================

@clip_app.command("show")
def clip_show(
    clip_id: str = typer.Argument(..., help="Clip ID to show details for"),
    show_transcript: bool = typer.Option(False, "--transcript", help="Include transcript"),
    show_analysis: bool = typer.Option(False, "--analysis", help="Include AI analysis")
):
    """Show detailed information about a specific video clip."""
    
    cmd = ClipsCommand()
    result = cmd.execute(action='show', clip_id=clip_id, show_transcript=show_transcript, show_analysis=show_analysis)
    
    if not result.get('success'):
        console.print(f"[red]❌ Failed to get clip details: {result.get('error')}[/red]")
        raise typer.Exit(1)
    
    # Display detailed clip information
    _display_clip_details(result.get('data', {}))


@clip_app.command("list")
def clip_list(
    sort_by: str = typer.Option("created_at", "--sort-by", help="Column to sort by (e.g., created_at, file_name, duration_seconds)"),
    sort_order: str = typer.Option("desc", "--sort-order", help="Sort order ('asc' or 'desc')"),
    limit: int = typer.Option(20, "--limit", "-l", help="Maximum number of clips to list"),
    offset: int = typer.Option(0, "--offset", help="Number of clips to skip (for pagination)"),
    filters: Optional[str] = typer.Option(None, "--filters", help="JSON string of filters to apply (e.g., '{\"content_category\": \"Tutorial\", \"duration_seconds >=\": 60}')"),
    format_type: str = typer.Option("table", "--format", "-f", help="Output format (table or json)")
):
    """List video clips with sorting, pagination, and filtering."""
    cmd = ClipsCommand()
    
    parsed_filters = None
    if filters:
        try:
            parsed_filters = json.loads(filters)
            if not isinstance(parsed_filters, dict):
                console.print(f"[red]❌ Invalid filters format. Must be a JSON object string.[/red]")
                raise typer.Exit(1)
        except json.JSONDecodeError:
            console.print(f"[red]❌ Invalid JSON in filters string.[/red]")
            raise typer.Exit(1)

    list_args = {
        'action': 'list',
        'sort_by': sort_by,
        'sort_order': sort_order,
        'limit': limit,
        'offset': offset,
        'filters': parsed_filters # Pass the parsed dictionary
    }
    result = cmd.execute(**list_args)

    if not result.get('success'):
        console.print(f"[red]❌ Failed to list clips: {result.get('error')}[/red]")
        raise typer.Exit(1)

    # Use _display_search_results, adapting it for a list of clips
    _display_search_results(result.get('data', {}), format_type, is_clip_list=True)


@clip_app.command("transcript")
def clip_transcript(
    clip_id: str = typer.Argument(..., help="Clip ID to get transcript for"),
    format_type: str = typer.Option("text", "--format", "-f", help="Output format (text or json)")
):
    """Get transcript for a specific video clip."""
    
    cmd = ClipsCommand()
    result = cmd.execute(action='transcript', clip_id=clip_id)
    
    if not result.get('success'):
        console.print(f"[red]❌ Failed to get transcript: {result.get('error')}[/red]")
        raise typer.Exit(1)

    transcript_data = result.get('data', {}).get('transcript', {})
    
    if format_type == "json":
        print(json.dumps(transcript_data, indent=2, default=_json_default_serializer)) # Changed to standard print
    else:
        # Display as formatted text
        transcript_text = transcript_data.get('text', 'No transcript text available')
        console.print(f"\n[bold blue]📝 Transcript for Clip {clip_id}[/bold blue]\n")
        console.print(Panel(transcript_text, title="Transcript", border_style="green"))


@clip_app.command("analysis")
def clip_analysis(
    clip_id: str = typer.Argument(..., help="Clip ID to get analysis for"),
    format_type: str = typer.Option("formatted", "--format", "-f", help="Output format (formatted or json)")
):
    """Get AI analysis for a specific video clip."""
    
    cmd = ClipsCommand()
    result = cmd.execute(action='analysis', clip_id=clip_id)
    
    if not result.get('success'):
        console.print(f"[red]❌ Failed to get analysis: {result.get('error')}[/red]")
        raise typer.Exit(1)
        
    analysis_data = result.get('data', {}).get('analysis', {})
    
    if format_type == "json":
        print(json.dumps(analysis_data, indent=2, default=_json_default_serializer)) # Changed to standard print
    else:
        # Display as formatted analysis
        console.print(f"\n[bold blue]🤖 AI Analysis for Clip {clip_id}[/bold blue]\n")
        console.print(Panel(json.dumps(analysis_data, indent=2), title="AI Analysis", border_style="magenta"))


# ============================================================================
# SERVICE MANAGEMENT COMMANDS
# ============================================================================

@app.command("start-services")
def start_services(
    service: str = typer.Argument("all", help="Service to start: 'prefect-server', 'prefect-worker', 'api-server', or 'all'"),
    port: Optional[int] = typer.Option(None, "--port", "-p", help="Port override (only for prefect-server or api-server)"),
    debug: bool = typer.Option(False, "--debug", help="Enable debug mode for API server"),
    foreground: bool = typer.Option(False, "--foreground", "-f", help="Run API server in foreground (only when starting api-server)")
):
    """Start one or more services (Prefect server, worker, API server)."""
    
    cmd = ServicesCommand()
    result = cmd.execute('start', service=service, port=port, debug=debug, foreground=foreground)
    
    if result.get('success'):
        data = result.get('data', {})
        console.print(f"\n[green]✅ {data.get('message', 'Services started')}[/green]")
        
        services = data.get('services', [])
        if services:
            table = Table(title="Started Services", show_header=True, header_style="bold magenta")
            table.add_column("Service", style="cyan")
            table.add_column("PID", justify="center")
            table.add_column("Port", justify="center")
            table.add_column("Log File", style="dim")
            
            for svc in services:
                port_str = str(svc.get('port', 'N/A'))
                log_file = svc.get('log_file', 'N/A')
                if svc.get('foreground'):
                    log_file = "Foreground (no log file)"
                
                table.add_row(
                    svc.get('service', 'Unknown'),
                    str(svc.get('pid', 'N/A')),
                    port_str,
                    log_file
                )
            
            console.print(table)
            
            # Special message for foreground API server
            if any(svc.get('foreground') for svc in services):
                console.print("\n[yellow]💡 API server is running in foreground. Press Ctrl+C to stop.[/yellow]")
        
    else:
        console.print(f"\n[red]❌ Failed to start services: {result.get('error')}[/red]")
        raise typer.Exit(1)


@app.command("stop-services")
def stop_services(
    service: str = typer.Argument("all", help="Service to stop: 'prefect-server', 'prefect-worker', 'api-server', or 'all'")
):
    """Stop one or more services."""
    
    cmd = ServicesCommand()
    result = cmd.execute('stop', service=service)
    
    if result.get('success'):
        data = result.get('data', {})
        stopped = data.get('stopped_services', [])
        console.print(f"\n[green]✅ {data.get('message', 'Services stopped')}[/green]")
        
        if stopped:
            for svc in stopped:
                console.print(f"  • Stopped {svc}")
    else:
        console.print(f"\n[red]❌ Failed to stop services: {result.get('error')}[/red]")
        raise typer.Exit(1)


@app.command("services-status")
def services_status():
    """Show status of all services."""
    
    cmd = ServicesCommand()
    result = cmd.execute('status')
    
    if result.get('success'):
        services = result.get('data', {}).get('services', {})
        
        console.print("\n[bold blue]🔧 Services Status[/bold blue]\n")
        
        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("Service", style="cyan")
        table.add_column("Status", justify="center")
        table.add_column("Port", justify="center")
        table.add_column("Processes", justify="center")
        
        for service_name, status in services.items():
            status_icon = "🟢 Running" if status.get('running') else "🔴 Stopped"
            port_str = str(status.get('port', 'N/A'))
            if service_name == 'prefect-worker':
                port_str = 'N/A'
            
            processes = status.get('processes', [])
            process_count = str(len(processes)) if processes else '0'
            
            table.add_row(
                service_name,
                status_icon,
                port_str,
                process_count
            )
        
        console.print(table)
        console.print()
        
    else:
        console.print(f"\n[red]❌ Failed to get services status: {result.get('error')}[/red]")
        raise typer.Exit(1)


@app.command("restart-services")
def restart_services(
    service: str = typer.Argument("all", help="Service to restart: 'prefect-server', 'prefect-worker', 'api-server', or 'all'"),
    port: Optional[int] = typer.Option(None, "--port", "-p", help="Port override (only for prefect-server or api-server)"),
    debug: bool = typer.Option(False, "--debug", help="Enable debug mode for API server"),
    foreground: bool = typer.Option(False, "--foreground", "-f", help="Run API server in foreground (only when restarting api-server)")
):
    """Restart one or more services."""
    
    cmd = ServicesCommand()
    result = cmd.execute('restart', service=service, port=port, debug=debug, foreground=foreground)
    
    if result.get('success'):
        data = result.get('data', {})
        console.print(f"\n[green]✅ {data.get('message', 'Services restarted')}[/green]")
        
        services = data.get('services', [])
        if services:
            for svc in services:
                console.print(f"  • Restarted {svc.get('service')} (PID: {svc.get('pid')})")
        
    else:
        console.print(f"\n[red]❌ Failed to restart services: {result.get('error')}[/red]")
        raise typer.Exit(1)


if __name__ == "__main__":
    app() 