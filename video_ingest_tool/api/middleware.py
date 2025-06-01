"""
Middleware for API authentication and error handling.

This module provides decorators and utilities for handling HTTP authentication,
error responses, and request validation in a consistent manner.
"""

import time
from functools import wraps
from typing import Any, Dict, Optional
from flask import jsonify, request, current_app
import structlog

# from ..auth import AuthManager  # Removed - authentication disabled

logger = structlog.get_logger(__name__)


def require_auth(f):
    """Decorator to require authentication for API endpoints.
    
    DEPRECATED: Authentication has been removed for local DuckDB setup.
    This decorator now does nothing and just passes through to the original function.
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        # Authentication disabled - just execute the function directly
        return f(*args, **kwargs)
    return decorated


def handle_errors(f):
    """Decorator to handle errors consistently across API endpoints.
    
    Catches exceptions and returns appropriate HTTP status codes and error messages.
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        try:
            return f(*args, **kwargs)
            
        except ValueError as e:
            logger.warning(f"Validation error in {f.__name__}: {str(e)}")
            return jsonify({
                "success": False,
                "error": str(e),
                "code": "VALIDATION_ERROR"
            }), 400
            
        except PermissionError as e:
            logger.warning(f"Permission error in {f.__name__}: {str(e)}")
            return jsonify({
                "success": False,
                "error": str(e),
                "code": "PERMISSION_ERROR"
            }), 403
            
        except FileNotFoundError as e:
            logger.warning(f"File not found in {f.__name__}: {str(e)}")
            return jsonify({
                "success": False,
                "error": f"File not found: {str(e)}",
                "code": "FILE_NOT_FOUND"
            }), 404
            
        except Exception as e:
            logger.error(f"Unexpected error in {f.__name__}: {str(e)}", exc_info=True)
            return jsonify({
                "success": False,
                "error": f"Internal server error: {str(e)}",
                "code": "INTERNAL_ERROR"
            }), 500
            
    return decorated


def validate_json_request(required_fields: Optional[list] = None):
    """Decorator to validate JSON request data.
    
    Args:
        required_fields: List of required field names in the JSON body
    """
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            # Check content type
            if not request.is_json:
                return jsonify({
                    "success": False,
                    "error": "Content-Type must be application/json",
                    "code": "INVALID_CONTENT_TYPE"
                }), 400
                
            # Check for valid JSON
            try:
                data = request.get_json()
                if data is None:
                    raise ValueError("No JSON data provided")
            except Exception as e:
                return jsonify({
                    "success": False,
                    "error": f"Invalid JSON: {str(e)}",
                    "code": "INVALID_JSON"
                }), 400
            
            # Check required fields
            if required_fields:
                missing_fields = [field for field in required_fields if field not in data]
                if missing_fields:
                    return jsonify({
                        "success": False,
                        "error": f"Missing required fields: {', '.join(missing_fields)}",
                        "code": "MISSING_FIELDS"
                    }), 400
            
            return f(*args, **kwargs)
            
        return decorated
    return decorator


def log_request():
    """Decorator to log API requests for monitoring and debugging."""
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            start_time = time.time()
            
            # Log request start
            logger.info(
                f"API request started",
                endpoint=f.__name__,
                method=request.method,
                path=request.path,
                user_agent=request.headers.get('User-Agent', 'unknown'),
                remote_addr=request.remote_addr
            )
            
            # Execute request
            try:
                result = f(*args, **kwargs)
                status_code = result[1] if isinstance(result, tuple) else 200
                
                # Log successful completion
                logger.info(
                    f"API request completed",
                    endpoint=f.__name__,
                    status_code=status_code,
                    duration_ms=round((time.time() - start_time) * 1000, 2)
                )
                
                return result
                
            except Exception as e:
                # Log error
                logger.error(
                    f"API request failed",
                    endpoint=f.__name__,
                    error=str(e),
                    duration_ms=round((time.time() - start_time) * 1000, 2),
                    exc_info=True
                )
                raise
                
        return decorated
    return decorator


def add_cors_headers(response):
    """Add CORS headers to response for cross-origin requests."""
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
    response.headers['Access-Control-Allow-Credentials'] = 'true'
    return response


def create_error_response(error_message: str, error_code: str = "UNKNOWN_ERROR", 
                         status_code: int = 500) -> tuple:
    """Create standardized error response.
    
    Args:
        error_message: Human-readable error message
        error_code: Machine-readable error code
        status_code: HTTP status code
        
    Returns:
        Tuple of (response, status_code) for Flask
    """
    return jsonify({
        "success": False,
        "error": error_message,
        "code": error_code,
        "timestamp": time.time()
    }), status_code


def create_success_response(data: Any = None, message: str = "Success") -> Dict[str, Any]:
    """Create standardized success response.
    
    Args:
        data: Response data payload
        message: Success message
        
    Returns:
        Dictionary for JSON response
    """
    response = {
        "success": True,
        "message": message,
        "timestamp": time.time()
    }
    
    if data is not None:
        response["data"] = data
        
    return response 