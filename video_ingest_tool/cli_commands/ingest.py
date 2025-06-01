"""
Ingest command class for API-friendly ingest operations.

This module provides the IngestCommand class that wraps the video ingest
functionality in a standardized command interface for use by both
CLI and API.
"""

import os
import uuid
import time
import threading
from typing import Dict, Any, Optional, List
import structlog

from . import BaseCommand
from ..discovery import scan_directory
from ..config.settings import get_default_pipeline_config
from ..config import setup_logging
from ..video_processor import DEFAULT_COMPRESSION_CONFIG
from ..flows.prefect_flows import process_videos_batch_flow
# AuthManager removed as authentication is being phased out for local DuckDB
from ..api.progress_tracker import get_progress_tracker

logger = structlog.get_logger(__name__)


class IngestCommand(BaseCommand):
    """Command class for video ingest operations.
    
    Provides a standardized interface for ingest operations that can be
    used by both CLI and API endpoints.
    """
    
    def __init__(self):
        """Initialize IngestCommand."""
        self.current_job: Optional[Dict[str, Any]] = None
    
    def execute(self, **kwargs) -> Dict[str, Any]:
        """Execute ingest with dict args, return dict result.
        
        Args:
            **kwargs: Ingest parameters including:
                - directory: Directory to scan for video files (required)
                - action: Ingest action ('start', 'stop', 'status', 'reset')
                - recursive: Whether to scan subdirectories (default: True)
                - limit: Maximum number of files to process (default: 0 = no limit)
                - output_dir: Base output directory (default: 'output')
                - store_database: Store results in database (default: False)
                - generate_embeddings: Generate embeddings (default: False)
                - force_reprocess: Force reprocessing (default: False)
                - ai_analysis: Enable AI analysis (default: False)
                - compression_fps: Frame rate for compression
                - compression_bitrate: Bitrate for compression
                
        Returns:
            Dict containing the operation result
        """
        try:
            kwargs = self.validate_args(**kwargs)
            action = kwargs.get('action', 'start')
            
            if action == 'start':
                return self.start_ingest(**kwargs)
            elif action == 'stop':
                return self.stop_ingest()
            elif action == 'status':
                return self.get_status()
            elif action == 'reset':
                return self.reset()
            else:
                return {
                    "success": False,
                    "error": f"Unknown ingest action: {action}"
                }
                
        except Exception as e:
            logger.error(f"Ingest command failed: {str(e)}")
            return {
                "success": False,
                "error": f"Ingest error: {str(e)}"
            }
    
    def validate_args(self, **kwargs) -> Dict[str, Any]:
        """Validate and clean arguments for ingest operations.
        
        Args:
            **kwargs: Raw command arguments
            
        Returns:
            Dict containing validated arguments
            
        Raises:
            ValueError: If required arguments are missing or invalid
        """
        action = kwargs.get('action', 'start')
        
        if action == 'start':
            directory = kwargs.get('directory', '').strip()
            if not directory:
                raise ValueError("Directory is required for start action")
            
            if not os.path.exists(directory):
                raise ValueError(f"Directory not found: {directory}")
            
            if not os.path.isdir(directory):
                raise ValueError(f"Path is not a directory: {directory}")
        
        # Validate numeric parameters
        for param in ['limit', 'compression_fps']:
            if param in kwargs:
                if param == 'limit' and kwargs[param] is None: # Handle None for limit
                    kwargs[param] = 0 # Default to 0 (no limit)
                try:
                    kwargs[param] = int(kwargs[param])
                    if kwargs[param] < 0:
                        raise ValueError(f"{param} must be non-negative")
                except (ValueError, TypeError): # TypeError can happen if kwargs[param] was None and not handled
                    raise ValueError(f"{param} must be a non-negative integer")
        
        # Validate boolean parameters
        for param in ['recursive', 'store_database', 'generate_embeddings',
                      'force_reprocess', 'ai_analysis_enabled']: # Changed 'ai_analysis' to 'ai_analysis_enabled'
            if param in kwargs:
                if isinstance(kwargs[param], str):
                    kwargs[param] = kwargs[param].lower() in ['true', '1', 'yes', 'on']
        
        return kwargs
    
    def start_ingest(self, directory: str, recursive: bool = True, limit: int = 0,
                     output_dir: str = "output", database_storage: bool = False,
                     generate_embeddings: bool = False, force_reprocess: bool = False,
                     ai_analysis_enabled: bool = False,
                     compression_fps: int = DEFAULT_COMPRESSION_CONFIG['fps'],
                     compression_bitrate: str = DEFAULT_COMPRESSION_CONFIG['video_bitrate'],
                     task_to_run: Optional[str] = None, # Added task_to_run
                     **kwargs) -> Dict[str, Any]:
        """Start video ingest process.
        
        If task_to_run is specified, processes only the first found video file with that task
        and returns the resulting data dictionary. Otherwise, submits a Prefect flow for batch processing.
        """
        try:
            logger.info("Scanning directory for videos...", directory=directory, recursive=recursive, limit=limit)
            video_files = scan_directory(directory, recursive=recursive)

            if not video_files:
                logger.info("No video files found.", directory=directory)
                return {"success": True, "data": {"message": "No video files found to process", "status": "completed", "total_files": 0}}

            # Determine data_base_dir to use data/ directory for organized clip structure
            project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
            
            data_base_dir = os.path.join(project_root, "data")
            os.makedirs(data_base_dir, exist_ok=True)
            logger.info(f"Data will be stored in: {data_base_dir}")
            
            # Create the clips subdirectory structure
            clips_dir = os.path.join(data_base_dir, "clips")
            os.makedirs(clips_dir, exist_ok=True)

            pipeline_config = get_default_pipeline_config()
            if 'ai_video_analysis_step' in pipeline_config:
                pipeline_config['ai_video_analysis_step'] = ai_analysis_enabled
                if 'ai_thumbnail_selection_step' in pipeline_config:
                    pipeline_config['ai_thumbnail_selection_step'] = ai_analysis_enabled
                if 'video_compression_step' in pipeline_config:
                    pipeline_config['video_compression_step'] = ai_analysis_enabled
                    logger.info(f"Video compression step {'enabled' if ai_analysis_enabled else 'disabled'} based on AI analysis setting")
            if 'generate_embeddings_step' in pipeline_config:
                pipeline_config['generate_embeddings_step'] = generate_embeddings
            if 'database_storage_step' in pipeline_config:
                pipeline_config['database_storage_step'] = database_storage
            
            # Add other step configs based on CLI options if they exist in PIPELINE_STEP_DEFINITIONS
            # For example, if 'focal_length_detection' was a CLI option:
            if 'detect_focal_length_step' in pipeline_config and 'focal_length_detection' in kwargs:
                 pipeline_config['detect_focal_length_step'] = kwargs['focal_length_detection']
            if 'upload_thumbnails_step' in pipeline_config and 'upload_thumbnails' in kwargs:
                 pipeline_config['upload_thumbnails_step'] = kwargs['upload_thumbnails']


            logger.info(f"Effective pipeline_config for flow: {pipeline_config}")

            if task_to_run:
                logger.info(f"Preparing to execute single task '{task_to_run}' for the first video: {video_files[0]}")
                from prefect import flow as prefect_flow # Renamed to avoid conflict
                from ..flows.prefect_flows import process_video_file_task

                # Define a dynamic flow to run the single task
                @prefect_flow(name=f"dynamic_single_task_runner_{task_to_run.replace(' ', '_')}")
                def single_task_execution_flow(
                    p_file_path: str,
                    p_data_base_dir: str,  # Fixed parameter name
                    p_config: Dict[str, Any],
                    p_compression_fps: int,
                    p_compression_bitrate: str,
                    p_force_reprocess: bool,
                    p_task_to_run: str
                ):
                    logger.info(f"Dynamic flow executing process_video_file_task for '{p_task_to_run}' on {p_file_path}")
                    # Use a unique batch_uuid for this single run if needed by task internals
                    # or rely on process_video_file_task to handle it if task_to_run is set
                    dynamic_batch_uuid = str(uuid.uuid4())
                    return process_video_file_task(
                        file_path=p_file_path,
                        data_base_dir=p_data_base_dir,  # Fixed parameter name
                        config=p_config,
                        compression_fps=p_compression_fps,
                        compression_bitrate=p_compression_bitrate,
                        force_reprocess=p_force_reprocess,
                        batch_uuid=dynamic_batch_uuid, # Ensure a batch_uuid is passed
                        file_index=0, # For single file, index is 0
                        task_to_run=p_task_to_run
                    )

                # Execute the dynamic flow
                try:
                    # Prefect 3.x flows are called like regular Python functions
                    task_result_data = single_task_execution_flow(
                        p_file_path=video_files[0],
                        p_data_base_dir=data_base_dir,  # Fixed parameter name
                        p_config=pipeline_config,
                        p_compression_fps=compression_fps,
                        p_compression_bitrate=compression_bitrate,
                        p_force_reprocess=force_reprocess,
                        p_task_to_run=task_to_run
                    )
                    logger.info(f"Single task '{task_to_run}' flow completed. Result data keys: {list(task_result_data.keys() if isinstance(task_result_data, dict) else [])}")
                    return {
                        "success": True,
                        "data": task_result_data
                    }
                except Exception as flow_exc:
                    logger.error(f"Dynamic flow execution for task '{task_to_run}' failed: {flow_exc}", exc_info=True)
                    return {"success": False, "error": f"Dynamic flow execution failed: {flow_exc}"}
            else:
                # Full batch processing
                if limit > 0:
                    logger.info(f"Applying limit of {limit} to {len(video_files)} found files.")
                    video_files = video_files[:limit]
                
                if not video_files: # Re-check after limit for batch mode
                    logger.info("No video files remaining after limit for batch processing.")
                    return {"success": True, "data": {"message": "No video files found to process after limit", "status": "completed", "total_files": 0}}

                batch_uuid = str(uuid.uuid4())
                progress_tracker = get_progress_tracker()
                progress_tracker.start_tracking(
                    flow_run_id=batch_uuid,
                    directory=directory,
                    total_files=len(video_files)
                )
                logger.info("Progress tracking initialized for batch", batch_uuid=batch_uuid, total_files=len(video_files))
                logger.info(f"Submitting batch processing flow for {len(video_files)} files.")

                flow_result = process_videos_batch_flow(
                    file_list=video_files,
                    data_base_dir=data_base_dir,  # Fixed parameter name
                    config=pipeline_config,
                    compression_fps=compression_fps,
                    compression_bitrate=compression_bitrate,
                    force_reprocess=force_reprocess,
                    batch_uuid=batch_uuid,
                    # task_to_run will be None here for batch flow, handled by process_video_file_task's default
                )
                
                logger.info("Batch processing flow completed.")
                successful_count = sum(1 for result in flow_result if result is not None)
                failed_count = len(flow_result) - successful_count
                
                progress_tracker.update_progress(batch_uuid, {
                    'status': 'completed', 'progress': 100,
                    'message': f'Completed: {successful_count} successful, {failed_count} failed',
                    'processed_count': successful_count, 'failed_count': failed_count
                })
                
                return {
                    'success': True,
                    'data': {
                        'task_run_id': batch_uuid,
                        'message': f'Ingest completed: {successful_count} successful, {failed_count} failed out of {len(video_files)} files',
                        'status': 'completed',
                        'total_files': len(video_files),
                        'files_processed': successful_count,
                        'files_failed': failed_count,
                        'clips_dir': data_base_dir,  # Fixed to use data_base_dir value
                        'results': flow_result # Optionally include detailed results
                    }
                }
        except Exception as e:
            error_msg = f"Failed to start ingest: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {"success": False, "error": error_msg}
    
    def stop_ingest(self) -> Dict[str, Any]:
        """Stop current ingest process by cancelling the Prefect flow run.
        
        Returns:
            Dict with stop result
        """
        try:
            if not self.current_job or not self.current_job.get("task_run_id"):
                logger.warning("No active ingest process (or task_run_id) found to stop.")
                return {
                    "success": False,
                    "error": "No active ingest process with a trackable task_run_id to stop."
                }
            
            task_run_id_to_cancel = self.current_job["task_run_id"]
            logger.info(f"Attempting to cancel Prefect flow run: {task_run_id_to_cancel}")

            self.current_job['status'] = 'cancelling'
            self.current_job['message'] = f'Cancellation requested for flow run {task_run_id_to_cancel}.'
            
            logger.info(f"Cancellation request logged for flow run: {task_run_id_to_cancel}. Manual Prefect cancellation might be needed.")

            return {
                "success": True,
                "status": "cancelling",
                "message": f"Ingest process cancellation initiated for flow run {task_run_id_to_cancel}. Check Prefect Dashboard."
            }
            
        except Exception as e:
            logger.error(f"Failed to stop ingest: {str(e)}", exc_info=True)
            return {
                "success": False,
                "error": f"Failed to stop ingest: {str(e)}"
            }
    
    def get_status(self) -> Dict[str, Any]:
        """Get current ingest status.
        
        Returns:
            Dict with current status
        """
        if not self.current_job:
            return {
                "success": True,
                "status": "idle",
                "message": "No ingest job active"
            }
        
        return {
            "success": True,
            **self.current_job
        }
    
    def reset(self) -> Dict[str, Any]:
        """Reset ingest status.
        
        Returns:
            Dict with reset result
        """
        logger.info("Resetting ingest status.")
        previous_job_id = self.current_job.get("task_run_id") if self.current_job else None
        self.current_job = None
        return {
            "success": True, 
            "message": "Ingest status reset.",
            "previous_job_id": previous_job_id
        } 