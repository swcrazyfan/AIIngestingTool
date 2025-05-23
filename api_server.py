#!/usr/bin/env python3
"""
HTTP API wrapper for video_ingest_tool to interface with Adobe CEP panel.
Run this alongside the CEP panel to provide HTTP API endpoints.
"""

import os
import sys
import json
import subprocess
import threading
import time
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime
from functools import wraps

from flask import Flask, request, jsonify
from flask_cors import CORS
from flask_socketio import SocketIO
import structlog

# Add the parent directory to Python path so we can import video_ingest_tool
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from video_ingest_tool.processor import process_video_file, get_default_pipeline_config, get_available_pipeline_steps
    from video_ingest_tool.discovery import scan_directory
    from video_ingest_tool.config import setup_logging
    from video_ingest_tool.auth import AuthManager
    from video_ingest_tool.search import VideoSearcher, format_search_results
    from video_ingest_tool.supabase_config import verify_connection, get_database_status
    from video_ingest_tool.video_processor import DEFAULT_COMPRESSION_CONFIG
    BACKEND_AVAILABLE = True
except ImportError as e:
    print(f"Warning: Could not import video_ingest_tool modules: {e}")
    print("Make sure you're running this from the AIIngestingTool directory")
    BACKEND_AVAILABLE = False

# Configure logging
logger = structlog.get_logger(__name__)

app = Flask(__name__)
# Enable CORS for CEP panel access with specific configuration
CORS(
    app, 
    origins=['http://localhost:3000', 'cep://com.ai-ingest-tool.cep.main', 'null'], 
    allow_headers=['Content-Type', 'Authorization'], 
    methods=['GET', 'POST', 'OPTIONS', 'PUT', 'DELETE', 'PATCH'], 
    supports_credentials=True
)

# Initialize SocketIO with proper configuration
socketio = SocketIO(
    app, 
    cors_allowed_origins=['http://localhost:3000', 'cep://com.ai-ingest-tool.cep.main', 'null'], 
    async_mode='threading',
    engineio_logger=True,  # Enable engine logging for debugging
    logger=True,          # Enable socketio logging
    ping_timeout=5,       # Shorter ping timeout for faster detection of disconnects
    ping_interval=25      # Ping interval in seconds
)

# Last successful token refresh timestamp
last_token_refresh = 0
# Minimum time between refresh attempts (5 minutes)
MIN_REFRESH_INTERVAL = 5 * 60  # seconds

# List of endpoints that don't require authentication
PUBLIC_ENDPOINTS = [
    '/api/health',
    '/api/auth/status',
    '/api/auth/login',
    '/api/auth/signup',
    '/api/auth/logout',
    '/api/thumbnail/',  # For serving thumbnails
]

# Global state
current_ingest_job = None
ingest_progress = {"status": "idle", "progress": 0, "message": ""}

# Function to emit progress updates via WebSocket
def emit_progress_update():
    """Emit the current progress state to all connected clients."""
    try:
        socketio.emit('ingest_progress', ingest_progress)
    except Exception as e:
        logger.error(f"Error emitting progress update: {str(e)}")

