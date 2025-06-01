import pytest
import os
import shutil
import json
import uuid
from typing import List, Dict, Optional, Any, Tuple # Import List, Dict, Optional, Any, Tuple
from typer.testing import CliRunner
from pathlib import Path

from video_ingest_tool.cli import app as cli_app # Main Typer app
from video_ingest_tool.database.duckdb.connection import get_db_connection, get_db_path
# get_db_path is needed by the test_db_session fixture
from video_ingest_tool.database.duckdb.schema import initialize_schema, create_fts_index_for_clips
# app_settings import removed as it's no longer used for patching DUCKDB_PATH here

# Define the path to the source sample video relative to the project root
# Assuming this test file is in video_ingest_tool/tests/cli_tests/
# and Wizard/ is at the project root.
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent # Go up one more level
SAMPLE_VIDEO_SOURCE_DIR = PROJECT_ROOT / "Wizard"
SAMPLE_VIDEO_FILENAME = "MVI_0484.MP4" # Make sure this file exists in Wizard/

@pytest.fixture(scope="function")
def cli_runner():
    """Fixture for invoking CLI commands."""
    return CliRunner()

@pytest.fixture(scope="function")
def temp_ingest_dir(tmp_path_factory):
    """Creates a temporary directory for ingest tests and a sample video file."""
    temp_dir = tmp_path_factory.mktemp("ingest_data")
    source_video_path = SAMPLE_VIDEO_SOURCE_DIR / SAMPLE_VIDEO_FILENAME
    
    if not source_video_path.exists():
        pytest.skip(f"Sample video {source_video_path} not found. Skipping CLI e2e test.")
        return None # Should not be reached if skipped

    temp_video_path = temp_dir / SAMPLE_VIDEO_FILENAME
    shutil.copy(source_video_path, temp_video_path)
    return temp_dir

@pytest.fixture(scope="function")
def test_db_session():
    """
    Provides a test-specific, temporary DuckDB database.
    Initializes schema and handles cleanup.
    """
    # Create a unique DB file for each test function to ensure isolation
    db_file_name = f"test_cli_e2e_{uuid.uuid4().hex}.duckdb"
    temp_db_path = Path(get_db_path()).parent / db_file_name
    
    # Ensure the data directory exists
    os.makedirs(temp_db_path.parent, exist_ok=True)

    conn = None
    try:
        conn = get_db_connection(db_path=str(temp_db_path))
        conn.execute("SET hnsw_enable_experimental_persistence=true;") # Enable HNSW for file-based DB
        initialize_schema(conn, create_fts=True) # Create tables and FTS index initially (on empty table)
        conn.commit()
        yield str(temp_db_path) # Pass the path to the test
    finally:
        if conn:
            conn.close()
        if temp_db_path.exists():
            os.remove(temp_db_path)
            # Attempt to remove the WAL file if it exists
            wal_path = temp_db_path.with_suffix(temp_db_path.suffix + ".wal")
            if wal_path.exists():
                try:
                    os.remove(wal_path)
                except OSError:
                    pass # Ignore if it can't be removed (e.g., already gone)


def run_cli_command(runner: CliRunner, command: List[str], env: Optional[Dict[str, str]] = None):
    """Helper function to run CLI commands and return the result."""
    # Ensure PREFECT_API_URL is set to something that won't try to connect to a real server
    # if not explicitly running with --use-api
    default_env = {"PREFECT_API_URL": "http://127.0.0.1:1234/api", "PREFECT_API_KEY": ""} # Dummy URL
    if env:
        default_env.update(env)
    
    result = runner.invoke(cli_app, command, env=default_env, catch_exceptions=False)
    print(f"CLI Command: {' '.join(command)}")
    print(f"CLI Exit Code: {result.exit_code}")
    print(f"CLI Output:\n{result.stdout}")
    if result.exception:
        print(f"CLI Exception: {result.exception}")
    return result

def extract_json_from_output(output: str) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """
    Extracts a JSON object or array from a string that might have leading log lines.
    Iterates through lines, and if a line (stripped) starts with '{' or '[',
    it attempts to parse the rest of the output from that line onwards as JSON.
    Returns a tuple: (parsed_json_data, error_message_if_any).
    """
    lines = output.splitlines()
    
    for i, line in enumerate(lines):
        stripped_line = line.strip()
        if stripped_line.startswith("{") or stripped_line.startswith("["):
            # Found a potential start of JSON. Assume this is it.
            json_str_candidate = "\n".join(lines[i:])
            try:
                return json.loads(json_str_candidate), None # Success
            except json.JSONDecodeError as e:
                # Parsing failed from this point. This is the definitive error.
                error_detail = f"JSONDecodeError: {e}. Candidate string (first 300 chars): '{json_str_candidate[:300]}...'"
                return None, error_detail # Return this specific error
                
    return None, "No JSON start ('{' or '[') found in output." # Only if no '{' or '[' was ever found at line start


