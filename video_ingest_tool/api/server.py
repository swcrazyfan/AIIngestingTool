"""
Streamlined API server for video ingest tool.

This server provides a thin HTTP wrapper over the CLI command classes,
following Prefect best practices for task submission and progress tracking.
"""

import os
import time
import asyncio
from typing import Any, Dict, Literal, Optional
from uuid import UUID

from flask import Flask, request, jsonify, send_file, Response
from flask_cors import CORS
from flask_socketio import SocketIO, emit
import structlog

# Import command classes
# Imports moved inside functions to avoid circular import

# Import middleware
from .middleware import (
    # require_auth, # Removed
    handle_errors, validate_json_request,
    log_request, add_cors_headers, create_success_response, create_error_response
)

# Import progress tracker
from .progress_tracker import get_progress_tracker

# For Prefect integration (when available)
try:
    from prefect.client.orchestration import get_client
    from prefect.client.schemas.objects import TaskRun
    from prefect.client.schemas.filters import FlowRunFilter, FlowRunFilterId
    from prefect.states import StateType
    PREFECT_AVAILABLE = True
except ImportError:
    PREFECT_AVAILABLE = False

logger = structlog.get_logger(__name__)
Status = Literal["completed", "pending", "error", "running"]


def create_app(debug: bool = False) -> tuple[Flask, SocketIO]:
    """Create and configure the Flask application with SocketIO.
    
    Args:
        debug: Enable debug mode
        
    Returns:
        Tuple of (Flask app, SocketIO instance)
    """
    app = Flask(__name__)
    app.config['DEBUG'] = debug
    
    # Enable CORS for cross-origin requests
    CORS(app, 
         supports_credentials=True,
         origins=['http://localhost:3000', 'http://localhost:8080'],  # Extension origins
         allow_headers=['Content-Type', 'Authorization'])
    
    # Initialize SocketIO for real-time progress updates
    socketio = SocketIO(
        app, 
        cors_allowed_origins="*",
        async_mode='threading',
        logger=debug,
        engineio_logger=debug
    )
    
    # Initialize progress tracker with app and socketio
    progress_tracker = get_progress_tracker(app=app, socketio=socketio)
    
    # Add CORS headers to all responses
    @app.after_request
    def after_request(response):
        return add_cors_headers(response)
    
    # ========================================================================
    # HEALTH AND STATUS ENDPOINTS
    # ========================================================================
    
    @app.route('/api/health', methods=['GET'])
    @log_request()
    def health_check():
        """Health check endpoint for monitoring."""
        return jsonify(create_success_response({
            "status": "healthy",
            "version": "2.0.0",
            "prefect_available": PREFECT_AVAILABLE,
            "timestamp": time.time()
        }))
    
    @app.route('/api/status', methods=['GET'])
    @log_request()
    @handle_errors
    def system_status():
        """Get basic system status."""
        # AuthCommand removed, this can be simplified or use SystemCommand
        # For now, return a basic healthy status if this endpoint is reached.
        # Future: Could check DuckDB file presence or other local checks.
        return jsonify(create_success_response({
            "status": "api_running",
            "database_type": "duckdb_local",
            "message": "System is operational with local DuckDB backend."
        }))
    
    # ========================================================================
    # AUTHENTICATION ENDPOINTS (REMOVED)
    # ========================================================================
    # All /api/auth/* endpoints (login, signup, logout, status) are removed
    # as authentication is handled locally or not at all with DuckDB.
    # The @require_auth decorator is also removed from other endpoints.
    
    # ========================================================================
    # SEARCH ENDPOINTS (Multiple Results)
    # ========================================================================
    
    @app.route('/api/search', methods=['GET'])
    @log_request()
    # @require_auth # Removed
    @handle_errors
    def search_query():
        """Search videos by query text."""
        query = request.args.get('q', '').strip()
        if not query:
            return create_error_response("Query parameter 'q' is required", 
                                       'MISSING_QUERY', 400)
        
        search_type = request.args.get('type', 'all')
        limit = request.args.get('limit', 10, type=int)
        semantic_weight = request.args.get('semantic_weight', 0.7, type=float)
        keyword_weight = request.args.get('keyword_weight', 0.3, type=float)
        
        from ..cli_commands import SearchCommand
        cmd = SearchCommand()
        result = cmd.execute(
            action='search',
            query=query,
            search_type=search_type,
            limit=limit,
            semantic_weight=semantic_weight,
            keyword_weight=keyword_weight
        )
        
        if result.get('success'):
            # Standardize response structure for RESTful consistency
            search_data = result.get('data', {})
            standardized_response = {
                "data": search_data.get('results', []),  # Move results to data array
                "pagination": {
                    "limit": limit,
                    "offset": 0,  # Search doesn't use offset, but keeping consistent structure
                    "total": search_data.get('total', len(search_data.get('results', [])))
                },
                "query": search_data.get('query', query),
                "search_type": search_data.get('search_type', search_type),
                "match_count": search_data.get('match_count', len(search_data.get('results', [])))
            }
            return jsonify(create_success_response(standardized_response))
        else:
            return create_error_response(result.get('error', 'Search failed'), 
                                       'SEARCH_ERROR', 500)
    
    @app.route('/api/search/similar', methods=['GET'])
    @log_request()
    # @require_auth # Removed
    @handle_errors
    def search_similar():
        """Find videos similar to a specific clip."""
        clip_id = request.args.get('clip_id', '').strip()
        if not clip_id:
            return create_error_response("Query parameter 'clip_id' is required", 
                                       'MISSING_CLIP_ID', 400)
        
        limit = request.args.get('limit', 10, type=int)
        similarity_threshold = request.args.get('similarity_threshold', type=float)
        mode = request.args.get('mode', 'combined').lower()
        
        # Validate mode parameter
        valid_modes = ['text', 'visual', 'combined']
        if mode not in valid_modes:
            return create_error_response(f"Invalid mode '{mode}'. Must be one of: {', '.join(valid_modes)}", 
                                       'INVALID_MODE', 400)
        
        from ..cli_commands import SearchCommand
        cmd = SearchCommand()
        result = cmd.execute(
            action='similar', 
            clip_id=clip_id, 
            limit=limit,
            similarity_threshold=similarity_threshold,
            mode=mode
        )
        
        if result.get('success'):
            # Standardize response structure for RESTful consistency
            similar_data = result.get('data', {})
            standardized_response = {
                "data": similar_data.get('results', []),  # Move results to data array
                "pagination": {
                    "limit": limit,
                    "offset": 0,
                    "total": similar_data.get('total', len(similar_data.get('results', [])))
                },
                "clip_id": clip_id,
                "mode": mode,
                "similarity_threshold": similarity_threshold,
                "match_count": similar_data.get('match_count', len(similar_data.get('results', [])))
            }
            return jsonify(create_success_response(standardized_response))
        else:
            return create_error_response(result.get('error', 'Similar search failed'), 
                                       'SIMILAR_SEARCH_ERROR', 500)
    
    # /api/search/stats endpoint removed as 'stats' action was removed from SearchCommand
    
    # ========================================================================
    # CLIPS ENDPOINTS (RESTful: list, details, transcript, analysis)
    # ========================================================================

    @app.route('/api/clips', methods=['GET'])
    @log_request()
    # @require_auth # Removed
    @handle_errors
    def list_clips():
        """List all clips with filtering, sorting, and pagination using ClipsCommand."""
        # Query params
        sort_by = request.args.get('sort_by', 'created_at') # Default to created_at as per ClipsCommand
        sort_order_param = request.args.get('sort_order', 'desc').lower() # Default to desc
        if sort_order_param not in ['asc', 'desc']:
            return create_error_response("Invalid sort_order. Must be 'asc' or 'desc'.", "INVALID_INPUT", 400)
        
        limit = request.args.get('limit', 20, type=int)
        if limit < 0:
            return create_error_response("Limit must be a non-negative integer.", "INVALID_INPUT", 400)
            
        offset = request.args.get('offset', 0, type=int)
        if offset < 0:
            return create_error_response("Offset must be a non-negative integer.", "INVALID_INPUT", 400)

        filters_json_str = request.args.get('filters', None)
        parsed_filters = None
        if filters_json_str:
            try:
                import json # Ensure json is imported
                parsed_filters = json.loads(filters_json_str)
                if not isinstance(parsed_filters, dict):
                    raise ValueError("Filters parameter must be a JSON object.")
            except (json.JSONDecodeError, ValueError) as e:
                logger.warning(f"Invalid filters JSON string provided: {filters_json_str}", error=str(e))
                return create_error_response(f"Invalid 'filters' format: {str(e)} Must be a valid JSON object string.",
                                           'INVALID_FILTERS', 400)
        
        from ..cli_commands import ClipsCommand # Use ClipsCommand for listing
        cmd = ClipsCommand()
        
        # Call the 'list' action of ClipsCommand
        result = cmd.execute(
            action='list',
            sort_by=sort_by,
            sort_order=sort_order_param, # Use validated sort_order
            limit=limit,
            offset=offset,
            filters=parsed_filters # Pass the parsed dictionary
        )
        
        if result.get('success'):
            # Standardize response structure for RESTful consistency
            clips_data = result.get('data', {})
            standardized_response = {
                "data": clips_data.get('clips', []),  # Move clips to data array
                "pagination": {
                    "limit": clips_data.get('limit', limit),
                    "offset": clips_data.get('offset', offset),
                    "total": len(clips_data.get('clips', []))  # Add total count
                },
                "filters": clips_data.get('filters')
            }
            return jsonify(create_success_response(standardized_response))
        else:
            return create_error_response(result.get('error', 'Failed to list clips'),
                                       'CLIPS_LIST_ERROR', 500)

    @app.route('/api/clips/<clip_id>', methods=['GET'])
    @log_request()
    # @require_auth # Removed
    @handle_errors
    def get_clip_details_rest(clip_id: str):
        """Get detailed information about a specific clip."""
        # Optionally allow ?include=transcript,analysis
        include = request.args.get('include', '')
        show_transcript = 'transcript' in include.split(',')
        show_analysis = 'analysis' in include.split(',')
        from ..cli_commands import ClipsCommand
        cmd = ClipsCommand()
        result = cmd.execute(action='show', clip_id=clip_id, show_transcript=show_transcript, show_analysis=show_analysis)
        if result.get('success'):
            # Return the clip data directly (RESTful: individual resource without wrapper)
            clip_data = result.get('data', {}).get('clip', {})
            return jsonify(create_success_response(clip_data))
        else:
            return create_error_response(result.get('error', 'Clip not found'), 'CLIP_NOT_FOUND', 404)

    @app.route('/api/clips/<clip_id>', methods=['DELETE'])
    @log_request()
    # @require_auth # Removed
    @handle_errors
    def delete_clip_rest(clip_id: str):
        """Delete a specific clip."""
        from ..cli_commands import ClipsCommand
        cmd = ClipsCommand()
        
        # API calls always confirm deletion (confirmation handled by frontend)
        result = cmd.execute(action='delete', clip_id=clip_id, confirm=True)
        
        if result.get('success'):
            data = result.get('data', {})
            message = result.get('message', 'Clip deleted successfully')
            logger.info(f"Clip deleted via API: {clip_id}", 
                       file_name=data.get('file_name'))
            
            return jsonify(create_success_response({
                "deleted_clip_id": clip_id,
                "file_name": data.get('file_name'),
                "message": message
            }))
        else:
            error_msg = result.get('error', 'Failed to delete clip')
            status_code = 404 if 'not found' in error_msg.lower() else 500
            error_code = 'CLIP_NOT_FOUND' if status_code == 404 else 'DELETE_ERROR'
            
            return create_error_response(error_msg, error_code, status_code)

    # /api/clips/<clip_id>/transcript endpoint removed (data consolidated)
    # /api/clips/<clip_id>/analysis endpoint removed (data consolidated)
    
    # ========================================================================
    # INGEST ENDPOINTS (Following Prefect Best Practices)
    # ========================================================================
    
    @app.route('/api/ingest', methods=['POST'])
    @log_request()
    # @require_auth # Removed
    @handle_errors
    @validate_json_request(['directory'])
    def start_ingest():
        """Start video ingest process for a directory."""
        data = request.get_json()
        directory = data.get('directory')
        # user_email = getattr(request, 'user_email', 'unknown_user') # Removed user_email

        # Extract options from the top level of the request
        # These correspond to IngestCommand.start_ingest parameters
        options = {
            'recursive': data.get('recursive', True),
            'limit': data.get('limit', 0),
            'output_dir': data.get('output_dir', 'output'),
            'database_storage': data.get('store_database', False),
            'generate_embeddings': data.get('generate_embeddings', False),
            'force_reprocess': data.get('force_reprocess', False),
            'ai_analysis_enabled': data.get('ai_analysis', False),
            'compression_fps': data.get('compression_fps', 30),
            'compression_bitrate': data.get('compression_bitrate', '1000k')
        }

        logger.info(f"Ingest request received by /api/ingest", directory=directory, options=options)

        from ..cli_commands import IngestCommand
        cmd = IngestCommand()
        result = cmd.execute(
            action='start',
            directory=directory,
            # user_email=user_email, # Removed user_email
            **options
        )
        logger.info("IngestCommand result in /api/ingest", raw_result=result)
        
        if result.get('success') and result.get('data', {}).get('task_run_id'):
            task_run_id = result['data']['task_run_id']
            total_files = result['data'].get('total_files', 0)
            logger.info(f"Ingest flow submitted successfully via /api/ingest",
                       task_run_id=task_run_id, directory=directory, total_files=total_files)
            
            # Start tracking progress
            progress_tracker.start_tracking(
                flow_run_id=task_run_id,
                directory=directory,
                total_files=total_files
                # user_email=user_email # Removed user_email
            )
            
            response_data = create_success_response(result['data'], f"Ingest process started for {directory}")
            logger.info("Response from /api/ingest", response_payload=result['data'])
            return response_data
        elif result.get('success'): 
            logger.warning("Ingest command succeeded but no task_run_id returned from IngestCommand", result_data=result.get('data'))
            return create_error_response("Ingest started but failed to get task ID for tracking.", "INGEST_ERROR", 500)
        else:
            logger.error(f"Ingest command failed in IngestCommand", directory=directory, error=result.get('error'))
            return create_error_response(result.get('error', 'Failed to start ingest'), 
                                       'INGEST_ERROR', 500)
    
    # ========================================================================
    # PROGRESS ENDPOINTS (REST API Fallback for WebSocket)
    # ========================================================================
    
    @app.route('/api/progress/<task_run_id>', methods=['GET'])
    @log_request()
    # @require_auth # Removed
    @handle_errors
    async def get_task_progress(task_run_id: str):
        """Get progress of a specific ingest task (flow run)."""
        if not PREFECT_AVAILABLE:
            return create_error_response("Prefect is not available on the server.", "PREFECT_UNAVAILABLE", 503)

        try:
            task_run_uuid = UUID(task_run_id)
        except ValueError:
            return create_error_response("Invalid task_run_id format.", "INVALID_INPUT", 400)

        async with get_client() as client:
            try:
                flow_run = await client.read_flow_run(task_run_uuid)
                
                if not flow_run:
                    logger.warning("Flow run not found", task_run_id=task_run_id)
                    return create_error_response("Flow run not found", "NOT_FOUND", 404)

                per_file_progress = []
                completed_tasks = 0
                failed_tasks = 0
                running_tasks = 0
                total_tasks = 0
                current_overall_file = "" # To show what's being processed overall for the flow

                if flow_run:
                    # Attempt to get the original file_list from parameters for total count
                    original_file_list = flow_run.parameters.get('file_list', [])
                    total_tasks = len(original_file_list) if original_file_list else 0 # Fallback to 0

                    # Fetch sub-task runs for this flow run
                    # This assumes individual file processing steps are direct task runs under the main flow.
                    # If you have nested flows, this query might need adjustment.
                    flow_run_id_filter = FlowRunFilterId(any_=[flow_run.id]) # Corrected
                    current_flow_run_filter = FlowRunFilter(id=flow_run_id_filter) # Corrected
                    sub_task_runs = await client.read_task_runs( # Corrected
                        flow_run_filter=current_flow_run_filter # Corrected
                    )

                    logger.info(f"Fetched {len(sub_task_runs)} sub-task runs for flow_run_id {flow_run.id}")
                    
                    # This maps original file paths to their latest known state and individual task states
                    latest_task_states: Dict[str, Dict[str, str]] = {} # file_name -> {task_type: state}


                    for task_run_item in sub_task_runs:
                        base_name = None  # Initialize base_name for each task run item

                        # Try to extract file name from task_run_item.name
                        if task_run_item.name:
                            parts = task_run_item.name.split('|')
                            if len(parts) > 1:
                                name_part = parts[1].strip()
                                # Further clean up if there's a suffix like " - sub_task" or just a run index
                                parsed_name_from_task = name_part.split(' - ')[0].strip()
                                if parsed_name_from_task: # Ensure we got something
                                    base_name = parsed_name_from_task
                        
                        # Determine the type of task (e.g., 'metadata_extraction_step', 'transcription_step')
                        task_name_for_display = task_run_item.task_key.split('-')[0] #  e.g. 'metadata_extraction_step-abcdef' -> 'metadata_extraction_step'
                        
                        current_state_type = task_run_item.state.type if task_run_item.state else StateType.PENDING
                        current_status_str: Status = "pending"

                        if current_state_type == StateType.COMPLETED:
                            completed_tasks += 1
                            current_status_str = "completed"
                        elif current_state_type == StateType.RUNNING:
                            running_tasks += 1
                            current_status_str = "running"
                            if base_name and not current_overall_file: 
                               current_overall_file = base_name
                            elif not base_name and not current_overall_file: 
                                current_overall_file = task_name_for_display
                        elif current_state_type == StateType.FAILED:
                            failed_tasks += 1
                            current_status_str = "error"
                        
                        if base_name:
                            if base_name not in latest_task_states:
                                latest_task_states[base_name] = {}
                            # Store/update the state for this specific sub-task (e.g., 'video_compression_step') for this file
                            # To ensure we have the LATEST state if a sub-task runs multiple times (e.g. retries),
                            # we'd ideally check timestamps. For now, this overwrites, implicitly taking the last seen.
                            latest_task_states[base_name][task_name_for_display] = current_status_str
                        else:
                            logger.debug(
                                "Could not determine base_name for sub-task, will not be included in per-file progress detail.", 
                                task_run_id=task_run_item.id, 
                                task_name=task_run_item.name,
                                task_key=task_run_item.task_key
                            )
                        
                        # Update overall counts based on task state (applies to all sub_task_runs)
                        # THIS BLOCK WAS THE SOURCE OF DOUBLE COUNTING - IT'S HANDLED ABOVE NOW.
                        # if current_state_type == StateType.COMPLETED:
                        #     completed_tasks += 1
                        # elif current_state_type == StateType.RUNNING:
                        #     running_tasks += 1
                        #     if base_name and not current_overall_file: 
                        #        current_overall_file = base_name
                        #     elif not base_name and not current_overall_file: 
                        #         current_overall_file = task_name_for_display
                        # elif current_state_type == StateType.FAILED:
                        #     failed_tasks += 1
                    
                    # Construct per_file_progress from the aggregated latest_task_states
                    processed_files_for_overall_status = set() # To count unique files processed for overall %

                    for file_name, tasks_dict in latest_task_states.items():
                        file_completed_count = sum(1 for state in tasks_dict.values() if state == 'completed')
                        file_running_count = sum(1 for state in tasks_dict.values() if state == 'running')
                        file_failed_count = sum(1 for state in tasks_dict.values() if state == 'failed')
                        # total_tasks_for_this_file should ideally be known from the flow definition for this file type
                        # For now, using the number of task types we found for this file.
                        total_tasks_for_this_file = len(tasks_dict) 

                        file_status_str: Status = "pending"
                        if file_failed_count > 0:
                            file_status_str = "error"
                            processed_files_for_overall_status.add(file_name)
                        elif file_running_count > 0:
                            file_status_str = "running"
                            current_overall_file = file_name # Update current_overall_file if this one is running
                            processed_files_for_overall_status.add(file_name)
                        elif file_completed_count == total_tasks_for_this_file and total_tasks_for_this_file > 0:
                            file_status_str = "completed"
                            processed_files_for_overall_status.add(file_name)
                        elif total_tasks_for_this_file == 0: # Should not happen if base_name was added to latest_task_states
                            file_status_str = "pending"
                        
                        # If still pending but some tasks completed, it implies it's partially running or starting
                        if file_status_str == "pending" and file_completed_count > 0 and file_completed_count < total_tasks_for_this_file:
                             file_status_str = "running" # Or "in_progress"
                             processed_files_for_overall_status.add(file_name)


                        per_file_progress.append({
                            "file_name": file_name,
                            "status": file_status_str,
                            "progress": (file_completed_count / total_tasks_for_this_file * 100) if total_tasks_for_this_file > 0 else 0,
                            "total_sub_tasks": total_tasks_for_this_file,
                            "completed_sub_tasks": file_completed_count,
                            "details": tasks_dict # Dictionary of {task_type: state} for this file
                        })

                    # total_tasks was based on original_file_list. If that's empty, use number of files we found tasks for.
                    if not original_file_list and latest_task_states:
                        total_tasks = len(latest_task_states) 
                    # If original_file_list is present, total_tasks is already set to len(original_file_list)
                    # The completed_tasks, failed_tasks, running_tasks are counts across ALL sub-task runs,
                    # not necessarily per unique file. We need to adjust overall progress calculation.

                # Determine overall status
                overall_status: Status = "pending"
                if flow_run.state:
                    if flow_run.state.is_completed():
                        overall_status = "completed"
                    elif flow_run.state.is_failed() or flow_run.state.is_crashed():
                        overall_status = "error"
                    elif flow_run.state.is_running():
                        overall_status = "running"
                    elif flow_run.state.is_pending(): # Or scheduled
                        overall_status = "pending"
                     # Add other states as needed
                
                progress_percentage = 0
                if total_tasks > 0:
                    # Consider a flow "running" if any tasks are running, or if flow itself is running and not all tasks are done
                    # Progress is based on tasks that have reached a final state (completed or error)
                    final_state_tasks = completed_tasks + failed_tasks
                    progress_percentage = (final_state_tasks / total_tasks) * 100
                elif overall_status == "completed": # If no tasks but flow is complete
                    progress_percentage = 100

                # If the flow is running but no specific file is "running" yet, try to find one from original list
                if overall_status == "running" and not current_overall_file and original_file_list:
                    processed_file_names = {f["file_name"] for f in per_file_progress}
                    for original_file_path in original_file_list:
                        original_base_name = os.path.basename(original_file_path)
                        if original_base_name not in processed_file_names:
                            current_overall_file = original_base_name # Show the next expected file
                            break
                
                response_data = {
                    "task_run_id": task_run_id,
                    "flow_name": flow_run.name,
                    "status": overall_status,
                    "progress": round(progress_percentage, 2),
                    "total_files": total_tasks, # Number of files in the input list
                    "processed_files": completed_tasks, # Files that completed successfully
                    "failed_files": failed_tasks, # Files that failed
                    "running_files": running_tasks, # Files actively being processed by a task
                    "current_overall_file": current_overall_file, # Name of file currently in a "running" task state for the flow
                    "per_file": per_file_progress,
                    "start_time": flow_run.start_time.isoformat() if flow_run.start_time else None,
                    "end_time": flow_run.end_time.isoformat() if flow_run.end_time else None,
                }
                logger.info("Successfully fetched task progress", **response_data)
                return jsonify(create_success_response(response_data))

            except Exception as e:
                logger.error(f"Error fetching progress for task {task_run_id}", exc_info=True)
                # Create a more informative error message for the client
                error_detail = f"Internal error retrieving details for task {task_run_id}."
                if isinstance(e, AttributeError) and 'model_dump' in str(e):
                    error_detail += " Problem with Prefect filter structure."
                elif "PrefectClient" in str(type(e)): # Catching generic Prefect client errors
                    error_detail += " Could not communicate effectively with Prefect."

                return create_error_response(error_detail, "PROGRESS_ERROR", 500)
    
    # Synchronous wrapper for the /api/progress GET endpoint
    @app.route('/api/progress', methods=['GET'])
    @log_request()
    # @require_auth # Removed
    @handle_errors
    def get_all_progress():
        """Get progress of the active ingest using the progress tracker."""
        logger.info("Request processing started for /api/progress")
        
        # Get progress from the tracker (which handles both legacy format and Prefect monitoring)
        progress_data = progress_tracker.get_progress()
        
        logger.info("Progress data from tracker", data=progress_data)
        return jsonify(create_success_response(progress_data))
    
    # ========================================================================
    # SYSTEM ENDPOINTS
    # ========================================================================
    
    @app.route('/api/pipeline/steps', methods=['GET'])
    @log_request()
    # @require_auth # Removed
    @handle_errors
    def get_pipeline_steps():
        """Get all available pipeline steps."""
        from ..cli_commands import SystemCommand
        cmd = SystemCommand()
        result = cmd.execute(action='list_steps', format_type='json')
        
        if result.get('success'):
            return jsonify(create_success_response(result.get('data', {})))
        else:
            return create_error_response(result.get('error', 'Failed to get steps'), 
                                       'STEPS_ERROR', 500)
    
    # ========================================================================
    # SPECIAL ROUTES (From old server for extension compatibility)
    # ========================================================================
    
    @app.route('/api/thumbnail/<clip_id>')
    # @require_auth # Removed
    @handle_errors
    def thumbnail_proxy(clip_id: str):
        """Serve thumbnail image from local storage."""
        try:
            # Imports moved to top of file if not already there,
            # but for clarity in this diff, showing them here.
            # Ensure 'os' and 'mimetypes' are imported at the top of server.py
            # from ..database.duckdb import connection as duckdb_connection # Already imported
            # from ..database.duckdb import crud as duckdb_crud # Already imported
            from ..database.duckdb import connection as duckdb_connection
            from ..database.duckdb import crud as duckdb_crud
            import mimetypes # Should be at the top of the file

            with duckdb_connection.get_db_connection() as conn:
                clip_details = duckdb_crud.get_clip_details(clip_id=clip_id, conn=conn)

            if not clip_details:
                return create_error_response("Clip not found", 'CLIP_NOT_FOUND', 404)

            thumbnail_path = clip_details.get('primary_thumbnail_path')

            if not thumbnail_path:
                thumbnails_list = clip_details.get('thumbnails') # This is List[str] of paths
                if isinstance(thumbnails_list, list) and thumbnails_list:
                    # Attempt to use the first thumbnail from the general list if primary is not set
                    # This list should contain paths to AI selected ones if ai_thumbnail_selection_step ran,
                    # or paths to general thumbnails if not.
                    thumbnail_path = thumbnails_list[0]
                    logger.info(f"Primary thumbnail not set for clip {clip_id}, using first from 'thumbnails' list: {thumbnail_path}")
                else:
                    logger.warning(f"No primary_thumbnail_path or thumbnails list for clip {clip_id}")
                    return create_error_response("Thumbnail path not found for clip", 'THUMBNAIL_NOT_FOUND', 404)
            
            if not isinstance(thumbnail_path, str):
                logger.error(f"Thumbnail path for clip {clip_id} is not a string: {thumbnail_path}")
                return create_error_response("Invalid thumbnail path format", 'INVALID_PATH', 500)

            # Security check: Ensure the path is within an expected base directory if necessary
            # For now, assuming paths stored in DB are safe and absolute or resolvable
            logger.info(f"__file__ = {__file__}")
            project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))
            logger.info(f"Calculated project_root = {project_root}")
            logger.info(f"Original thumbnail_path = {thumbnail_path}")
            if not os.path.isabs(thumbnail_path):
                thumbnail_path = os.path.normpath(os.path.join(project_root, thumbnail_path))
                logger.info(f"Resolved relative thumbnail path to absolute: {thumbnail_path}")
            else:
                logger.info(f"Thumbnail path is already absolute: {thumbnail_path}")

            if not os.path.exists(thumbnail_path):
                logger.error(f"Thumbnail file not found at path: {thumbnail_path} for clip {clip_id}")
                return create_error_response(
                    f"Thumbnail file not found on server (resolved path: {thumbnail_path})",
                    'FILE_NOT_FOUND_SERVER',
                    404
                )
            
            if not os.path.isfile(thumbnail_path):
                logger.error(f"Thumbnail path is not a file: {thumbnail_path} for clip {clip_id}")
                return create_error_response("Thumbnail path is not a file", 'PATH_NOT_FILE', 500)

            content_type = mimetypes.guess_type(thumbnail_path)[0] or 'image/jpeg'
            
            logger.info(f"Serving thumbnail for clip {clip_id} from path: {thumbnail_path}")
            return send_file(thumbnail_path, mimetype=content_type)

        except Exception as e:
            logger.error(f"Failed to get thumbnail for clip {clip_id}", error=str(e), exc_info=True)
            return create_error_response(f"Failed to get thumbnail: {str(e)}",
                                       'THUMBNAIL_ERROR', 500)
    
    # ========================================================================
    # WEBSOCKET EVENTS (Real-time Progress Updates)
    # ========================================================================
    
    @socketio.on('connect')
    def handle_connect():
        """Handle WebSocket connection."""
        try:
            logger.info("WebSocket client connected", 
                       client_id=request.sid,
                       remote_addr=request.remote_addr)
            
            emit('connection_status', {
                'connected': True,
                'fallback_available': True,
                'prefect_available': PREFECT_AVAILABLE,
                'timestamp': time.time()
            })
        except Exception as e:
            logger.error(f"Error in WebSocket connect handler: {str(e)}")
    
    @socketio.on('ping')
    def handle_ping():
        """Simple ping handler for WebSocket testing."""
        emit('pong', {'timestamp': time.time()})
    
    @socketio.on('disconnect')
    def handle_disconnect():
        """Handle WebSocket disconnection."""
        logger.info("WebSocket client disconnected", 
                   client_id=request.sid)
    
    @socketio.on('subscribe_progress')
    def handle_subscribe_progress(data):
        """Subscribe to real-time progress updates for a task.
        
        Client should fallback to REST API if this fails.
        """
        task_run_uuid = data.get('task_run_id')
        request_id = data.get('requestId') # Useful for client-side tracking if needed
        client_sid = request.sid  # Capture sid here, in the request context

        logger.info(
            "Received subscribe_progress event", 
            task_run_id=task_run_uuid, 
            request_id=request_id,
            client_sid=client_sid # Log the captured sid
        )

        # Send immediate progress update (works for both specific task and general progress)
        progress_data = progress_tracker.get_progress(task_run_uuid)
        emit('ingest_progress_update', progress_data, room=client_sid)
        
        # Send subscription confirmation
        emit('progress_subscribed', {
            'task_run_id': task_run_uuid,
            'status': 'subscribed',
            'request_id': request_id,
            'timestamp': time.time()
        }, room=client_sid)
        
        logger.info("Progress subscription confirmed", 
                   task_run_id=task_run_uuid, 
                   client_sid=client_sid)
    
    @socketio.on('get_ingest_progress')
    def handle_get_ingest_progress(data):
        """Get current ingest progress via WebSocket."""
        request_id = data.get('requestId')
        
        # Get progress from tracker
        progress_data = progress_tracker.get_progress()
        
        # Emit response with request ID for client correlation
        emit('response', {
            'requestId': request_id,
            'payload': progress_data
        })
    
    @socketio.on('start_ingest')
    def handle_start_ingest(data):
        """Start ingest via WebSocket (for compatibility)."""
        request_id = data.get('requestId')
        directory = data.get('directory')
        options = data.get('options', {})
        
        # Use the IngestCommand to start
        cmd = IngestCommand()
        result = cmd.execute(
            action='start',
            directory=directory,
            **options
        )
        
        if result.get('success'):
            # Start tracking if we got a task ID
            task_data = result.get('data', {})
            if task_data.get('task_run_id'):
                progress_tracker.start_tracking(
                    flow_run_id=task_data['task_run_id'],
                    directory=directory,
                    total_files=task_data.get('total_files', 0)
                )
            
            # Emit success response
            emit('response', {
                'requestId': request_id,
                'payload': task_data
            })
        else:
            # Emit error response
            emit('response_error', {
                'requestId': request_id,
                'error': result.get('error', 'Failed to start ingest')
            })

        if PREFECT_AVAILABLE:
            # Define a wrapper to run the async monitor task
            def run_async_monitor_wrapper(current_task_run_uuid, current_client_sid):
                try:
                    loop = asyncio.get_event_loop()
                except RuntimeError:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                
                loop.run_until_complete(monitor_task_progress(current_task_run_uuid, current_client_sid)) # Pass captured sid

            socketio.start_background_task(run_async_monitor_wrapper, task_run_uuid, client_sid) # Pass captured sid
            
            emit('progress_subscribed', {
                'task_run_id': task_run_uuid,
                'status': 'subscribed',
                'request_id': request_id,
                'timestamp': datetime.utcnow().isoformat()
            }, room=client_sid)
        else:
            logger.warning("Prefect is not available. Real-time progress monitoring disabled.")
            emit('progress_error', {
                'message': 'Prefect not available, cannot monitor progress.', 
                'task_run_id': task_run_uuid,
                'request_id': request_id
            }, room=client_sid)
    
    # ========================================================================
    # HELPER FUNCTIONS
    # ========================================================================
    
    async def get_task_result(task_run_id: UUID) -> tuple[Status, Any]:
        """Get task result using official Prefect pattern.
        
        Args:
            task_run_id: UUID of the task run
            
        Returns:
            Tuple of (status, data)
        """
        try:
            async with get_client() as client:
                task_run = await client.read_task_run(task_run_id)
                
                if not task_run or not task_run.state:
                    return "pending", None
                
                if task_run.state.is_completed():
                    try:
                        result = task_run.state.result(_sync=True)
                        return "completed", result
                    except Exception as e:
                        logger.warning(f"Could not retrieve result for {task_run_id}: {e}")
                        return "completed", {"message": "Task completed but result unavailable"}
                        
                elif task_run.state.is_failed():
                    try:
                        error_result = task_run.state.result(_sync=True)
                        return "error", str(error_result) if error_result else "Task failed"
                    except Exception as e:
                        logger.warning(f"Could not retrieve error for {task_run_id}: {e}")
                        return "error", "Task failed but error details unavailable"
                        
                elif task_run.state.is_running():
                    return "running", {"message": "Task is currently running"}
                    
                else:
                    return "pending", {"message": "Task is pending execution"}
                    
        except Exception as e:
            logger.error(f"Error checking task status for {task_run_id}: {e}")
            return "error", f"Failed to check task status: {str(e)}"
    
    async def monitor_task_progress(task_run_uuid: str, client_sid: str):
        """Monitor task progress and emit updates via WebSocket.
        
        Args:
            task_run_uuid: UUID of the task to monitor
            client_sid: SocketIO client ID to send updates to
        """
        try:
            while True:
                status, data = await get_task_result(UUID(task_run_uuid))
                
                # Emit progress update to specific client
                socketio.emit('progress_update', {
                    'task_run_id': task_run_uuid,
                    'status': status,
                    'data': data,
                    'timestamp': time.time()
                }, room=client_sid)
                
                # Stop monitoring if task is complete or failed
                if status in ['completed', 'error']:
                    break
                    
                # Wait before next check
                await asyncio.sleep(2)
                
        except Exception as e:
            logger.error(f"Progress monitoring failed for {task_run_uuid}: {str(e)}")
            socketio.emit('progress_error', {
                'error': str(e),
                'fallback_to_rest': True,
                'task_run_id': task_run_uuid
            }, room=client_sid)
    
    return app, socketio