class IngestJob:
    """Manages background ingest processing."""
    
    def __init__(self, directory: str, options: Dict[str, Any]):
        self.directory = directory
        self.options = options
        self.status = "starting"
        self.progress = 0
        self.message = "Initializing..."
        self.results = []
        self.error = None
        self.start_time = datetime.now()
        
    def run(self):
        """Execute the ingest job in background."""
        global ingest_progress
        
        if not BACKEND_AVAILABLE:
            self.status = "error"
            self.error = "Backend modules not available"
            self.message = "Video ingest tool backend not properly installed"
            ingest_progress.update({
                "status": self.status,
                "progress": 0,
                "message": self.message,
                "error": self.error
            })
            
            # Emit error update via WebSocket
            emit_progress_update()
            return
        
        try:
            self.status = "scanning"
            self.message = "Scanning directory for video files..."
            ingest_progress.update({
                "status": self.status,
                "progress": 10,
                "message": self.message
            })
            
            # Emit scanning update via WebSocket
            emit_progress_update()
            
            # Setup logging
            logger_instance, timestamp, json_dir, log_file = setup_logging()
            run_dir = os.path.dirname(json_dir)
            thumbnails_dir = os.path.join(run_dir, "thumbnails")
            os.makedirs(thumbnails_dir, exist_ok=True)
            
            # Scan directory
            video_files = scan_directory(
                self.directory, 
                recursive=self.options.get('recursive', True),
                logger=logger_instance
            )
            
            # Apply limit if specified
            limit = self.options.get('limit', 0)
            if limit > 0:
                video_files = video_files[:limit]
            
            if not video_files:
                self.status = "completed"
                self.message = "No video files found"
                ingest_progress.update({
                    "status": self.status,
                    "progress": 100,
                    "message": self.message
                })
                
                # Emit update via WebSocket
                emit_progress_update()
                return
            
            self.status = "processing"
            self.message = f"Processing {len(video_files)} video files..."
            ingest_progress.update({
                "status": self.status,
                "progress": 20,
                "message": self.message
            })
            
            # Emit processing update via WebSocket
            emit_progress_update()
            
            # Process videos with progress tracking
            processed_files = []
            failed_files = []
            
            for i, file_path in enumerate(video_files):
                try:
                    progress_percent = 20 + (70 * i / len(video_files))
                    self.message = f"Processing {os.path.basename(file_path)}..."
                    ingest_progress.update({
                        "status": self.status,
                        "progress": progress_percent,
                        "message": self.message,
                        "processed_count": len(processed_files),
                        "failed_count": len(failed_files),
                        "total_count": len(video_files)
                    })
                    
                    # Emit progress update via WebSocket
                    emit_progress_update()
                    
                    # Get pipeline configuration
                    pipeline_config = get_default_pipeline_config()
                    
                    # Apply enable/disable steps
                    disable_steps = self.options.get('disable_steps', [])
                    enable_steps = self.options.get('enable_steps', [])
                    
                    for step in disable_steps:
                        if step in pipeline_config:
                            pipeline_config[step] = False
                    
                    for step in enable_steps:
                        if step in pipeline_config:
                            pipeline_config[step] = True
                    
                    # Apply options
                    if self.options.get('ai_analysis'):
                        pipeline_config['ai_video_analysis'] = True
                    if self.options.get('store_database'):
                        pipeline_config['database_storage'] = True
                    if self.options.get('generate_embeddings'):
                        pipeline_config['generate_embeddings'] = True
                        pipeline_config['database_storage'] = True  # Embeddings require database
                    
                    # Process the video file
                    result = process_video_file(
                        file_path=file_path,
                        thumbnails_dir=thumbnails_dir,
                        logger=logger_instance,
                        config=pipeline_config,
                        compression_fps=self.options.get('compression_fps', DEFAULT_COMPRESSION_CONFIG['fps']),
                        compression_bitrate=self.options.get('compression_bitrate', DEFAULT_COMPRESSION_CONFIG['video_bitrate']),
                        force_reprocess=self.options.get('force_reprocess', False)
                    )
                    
                    # Handle skipped files (duplicates)
                    if isinstance(result, dict) and result.get('skipped'):
                        logger_instance.info(f"Skipped duplicate file: {file_path}")
                        continue
                    
                    # Convert Pydantic model to dict for JSON serialization
                    if hasattr(result, 'model_dump'):
                        result_dict = result.model_dump()
                    else:
                        result_dict = result
                    
                    processed_files.append(result_dict)
                    
                except Exception as e:
                    logger_instance.error(f"Failed to process {file_path}: {str(e)}")
                    failed_files.append({
                        'file_path': file_path,
                        'error': str(e)
                    })
            
            self.status = "completed"
            self.message = f"Processing complete. {len(processed_files)} files processed, {len(failed_files)} failed."
            self.results = processed_files
            
            ingest_progress.update({
                "status": self.status,
                "progress": 100,
                "message": self.message,
                "processed_count": len(processed_files),
                "failed_count": len(failed_files),
                "total_count": len(video_files),
                "results_count": len(processed_files)
            })
            
            # Emit final progress update via WebSocket
            emit_progress_update()
        
        except Exception as e:
            self.status = "error"
            self.error = str(e)
            self.message = f"Error during ingest: {str(e)}"
            ingest_progress.update({
                "status": self.status,
                "progress": 0,
                "message": self.message,
                "error": self.error
            })


