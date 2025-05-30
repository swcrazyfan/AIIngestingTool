"""
Progress tracking compatibility layer for the video ingest API.

This module provides a compatibility layer between the new Prefect-based
ingest system and the legacy progress tracking format expected by the
frontend extension.
"""

import asyncio
import time
from typing import Dict, Any, Optional, List
from uuid import UUID
import structlog

try:
    from prefect.client.orchestration import get_client
    from prefect.client.schemas.filters import FlowRunFilter, FlowRunFilterId
    from prefect.states import StateType
    PREFECT_AVAILABLE = True
except ImportError:
    PREFECT_AVAILABLE = False

logger = structlog.get_logger(__name__)


class ProgressTracker:
    """Tracks ingest progress and provides legacy-compatible progress updates."""
    
    def __init__(self, app=None, socketio=None):
        """Initialize the progress tracker.
        
        Args:
            app: Flask application instance
            socketio: Flask-SocketIO instance for emitting progress updates
        """
        self.app = app
        self.socketio = socketio
        self.active_ingests: Dict[str, Dict[str, Any]] = {}
    
    def start_tracking(self, flow_run_id: str, directory: str, total_files: int,
                      user_email: Optional[str] = None) -> None:
        """Start tracking progress for a new ingest.
        
        Args:
            flow_run_id: The Prefect flow run ID
            directory: Directory being ingested
            total_files: Total number of files to process
            user_email: Email of user who started the ingest
        """
        logger.info("Starting progress tracking", 
                   flow_run_id=flow_run_id, 
                   directory=directory, 
                   total_files=total_files)
        
        self.active_ingests[flow_run_id] = {
            'task_run_id': flow_run_id,
            'status': 'starting',
            'progress': 0,
            'message': f'Starting ingest for {directory}',
            'current_file': '',
            'error': None,
            'processed_count': 0,
            'results_count': 0,
            'failed_count': 0,
            'total_count': total_files,
            'total': total_files,
            'processed_files': [],
            'file_details': {},  # New: detailed per-file tracking
            'directory': directory,
            'user_email': user_email,
            'started_at': time.time()
        }
        
        logger.info("Progress tracking started", flow_run_id=flow_run_id)
    
    def update_file_step(self, flow_run_id: str, file_path: str, step_name: str,
                         step_progress: int = 0, step_status: str = "processing",
                         compression_update: Optional[Dict[str, Any]] = None) -> None:
        """Update the current step for a specific file.

        Args:
            flow_run_id: The Prefect flow run ID
            file_path: Full path to the file being processed
            step_name: Name of the current processing step
            step_progress: Progress percentage for this step (0-100)
            step_status: Status of this step (processing, completed, failed, skipped)
            compression_update: Optional dict with detailed compression progress
                                (total_frames, processed_frames, current_rate, speed, error_detail)
        """
        try:
            if flow_run_id not in self.active_ingests:
                logger.warning("Attempted to update file step for unknown flow run",
                             flow_run_id=flow_run_id)
                return

            import os
            file_name = os.path.basename(file_path)

            # Initialize file details if not exists
            if file_path not in self.active_ingests[flow_run_id]['file_details']:
                self.active_ingests[flow_run_id]['file_details'][file_path] = {
                    'file_name': file_name,
                    'file_path': file_path,
                    'current_step': '',
                    'step_progress': 0,
                    'status': 'pending',
                    'completed_steps': [],
                    'error': None,
                    'started_at': None,
                    'completed_at': None,
                    'compression_details': None # Initialize compression_details
                }

            # Update file details
            file_data = self.active_ingests[flow_run_id]['file_details'][file_path]
            logger.debug("Before update in update_file_step",
                         file_name=file_name,
                         incoming_step=step_name,
                         incoming_progress=step_progress,
                         incoming_status=step_status,
                         current_file_step=file_data.get('current_step'),
                         current_file_status=file_data.get('status'),
                         current_file_progress=file_data.get('step_progress'))

            is_currently_compressing = file_data.get('current_step') == "video_compression" and \
                                     file_data.get('status') == "processing"

            if step_name == "video_compression":
                # If it's a video_compression update, it always takes precedence for step/progress/status
                file_data['current_step'] = step_name
                file_data['step_progress'] = step_progress # This will be compression's own progress
                file_data['status'] = step_status
                logger.debug("Applied video_compression update", file_name=file_name, step=file_data['current_step'], progress=file_data['step_progress'], status=file_data['status'])
            elif is_currently_compressing:
                # If currently compressing and a *different* step update comes in:
                logger.debug(f"File {file_name} is in active video_compression (step: {file_data.get('current_step')}, status: {file_data.get('status')}). Incoming non-compression step '{step_name}' (status: {step_status}).")
                # - Don't change current_step (stays "video_compression")
                # - Don't change step_progress (stays compression's progress)
                # - Only update overall file status if the incoming step *failed*.
                if step_status == "failed" and file_data['status'] != "failed": # Avoid multiple failed states if already failed
                    logger.warning(f"Concurrent step '{step_name}' failed for {file_name} during video compression. Marking file as failed.")
                    file_data['status'] = "failed"
                    file_data['error'] = file_data.get('error', '') + f" | Concurrent step '{step_name}' failed."
                # else, keep current 'processing' status for video_compression
            else:
                # Not currently compressing, or the incoming step is not "video_compression"
                # and compression is not active: update normally.
                file_data['current_step'] = step_name
                file_data['step_progress'] = step_progress
                file_data['status'] = step_status
                logger.debug("Applied normal update", file_name=file_name, step=file_data['current_step'], progress=file_data['step_progress'], status=file_data['status'])


            # Handle compression-specific updates (this should now only effectively run if step_name IS "video_compression")
            if step_name == "video_compression" and compression_update:
                if file_data['compression_details'] is None:
                    file_data['compression_details'] = {}
                
                for key in ['total_frames', 'processed_frames', 'current_rate', 'speed', 'error_detail']:
                    if key in compression_update:
                        file_data['compression_details'][key] = compression_update[key]

                # Calculate ETR
                cd = file_data['compression_details']
                if cd.get('current_rate', 0) > 0 and cd.get('total_frames', 0) > 0:
                    remaining_frames = cd['total_frames'] - cd.get('processed_frames', 0)
                    if remaining_frames > 0:
                        cd['etr_seconds'] = remaining_frames / cd['current_rate']
                    else:
                        cd['etr_seconds'] = 0
                else:
                    cd['etr_seconds'] = None # Cannot calculate ETR

            # Track when file processing starts
            if file_data['started_at'] is None and step_status == "processing":
                file_data['started_at'] = time.time()

            # Mark step as completed if status indicates completion
            if step_status in ["completed", "skipped"] and step_name not in file_data['completed_steps']:
                file_data['completed_steps'].append(step_name)

            # Mark file as completed when it reaches final status
            if step_status in ["completed", "failed", "skipped"] and file_data['completed_at'] is None:
                file_data['completed_at'] = time.time()

            # Update overall progress based on file statuses
            self._update_overall_progress(flow_run_id)

            logger.debug("File step updated",
                        flow_run_id=flow_run_id,
                        file_name=file_name,
                        step=step_name,
                        progress=step_progress,
                        status=step_status,
                        compression_update=compression_update)

            # Emit WebSocket update
            if self.socketio and self.app: # Ensure both app and socketio are available
                try:
                    # Ensure Flask app context for the emit, especially if called from background threads
                    with self.app.app_context():
                        formatted_data = self._format_progress_response(self.active_ingests[flow_run_id])
                        self.socketio.emit('ingest_progress_update', formatted_data)
                except Exception as e:
                    logger.warning("Failed to emit WebSocket update", error=str(e), exc_info=True)
            elif not self.app:
                logger.warning("ProgressTracker: Flask app instance not available, cannot emit WebSocket update with app_context.")
            elif not self.socketio:
                logger.debug("ProgressTracker: SocketIO instance not available, skipping WebSocket update.")


        except Exception as e:
            logger.error("Error updating file step", error=str(e),
                        flow_run_id=flow_run_id, file_path=file_path)
    
    def _update_overall_progress(self, flow_run_id: str) -> None:
        """Update overall progress based on individual file progress.
        
        Args:
            flow_run_id: The Prefect flow run ID
        """
        try:
            ingest = self.active_ingests[flow_run_id]
            file_details = ingest['file_details']
            
            if not file_details:
                return
            
            total_files = len(file_details)
            completed_files = 0
            failed_files = 0
            overall_progress = 0
            
            for file_info in file_details.values():
                if file_info['status'] == 'completed':
                    completed_files += 1
                    overall_progress += 100
                elif file_info['status'] == 'failed':
                    failed_files += 1
                    overall_progress += 100  # Failed files are "done" for progress calc
                elif file_info['status'] == 'skipped':
                    completed_files += 1  # Skipped files count as completed
                    overall_progress += 100
                elif file_info['status'] == 'processing':
                    # Add partial progress for files currently being processed
                    overall_progress += file_info.get('step_progress', 0)
            
            # Calculate overall percentage
            if total_files > 0:
                ingest['progress'] = int(overall_progress / total_files)
            else:
                ingest['progress'] = 0
            
            # Update counts
            ingest['processed_count'] = completed_files
            ingest['failed_count'] = failed_files
            ingest['results_count'] = completed_files  # For compatibility
            
            # Update status based on progress
            if completed_files + failed_files == total_files:
                ingest['status'] = 'completed'
                ingest['message'] = f'Completed: {completed_files} successful, {failed_files} failed'
            elif completed_files + failed_files > 0:
                ingest['status'] = 'processing'
                ingest['message'] = f'Processing: {completed_files + failed_files}/{total_files} files processed'
            else:
                ingest['status'] = 'processing'
                ingest['message'] = f'Processing {total_files} files...'
                
        except Exception as e:
            logger.error("Error updating overall progress", error=str(e), flow_run_id=flow_run_id)

    def get_progress(self, flow_run_id: Optional[str] = None) -> Dict[str, Any]:
        """Get progress for a specific flow run or the most recent one.
        
        Args:
            flow_run_id: Optional flow run ID to get progress for
            
        Returns:
            Progress dictionary in legacy format with detailed file information
        """
        try:
            if flow_run_id and flow_run_id in self.active_ingests:
                logger.debug("Returning progress for specific flow run", flow_run_id=flow_run_id)
                return self._format_progress_response(self.active_ingests[flow_run_id])
            
            # Get most recent active ingest
            if self.active_ingests:
                # Sort by started_at descending
                sorted_ingests = sorted(
                    self.active_ingests.items(),
                    key=lambda x: x[1].get('started_at', 0),
                    reverse=True
                )
                
                # Find first non-completed ingest
                for ingest_id, progress in sorted_ingests:
                    if progress['status'] not in ['completed', 'failed', 'cancelled']:
                        logger.debug("Returning progress for active ingest", ingest_id=ingest_id)
                        return self._format_progress_response(progress)
                
                # If all are completed, return the most recent one
                if sorted_ingests:
                    logger.debug("Returning progress for most recent completed ingest")
                    return self._format_progress_response(sorted_ingests[0][1])
            
            # No active ingests - return idle status
            logger.debug("No active ingests, returning idle status")
            return self._format_progress_response({
                'status': 'idle',
                'progress': 0,
                'message': 'No active ingest process',
                'current_file': '',
                'processed_count': 0,
                'failed_count': 0,
                'total_count': 0,
                'processed_files': [],
                'file_details': {}
            })
            
        except Exception as e:
            logger.error("Error getting progress", error=str(e), flow_run_id=flow_run_id)
            # Return safe fallback
            return self._format_progress_response({
                'status': 'idle',
                'progress': 0,
                'message': 'Error retrieving progress',
                'current_file': '',
                'processed_count': 0,
                'failed_count': 0,
                'total_count': 0,
                'processed_files': [],
                'file_details': {}
            })
    
    def _format_progress_response(self, progress_data: Dict[str, Any]) -> Dict[str, Any]:
        """Format progress data to match the IngestProgress interface with detailed file tracking.
        
        Args:
            progress_data: Raw progress data
            
        Returns:
            Formatted progress data with per-file step details compatible with IngestPanel.tsx
        """
        # Ensure all required fields are present
        formatted = {
            'status': progress_data.get('status', 'idle'),
            'progress': progress_data.get('progress', 0),
            'message': progress_data.get('message', ''),
            'current_file': progress_data.get('current_file', ''),
            'error': progress_data.get('error'),
            'processed_count': progress_data.get('processed_count', 0),
            'results_count': progress_data.get('results_count', 0),
            'failed_count': progress_data.get('failed_count', 0),
            'total_count': progress_data.get('total_count', 0),
            'total': progress_data.get('total_count', 0),  # Legacy compatibility
        }
        
        # Convert file_details to processed_files array for IngestPanel.tsx compatibility
        file_details = progress_data.get('file_details', {})
        processed_files = []
        
        for file_path, file_info in file_details.items():
            processed_file = {
                'file_name': file_info.get('file_name', ''),
                'path': file_path,
                'current_step': file_info.get('current_step', ''),
                'progress_percentage': file_info.get('step_progress', 0),  # Map step_progress to progress_percentage
                'status': file_info.get('status', ''),
                'started_at': file_info.get('started_at'),
                'completed_at': file_info.get('completed_at'),
                'completed_steps': file_info.get('completed_steps', []),
                'error': file_info.get('error'),
            }
            
            # Safely add compression details if available
            compression_details = file_info.get('compression_details') # This might be None
            if isinstance(compression_details, dict):
                processed_file.update({
                    'compression_total_frames': compression_details.get('total_frames'),
                    'compression_processed_frames': compression_details.get('processed_frames'),
                    'compression_current_rate': compression_details.get('current_rate'),
                    'compression_etr_seconds': compression_details.get('etr_seconds'),
                    'compression_speed': compression_details.get('speed'),
                    'compression_error_detail': compression_details.get('error_detail')
                })
            else: # Ensure keys exist even if None, for frontend type consistency
                processed_file.update({
                    'compression_total_frames': None,
                    'compression_processed_frames': None,
                    'compression_current_rate': None,
                    'compression_etr_seconds': None,
                    'compression_speed': None,
                    'compression_error_detail': None
                })
            processed_files.append(processed_file)
        
        # Sort files by status (processing first, then completed/failed)
        def sort_key(f):
            status_priority = {'processing': 0, 'completed': 1, 'failed': 2, 'skipped': 3}
            return status_priority.get(f['status'], 4)
        
        processed_files.sort(key=sort_key)
        formatted['processed_files'] = processed_files
        
        # Keep file_details for backward compatibility if needed
        formatted['file_details'] = file_details
        
        return formatted
    
    def update_progress(self, flow_run_id: str, updates: Dict[str, Any]) -> None:
        """Manually update progress for a flow run.
        
        Args:
            flow_run_id: The flow run ID
            updates: Dictionary of fields to update
        """
        try:
            if flow_run_id in self.active_ingests:
                self.active_ingests[flow_run_id].update(updates)
                logger.debug("Progress updated", flow_run_id=flow_run_id, updates=updates)
                
                # Emit WebSocket update
                if self.socketio:
                    try:
                        formatted_data = self._format_progress_response(self.active_ingests[flow_run_id])
                        self.socketio.emit('ingest_progress_update', formatted_data)
                    except Exception as e:
                        logger.warning("Failed to emit WebSocket update", error=str(e))
            else:
                logger.warning("Attempted to update progress for unknown flow run", 
                             flow_run_id=flow_run_id)
                             
        except Exception as e:
            logger.error("Error updating progress", error=str(e), flow_run_id=flow_run_id)
    
    def stop_tracking(self, flow_run_id: str) -> None:
        """Stop tracking progress for a flow run.
        
        Args:
            flow_run_id: The flow run ID
        """
        try:
            if flow_run_id in self.active_ingests:
                # Mark as completed/cancelled if still processing
                if self.active_ingests[flow_run_id]['status'] in ['starting', 'processing', 'scanning']:
                    self.active_ingests[flow_run_id]['status'] = 'cancelled'
                    self.active_ingests[flow_run_id]['message'] = 'Tracking stopped'
                
                logger.info("Stopped tracking progress", flow_run_id=flow_run_id)
                
                # Keep the record for a bit longer for final status checks
                # Remove after 60 seconds
                def delayed_cleanup():
                    time.sleep(60)
                    if flow_run_id in self.active_ingests:
                        del self.active_ingests[flow_run_id]
                        logger.debug("Cleaned up tracking record", flow_run_id=flow_run_id)
                
                import threading
                cleanup_thread = threading.Thread(target=delayed_cleanup)
                cleanup_thread.daemon = True
                cleanup_thread.start()
            else:
                logger.warning("Attempted to stop tracking for unknown flow run", 
                             flow_run_id=flow_run_id)
                             
        except Exception as e:
            logger.error("Error stopping progress tracking", error=str(e), flow_run_id=flow_run_id)


# Global progress tracker instance
_progress_tracker = None


def get_progress_tracker(app=None, socketio=None) -> ProgressTracker:
    """Get or create the global progress tracker instance.
    
    Args:
        app: Flask application instance (only needed on first call or if updating)
        socketio: Flask-SocketIO instance (only needed on first call or if updating)
        
    Returns:
        The global ProgressTracker instance
    """
    global _progress_tracker
    try:
        if _progress_tracker is None:
            _progress_tracker = ProgressTracker(app=app, socketio=socketio)
            logger.info("Created new progress tracker instance")
        else:
            if app and not _progress_tracker.app:
                _progress_tracker.app = app
                logger.info("Updated progress tracker with Flask app instance")
            if socketio and not _progress_tracker.socketio:
                _progress_tracker.socketio = socketio
                logger.info("Updated progress tracker with socketio instance")
        
        return _progress_tracker
        
    except Exception as e:
        logger.error("Error creating/getting progress tracker", error=str(e), exc_info=True)
        # Return a fallback instance
        return ProgressTracker(app=app, socketio=socketio)