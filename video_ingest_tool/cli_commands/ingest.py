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
from ..auth import AuthManager
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
                try:
                    kwargs[param] = int(kwargs[param])
                    if kwargs[param] < 0:
                        raise ValueError(f"{param} must be non-negative")
                except (ValueError, TypeError):
                    raise ValueError(f"{param} must be a non-negative integer")
        
        # Validate boolean parameters
        for param in ['recursive', 'store_database', 'generate_embeddings', 
                      'force_reprocess', 'ai_analysis']:
            if param in kwargs:
                if isinstance(kwargs[param], str):
                    kwargs[param] = kwargs[param].lower() in ['true', '1', 'yes', 'on']
        
        return kwargs
    
    def start_ingest(self, directory: str, recursive: bool = True, limit: int = 0,
                     output_dir: str = "output", store_database: bool = False,
                     generate_embeddings: bool = False, force_reprocess: bool = False,
                     ai_analysis: bool = False, 
                     compression_fps: int = DEFAULT_COMPRESSION_CONFIG['fps'],
                     compression_bitrate: str = DEFAULT_COMPRESSION_CONFIG['video_bitrate'],
                     user_email: Optional[str] = None,
                     **kwargs) -> Dict[str, Any]:
        """Start video ingest process by submitting a Prefect flow.
        
        Args:
            directory: Directory to scan for video files
            recursive: Whether to scan subdirectories
            limit: Maximum number of files to process (0 = no limit)
            output_dir: Base output directory for processing results
            store_database: Store results in Supabase database
            generate_embeddings: Generate vector embeddings for search
            force_reprocess: Force reprocessing of existing files
            ai_analysis: Enable comprehensive AI analysis
            compression_fps: Frame rate for video compression
            compression_bitrate: Bitrate for video compression
            user_email: Email of the user initiating the ingest
            
        Returns:
            Dict with ingest start result, including task_run_id (flow_run_id)
        """
        try:
            # Validate authentication for database operations
            if store_database or generate_embeddings or ai_analysis:
                auth_manager = AuthManager()
                current_session = auth_manager.get_current_session()
                if not current_session:
                    logger.warning("Authentication required for database operations or AI analysis.", user_email=user_email)
                    return {
                        "success": False,
                        "error": "Authentication required for database operations or AI analysis."
                    }

            logger.info("Scanning directory for videos...", directory=directory, recursive=recursive, limit=limit)
            video_files = scan_directory(directory, recursive=recursive)

            if limit > 0:
                logger.info(f"Applying limit of {limit} to {len(video_files)} found files.")
                video_files = video_files[:limit]

            if not video_files:
                logger.info("No video files found or remaining after limit.", directory=directory, limit=limit)
                return {
                    "success": True, 
                    "data": {
                        "task_run_id": None, 
                        "message": "No video files found to process", 
                        "status": "completed", 
                        "total_files": 0
                    }
                }

            # Generate batch UUID for progress tracking coordination
            batch_uuid = str(uuid.uuid4())
            
            # Initialize progress tracking for this batch
            progress_tracker = get_progress_tracker()
            progress_tracker.start_tracking(
                flow_run_id=batch_uuid,
                directory=directory, 
                total_files=len(video_files),
                user_email=user_email
            )
            logger.info("Progress tracking initialized", batch_uuid=batch_uuid, total_files=len(video_files))

            pipeline_config = get_default_pipeline_config()
            
            # Apply user-selected options to pipeline_config steps
            # pipeline_config is a flat dictionary where keys are step names and values are booleans.
            if 'ai_video_analysis_step' in pipeline_config:
                pipeline_config['ai_video_analysis_step'] = ai_analysis
                # AI thumbnail selection is typically enabled together with AI analysis
                if 'ai_thumbnail_selection_step' in pipeline_config:
                    pipeline_config['ai_thumbnail_selection_step'] = ai_analysis
                # Video compression is primarily used for AI analysis, so disable it when AI analysis is disabled
                if 'video_compression_step' in pipeline_config:
                    pipeline_config['video_compression_step'] = ai_analysis
                    logger.info(f"Video compression step {'enabled' if ai_analysis else 'disabled'} based on AI analysis setting")
            else:
                logger.warning("'ai_video_analysis_step' not found in default pipeline_config. AI analysis option may not apply.")

            if 'embedding_generation_step' in pipeline_config:
                pipeline_config['embedding_generation_step'] = generate_embeddings
            else:
                logger.warning("'embedding_generation_step' not found in default pipeline_config. Embedding option may not apply.")

            if 'database_storage_step' in pipeline_config: 
                pipeline_config['database_storage_step'] = store_database
            else:
                logger.warning("'database_storage_step' not found in default pipeline_config. Database storage option may not apply.")

            # Prepare compression config
            current_compression_config = DEFAULT_COMPRESSION_CONFIG.copy()
            current_compression_config['fps'] = compression_fps
            current_compression_config['video_bitrate'] = compression_bitrate

            logger.info(f"Submitting video processing flow for {len(video_files)} files.")

            # Determine thumbnails_dir based on output_dir_base
            # output_dir_base is 'output_dir' argument to start_ingest
            thumbnails_dir = os.path.join(output_dir, "thumbnails")
            os.makedirs(thumbnails_dir, exist_ok=True)
            logger.info(f"Thumbnails will be stored in: {thumbnails_dir}")

            # In Prefect 3.x, flows are called directly like regular Python functions
            # The flow will be tracked by Prefect automatically when called
            logger.info(f"Starting video processing flow for {len(video_files)} files.")
            logger.info(f"Thumbnails will be stored in: {thumbnails_dir}")
            
            # Call the flow directly - Prefect 3.x handles all orchestration automatically
            # The flow uses .map() internally to process files in parallel
            # Pass the batch_uuid to coordinate with progress tracking
            flow_result = process_videos_batch_flow(
                file_list=video_files,
                thumbnails_dir=thumbnails_dir,
                config=pipeline_config,
                compression_fps=compression_fps,
                compression_bitrate=compression_bitrate,
                force_reprocess=force_reprocess,
                user_id=user_email,
                batch_uuid=batch_uuid  # Pass our batch_uuid for progress coordination
            )
            
            logger.info("Video processing flow completed successfully.")
            
            # Count successful results
            successful_count = sum(1 for result in flow_result if result is not None)
            failed_count = len(flow_result) - successful_count
            
            # Update final progress status
            progress_tracker.update_progress(batch_uuid, {
                'status': 'completed',
                'progress': 100,
                'message': f'Completed: {successful_count} successful, {failed_count} failed',
                'processed_count': successful_count,
                'failed_count': failed_count
            })
            
            # Return flow information for API compatibility
            return {
                'success': True,
                'data': {
                    'task_run_id': batch_uuid,  # Use batch_uuid as task_run_id for API tracking
                    'message': f'Ingest completed: {successful_count} successful, {failed_count} failed out of {len(video_files)} files',
                    'status': 'completed',  # Since Prefect 3.x runs synchronously
                    'total_files': len(video_files),
                    'files_processed': successful_count,
                    'files_failed': failed_count,
                    'thumbnails_dir': thumbnails_dir
                }
            }
            
        except Exception as e:
            error_msg = f"Failed to start ingest flow: {str(e)}"
            logger.error("Failed to execute ingest flow via Prefect.", error=str(e))
            return {
                "success": False,
                "error": error_msg
            }
    
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