@app.before_request
def log_request():
    """Log all incoming requests for debugging.
    Also refreshes authentication token if needed and enforces authentication.
    """
    if request.path.startswith('/api/'):
        logger.info(f"Request: {request.method} {request.path}")
        
        # Skip auth refresh for auth-related endpoints to avoid loops
        if not request.path.startswith('/api/auth/'):
            # Silently refresh token if needed (no console logs)
            check_and_refresh_auth(log_to_console=False)
            
        # Check if endpoint requires authentication
        requires_auth = True
        for public_endpoint in PUBLIC_ENDPOINTS:
            if request.path.startswith(public_endpoint):
                requires_auth = False
                break
                
        # Enforce authentication for protected endpoints
        if requires_auth and BACKEND_AVAILABLE:
            auth_manager = AuthManager()
            if not auth_manager.get_current_session():
                # Return 401 for API requests that require authentication
                if request.path.startswith('/api/'):
                    return jsonify({"error": "Authentication required"}), 401
                    
    if request.method == 'POST' and request.content_type == 'application/json':
        print(f"📄 Body: {request.get_json()}")

@app.after_request
def log_response(response):
    """Log all responses for debugging."""
    print(f"📤 Response: {response.status_code} for {request.method} {request.path}")
    return response

@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint."""
    return jsonify({
        "status": "ok",
        "service": "video_ingest_api",
        "backend_available": BACKEND_AVAILABLE,
        "timestamp": datetime.now().isoformat()
    })


@app.route('/api/auth/status', methods=['GET'])
def auth_status():
    """Check authentication status."""
    if not BACKEND_AVAILABLE:
        return jsonify({"error": "Backend not available"}), 500
    
    try:
        auth_manager = AuthManager()
        session = auth_manager.get_current_session()
        
        if session:
            profile = auth_manager.get_user_profile()
            return jsonify({
                "authenticated": True,
                "user": {
                    "email": session.get('user', {}).get('email'),
                    "profile": profile
                }
            })
        else:
            return jsonify({"authenticated": False})
            
    except Exception as e:
        logger.error(f"Auth status check failed: {str(e)}")
        return jsonify({"error": "Auth check failed", "authenticated": False})


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
            profile = auth_manager.get_user_profile()
            return jsonify({
                "success": True,
                "user": {
                    "email": email,
                    "profile": profile
                }
            })
        else:
            return jsonify({"error": "Invalid credentials"}), 401
            
    except Exception as e:
        logger.error(f"Login failed: {str(e)}")
        return jsonify({"error": "Login failed"}), 500


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
        return jsonify({"error": "Invalid directory path"}), 400
    
    # Create and start job
    options = {
        'recursive': data.get('recursive', True),
        'ai_analysis': data.get('ai_analysis', False),
        'store_database': data.get('store_database', False),
        'generate_embeddings': data.get('generate_embeddings', False),
        'force_reprocess': data.get('force_reprocess', False),
        'limit': data.get('limit', 0),
        'compression_fps': data.get('compression_fps', DEFAULT_COMPRESSION_CONFIG['fps']),
        'compression_bitrate': data.get('compression_bitrate', DEFAULT_COMPRESSION_CONFIG['video_bitrate']),
        'disable_steps': data.get('disable_steps', []),
        'enable_steps': data.get('enable_steps', [])
    }
    
    current_ingest_job = IngestJob(directory, options)
    
    # Start in background thread
    thread = threading.Thread(target=current_ingest_job.run)
    thread.daemon = True
    thread.start()
    
    return jsonify({
        "message": "Ingest job started",
        "job_id": id(current_ingest_job),
        "directory": directory,
        "options": options
    })


@app.route('/api/ingest/progress', methods=['GET'])
def get_ingest_progress():
    """Get current ingest progress."""
    global current_ingest_job, ingest_progress
    
    if not current_ingest_job:
        return jsonify({
            "status": "idle",
            "progress": 0,
            "message": "No active ingest job"
        })
    
    return jsonify(ingest_progress)


@app.route('/api/ingest/results', methods=['GET'])
def get_ingest_results():
    """Get results from the latest ingest job."""
    global current_ingest_job
    
    if not current_ingest_job:
        return jsonify({"error": "No ingest job found"}), 404
    
    return jsonify({
        "status": current_ingest_job.status,
        "results": current_ingest_job.results,
        "total": len(current_ingest_job.results)
    })


@app.route('/api/search', methods=['POST'])
def search_videos():
    """Search processed videos."""
    try:
        data = request.get_json()
        query = data.get('query', '')
        search_type = data.get('search_type', 'hybrid')
        limit = data.get('limit', 20)
        
        # If no query, return recent files from database or JSON
        if not query.strip() or search_type == 'recent':
            return get_recent_videos(limit)
        
        if not BACKEND_AVAILABLE:
            return jsonify({"error": "Backend not available for search"}), 500
        
        # Check authentication for database search
        auth_manager = AuthManager()
        if not auth_manager.get_current_session():
            return jsonify({"error": "Authentication required for search"}), 401
        
        # Initialize searcher
        searcher = VideoSearcher()
        
        # Perform search
        results = searcher.search(
            query=query,
            search_type=search_type,
            match_count=limit
        )
        
        # Format results for CEP panel
        formatted_results = []
        for result in results:
            formatted_results.append({
                'id': result.get('id'),
                'file_name': result.get('file_name'),
                'local_path': result.get('local_path'),
                'file_path': result.get('file_path'),
                'content_summary': result.get('content_summary'),
                'content_tags': result.get('content_tags', []),
                'duration_seconds': result.get('duration_seconds'),
                'camera_make': result.get('camera_make'),
                'camera_model': result.get('camera_model'),
                'content_category': result.get('content_category'),
                'processed_at': result.get('processed_at'),
                'similarity_score': result.get('similarity_score', 0),
                'search_rank': result.get('search_rank', 0)
            })
        
        return jsonify({
            "results": formatted_results,
            "total": len(formatted_results),
            "search_type": search_type,
            "query": query
        })
        
    except Exception as e:
        logger.error(f"Search failed: {str(e)}")
        return jsonify({"error": f"Search failed: {str(e)}"}), 500


@app.route('/api/search/similar', methods=['POST'])
def search_similar_videos():
    """Find videos similar to a given clip."""
    try:
        data = request.get_json()
        clip_id = data.get('clip_id')
        limit = data.get('limit', 5)
        
        if not clip_id:
            return jsonify({"error": "clip_id is required"}), 400
        
        if not BACKEND_AVAILABLE:
            return jsonify({"error": "Backend not available for search"}), 500
        
        # Check authentication
        auth_manager = AuthManager()
        if not auth_manager.get_current_session():
            return jsonify({"error": "Authentication required for similar search"}), 401
        
        # Initialize searcher
        searcher = VideoSearcher()
        
        # Find similar videos
        results = searcher.find_similar(
            clip_id=clip_id,
            match_count=limit
        )
        
        # Format results for CEP panel
        formatted_results = []
        for result in results:
            formatted_results.append({
                'id': result.get('id'),
                'file_name': result.get('file_name'),
                'local_path': result.get('local_path'),
                'file_path': result.get('file_path'),
                'content_summary': result.get('content_summary'),
                'content_tags': result.get('content_tags', []),
                'duration_seconds': result.get('duration_seconds'),
                'camera_make': result.get('camera_make'),
                'camera_model': result.get('camera_model'),
                'content_category': result.get('content_category'),
                'processed_at': result.get('processed_at'),
                'similarity_score': result.get('similarity_score', 0)
            })
        
        return jsonify({
            "results": formatted_results,
            "total": len(formatted_results),
            "source_clip_id": clip_id
        })
        
    except Exception as e:
        logger.error(f"Similar search failed: {str(e)}")
        return jsonify({"error": f"Similar search failed: {str(e)}"}), 500


def get_recent_videos(limit: int = 20):
    """Get recent videos from latest ingest or database."""
    try:
        # Try to get from current ingest job first
        if current_ingest_job and current_ingest_job.results:
            results = current_ingest_job.results[-limit:]
            return jsonify({
                "results": results,
                "total": len(results),
                "source": "current_job"
            })
        
        # Try to get from database if authenticated
        if BACKEND_AVAILABLE:
            try:
                auth_manager = AuthManager()
                if auth_manager.get_current_session():
                    client = auth_manager.get_authenticated_client()
                    
                    # Get recent clips from database
                    result = client.table('clips').select(
                        'id, file_name, local_path, content_summary, content_tags, '
                        'duration_seconds, camera_make, camera_model, content_category, processed_at'
                    ).order('processed_at', desc=True).limit(limit).execute()
                    
                    return jsonify({
                        "results": result.data,
                        "total": len(result.data),
                        "source": "database"
                    })
            except Exception as e:
                logger.warning(f"Database query failed: {str(e)}")
        
        # Fallback: look for recent JSON files
        output_dir = os.path.join(os.getcwd(), "output", "runs")
        if os.path.exists(output_dir):
            run_dirs = [d for d in os.listdir(output_dir) if d.startswith("run_")]
            if run_dirs:
                latest_run = sorted(run_dirs)[-1]
                json_dir = os.path.join(output_dir, latest_run, "json")
                
                if os.path.exists(json_dir):
                    results = []
                    json_files = [f for f in os.listdir(json_dir) if f.endswith('.json')]
                    
                    for json_file in sorted(json_files)[-limit:]:
                        try:
                            with open(os.path.join(json_dir, json_file), 'r') as f:
                                video_data = json.load(f)
                                
                            # Extract relevant fields for display
                            result = {
                                'id': video_data.get('id'),
                                'file_name': video_data.get('file_info', {}).get('file_name'),
                                'local_path': video_data.get('file_info', {}).get('file_path'),
                                'content_summary': video_data.get('analysis', {}).get('content_summary'),
                                'content_tags': video_data.get('analysis', {}).get('content_tags', []),
                                'duration_seconds': video_data.get('video', {}).get('resolution', {}).get('duration_seconds'),
                                'camera_make': video_data.get('camera', {}).get('make'),
                                'camera_model': video_data.get('camera', {}).get('model'),
                                'processed_at': video_data.get('file_info', {}).get('processed_at')
                            }
                            results.append(result)
                        except Exception as e:
                            logger.warning(f"Failed to parse JSON file {json_file}: {str(e)}")
                    
                    return jsonify({
                        "results": results,
                        "total": len(results),
                        "source": "json_files"
                    })
        
        # No results found
        return jsonify({
            "results": [],
            "total": 0,
            "source": "none"
        })
        
    except Exception as e:
        logger.error(f"Failed to get recent videos: {str(e)}")
        return jsonify({"error": "Failed to load recent videos"}), 500


@app.route('/api/database/status', methods=['GET'])
def database_status():
    """Get database connection status."""
    if not BACKEND_AVAILABLE:
        return jsonify({"connected": False, "error": "Backend not available"})
    
    try:
        connected = verify_connection()
        status = get_database_status() if connected else {}
        
        return jsonify({
            "connected": connected,
            "status": status
        })
    except Exception as e:
        logger.error(f"Database status check failed: {str(e)}")
        return jsonify({"connected": False, "error": str(e)})


@app.route('/api/clips/<clip_id>', methods=['GET'])
def get_clip_details(clip_id):
    """Get detailed information about a specific clip."""
    if not BACKEND_AVAILABLE:
        return jsonify({"error": "Backend not available"}), 500
    
    try:
        auth_manager = AuthManager()
        if not auth_manager.get_current_session():
            return jsonify({"error": "Authentication required"}), 401
        
        client = auth_manager.get_authenticated_client()
        
        # Get clip details
        clip_result = client.table('clips').select('*').eq('id', clip_id).execute()
        
        if not clip_result.data:
            return jsonify({"error": "Clip not found"}), 404
        
        clip = clip_result.data[0]
        
        # Get transcript if available
        transcript_result = client.table('transcripts').select('full_text').eq('clip_id', clip_id).execute()
        transcript = transcript_result.data[0] if transcript_result.data else None
        
        # Get AI analysis if available
        analysis_result = client.table('analysis').select('*').eq('clip_id', clip_id).execute()
        analysis = analysis_result.data[0] if analysis_result.data else None
        
        return jsonify({
            "clip": clip,
            "transcript": transcript,
            "analysis": analysis
        })
        
    except Exception as e:
        logger.error(f"Failed to get clip details: {str(e)}")
        return jsonify({"error": str(e)}), 500


def require_auth(f):
    """Decorator to require authentication for an endpoint.
    
    Note: This is kept for backward compatibility but is no longer needed
    since authentication is now enforced at the middleware level.
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        if not BACKEND_AVAILABLE:
            return jsonify({"error": "Backend not available"}), 500
            
        auth_manager = AuthManager()
        if not auth_manager.get_current_session():
            return jsonify({"error": "Authentication required"}), 401
            
        return f(*args, **kwargs)
    return decorated


