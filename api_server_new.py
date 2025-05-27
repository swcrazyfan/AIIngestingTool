#!/usr/bin/env python3
"""
New API Server for AI Ingesting Tool that acts as a proxy to the CLI functionality.
This server maintains compatibility with the existing extension.
"""

import os
import sys
import json
import time
import logging
import structlog
from typing import Dict, Any, List, Optional, Union, Tuple

from flask import Flask, request, jsonify, Response
from flask_cors import CORS
from flask_socketio import SocketIO, emit

# Import CLI functionality
from video_ingest_tool.cli import search_videos as cli_search_videos
from video_ingest_tool.cli import find_similar_videos as cli_find_similar
from video_ingest_tool.cli import show_clip_details as cli_clip_details
from video_ingest_tool.cli import show_catalog_stats as cli_catalog_stats
from video_ingest_tool.cli import ingest as cli_ingest
from video_ingest_tool.cli import list_steps as cli_list_steps
from video_ingest_tool.cli import auth_login as cli_auth_login
from video_ingest_tool.cli import auth_logout as cli_auth_logout
from video_ingest_tool.cli import auth_signup as cli_auth_signup
from video_ingest_tool.cli import auth_status as cli_auth_status

# Import additional components as needed
from video_ingest_tool.auth import AuthManager
from video_ingest_tool.search import VideoSearcher, format_search_results
from video_ingest_tool.processor import get_available_pipeline_steps, process_video_file, get_default_pipeline_config
from video_ingest_tool.discovery import scan_directory
from video_ingest_tool.config import setup_logging
from video_ingest_tool.output import save_to_json, save_run_outputs
from video_ingest_tool.utils import calculate_checksum
from video_ingest_tool.video_processor import DEFAULT_COMPRESSION_CONFIG

# Setup logging
logger = structlog.get_logger(__name__)

# Initialize Flask app
app = Flask(__name__)
CORS(app, supports_credentials=True)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading")

# Global variables for ingest job tracking
current_ingest_job = None
ingest_progress = {"status": "idle", "progress": 0, "total": 0, "current_file": "", "results": [], "processed_files": []}
BACKEND_AVAILABLE = True

# Helper functions
def get_json_files():
    """Get processed video files from JSON output directories.
    
    Returns:
        List of video metadata dictionaries from JSON files
    """
    try:
        # Look for recent JSON files in output directory
        output_dir = os.path.join(os.getcwd(), "output", "runs")
        if not os.path.exists(output_dir):
            return []
            
        # Find the most recent run directory
        run_dirs = [d for d in os.listdir(output_dir) if d.startswith("run_")]
        if not run_dirs:
            return []
            
        latest_run = sorted(run_dirs)[-1]
        json_dir = os.path.join(output_dir, latest_run, "json")
        
        if not os.path.exists(json_dir):
            return []
            
        # Read all JSON files in the directory
        results = []
        for filename in os.listdir(json_dir):
            if filename.endswith(".json"):
                try:
                    with open(os.path.join(json_dir, filename), 'r') as f:
                        data = json.load(f)
                        # Add ID if not present
                        if 'id' not in data:
                            data['id'] = filename.replace('.json', '')
                        results.append(data)
                except Exception as e:
                    logger.error(f"Error reading JSON file {filename}: {str(e)}")
        
        return results
    except Exception as e:
        logger.error(f"Error getting JSON files: {str(e)}")
        return []

def check_and_refresh_auth(log_to_console=True) -> bool:
    """Check authentication status and refresh token if needed."""
    try:
        auth_manager = AuthManager()
        session = auth_manager.get_current_session()
        if not session:
            if log_to_console:
                logger.warning("Not authenticated")
            return False
        return True
    except Exception as e:
        logger.error(f"Auth check failed: {str(e)}")
        return False

def perform_search(query='', search_type='hybrid', limit=20) -> Tuple[bool, Dict[str, Any], int]:
    """Shared search implementation for both HTTP API and WebSocket.
    
    Args:
        query: Search query string
        search_type: Type of search to perform (hybrid, semantic, fulltext, etc.)
        limit: Maximum number of results to return
            
    Returns:
        Tuple of (success, results_or_error, status_code)
        - success is True if search was successful, False otherwise
        - results_or_error is either the search results or an error message
        - status_code is the HTTP status code (only relevant for HTTP API)
    """
    if not BACKEND_AVAILABLE:
        return False, {"error": "Backend not available"}, 503

    if not check_and_refresh_auth(log_to_console=False):
        return False, {"error": "Authentication required"}, 401

    try:
        logger.info("Performing search", query=query, search_type=search_type, limit=limit)
        searcher = VideoSearcher()
        
        # Removed special handling for 'recent' search_type
        # All search_types are now passed directly to VideoSearcher.search
        if not query and search_type != 'similar': # 'similar' search type uses clip_id not query
             # For empty queries (excluding 'similar'), it's better to use the new list_videos functionality.
             # However, perform_search is for keyword-based search. Returning empty for now.
             # Clients should be updated to call /api/videos for general listings.
            logger.warning("Search query is empty, returning empty results for keyword search.")
            return True, {"results": [], "total": 0, "query": query, "search_type": search_type}, 200

        results = searcher.search(query=query, search_type=search_type, match_count=limit)
        formatted_results = format_search_results(results, search_type)
        
        return True, {"results": formatted_results, "total": len(formatted_results), "query": query, "search_type": search_type}, 200

    except ValueError as ve:
        error_msg = str(ve)
        logger.error("Search operation ValueError: {error_msg}")
        if "Authentication required" in error_msg or "Invalid Refresh Token" in error_msg or "Failed to create authenticated client" in error_msg:
            return False, {"error": error_msg}, 401
        return False, {"error": str(ve)}, 400 # Bad Request for validation errors
    except Exception as e:
        logger.error("Search failed", error=str(e), query=query, search_type=search_type)
        return False, {"error": f"Search failed: {str(e)}"}, 500

