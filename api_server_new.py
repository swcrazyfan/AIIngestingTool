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
from video_ingest_tool.processor import get_available_pipeline_steps
from video_ingest_tool.discovery import scan_directory
from video_ingest_tool.utils import calculate_checksum

# Setup logging
logger = structlog.get_logger(__name__)

# Initialize Flask app
app = Flask(__name__)
CORS(app, supports_credentials=True)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading")

# Global variables for ingest job tracking
current_ingest_job = None
ingest_progress = {"status": "idle", "progress": 0, "total": 0, "current_file": "", "results": []}
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
        logger.error("Search validation error", error=str(ve), query=query, search_type=search_type)
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
    global current_ingest_job, ingest_progress
    
    if not BACKEND_AVAILABLE:
        return jsonify({
            "error": "Backend not available. Please ensure video_ingest_tool is properly installed."
        }), 500
    
    # Check if already running
    if current_ingest_job and current_ingest_job.status in ["starting", "scanning", "processing"]:
        return jsonify({
            "error": "Ingest job already running",
            "current_status": current_ingest_job.status
        }), 400
    
    data = request.get_json()
    directory = data.get('directory')
    
    if not directory or not os.path.exists(directory):
        return jsonify({
            "error": f"Directory not found: {directory}"
        }), 400
    
    # Reset progress
    ingest_progress = {
        "status": "starting",
        "progress": 0,
        "total": 0,
        "current_file": "",
        "results": []
    }
    
    # Start ingest job in background thread
    from threading import Thread
    from video_ingest_tool.ingest import IngestJob
    
    # Create ingest job
    current_ingest_job = IngestJob(
        directory=directory,
        recursive=data.get('recursive', True),
        limit=data.get('limit', 0),
        store_database=data.get('store_database', False),
        generate_embeddings=data.get('generate_embeddings', False),
        force_reprocess=data.get('force_reprocess', False)
    )
    
    # Start job in background
    Thread(target=current_ingest_job.run, daemon=True).start()
    
    return jsonify({
        "status": "started",
        "directory": directory
    })

@app.route('/api/ingest/progress', methods=['GET'])
def get_ingest_progress():
    """Get current ingest job progress."""
    global ingest_progress
    
    return jsonify(ingest_progress)