def main():
    """Main entry point for running the API server."""
    import argparse
    import sys
    import os
    
    parser = argparse.ArgumentParser(description='Video Ingest Tool API Server')
    parser.add_argument('--port', type=int, default=8001, 
                       help='Port to run the server on (default: 8001)')
    parser.add_argument('--host', default='localhost',
                       help='Host to bind to (default: localhost)')
    parser.add_argument('--debug', action='store_true',
                       help='Enable debug mode')
    parser.add_argument('--reload', action='store_true',
                       help='Enable auto-reload on file changes (useful for development)')
    
    args = parser.parse_args()
    
    # Create app and socketio
    app, socketio = create_app(debug=args.debug)
    
    # More comprehensive TTY detection for auto-reload
    def can_use_reloader():
        """Check if we can safely use the reloader."""
        try:
            # Check if we have a TTY
            if not sys.stdin.isatty():
                return False
            
            # Check if we're in a subprocess that might not have proper TTY access
            if os.getenv('_') and 'subprocess' in str(os.getenv('_')):
                return False
                
            # Check if stdout/stderr are properly connected
            if not sys.stdout.isatty() or not sys.stderr.isatty():
                return False
                
            # Additional check for shell subprocess context
            if os.getppid() == 1:  # Parent process is init, likely detached
                return False
                
            return True
        except (AttributeError, OSError):
            return False
    
    # Enable auto-reload if debug mode or explicitly requested, and TTY is available
    use_reloader = (args.debug or args.reload) and can_use_reloader()
    
    if (args.debug or args.reload) and not use_reloader:
        logger.warning("⚠️  Auto-reload requested but TTY not properly available.")
        logger.info("💡 For auto-reload to work:")
        logger.info("   1. Run directly in terminal (not in background)")
        logger.info("   2. Use --foreground option with restart-services")
        logger.info("   3. Or run server directly: python -m video_ingest_tool.api.server --reload")
    
    logger.info(f"Starting Video Ingest API Server",
               host=args.host,
               port=args.port,
               debug=args.debug,
               auto_reload=use_reloader,
               prefect_available=PREFECT_AVAILABLE)
    
    if use_reloader:
        logger.info("🔄 Auto-reload enabled - server will restart when files change")
    
    # Run with SocketIO support and proper error handling
    try:
        socketio.run(
            app, 
            host=args.host, 
            port=args.port, 
            debug=args.debug,
            use_reloader=use_reloader,
            allow_unsafe_werkzeug=True
        )
    except Exception as e:
        if "termios" in str(e) or "Input/output error" in str(e):
            logger.warning("⚠️  Auto-reload failed due to TTY issues. Falling back to normal mode.")
            logger.info("💡 Restart without --reload or use --foreground mode")
            # Fallback to running without reloader
            socketio.run(
                app, 
                host=args.host, 
                port=args.port, 
                debug=False,  # Disable debug to avoid reloader
                use_reloader=False,
                allow_unsafe_werkzeug=True
            )
        else:
            raise


if __name__ == '__main__':
    main() 