def test_cli_ingest_list_show_cycle(cli_runner: CliRunner, temp_ingest_dir: Path, test_db_session: str, monkeypatch):
    """
    Tests the end-to-end CLI flow: ingest -> list -> show.
    """
    if temp_ingest_dir is None: # Handles skip from fixture
        return

    db_path_override = test_db_session
    # Patch video_ingest_tool.database.duckdb.connection.get_db_path
    # to make it return the temporary test database path.
    monkeypatch.setattr("video_ingest_tool.database.duckdb.connection.get_db_path", lambda: db_path_override)

    # 1. Ingest a single file
    ingest_command = [
        "ingest",
        str(temp_ingest_dir),
        "--limit", "1",
        "--no-recursive",
        "--file-types", "MP4",
        "--no-ai-analysis",
        "--no-generate-embeddings",
        "--no-ai-thumbnail-selection",
        "--no-focal-length-detection",
        "--database-storage" # Ensure this is on
        # The DUCKDB_PATH will be implicitly picked up by get_db_connection if we set it via env
        # Or, if IngestCommand/underlying logic can accept db_path, that's better.
        # For now, relying on the default DUCKDB_PATH or overriding it via env for the subprocess.
    ]
    # DUCKDB_PATH is now set via monkeypatch for the test's process
    ingest_result = run_cli_command(cli_runner, ingest_command) # Removed env override

    assert ingest_result.exit_code == 0, f"Ingest command failed: {ingest_result.stdout}"
    assert "Ingest completed successfully!" in ingest_result.stdout
    assert "Files processed: 1" in ingest_result.stdout

    # After ingest, the FTS index needs to be rebuilt on the new data for this test DB
    # This is because initialize_schema (called by fixture) ran on an empty table.
    # For CLI tests, it's simpler to do this programmatically than via another CLI command.
    with get_db_connection(db_path=db_path_override) as conn_after_ingest:
        create_fts_index_for_clips(conn_after_ingest)
        conn_after_ingest.commit()

    # 2. List clips and find the ingested one
    list_command = [
        "clip", 
        "list",
        "--format", "json"
    ]
    # DUCKDB_PATH is now set via monkeypatch
    list_result = run_cli_command(cli_runner, list_command) # Removed env override

    assert list_result.exit_code == 0, f"Clip list command failed: {list_result.stdout}"
    
    list_data, list_error_msg = extract_json_from_output(list_result.stdout)
    if list_data is None:
        full_output_for_debug = list_result.stdout
        pytest.fail(f"Failed to parse JSON from 'clip list' output. Error detail: {list_error_msg}. Full output (first 500 chars): {full_output_for_debug[:500]}")

    assert list_data.get("success") is True
    clips = list_data.get("data", {}).get("clips", [])
    assert len(clips) > 0, "No clips found after ingest"
    
    ingested_clip = None
    for clip in clips:
        if clip.get("file_name") == SAMPLE_VIDEO_FILENAME:
            ingested_clip = clip
            break
    
    assert ingested_clip is not None, f"Ingested clip '{SAMPLE_VIDEO_FILENAME}' not found in list output."
    ingested_clip_id = ingested_clip.get("id")
    assert ingested_clip_id is not None, "Ingested clip does not have an ID."

    # 3. Show the specific clip
    show_command = [
        "clip",
        "show",
        ingested_clip_id,
        "--format", "json" # Assuming show also supports JSON, or adjust parsing
    ]
    # DUCKDB_PATH is now set via monkeypatch
    show_result = run_cli_command(cli_runner, show_command) # Removed env override
    
    assert show_result.exit_code == 0, f"Clip show command failed: {show_result.stdout}"
    
    show_data, show_error_msg = extract_json_from_output(show_result.stdout)
    if show_data is None:
        full_output_for_debug_show = show_result.stdout
        pytest.fail(f"Failed to parse JSON from 'clip show' output. Error detail: {show_error_msg}. Full output (first 500 chars): {full_output_for_debug_show[:500]}")
        
    assert show_data.get("success") is True
    shown_clip_details = show_data.get("data", {}).get("clip", {})
    
    assert shown_clip_details.get("id") == ingested_clip_id
    assert shown_clip_details.get("file_name") == SAMPLE_VIDEO_FILENAME
    assert shown_clip_details.get("local_path") == str(temp_ingest_dir / SAMPLE_VIDEO_FILENAME)

    # Add more assertions as needed, e.g., checking checksum if available in output
    # For this test, AI analysis was off, so AI-related fields would be None or default.
    assert shown_clip_details.get("full_ai_analysis_json") is None 
    # (or check for default empty ComprehensiveAIAnalysis if that's what mapper does)