@app.route('/api/stats', methods=['GET'])
@require_auth
def get_catalog_stats():
    """Get catalog statistics for the current user."""
    try:
        from .search import VideoSearcher
        searcher = VideoSearcher()
        stats = searcher.get_user_stats()
        
        return jsonify(stats)
        
    except Exception as e:
        logger.error(f"Failed to get stats: {str(e)}")
        return jsonify({"error": str(e)}), 500


@app.route('/api/pipeline/steps', methods=['GET'])
def get_pipeline_steps():
    """Get available pipeline steps."""
    if not BACKEND_AVAILABLE:
        return jsonify({"error": "Backend not available"}), 500
    
    try:
        from .processor import get_available_pipeline_steps
        steps = get_available_pipeline_steps()
        return jsonify({"steps": steps})
        
    except Exception as e:
        logger.error(f"Failed to get pipeline steps: {str(e)}")
        return jsonify({"error": str(e)}), 500


def check_and_refresh_auth(log_to_console=True):
    """Check authentication status and refresh token if needed.
    
    This runs when the server starts and periodically during requests
    to ensure the token is valid, preventing the need for users to log in again.
    
    Args:
        log_to_console: Whether to print status messages to console
    
    Returns:
        bool: True if authenticated with a valid session, False otherwise
    """
    global last_token_refresh
    
    if not BACKEND_AVAILABLE:
        return False
    
    # Skip refresh if we've refreshed recently
    current_time = time.time()
    if current_time - last_token_refresh < MIN_REFRESH_INTERVAL:
        return True
        
    try:
        auth_manager = AuthManager()
        session = auth_manager.get_current_session()
        
        if session:
            # Session exists and has been refreshed if needed
            last_token_refresh = current_time
            user_email = session.get('email')
            if log_to_console:
                if user_email:
                    print(f"✅ Authenticated as {user_email}")
                else:
                    print(f"✅ Authentication token refreshed successfully")
            return True
        else:
            if log_to_console:
                print("ℹ️ No active session found - login required")
            return False
            
    except Exception as e:
        if log_to_console:
            print(f"⚠️ Auth check failed: {str(e)}")
        logger.error(f"Auth check failed: {str(e)}")
        return False

