"""
Modern CLI for the video ingest tool using command classes.

This CLI is built on top of standardized command classes that can also be used
by the API server, ensuring consistent behavior across interfaces.
"""

import typer
from typing import Optional, List
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeRemainingColumn
import json

from .cli_commands import AuthCommand, SearchCommand, IngestCommand, SystemCommand, ClipsCommand
from .config import console

# Create the main CLI app
app = typer.Typer(
    name="video-ingest",
    help="AI-powered video ingestion and analysis tool"
)

# Create subgroups  
auth_app = typer.Typer(help="Authentication commands")
search_app = typer.Typer(help="Search and discovery commands")
clip_app = typer.Typer(help="Individual clip operations")

app.add_typer(auth_app, name="auth")
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
    ai_analysis_enabled: bool = typer.Option(True, "--ai-analysis/--no-ai-analysis", help="Enable AI video analysis"),
    compression_enabled: bool = typer.Option(True, "--compression/--no-compression", help="Enable video compression for AI analysis"),
    compression_fps: int = typer.Option(2, "--compression-fps", help="Frame rate for compression"),
    compression_bitrate: str = typer.Option("500k", "--compression-bitrate", help="Bitrate for compression"),
    database_storage: bool = typer.Option(True, "--database-storage/--no-database-storage", help="Store results in database"),
    upload_thumbnails: bool = typer.Option(True, "--upload-thumbnails/--no-upload-thumbnails", help="Upload thumbnails to storage"),
    generate_embeddings: bool = typer.Option(True, "--generate-embeddings/--no-generate-embeddings", help="Generate vector embeddings"),
    focal_length_detection: bool = typer.Option(True, "--focal-length-detection/--no-focal-length-detection", help="Enable AI focal length detection"),
    ai_thumbnail_selection: bool = typer.Option(True, "--ai-thumbnail-selection/--no-ai-thumbnail-selection", help="Enable AI thumbnail selection"),
    parallel_tasks: int = typer.Option(4, "--parallel-tasks", "-p", help="Number of parallel processing tasks"),
    use_api: bool = typer.Option(False, "--use-api/--no-use-api", help="Use API server for background processing")
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
        'use_api': use_api
    }
    
    console.print(f"\n[bold blue]🎬 Starting video ingest from:[/bold blue] {directory}")
    
    # Execute the ingest command
    result = cmd.execute(**ingest_args)
    
    if result.get('success'):
        data = result.get('data', {})
        
        # Handle Prefect task_run_id (background processing)
        if 'task_run_id' in result:
            task_run_id = result['task_run_id']
            console.print(f"\n[green]✅ Ingest started successfully![/green]")
            console.print(f"[cyan]Task Run ID:[/cyan] {task_run_id}")
            console.print("[yellow]💡 Use 'check-progress' to monitor progress[/yellow]")
            console.print(f"[yellow]   Or visit API server for real-time updates[/yellow]")
            
        # Handle direct processing result  
        else:
            console.print(f"\n[green]✅ Ingest completed successfully![/green]")
            
            if 'files_processed' in data:
                console.print(f"Files processed: {data['files_processed']}")
            if 'run_id' in data:
                console.print(f"Run ID: {data['run_id']}")
            if 'output_directory' in data:
                console.print(f"Output directory: {data['output_directory']}")
            if 'results' in data and isinstance(data['results'], list):
                console.print(f"Results: {len(data['results'])} files processed")
                
            # Show processing summary if available
            if 'processing_summary' in data:
                summary = data['processing_summary']
                console.print(f"\n[bold blue]📊 Processing Summary:[/bold blue]")
                for key, value in summary.items():
                    console.print(f"  {key}: {value}")
            
    else:
        console.print(f"\n[red]❌ Ingest failed: {result.get('error')}[/red]")
        
        # Provide helpful troubleshooting hints
        error_msg = result.get('error', '').lower()
        if 'directory' in error_msg:
            console.print("[yellow]💡 Check that the directory path exists and is accessible[/yellow]")
        elif 'authentication' in error_msg:
            console.print("[yellow]💡 Try running 'auth login' first[/yellow]")
        elif 'database' in error_msg:
            console.print("[yellow]💡 Check database connection with 'auth status'[/yellow]")
            
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
        console.print(json.dumps(steps, indent=2))
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
    api_url: str = typer.Option("http://localhost:8000", "--api-url", help="API server URL")
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
# AUTH COMMANDS  
# ============================================================================

@auth_app.command("login")
def auth_login():
    """Log in to your account."""
    
    email = typer.prompt("Email")
    password = typer.prompt("Password", hide_input=True)
    
    cmd = AuthCommand()
    result = cmd.execute('login', email=email, password=password)
    
    if result.get('success'):
        user_data = result.get('data', {}).get('user', {})
        console.print(f"\n[green]✅ Successfully logged in as {user_data.get('email', email)}[/green]")
        
        # Show user info if available
        if user_data:
            panel_content = []
            for key, value in user_data.items():
                if key != 'email':  # Already shown above
                    panel_content.append(f"[cyan]{key.title()}:[/cyan] {value}")
            
            if panel_content:
                console.print(Panel("\n".join(panel_content), title="User Information", border_style="green"))
                
    else:
        console.print(f"\n[red]❌ Login failed: {result.get('error')}[/red]")
        raise typer.Exit(1)


