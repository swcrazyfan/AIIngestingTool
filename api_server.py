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

from flask import Flask, request, jsonify
from flask_cors import CORS
import structlog

# Add the parent directory to Python path so we can import video_ingest_tool
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from video_ingest_tool.processor import process_video_file, get_default_pipeline_config
    from video_ingest_tool.discovery import scan_directory
    from video_ingest_tool.config import setup_logging
    from video_ingest_tool.auth import AuthManager
    from video_ingest_tool.search import VideoSearcher, format_search_results
    from video_ingest_tool.supabase_config import verify_connection, get_database_status
    BACKEND_AVAILABLE = True
except ImportError as e:
    print(f"Warning: Could not import video_ingest_tool modules: {e}")
    print("Make sure you're running this from the AIIngestingTool directory")
    BACKEND_AVAILABLE = False

# Configure logging
logger = structlog.get_logger(__name__)

app = Flask(__name__)
# Enable CORS for CEP panel access with specific configuration
CORS(app, origins=['*'], allow_headers=['Content-Type'], methods=['GET', 'POST', 'OPTIONS'])

# Global state
current_ingest_job = None
ingest_progress = {"status": "idle", "progress": 0, "message": ""}

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
            return
        
        try:
            self.status = "scanning"
            self.message = "Scanning directory for video files..."
            ingest_progress.update({
                "status": self.status,
                "progress": 10,
                "message": self.message
            })
            
            # Setup logging
            logger_instance, json_dir, timestamp = setup_logging()
            run_dir = os.path.dirname(json_dir)
            thumbnails_dir = os.path.join(run_dir, "thumbnails")
            os.makedirs(thumbnails_dir, exist_ok=True)
            
            # Scan directory
            video_files = scan_directory(
                self.directory, 
                recursive=self.options.get('recursive', True),
                logger=logger_instance
            )
            
            if not video_files:
                self.status = "completed"
                self.message = "No video files found"
                ingest_progress.update({
                    "status": self.status,
                    "progress": 100,
                    "message": self.message
                })
                return
            
            self.status = "processing"
            self.message = f"Processing {len(video_files)} video files..."
            ingest_progress.update({
                "status": self.status,
                "progress": 20,
                "message": self.message
            })
            
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
                    
                    # Get pipeline configuration
                    pipeline_config = get_default_pipeline_config()
                    
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
                        config=pipeline_config
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
            self.message = f"Processing completed! {len(processed_files)} processed, {len(failed_files)} failed"
            self.results = processed_files
            ingest_progress.update({
                "status": self.status,
                "progress": 100,
                "message": self.message,
                "results": processed_files,
                "processed_count": len(processed_files),
                "failed_count": len(failed_files),
                "total_count": len(video_files)
            })
            
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
    """Log all incoming requests for debugging."""
    print(f"📥 Request: {request.method} {request.path} from {request.remote_addr}")
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
        'generate_embeddings': data.get('generate_embeddings', False)
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


if __name__ == '__main__':
    print("🚀 Starting Video Ingest API Server...")
    print(f"📡 CEP Panel can connect to: http://localhost:8000")
    print(f"🔍 Health check: http://localhost:8000/api/health")
    
    if BACKEND_AVAILABLE:
        print("✅ Backend modules loaded successfully")
    else:
        print("⚠️  Backend modules not available - some features will be limited")
    
    print("⚡ Ready for Adobe Premiere Pro CEP panel!")
    
    # Run Flask app
    app.run(
        host='localhost',
        port=8000,
        debug=True,  # Enable debug mode
        threaded=True
    )
