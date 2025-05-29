"""
System command class for API-friendly system operations.

This module provides the SystemCommand class that handles system information
and utility operations like listing pipeline steps and checking progress.
"""

import requests
from typing import Dict, Any, Optional
import structlog

from . import BaseCommand
from ..config.settings import get_available_pipeline_steps

logger = structlog.get_logger(__name__)


class SystemCommand(BaseCommand):
    """Command class for system operations.
    
    Provides a standardized interface for system operations that can be
    used by both CLI and API endpoints.
    """
    
    def execute(self, action: str, **kwargs) -> Dict[str, Any]:
        """Execute system command with provided arguments.
        
        Args:
            action: The system action to perform (list_steps, check_progress)
            **kwargs: Additional arguments for the action
            
        Returns:
            Dict with command results
        """
        try:
            if action == "list_steps":
                return self._list_steps(**kwargs)
            elif action == "check_progress":
                return self._check_progress(**kwargs)
            else:
                return {
                    "success": False,
                    "error": f"Unknown system action: {action}"
                }
                
        except Exception as e:
            logger.error("System command failed", action=action, error=str(e))
            return {
                "success": False,
                "error": f"System command failed: {str(e)}"
            }
    
    def _list_steps(self, format_type: str = "table", **kwargs) -> Dict[str, Any]:
        """List all available pipeline steps.
        
        Args:
            format_type: Output format ('table', 'json', 'simple')
            **kwargs: Additional formatting options
            
        Returns:
            Dict with step information
        """
        try:
            steps = get_available_pipeline_steps()
            
            # Group steps by category for better organization
            categories = {}
            for step in steps:
                category = step['category']
                if category not in categories:
                    categories[category] = []
                categories[category].append(step)
            
            return {
                "success": True,
                "data": {
                    "steps": steps,
                    "categories": categories,
                    "total_steps": len(steps),
                    "format": format_type
                }
            }
            
        except Exception as e:
            logger.error("Failed to list steps", error=str(e))
            return {
                "success": False,
                "error": f"Failed to list steps: {str(e)}"
            }
    
    def _check_progress(self, task_run_id: Optional[str] = None, **kwargs) -> Dict[str, Any]:
        """Check ingest progress. 

        If task_run_id is provided, checks specific task (intended for internal server use by /api/progress/:id).
        If no task_run_id, returns a general status (intended for internal server use by /api/progress).
        The CLI client should use ingestApi.getProgress() for actual HTTP calls.
        
        Args:
            task_run_id: Optional ID of the specific task to check.
            **kwargs: Additional options (currently unused here for internal calls).
            
        Returns:
            Dict with progress information
        """
        try:
            if task_run_id:
                # This is where specific task lookup via Prefect client would happen.
                # For now, returning a placeholder as direct Prefect client integration
                # from within this command class for API server use is complex.
                # The API server's /api/progress/<task_run_id> route handles Prefect directly.
                logger.info("SystemCommand._check_progress called with task_run_id (should be handled by API route directly)", task_run_id=task_run_id)
                return {
                    "success": True,
                    "data": {
                        "task_run_id": task_run_id,
                        "status": "unknown_internal_call", 
                        "progress": 0,
                        "message": "Specific task status should be fetched by the API route directly using Prefect client."
                    }
                }
            else:
                # General progress check (e.g., when /api/progress is hit)
                # Return a default idle status. The client will use this to know no task is active.
                return {
                    "success": True,
                    "data": { # This structure should align with IngestProgress type
                        "status": "idle",
                        "progress": 0,
                        "total": 0,
                        "processed_count": 0,
                        "failed_count": 0,
                        "running_count": 0,
                        "current_file": "",
                        "message": "No active ingest process.",
                        "processed_files": [],
                        "per_file": [],
                        # task_run_id is omitted here as it's general progress
                    }
                }
                
        except Exception as e:
            logger.error("Failed to check progress internally", task_run_id=task_run_id, error=str(e))
            return {
                "success": False,
                "error": f"Failed to check progress internally: {str(e)}"
            } 