# WebSocket event handlers
@socketio.on('connect')
def handle_connect():
    """Handle client connection to WebSocket."""
    try:
        logger.info("Client connected to WebSocket")
        # Send current progress state to newly connected client
        socketio.emit('ingest_progress', ingest_progress)
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
        logger.info("Received search request via WebSocket")
        request_id = data.get('requestId')
        
        # Extract search parameters
        query = data.get('query', '')
        search_type = data.get('search_type', 'hybrid')
        limit = data.get('limit', 20)
        offset = data.get('offset', 0)
        
        # Check if backend is available
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
            
        # Perform search
        try:
            from video_ingest_tool.search import VideoSearcher
            
            # Create searcher instance
            searcher = VideoSearcher()
            
            # Perform search
            results = searcher.search(
                query=query,
                search_type=search_type,
                match_count=limit
            )
            
            # Format results for display
            from video_ingest_tool.search import format_search_results
            formatted_results = format_search_results(results, search_type)
            count = len(results)
            
            # Send results back through WebSocket
            socketio.emit('response', {
                "requestId": request_id,
                "result": {
                    "results": formatted_results,
                    "count": count
                }
            })
            
        except Exception as e:
            logger.error(f"Search error: {str(e)}")
            socketio.emit('response', {
                "requestId": request_id,
                "error": f"Search failed: {str(e)}"
            })
    except Exception as e:
        logger.error(f"Error handling WebSocket search request: {str(e)}")
        if data and data.get('requestId'):
            socketio.emit('response', {
                "requestId": data.get('requestId'),
                "error": "Server error processing search"
            })