def get_recent_videos(limit: int = 20, return_json: bool = True):
    """Get recent videos from latest ingest or database."""
    try:
        # Try to get from current ingest job first
        if current_ingest_job and current_ingest_job.results:
            results = current_ingest_job.results[-limit:]
            response_data = {
                "results": results,
                "total": len(results),
                "source": "current_job"
            }
            return jsonify(response_data) if return_json else response_data
        
        # Try to get from database if authenticated
        if BACKEND_AVAILABLE and check_and_refresh_auth(log_to_console=False):
            try:
                # Get recent videos from database
                # Note: VideoSearcher doesn't actually support 'recent' as a search_type
                # So we use a supported type (hybrid) with an empty query to get recent videos
                searcher = VideoSearcher()
                results = searcher.search(
                    query="",  # Empty query returns recent videos
                    search_type="hybrid",  # Use a supported search type
                    match_count=limit
                )
                
                # Format results
                formatted_results = format_search_results(results, "recent")
                
                response_data = {
                    "results": formatted_results,
                    "total": len(formatted_results),
                    "source": "database"
                }
                return jsonify(response_data) if return_json else response_data
                
            except Exception as e:
                logger.warning(f"Database query failed: {str(e)}")
                # Fall through to JSON files
        
        # Try to get from JSON files
        json_files = get_json_files()
        if json_files:
            results = []
            for json_file in sorted(json_files, key=lambda x: x.get('processed_at', ''), reverse=True)[:limit]:
                results.append(json_file)
                
            response_data = {
                "results": results,
                "total": len(results),
                "source": "json_files"
            }
            return jsonify(response_data) if return_json else response_data
        
        # No results found
        response_data = {
            "results": [],
            "total": 0,
            "source": "none"
        }
        return jsonify(response_data) if return_json else response_data
        
    except Exception as e:
        logger.error(f"Failed to get recent videos: {str(e)}")
        error_response = {"error": "Failed to load recent videos"}
        return (jsonify(error_response), 500) if return_json else (error_response, 500)