@auth_app.command("signup")  
def auth_signup():
    """Create a new account."""
    
    email = typer.prompt("Email")
    password = typer.prompt("Password", hide_input=True)
    password_confirm = typer.prompt("Confirm password", hide_input=True)
    
    if password != password_confirm:
        console.print("[red]❌ Passwords do not match[/red]")
        raise typer.Exit(1)
        
    cmd = AuthCommand()
    result = cmd.execute('register', email=email, password=password)
    
    if result.get('success'):
        console.print(f"\n[green]✅ Account created successfully![/green]")
        console.print(f"You can now log in with email: {email}")
    else:
        console.print(f"\n[red]❌ Signup failed: {result.get('error')}[/red]")
        raise typer.Exit(1)


@auth_app.command("logout")
def auth_logout():
    """Log out of your current session."""
    
    cmd = AuthCommand()
    result = cmd.execute('logout')
    
    if result.get('success'):
        console.print("\n[green]✅ Successfully logged out[/green]")
    else:
        console.print(f"\n[red]❌ Logout failed: {result.get('error')}[/red]")
        raise typer.Exit(1)


@auth_app.command("status")
def auth_status():
    """Show current authentication status."""
    
    cmd = AuthCommand()
    result = cmd.execute('status')
    
    if result.get('success'):
        data = result.get('data', {})
        is_authenticated = data.get('authenticated', False)
        
        if is_authenticated:
            user = data.get('user', {})
            console.print(f"\n[green]✅ Logged in as {user.get('email', 'Unknown')}[/green]")
            
            # Show additional user details
            if user:
                details = []
                for key, value in user.items():
                    if key != 'email':  # Already shown above
                        details.append(f"[cyan]{key.title()}:[/cyan] {value}")
                        
                if details:
                    console.print(Panel("\n".join(details), title="Account Details", border_style="green"))
        else:
            console.print("\n[yellow]ℹ️  Not logged in[/yellow]")
            console.print("Use [cyan]auth login[/cyan] to authenticate")
            
        # Show database connection status
        db_status = data.get('database_connection', {})
        if db_status:
            status_text = "✅ Connected" if db_status.get('connected') else "❌ Disconnected"
            console.print(f"\nDatabase: {status_text}")
            
    else:
        console.print(f"\n[red]❌ Status check failed: {result.get('error')}[/red]")
        raise typer.Exit(1)


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
            raise typer.Exit(1)
        
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

def _display_search_results(data: dict, format_type: str, show_relevance: bool = False, show_similarity: bool = False):
    """Display search results in the specified format."""
    
    results = data.get('results', [])
    total = data.get('total', 0)
    
    if format_type == "json":
        console.print(json.dumps(data, indent=2))
        return
        
    if not results:
        console.print("\n[yellow]No results found[/yellow]")
            return
        
    console.print(f"\n[bold blue]🔍 Found {total} video(s)[/bold blue]\n")
    
    # Create results table
    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("File Name", style="cyan", no_wrap=True, max_width=40)
    table.add_column("Duration", justify="center", max_width=10)
    table.add_column("Size", justify="center", max_width=10)
    table.add_column("Processed", justify="center", max_width=12)
    
    if show_relevance:
        table.add_column("Relevance", justify="center", max_width=10)
    elif show_similarity:
        table.add_column("Similarity", justify="center", max_width=10)
        
    table.add_column("Clip ID", style="dim", max_width=20)
    
    for result in results:
        row = [
            result.get('file_name', 'Unknown'),
            f"{result.get('duration_seconds', 0):.1f}s",
            f"{result.get('file_size_mb', 0):.1f}MB",
            result.get('processed_at', 'Unknown')[:10] if result.get('processed_at') else 'Unknown'
        ]
        
        if show_relevance:
            row.append(f"{result.get('relevance_score', 0):.3f}")
        elif show_similarity:
            row.append(f"{result.get('similarity_score', 0):.3f}")
            
        row.append(result.get('clip_id', 'Unknown')[:12] + '...' if result.get('clip_id') else 'Unknown')
        
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
        console.print(Panel(json.dumps(analysis, indent=2), title="AI Analysis", border_style="magenta"))
        
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
        console.print(json.dumps(transcript_data, indent=2))
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
        console.print(json.dumps(analysis_data, indent=2))
    else:
        # Display as formatted analysis
        console.print(f"\n[bold blue]🤖 AI Analysis for Clip {clip_id}[/bold blue]\n")
        console.print(Panel(json.dumps(analysis_data, indent=2), title="AI Analysis", border_style="magenta"))


if __name__ == "__main__":
    app() 