@socketio.on('start_ingest')
def handle_start_ingest(data):
    """Handle ingest start requests through WebSocket."""
    try:
        logger.info("Received start ingest request via WebSocket")
        request_id = data.get('requestId')
        
        # Extract parameters
        directory = data.get('directory')
        options = data.get('options', {})
        
        if not directory or not os.path.exists(directory):
            socketio.emit('response', {
                "requestId": request_id,
                "error": "Invalid directory path"
            })
            return
            
        global current_ingest_job, ingest_progress
            
        # Check if already running
        if current_ingest_job and current_ingest_job.status in ["starting", "scanning", "processing"]:
            socketio.emit('response', {
                "requestId": request_id,
                "error": "Ingest job already running"
            })
            return
            
        # Create and start job
        try:
            
            # Extract options
            recursive = options.get('recursive', True)
            ai_analysis = options.get('ai_analysis', True)
            generate_embeddings = options.get('generate_embeddings', True)
            store_database = options.get('store_database', True)
            force_reprocess = options.get('force_reprocess', False)
            
            # Start ingest job in background thread
            current_ingest_job = IngestJob(directory, recursive, ai_analysis, generate_embeddings, store_database, force_reprocess)
            ingest_thread = threading.Thread(target=current_ingest_job.run)
            ingest_thread.daemon = True
            ingest_thread.start()
            
            # Return success response
            socketio.emit('response', {
                "requestId": request_id,
                "result": {
                    "success": True,
                    "message": "Ingest job started"
                }
            })
            
        except Exception as e:
            logger.error(f"Error starting ingest job: {str(e)}")
            socketio.emit('response', {
                "requestId": request_id,
                "error": f"Failed to start ingest job: {str(e)}"
            })
            
    except Exception as e:
        logger.error(f"Error handling WebSocket start ingest request: {str(e)}")
        if data and data.get('requestId'):
            socketio.emit('response', {
                "requestId": data.get('requestId'),
                "error": "Server error processing ingest request"
            })