@app.route('/api/ingest/results', methods=['GET'])
def get_ingest_results():
    """Get results from the most recent ingest job."""
    global current_ingest_job
    
    if current_ingest_job and current_ingest_job.results:
        return jsonify({
            "results": current_ingest_job.results,
            "count": len(current_ingest_job.results)
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

    except ValueError as ve:
        logger.error("List videos validation error", error=str(ve), args=request.args)
        return jsonify({"error": str(ve)}), 400
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
        
    except Exception as e:
        logger.error(f"Failed to get catalog stats: {str(e)}")
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
    try:
        logger.info("Received start ingest request via WebSocket")
        request_id = data.get('requestId')
        
        # Extract ingest parameters
        directory = data.get('directory')
        options = data.get('options', {})
        
        if not directory or not os.path.exists(directory):
            socketio.emit('response', {
                "requestId": request_id,
                "error": f"Directory not found: {directory}"
            })
            return
        
        # Check if already running
        global current_ingest_job, ingest_progress
        if current_ingest_job and current_ingest_job.status in ["starting", "scanning", "processing"]:
            socketio.emit('response', {
                "requestId": request_id,
                "error": "Ingest job already running",
                "current_status": current_ingest_job.status
            })
            return
        
        # Reset progress
        ingest_progress = {
            "status": "starting",
            "progress": 0,
            "total": 0,
            "current_file": "",
            "results": []
        }
        
        # Start ingest job in background thread
        from threading import Thread
        from video_ingest_tool.ingest import IngestJob
        
        # Create ingest job
        current_ingest_job = IngestJob(
            directory=directory,
            recursive=options.get('recursive', True),
            limit=options.get('limit', 0),
            store_database=options.get('store_database', False),
            generate_embeddings=options.get('generate_embeddings', False),
            force_reprocess=options.get('force_reprocess', False)
        )
        
        # Start job in background
        Thread(target=current_ingest_job.run, daemon=True).start()
        
        # Send response
        socketio.emit('response', {
            "requestId": request_id,
            "result": {
                "status": "started",
                "directory": directory
            }
        })
        
    except Exception as e:
        logger.error(f"Error handling WebSocket start ingest request: {str(e)}")
        if data and data.get('requestId'):
            socketio.emit('response', {
                "requestId": data.get('requestId'),
                "error": f"Request failed: {str(e)}"
            })

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
    try:
        logger.info("Received get video details request via WebSocket")
        request_id = data.get('requestId')
        clip_id = data.get('clipId')
        
        if not clip_id:
            socketio.emit('response', {
                "requestId": request_id,
                "error": "Clip ID required"
            })
            return
        
        if not BACKEND_AVAILABLE:
            socketio.emit('response', {
                "requestId": request_id,
                "error": "Backend not available"
            })
            return
        
        # Check authentication
        if not check_and_refresh_auth(log_to_console=False):
            socketio.emit('response', {
                "requestId": request_id,
                "error": "Authentication required"
            })
            return
        
        # Get authenticated client
        auth_manager = AuthManager()
        client = auth_manager.get_authenticated_client()
        
        # Get clip details
        clip_result = client.rpc('get_clip_details', {
            'clip_id_param': clip_id
        }).execute()
        
        if not clip_result.data:
            socketio.emit('response', {
                "requestId": request_id,
                "error": "Clip not found"
            })
            return
        
        clip = clip_result.data[0]
        
        # Get transcript if available
        transcript_result = client.table('transcripts').select('*').eq('clip_id', clip_id).execute()
        transcript = transcript_result.data[0] if transcript_result.data else None
        
        # Get analysis if available
        analysis_result = client.table('analyses').select('*').eq('clip_id', clip_id).execute()
        analysis = analysis_result.data[0] if analysis_result.data else None
        
        # Send response
        socketio.emit('response', {
            "requestId": request_id,
            "result": {
                "clip": clip,
                "transcript": transcript,
                "analysis": analysis
            }
        })
        
    except Exception as e:
        logger.error(f"Error handling WebSocket get video details request: {str(e)}")
        if data and data.get('requestId'):
            socketio.emit('response', {
                "requestId": data.get('requestId'),
                "error": f"Request failed: {str(e)}"
            })

@socketio.on('get_similar_videos')
def handle_get_similar_videos(data):
    """Handle similar videos requests through WebSocket."""
    try:
        logger.info("Received get similar videos request via WebSocket")
        request_id = data.get('requestId')
        clip_id = data.get('clipId')
        limit = data.get('limit', 5)
        
        if not clip_id:
            socketio.emit('response', {
                "requestId": request_id,
                "error": "Clip ID required"
            })
            return
        
        if not BACKEND_AVAILABLE:
            socketio.emit('response', {
                "requestId": request_id,
                "error": "Backend not available"
            })
            return
        
        # Check authentication
        if not check_and_refresh_auth(log_to_console=False):
            socketio.emit('response', {
                "requestId": request_id,
                "error": "Authentication required"
            })
            return
        
        # Use the VideoSearcher to find similar videos
        searcher = VideoSearcher()
        results = searcher.find_similar(
            clip_id=clip_id,
            match_count=limit
        )
        
        # Format results
        formatted_results = format_search_results(results, "similar")
        
        # Send response
        socketio.emit('response', {
            "requestId": request_id,
            "result": {
                "results": formatted_results,
                "total": len(formatted_results),
                "source_clip_id": clip_id
            }
        })
        
    except Exception as e:
        logger.error(f"Error handling WebSocket get similar videos request: {str(e)}")
        if data and data.get('requestId'):
            socketio.emit('response', {
                "requestId": data.get('requestId'),
                "error": f"Request failed: {str(e)}"
            })

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
        debug=False,  # Disable debug mode to avoid issues with WebSocket
        use_reloader=False  # Disable reloader to avoid duplicate processes
    )