# API Routes
@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint."""
    return jsonify({
        "status": "ok",
        "timestamp": time.time(),
        "backend_available": BACKEND_AVAILABLE
    })

# Auth endpoints
@app.route('/api/auth/status', methods=['GET'])
def auth_status():
    """Get authentication status."""
    if not BACKEND_AVAILABLE:
        return jsonify({"authenticated": False, "error": "Backend not available"}), 500
    
    try:
        auth_manager = AuthManager()
        session = auth_manager.get_current_session()
        
        if session:
            # Get user profile
            profile = auth_manager.get_user_profile()
            
            return jsonify({
                "authenticated": True,
                "user": {
                    "id": session.get('user_id'),
                    "email": session.get('email'),
                    "display_name": profile.get('display_name') if profile else None,
                    "profile_type": profile.get('profile_type') if profile else None
                }
            })
        else:
            return jsonify({"authenticated": False})
            
    except Exception as e:
        logger.error(f"Auth status check failed: {str(e)}")
        return jsonify({"authenticated": False, "error": str(e)}), 500

@app.route('/api/auth/login', methods=['POST'])
def auth_login():
    """Login endpoint."""
    if not BACKEND_AVAILABLE:
        return jsonify({"error": "Backend not available"}), 500
    
    try:
        data = request.get_json()
        email = data.get('email')
        password = data.get('password')
        
        if not email or not password:
            return jsonify({"error": "Email and password required"}), 400
        
        auth_manager = AuthManager()
        success = auth_manager.login(email, password)
        
        if success:
            # Get user profile
            profile = auth_manager.get_user_profile()
            
            return jsonify({
                "success": True,
                "user": {
                    "email": email,
                    "display_name": profile.get('display_name') if profile else None,
                    "profile_type": profile.get('profile_type') if profile else None
                }
            })
        else:
            return jsonify({"error": "Login failed"}), 401
            
    except Exception as e:
        logger.error(f"Login failed: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/auth/signup', methods=['POST'])
def auth_signup():
    """Signup endpoint."""
    if not BACKEND_AVAILABLE:
        return jsonify({"error": "Backend not available"}), 500
    
    try:
        data = request.get_json()
        email = data.get('email')
        password = data.get('password')
        
        if not email or not password:
            return jsonify({"error": "Email and password required"}), 400
        
        auth_manager = AuthManager()
        success = auth_manager.signup(email, password)
        
        if success:
            return jsonify({"success": True, "message": "Account created successfully"})
        else:
            return jsonify({"error": "Signup failed"}), 400
            
    except Exception as e:
        logger.error(f"Signup failed: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/auth/logout', methods=['POST'])
def auth_logout():
    """Logout endpoint."""
    if not BACKEND_AVAILABLE:
        return jsonify({"error": "Backend not available"}), 500
    
    try:
        auth_manager = AuthManager()
        success = auth_manager.logout()
        return jsonify({"success": success})
        
    except Exception as e:
        logger.error(f"Logout failed: {str(e)}")
        return jsonify({"error": "Logout failed"}), 500

# Ingest endpoints
@app.route('/api/ingest', methods=['POST'])
def start_ingest():
    """Start video ingest process."""
    global ingest_progress
    
    if not BACKEND_AVAILABLE:
        return jsonify({
            "error": "Backend not available. Please ensure video_ingest_tool is properly installed."
        }), 500
    
    # Check if already running
    if ingest_progress["status"] in ["starting", "scanning", "processing"]:
        return jsonify({
            "error": "Ingest job already running",
            "current_status": ingest_progress["status"]
        }), 400
    
    try:
        data = request.get_json()
        if data is None:
            # This case handles if get_json() returns None (e.g. wrong content type and not force=True)
            logger.error("Failed to parse request JSON: request.get_json() returned None. Check Content-Type header.")
            return jsonify({"error": "Invalid request: Could not parse JSON body. Ensure Content-Type is application/json."}), 400
        directory = data.get('directory')
    except Exception as e: # Catches errors during get_json() itself (e.g. malformed JSON)
        logger.error("Error parsing request JSON for ingest", exc_info=True, error=str(e))
        return jsonify({"error": "Invalid request: Failed to parse JSON body.", "details": str(e)}), 400

    if not directory or not os.path.exists(directory):
        return jsonify({
            "error": f"Directory not found or not accessible: {directory}"
        }), 400
    
    # Reset progress
    ingest_progress = {
        "status": "starting",
        "progress": 0,
        "total": 0,
        "current_file": "",
        "message": "Initializing...",
        "results": [],
        "processed_files": []
    }
    
    # Start ingest task in background thread
    from threading import Thread
    
    try:
        # Create thread with execute_ingest_task
        ingest_thread = Thread(
            target=execute_ingest_task,
            args=(directory,),
            kwargs={
                'recursive': data.get('recursive', True),
                'limit': data.get('limit', 0),
                'store_database': data.get('store_database', False),
                'generate_embeddings': data.get('generate_embeddings', False),
                'force_reprocess': data.get('force_reprocess', False),
                'ai_analysis': data.get('ai_analysis', False),
                'compression_fps': data.get('compression_fps', DEFAULT_COMPRESSION_CONFIG['fps']),
                'compression_bitrate': data.get('compression_bitrate', DEFAULT_COMPRESSION_CONFIG['video_bitrate'])
            },
            daemon=True
        )
        
        # Start the thread
        ingest_thread.start()
        
        return jsonify({
            "status": "started",
            "directory": directory
        })
    except Exception as e:
        logger.error("Error starting ingest thread", exc_info=True, error=str(e))
        ingest_progress["status"] = "idle"
        return jsonify({"error": "Failed to start ingest job", "details": str(e)}), 500

@app.route('/api/ingest/progress', methods=['GET'])
def get_ingest_progress():
    """Get current ingest job progress."""
    global ingest_progress
    
    return jsonify(ingest_progress)

@app.route('/api/ingest/results', methods=['GET'])
def get_ingest_results():
    """Get results from the most recent ingest job."""
    global ingest_progress
    
    if ingest_progress and "results" in ingest_progress and ingest_progress["results"]:
        return jsonify({
            "results": ingest_progress["results"],
            "count": len(ingest_progress["results"])
        })
    else:
        return jsonify({
            "results": [],
            "count": 0
        })

# Search endpoints
@app.route('/api/search', methods=['GET'])
def search_videos():
    """HTTP API endpoint for searching processed videos."""
    query = request.args.get('query', '')
    search_type = request.args.get('type', 'hybrid')
    limit = request.args.get('limit', 20, type=int)
    
    success, results_or_error, status_code = perform_search(query, search_type, limit)
    return jsonify(results_or_error), status_code

@app.route('/api/videos', methods=['GET'])
def list_videos_endpoint():
    """HTTP API endpoint for listing videos with sorting and filtering."""
    if not BACKEND_AVAILABLE:
        return jsonify({"error": "Backend not available"}), 503

    if not check_and_refresh_auth(log_to_console=False):
        return jsonify({"error": "Authentication required"}), 401

    try:
        sort_by = request.args.get('sort_by', 'processed_at')
        sort_order = request.args.get('sort_order', 'descending')
        limit = request.args.get('limit', 20, type=int)
        offset = request.args.get('offset', 0, type=int)
        date_start = request.args.get('date_start') # ISO format string
        date_end = request.args.get('date_end')     # ISO format string

        filters = {}
        if date_start:
            filters['date_start'] = date_start
        if date_end:
            filters['date_end'] = date_end
        
        # Validate sort_by and sort_order against SortField and SortOrder literals if possible
        # For simplicity, direct pass-through for now. Add validation if needed.
        # from video_ingest_tool.search import SortField, SortOrder (potential import)
        # if sort_by not in get_args(SortField): ... error
        # if sort_order not in get_args(SortOrder): ... error

        searcher = VideoSearcher()
        videos = searcher.list_videos(
            sort_by=sort_by,
            sort_order=sort_order,
            limit=limit,
            offset=offset,
            filters=filters
        )
        
        # format_search_results might not be directly applicable here as list_videos returns raw data.
        # The client might expect a consistent structure, or we return the raw video objects.
        # For now, returning raw video objects.
        return jsonify({"results": videos, "total": len(videos)}), 200 # Consider adding total count from DB if pagination is used

    except ValueError as e:
        error_msg = str(e)
        logger.error("List videos validation error", error=str(e), args=request.args)
        if "Authentication required" in error_msg or "Invalid Refresh Token" in error_msg or "Failed to create authenticated client" in error_msg:
            return jsonify({"error": error_msg}), 401
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.error("List videos failed", error=str(e), args=request.args)
        return jsonify({"error": f"Failed to list videos: {str(e)}"}), 500

@app.route('/api/similar', methods=['GET'])
def search_similar_videos():
    """Find videos similar to a given clip."""
    if not BACKEND_AVAILABLE:
        return jsonify({"error": "Backend not available for similar search"}), 500
    
    try:
        clip_id = request.args.get('clip_id')
        limit = request.args.get('limit', 5, type=int)
        
        if not clip_id:
            return jsonify({"error": "Clip ID required"}), 400
        
        # Check authentication
        if not check_and_refresh_auth():
            return jsonify({"error": "Authentication required for similar search"}), 401
        
        # Use the VideoSearcher to find similar videos
        searcher = VideoSearcher()
        results = searcher.find_similar(
            clip_id=clip_id,
            match_count=limit
        )
        
        # Format results
        formatted_results = format_search_results(results, "similar")
        
        return jsonify({
            "results": formatted_results,
            "total": len(formatted_results),
            "source_clip_id": clip_id
        })
        
    except ValueError as e:
        error_msg = str(e)
        logger.error(f"Similar search ValueError for clip {clip_id}: {error_msg}")
        if "Authentication required" in error_msg or "Invalid Refresh Token" in error_msg or "Failed to create authenticated client" in error_msg:
            return jsonify({"error": error_msg}), 401
        if "Clip not found" in error_msg:
             return jsonify({"error": error_msg}), 404
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.error(f"Similar search failed: {str(e)}")
        return jsonify({"error": f"Similar search failed: {str(e)}"}), 500

@app.route('/api/database/status', methods=['GET'])
def database_status():
    """Get database connection status."""
    if not BACKEND_AVAILABLE:
        return jsonify({
            "connection": "unavailable",
            "message": "Backend not available"
        }), 500
    
    try:
        from video_ingest_tool.supabase_config import get_database_status
        
        status = get_database_status()
        return jsonify(status)
        
    except Exception as e:
        logger.error(f"Failed to get database status: {str(e)}")
        return jsonify({
            "connection": "error",
            "message": str(e)
        }), 500

@app.route('/api/clips/<clip_id>', methods=['GET'])
def get_clip_details(clip_id):
    """Get detailed information about a specific clip."""
    if not BACKEND_AVAILABLE:
        return jsonify({"error": "Backend not available"}), 500
    
    try:
        # Check authentication
        if not check_and_refresh_auth():
            return jsonify({"error": "Authentication required"}), 401
        
        # Get authenticated client
        auth_manager = AuthManager()
        client = auth_manager.get_authenticated_client()
        
        # Get clip details
        clip_result = client.rpc('get_clip_details', {
            'clip_id_param': clip_id
        }).execute()
        
        if not clip_result.data:
            return jsonify({"error": "Clip not found"}), 404
        
        clip = clip_result.data[0]
        
        # Get transcript if available
        transcript_result = client.table('transcripts').select('*').eq('clip_id', clip_id).execute()
        transcript = transcript_result.data[0] if transcript_result.data else None
        
        # Get analysis if available
        analysis_result = client.table('analyses').select('*').eq('clip_id', clip_id).execute()
        analysis = analysis_result.data[0] if analysis_result.data else None
        
        return jsonify({
            "clip": clip,
            "transcript": transcript,
            "analysis": analysis
        })
        
    except ValueError as e:
        error_msg = str(e)
        logger.error(f"Get clip details ValueError for {clip_id}: {error_msg}")
        if "Authentication required" in error_msg or "Invalid Refresh Token" in error_msg or "Failed to create authenticated client" in error_msg:
            return jsonify({"error": error_msg}), 401
        if "Clip not found" in error_msg: # Should be caught by earlier check, but good to have
             return jsonify({"error": error_msg}), 404
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.error(f"Failed to get clip details: {str(e)}")
        return jsonify({"error": f"Failed to get clip details: {str(e)}"}), 500

@app.route('/api/stats', methods=['GET'])
def get_catalog_stats():
    """Get statistics about the video catalog."""
    if not BACKEND_AVAILABLE:
        return jsonify({"error": "Backend not available"}), 500
    
    try:
        # Check authentication
        if not check_and_refresh_auth():
            return jsonify({"error": "Authentication required"}), 401
        
        # Use the VideoSearcher to get stats
        searcher = VideoSearcher()
        stats = searcher.get_user_stats()
        
        return jsonify(stats)
        
    except ValueError as e:
        error_msg = str(e)
        logger.error(f"Get catalog stats ValueError: {error_msg}")
        if "Authentication required" in error_msg or "Invalid Refresh Token" in error_msg or "Failed to create authenticated client" in error_msg:
            return jsonify({"error": error_msg}), 401
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.error(f"Error getting catalog stats: {str(e)}")
        return jsonify({"error": f"Failed to get catalog stats: {str(e)}"}), 500

@app.route('/api/pipeline/steps', methods=['GET'])
def get_pipeline_steps():
    """Get available pipeline steps."""
    if not BACKEND_AVAILABLE:
        return jsonify({"error": "Backend not available"}), 500
    
    try:
        steps = get_available_pipeline_steps()
        
        # Format steps for display
        formatted_steps = []
        for step_id, step_info in steps.items():
            formatted_steps.append({
                "id": step_id,
                "name": step_info.get('name', step_id),
                "description": step_info.get('description', ''),
                "enabled_by_default": step_info.get('enabled_by_default', True)
            })
        
        return jsonify({
            "steps": formatted_steps
        })
        
    except Exception as e:
        logger.error(f"Failed to get pipeline steps: {str(e)}")
        return jsonify({"error": f"Failed to get pipeline steps: {str(e)}"}), 500

# WebSocket event handlers
@socketio.on('connect')
def handle_connect():
    """Handle client connection to WebSocket."""
    try:
        logger.info("Client connected to WebSocket")
    except Exception as e:
        logger.error(f"Error in connect handler: {str(e)}")

@socketio.on('disconnect')
def handle_disconnect():
    """Handle client disconnection from WebSocket."""
    try:
        logger.info("Client disconnected from WebSocket")
    except Exception as e:
        logger.error(f"Error in disconnect handler: {str(e)}")

@socketio.on('search_request')
def handle_search_request(data):
    """Handle search requests through WebSocket."""
    try:
        logger.info("Received search request via WebSocket", data=data)
        request_id = data.get('requestId')
        query = data.get('query', '')
        search_type = data.get('searchType', 'hybrid')
        limit = data.get('limit', 20)

        # perform_search now handles auth and backend checks internally
        success, results_or_error, _ = perform_search(query, search_type, limit)
        
        response_data = {"requestId": request_id}
        if success:
            response_data["result"] = results_or_error
        else:
            response_data["error"] = results_or_error.get("error", "Search failed")
            
        socketio.emit('response', response_data)

    except Exception as e:
        logger.error("Error handling WebSocket search request", error=str(e), data=data)
        if data and data.get('requestId'):
            socketio.emit('response', {
                "requestId": data.get('requestId'),
                "error": f"Request failed: {str(e)}"
            })

@socketio.on('start_ingest')
def handle_start_ingest(data):
    """Handle ingest start requests through WebSocket."""
    global ingest_progress
    request_id = data.get('requestId')
    
    try:
        logger.info("Received start ingest request via WebSocket")
        directory = data.get('directory')
        options = data.get('options', {})
        
        if not directory or not os.path.exists(directory):
            emit_error(request_id, f"Directory not found: {directory}")
            return
        
        if ingest_progress["status"] in ["starting", "scanning", "processing"]:
            emit_error(request_id, "Ingest job already running")
            return
        
        # Reset progress
        ingest_progress = {
            "status": "starting",
            "progress": 0,
            "total": 0,
            "current_file": "",
            "message": "Initializing...",
            "results": [],
            "processed_files": []
        }
        
        # Start ingest task in background thread
        from threading import Thread
        
        # Create thread with execute_ingest_task
        ingest_thread = Thread(
            target=execute_ingest_task,
            args=(directory,),
            kwargs={
                'recursive': options.get('recursive', True),
                'limit': options.get('limit', 0),
                'store_database': options.get('store_database', False),
                'generate_embeddings': options.get('generate_embeddings', False),
                'force_reprocess': options.get('force_reprocess', False),
                'ai_analysis': options.get('ai_analysis', False),
                'compression_fps': options.get('compression_fps', DEFAULT_COMPRESSION_CONFIG['fps']),
                'compression_bitrate': options.get('compression_bitrate', DEFAULT_COMPRESSION_CONFIG['video_bitrate'])
            },
            daemon=True
        )
        
        # Start the thread
        ingest_thread.start()
        
        # Send response
        socketio.emit('response', {
            "requestId": request_id,
            "result": {
                "status": "started",
                "directory": directory
            }
        })
        
    except Exception as e:
        logger.error("Error starting ingest thread (WebSocket)", exc_info=True, error=str(e))
        ingest_progress["status"] = "idle"
        emit_error(request_id, f"Failed to start ingest job: {str(e)}")

@socketio.on('get_ingest_progress')
def handle_get_ingest_progress(data):
    """Handle ingest progress requests through WebSocket."""
    try:
        logger.info("Received get ingest progress request via WebSocket")
        request_id = data.get('requestId')
        
        # Send current progress
        socketio.emit('response', {
            "requestId": request_id,
            "result": ingest_progress
        })
        
    except Exception as e:
        logger.error(f"Error handling WebSocket get ingest progress request: {str(e)}")
        if data and data.get('requestId'):
            socketio.emit('response', {
                "requestId": data.get('requestId'),
                "error": f"Request failed: {str(e)}"
            })

@socketio.on('get_video_details')
def handle_get_video_details(data):
    """Handle video details requests through WebSocket."""
    request_id = data.get('requestId')
    clip_id = data.get('clipId')
    try:
        logger.info(f"Received get video details request via WebSocket for clip_id: {clip_id}")
        if not clip_id:
            emit_error(request_id, "Clip ID required")
            return

        if not BACKEND_AVAILABLE:
            emit_error(request_id, "Backend not available")
            return

        if not check_and_refresh_auth(log_to_console=False):
            emit_error(request_id, "Authentication required") # Client needs to interpret this
            return
            
        auth_manager = AuthManager()
        client = auth_manager.get_authenticated_client()

        clip_result = client.rpc('get_clip_details', {'clip_id_param': clip_id}).execute()
        if not clip_result.data:
            emit_error(request_id, "Clip not found")
            return
        clip_data = clip_result.data[0]
        
        transcript_result = client.table('transcripts').select('*').eq('clip_id', clip_id).limit(1).execute()
        transcript_data = transcript_result.data[0] if transcript_result.data else None
        
        analysis_result = client.table('analyses').select('*').eq('clip_id', clip_id).limit(1).execute()
        analysis_data = analysis_result.data[0] if analysis_result.data else None
        
        socketio.emit('response', {
            "requestId": request_id,
            "result": {"clip": clip_data, "transcript": transcript_data, "analysis": analysis_data}
        })

    except ValueError as e:
        error_msg = str(e)
        logger.error(f"WS get_video_details ValueError for clip {clip_id}: {error_msg}")
        # For WebSocket, we send the error message. Client needs to detect auth errors.
        if "Authentication required" in error_msg or "Invalid Refresh Token" in error_msg or "Failed to create authenticated client" in error_msg:
            emit_error(request_id, f"Authentication error: {error_msg}")
        elif "Clip not found" in error_msg:
            emit_error(request_id, error_msg)
        else:
            emit_error(request_id, f"Request failed: {error_msg}")
    except Exception as e:
        logger.error(f"Error handling WebSocket get video details for clip {clip_id}: {str(e)}", exc_info=True)
        emit_error(request_id, f"Unexpected error: {str(e)}")

@socketio.on('get_similar_videos')
def handle_get_similar_videos(data):
    """Handle similar videos requests through WebSocket."""
    request_id = data.get('requestId')
    clip_id = data.get('clipId')
    limit = data.get('limit', 5)
    try:
        logger.info(f"Received get similar videos request via WebSocket for clip_id: {clip_id}")
        if not clip_id:
            emit_error(request_id, "Clip ID required")
            return
        
        if not BACKEND_AVAILABLE:
            emit_error(request_id, "Backend not available")
            return
        
        if not check_and_refresh_auth(log_to_console=False):
            emit_error(request_id, "Authentication required") # Client needs to interpret this
            return
        
        searcher = VideoSearcher()
        results = searcher.find_similar(clip_id=clip_id, match_count=limit)
        formatted_results = format_search_results(results, "similar")
        
        socketio.emit('response', {
            "requestId": request_id,
            "result": {"results": formatted_results, "total": len(formatted_results), "source_clip_id": clip_id}
        })

    except ValueError as e:
        error_msg = str(e)
        logger.error(f"WS get_similar_videos ValueError for clip {clip_id}: {error_msg}")
        if "Authentication required" in error_msg or "Invalid Refresh Token" in error_msg or "Failed to create authenticated client" in error_msg:
            emit_error(request_id, f"Authentication error: {error_msg}")
        elif "Clip not found" in error_msg:
            emit_error(request_id, error_msg)
        else:
            emit_error(request_id, f"Request failed: {error_msg}")
    except Exception as e:
        logger.error(f"Error handling WebSocket get similar videos for clip {clip_id}: {str(e)}", exc_info=True)
        emit_error(request_id, f"Unexpected error: {str(e)}")

# Helper to emit errors consistently for WebSocket
def emit_error(request_id: Optional[str], message: str):
    if request_id:
        socketio.emit('response', {"requestId": request_id, "error": message})
    else:
        # If no request_id, it might be a general connection issue or unprompted error
        # This case needs careful handling based on client capabilities
        logger.warning(f"Emitting error without request_id: {message}")
        # socketio.emit('error_occurred', {"error": message}) # Example of a general error event

# Helper functions for ingest
def update_ingest_progress(status, message="", current_file="", progress=0, total=0, processed_count=0, total_count=0, results=None, processed_file=None):
    """Update the global ingest_progress dictionary with new values."""
    global ingest_progress
    
    # Update values
    ingest_progress["status"] = status
    ingest_progress["message"] = message
    ingest_progress["current_file"] = current_file
    
    # Calculate progress percentage if total_count is provided
    if total_count > 0:
        ingest_progress["progress"] = int(processed_count / total_count * 100)
    else:
        ingest_progress["progress"] = progress
    
    ingest_progress["total"] = total_count if total_count > 0 else total
    
    # Add results if provided
    if results:
        if "results" not in ingest_progress:
            ingest_progress["results"] = []
        ingest_progress["results"].extend(results)
    
    # Add processed_count and failed_count for better UI display
    if processed_count > 0:
        ingest_progress["processed_count"] = processed_count
    
    # Add or update processed file in the processed_files list
    if processed_file:
        if "processed_files" not in ingest_progress:
            ingest_progress["processed_files"] = []
        
        # Check if file already exists in the list (by path)
        file_path = processed_file.get('path', '')
        file_name = processed_file.get('file_name', '')
        
        # Look for existing entry to update
        found = False
        for i, pf in enumerate(ingest_progress["processed_files"]):
            if (file_path and pf.get('path') == file_path) or (file_name and pf.get('file_name') == file_name):
                ingest_progress["processed_files"][i] = processed_file
                found = True
                break
        
        # If not found, add it
        if not found:
            ingest_progress["processed_files"].append(processed_file)
    
    logger.info(f"Ingest progress updated: {status}", 
                progress=ingest_progress["progress"],
                total=ingest_progress["total"],
                current_file=current_file,
                message=message)
                
    # Emit WebSocket event for real-time updates to all connected clients
    try:
        # Create a simplified progress object for the WebSocket event
        progress_update = {
            "status": status,
            "progress": ingest_progress["progress"],
            "total": ingest_progress["total"],
            "current_file": current_file,
            "message": message
        }
        
        # Add additional information if available
        if "processed_count" in ingest_progress:
            progress_update["processed_count"] = ingest_progress["processed_count"]
        if "failed_count" in ingest_progress:
            progress_update["failed_count"] = ingest_progress["failed_count"]
        if "processed_files" in ingest_progress:
            progress_update["processed_files"] = ingest_progress["processed_files"]
            
        # Broadcast progress update to all clients
        socketio.emit('ingest_progress_update', progress_update)
    except Exception as e:
        logger.error(f"Failed to emit WebSocket progress update: {str(e)}")

def execute_ingest_task(directory, recursive=True, limit=0, store_database=False, 
                        generate_embeddings=False, force_reprocess=False, ai_analysis=False,
                        compression_fps=DEFAULT_COMPRESSION_CONFIG['fps'],
                        compression_bitrate=DEFAULT_COMPRESSION_CONFIG['video_bitrate']):
    """
    Execute an ingest task on a directory of video files.
    
    This function replicates the core functionality of the CLI's ingest command,
    but adapted for the API server with progress updates.
    
    Args:
        directory: Directory to scan for video files
        recursive: Whether to scan subdirectories
        limit: Limit number of files to process (0 = no limit)
        store_database: Whether to store results in the database
        generate_embeddings: Whether to generate vector embeddings
        force_reprocess: Whether to force reprocessing of files
        ai_analysis: Whether to enable AI analysis steps
        compression_fps: Frame rate for compressed videos
        compression_bitrate: Video bitrate for compression
    """
    global ingest_progress
    
    # Initial progress update
    update_ingest_progress("starting", message="Initializing ingest...")
    
    try:
        # Setup logging and get paths - similar to cli.py
        logger_task, timestamp, json_dir, log_file = setup_logging()
        
        # Get run directory from json_dir path
        run_dir = os.path.dirname(json_dir)
        
        # Create subdirectories
        thumbnails_dir = os.path.join(run_dir, "thumbnails")
        os.makedirs(thumbnails_dir, exist_ok=True)
        
        # Create summary filename
        summary_filename = f"api_ingest_{os.path.basename(directory)}_{timestamp}.json"
        
        logger_task.info("Starting API ingest task", 
                    directory=directory, 
                    recursive=recursive,
                    run_dir=run_dir,
                    limit=limit,
                    compression_fps=compression_fps,
                    compression_bitrate=compression_bitrate)
        
        # Update progress for scanning stage
        update_ingest_progress("scanning", message="Scanning directory for video files...")
        
        # Scan directory for video files
        video_files = scan_directory(directory, recursive, logger_task)
        
        # Apply limit if specified
        if limit > 0 and len(video_files) > limit:
            video_files = video_files[:limit]
            logger_task.info("Applied file limit", limit=limit)
        
        # Update progress after scanning
        update_ingest_progress(
            "scanning", 
            message=f"Found {len(video_files)} video files",
            total_count=len(video_files)
        )
        
        if not video_files:
            update_ingest_progress("completed", message="No video files found")
            logger_task.info("No video files found, task completed")
            return
        
        # Add all files to processed_files list with status "waiting"
        for file_path in video_files:
            file_name = os.path.basename(file_path)
            update_ingest_progress(
                "scanning",
                message=f"Preparing to process {len(video_files)} files",
                total_count=len(video_files),
                processed_file={
                    "file_name": file_name,
                    "path": file_path,
                    "status": "waiting",
                    "progress_percentage": 0
                }
            )
        
        # Set up pipeline configuration
        pipeline_config = get_default_pipeline_config()
        
        # Apply API options to pipeline configuration
        if store_database:
            pipeline_config['database_storage'] = True
            logger_task.info("Enabled database storage")
        
        if generate_embeddings:
            pipeline_config['generate_embeddings'] = True
            pipeline_config['database_storage'] = True  # Embeddings require database
            logger_task.info("Enabled vector embeddings generation")
        
        # Apply AI analysis options
        if ai_analysis:
            # Enable AI-related steps
            pipeline_config['ai_summary_generation'] = True
            pipeline_config['ai_tag_generation'] = True
            # Enable the main AI video analysis step
            pipeline_config['ai_video_analysis'] = True
            # Other related steps
            pipeline_config['transcript_generation'] = True
            
            logger_task.info("Enabled AI analysis steps including comprehensive video analysis")
        
        # Handle database checks for store_database or generate_embeddings
        if store_database or generate_embeddings:
            from video_ingest_tool.supabase_config import verify_connection
            
            # Check Supabase connection
            if not verify_connection():
                error_msg = "Cannot connect to Supabase database"
                logger_task.error(error_msg)
                update_ingest_progress("failed", message=error_msg)
                return
            
            # Check authentication
            auth_manager = AuthManager()
            if not auth_manager.get_current_session():
                error_msg = "Database storage/embeddings require authentication"
                logger_task.error(error_msg)
                update_ingest_progress("failed", message=error_msg)
                return
        
        # Save the active configuration to the run directory
        config_path = os.path.join(run_dir, "pipeline_config.json")
        with open(config_path, 'w') as f:
            json.dump(pipeline_config, f, indent=2)
        
        # Update progress for processing stage
        update_ingest_progress(
            "processing", 
            message="Starting to process video files...",
            total_count=len(video_files)
        )
        
        # Process each video file
        processed_files = []
        failed_files = []
        skipped_files = []
        
        for i, file_path in enumerate(video_files):
            # Update progress for current file
            file_name = os.path.basename(file_path)
            update_ingest_progress(
                "processing",
                message=f"Processing file {i+1} of {len(video_files)}",
                current_file=file_name,
                processed_count=i,
                total_count=len(video_files),
                processed_file={
                    "file_name": file_name,
                    "path": file_path,
                    "status": "processing",
                    "current_step": "initializing"  # Add initial step
                }
            )
            
            logger_task.info(f"Processing video file ({i+1}/{len(video_files)})", path=file_path)
            
            try:
                # Create a callback to update progress with current step
                def step_progress_callback(step_name):
                    # Define pipeline steps for progress calculation
                    # This is a simplified list of steps in typical processing order
                    pipeline_steps = [
                        "checksum_generation", "duplicate_check", "mediainfo_extraction", 
                        "ffprobe_extraction", "exiftool_extraction", "extended_exif_extraction",
                        "codec_extraction", "hdr_extraction", "audio_extraction", 
                        "subtitle_extraction", "thumbnail_generation", "exposure_analysis",
                        "ai_focal_length", "ai_video_analysis", "metadata_consolidation",
                        "model_creation", "database_storage", "generate_embeddings"
                    ]
                    
                    # Find current step index
                    try:
                        current_step_index = pipeline_steps.index(step_name)
                    except ValueError:
                        current_step_index = 0
                    
                    # Calculate progress percentage (0-100)
                    total_steps = len(pipeline_steps)
                    step_progress = int((current_step_index / total_steps) * 100) if total_steps > 0 else 0
                    
                    # Log step progress
                    logger_task.info(f"Step progress: {step_name} ({current_step_index+1}/{total_steps}): {step_progress}%")
                    
                    update_ingest_progress(
                        "processing",
                        message=f"Processing file {i+1} of {len(video_files)} - {step_name}",
                        current_file=file_name,
                        processed_count=i,
                        total_count=len(video_files),
                        processed_file={
                            "file_name": file_name,
                            "path": file_path,
                            "status": "processing",
                            "current_step": step_name,
                            "progress_percentage": step_progress
                        }
                    )
                
                # Pass the callback to process_video_file
                result = process_video_file(
                    file_path, 
                    thumbnails_dir, 
                    logger_task,
                    config=pipeline_config,
                    compression_fps=compression_fps,
                    compression_bitrate=compression_bitrate,
                    force_reprocess=force_reprocess,
                    step_callback=step_progress_callback
                )
                
                # Handle skipped files (duplicates)
                if isinstance(result, dict) and result.get('skipped'):
                    skipped_files.append({
                        'file_path': file_path,
                        'reason': result.get('reason'),
                        'existing_clip_id': result.get('existing_clip_id'),
                        'existing_file_name': result.get('existing_file_name'),
                        'existing_processed_at': result.get('existing_processed_at')
                    })
                    logger_task.info("Skipped duplicate file", 
                               file=file_path, 
                               existing_id=result.get('existing_clip_id'))
                    
                    # Update processed file status to skipped
                    update_ingest_progress(
                        "processing",
                        message=f"Skipped duplicate file {i+1} of {len(video_files)}",
                        current_file=file_name,
                        processed_count=i+1,
                        total_count=len(video_files),
                        processed_file={
                            "file_name": file_name,
                            "path": file_path,
                            "status": "skipped",
                            "error": result.get('reason', 'Duplicate file'),
                            "current_step": "duplicate_check",
                            "progress_percentage": 100
                        }
                    )
                else:
                    # Normal processing result
                    video_file = result
                    processed_files.append(video_file)
                    
                    # Create filename with original name and UUID
                    base_name = os.path.splitext(os.path.basename(file_path))[0]
                    json_filename = f"{base_name}_{video_file.id}.json"
                    
                    # Save individual JSON to run directory
                    individual_json_path = os.path.join(json_dir, json_filename)
                    save_to_json(video_file, individual_json_path, logger_task)
                    
                    # Update processed file status to completed
                    update_ingest_progress(
                        "processing",
                        message=f"Completed file {i+1} of {len(video_files)}",
                        current_file=file_name,
                        processed_count=i+1,
                        total_count=len(video_files),
                        processed_file={
                            "file_name": file_name,
                            "path": file_path,
                            "status": "completed",
                            "current_step": "finished",
                            "progress_percentage": 100
                        }
                    )
            except Exception as e:
                failed_files.append(file_path)
                logger_task.error("Error processing video file", path=file_path, error=str(e))
                
                # Update processed file status to failed
                update_ingest_progress(
                    "processing",
                    message=f"Failed to process file {i+1} of {len(video_files)}",
                    current_file=file_name,
                    processed_count=i+1,
                    total_count=len(video_files),
                    processed_file={
                        "file_name": file_name,
                        "path": file_path,
                        "status": "failed",
                        "error": str(e),
                        "current_step": "error",
                        "progress_percentage": 100
                    }
                )
        
        # Save run outputs
        output_paths = save_run_outputs(
            processed_files,
            run_dir,
            summary_filename,
            json_dir,
            log_file,
            logger_task
        )
        
        # Compile results for the API response
        api_results = []
        for video_file in processed_files:
            # Convert to dict if it's an object
            if hasattr(video_file, 'to_dict'):
                api_results.append(video_file.to_dict())
            elif hasattr(video_file, '__dict__'):
                api_results.append(video_file.__dict__)
            else:
                api_results.append(video_file)
        
        # Final progress update
        update_ingest_progress(
            "completed",
            message=f"Completed processing {len(processed_files)} files, skipped {len(skipped_files)}, failed {len(failed_files)}",
            processed_count=len(video_files),
            total_count=len(video_files),
            results=api_results
        )
        
        logger_task.info("API ingest task completed", 
                    files_processed=len(processed_files),
                    skipped_files=len(skipped_files),
                    failed_files=len(failed_files),
                    run_directory=run_dir)
        
    except Exception as e:
        error_msg = f"Ingest task failed: {str(e)}"
        logger.error(error_msg, exc_info=True)
        update_ingest_progress("failed", message=error_msg)

if __name__ == "__main__":
    # Print startup message
    print("\n" + "=" * 80)
    print(f"🚀 AI Ingesting Tool API Server")
    print(f"🕒 Started at: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"🌐 HTTP API available at: http://localhost:8000/api/")
    print(f"🔌 WebSocket available at: ws://localhost:8000/socket.io/")
    print("=" * 80 + "\n")
    
    # Start the server
    socketio.run(
        app,
        host="0.0.0.0",
        port=8000,
        debug=True,  # Enable debug mode as per user request
        use_reloader=False  # Disable reloader to avoid duplicate processes
    )