@socketio.on('get_ingest_progress')
def handle_get_ingest_progress(data):
    """Handle ingest progress requests through WebSocket."""
    try:
        logger.info("Received get ingest progress request via WebSocket")
        request_id = data.get('requestId')
        
        # Return current progress
        if not current_ingest_job:
            socketio.emit('response', {
                "requestId": request_id,
                "result": {
                    "status": "idle",
                    "progress": 0,
                    "message": "No active ingest job"
                }
            })
        else:
            socketio.emit('response', {
                "requestId": request_id,
                "result": ingest_progress
            })
            
    except Exception as e:
        logger.error(f"Error handling WebSocket get ingest progress request: {str(e)}")
        if data and data.get('requestId'):
            socketio.emit('response', {
                "requestId": data.get('requestId'),
                "error": "Server error getting ingest progress"
            })

@socketio.on('get_video_details')
def handle_get_video_details(data):
    """Handle video details requests through WebSocket."""
    try:
        logger.info("Received get video details request via WebSocket")
        request_id = data.get('requestId')
        video_id = data.get('id')
        
        if not video_id:
            socketio.emit('response', {
                "requestId": request_id,
                "error": "Missing video ID"
            })
            return
            
        # Check authentication
        if not check_and_refresh_auth(log_to_console=False):
            socketio.emit('response', {
                "requestId": request_id,
                "error": "Authentication required"
            })
            return
            
        try:
            from video_ingest_tool.supabase_config import get_supabase_client
            
            supabase = get_supabase_client()
            if not supabase:
                socketio.emit('response', {
                    "requestId": request_id,
                    "error": "Database connection failed"
                })
                return
                
            # Get video details from database
            result = supabase.table('videos').select('*').eq('id', video_id).execute()
            
            if not result.data or len(result.data) == 0:
                socketio.emit('response', {
                    "requestId": request_id,
                    "error": "Video not found"
                })
                return
                
            # Return video details
            socketio.emit('response', {
                "requestId": request_id,
                "result": result.data[0]
            })
            
        except Exception as e:
            logger.error(f"Error getting video details: {str(e)}")
            socketio.emit('response', {
                "requestId": request_id,
                "error": f"Failed to get video details: {str(e)}"
            })
            
    except Exception as e:
        logger.error(f"Error handling WebSocket get video details request: {str(e)}")
        if data and data.get('requestId'):
            socketio.emit('response', {
                "requestId": data.get('requestId'),
                "error": "Server error getting video details"
            })

