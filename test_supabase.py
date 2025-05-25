#!/usr/bin/env python3
"""
Test script to verify Supabase integration for AI Ingesting Tool.
"""

import os
import sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from video_ingest_tool.supabase_config import verify_connection, get_database_status
from video_ingest_tool.auth import AuthManager
from rich.console import Console
from rich.table import Table

console = Console()

def test_connection():
    """Test basic connection to Supabase."""
    console.print("[cyan]Testing Supabase connection...[/cyan]")
    
    if verify_connection():
        console.print("[green]✓ Connection successful[/green]")
        return True
    else:
        console.print("[red]✗ Connection failed[/red]")
        return False

def test_database_status():
    """Test database status and table existence."""
    console.print("[cyan]Checking database status...[/cyan]")
    
    status = get_database_status()
    
    if status['connection'] == 'success':
        console.print("[green]✓ Database connection successful[/green]")
        
        # Check tables
        table = Table(title="Database Tables")
        table.add_column("Table", style="cyan")
        table.add_column("Status", style="green")
        
        for table_name, table_status in status.get('tables', {}).items():
            status_text = "[green]Exists[/green]" if table_status == 'exists' else "[red]Missing[/red]"
            table.add_row(table_name, status_text)
        
        console.print(table)
        return True
    else:
        console.print(f"[red]✗ Database connection failed: {status.get('error', 'Unknown error')}[/red]")
        return False

def main():
    """Run all tests."""
    console.print("[bold]AI Ingesting Tool - Supabase Integration Test[/bold]")
    console.print("=" * 50)
    
    # Test connection
    if not test_connection():
        console.print("[red]Basic connection failed. Check your .env file.[/red]")
        return
    
    # Test database status
    test_database_status()
    
    console.print("\n[yellow]Next steps:[/yellow]")
    console.print("1. Run the database_setup.sql in your Supabase SQL Editor")
    console.print("2. Test authentication: python -m video_ingest_tool auth signup")
    console.print("3. Test login: python -m video_ingest_tool auth login")
    console.print("4. Check status: python -m video_ingest_tool auth status")

if __name__ == "__main__":
    main()
