"""
Output handling for the video ingest tool.

Contains functions for saving data to JSON and potentially other formats in the future.
"""

import os
import json
import shutil
from typing import Any, Dict, List, Optional
from pydantic import BaseModel

def save_to_json(data: Any, filename: str, logger=None) -> None:
    """
    Save data to JSON file.
    
    Args:
        data: Data to save (can be a Pydantic model or dictionary)
        filename: Output filename
        logger: Logger instance
    """
    if logger:
        logger.info("Saving data to JSON", filename=filename)
    
    # Handle Pydantic models
    if isinstance(data, BaseModel):
        data = data.model_dump()
    elif isinstance(data, list) and all(isinstance(item, BaseModel) for item in data):
        data = [item.model_dump() for item in data]
    
    # Create directory if it doesn't exist
    os.makedirs(os.path.dirname(filename), exist_ok=True)
    
    with open(filename, 'w') as f:
        json.dump(data, f, indent=2, default=str)
    
    if logger:
        logger.info("Data saved to JSON", filename=filename)

def save_run_outputs(processed_files: List[Any], run_dir: str, run_timestamp: str, json_dir: str, 
                    log_file: str, logger=None) -> Dict[str, str]:
    """
    Save all outputs from a processing run.
    
    Args:
        processed_files: List of processed video data
        run_dir: Directory for this run
        run_timestamp: Timestamp string for this run
        json_dir: Global JSON output directory
        log_file: Path to log file
        logger: Logger instance
        
    Returns:
        Dict[str, str]: Paths to key output files
    """
    # Save summary JSON to run-specific directory
    run_summary_path = os.path.join(run_dir, "json", "all_videos.json")
    save_to_json(processed_files, run_summary_path, logger)
    
    # Also save to global JSON directory with timestamp
    global_summary_path = os.path.join(json_dir, f"all_videos_{run_timestamp}.json")
    save_to_json(processed_files, global_summary_path, logger)
    
    # Create a copy of the log file in the run directory
    run_log_file = os.path.join(run_dir, "ingestor.log")
    try:
        shutil.copy2(log_file, run_log_file)
        if logger:
            logger.info("Copied log file to run directory", source=log_file, destination=run_log_file)
    except Exception as e:
        if logger:
            logger.error("Failed to copy log file to run directory", error=str(e))
    
    return {
        'run_summary': run_summary_path,
        'global_summary': global_summary_path,
        'run_log': run_log_file
    }

# Placeholder for future database output handler
# This can be expanded later to save data to a database
class DatabaseOutputHandler:
    """Placeholder for database output functionality."""
    
    def __init__(self, connection_string: str = None):
        self.connection_string = connection_string
        self.connected = False
    
    def connect(self) -> bool:
        """Connect to the database. Will be implemented in the future."""
        # This is just a placeholder for future implementation
        self.connected = True
        return True
    
    def save(self, data: Any) -> bool:
        """Save data to the database. Will be implemented in the future."""
        # This is just a placeholder for future implementation
        if not self.connected:
            return False
        return True
    
    def close(self) -> None:
        """Close the database connection. Will be implemented in the future."""
        # This is just a placeholder for future implementation
        self.connected = False