@socketio.on('get_similar_videos')
def handle_get_similar_videos(data):
    """Handle similar videos requests through WebSocket."""
    try:
        logger.info("Received get similar videos request via WebSocket")
        request_id = data.get('requestId')
        video_id = data.get('id')
        limit = data.get('limit', 5)
        
        if not video_id:
            socketio.emit('response', {
                "requestId": request_id,
                "error": "Missing video ID"
            })
            return
            
        # Check authentication
        if not check_and_refresh_auth(log_to_console=False):
            socketio.emit('response', {
                "requestId": request_id,
                "error": "Authentication required"
            })
            return
            
        try:
            from video_ingest_tool.search import find_similar_videos
            from video_ingest_tool.supabase_config import get_supabase_client
            
            supabase = get_supabase_client()
            if not supabase:
                socketio.emit('response', {
                    "requestId": request_id,
                    "error": "Database connection failed"
                })
                return
                
            # Get similar videos
            similar_videos = find_similar_videos(video_id, limit, supabase=supabase)
            
            # Return similar videos
            socketio.emit('response', {
                "requestId": request_id,
                "result": similar_videos
            })
            
        except Exception as e:
            logger.error(f"Error getting similar videos: {str(e)}")
            socketio.emit('response', {
                "requestId": request_id,
                "error": f"Failed to get similar videos: {str(e)}"
            })
            
    except Exception as e:
        logger.error(f"Error handling WebSocket get similar videos request: {str(e)}")
        if data and data.get('requestId'):
            socketio.emit('response', {
                "requestId": data.get('requestId'),
                "error": "Server error getting similar videos"
            })

if __name__ == '__main__':
    print("🚀 Starting Video Ingest API Server...")
    print(f"📡 CEP Panel can connect to: http://localhost:8000")
    print(f"🔍 Health check: http://localhost:8000/api/health")
    print(f"🔌 WebSocket available at: ws://localhost:8000/socket.io/")
    
    if BACKEND_AVAILABLE:
        print("✅ Backend modules loaded successfully")
        # Check and refresh authentication on startup
        check_and_refresh_auth()
    else:
        print("⚠️  Backend modules not available - some features will be limited")
    
    print("⚡ Ready for Adobe Premiere Pro CEP panel!")
    
    # Run Flask app with SocketIO
    socketio.run(
        app,
        host='localhost',
        port=8000,
        debug=False,  # Disable debug mode to avoid issues with WebSocket
        use_reloader=False,  # Disable reloader to avoid duplicate socketio instances
        allow_unsafe_werkzeug=True  # Allow unsafe Werkzeug server for development
    )
