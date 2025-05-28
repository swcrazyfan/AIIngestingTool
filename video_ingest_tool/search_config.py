"""
Search configuration module for video ingest tool.

This module defines all search parameters used across the system,
providing a single source of truth for search behavior.
"""

import os
import json
from typing import Dict, Any
import structlog

logger = structlog.get_logger(__name__)

# Default search parameters (baseline)
DEFAULT_SEARCH_PARAMS = {
    # Hybrid search parameters
    'fulltext_weight': 2.5,        # Weight for full-text search in hybrid search
    'summary_weight': 1.0,         # Weight for summary embeddings in hybrid/semantic search
    'keyword_weight': 0.8,         # Weight for keyword embeddings in hybrid/semantic search
    'rrf_k': 50,                   # Reciprocal Rank Fusion constant
    'similarity_threshold': 0.4,   # Minimum similarity threshold for semantic matches
    
    # Similar search parameters
    'similar_threshold': 0.65,     # Minimum similarity threshold for similar search
    
    # Result limits
    'default_match_count': 10,     # Default number of results to return
    'max_match_count': 100         # Maximum number of results allowed
}

# Configurable paths
CONFIG_FILE_PATH = os.environ.get('SEARCH_CONFIG_PATH', 
                                  os.path.join(os.path.dirname(os.path.dirname(__file__)), 
                                               'config', 'search_params.json'))

def _load_file_params() -> Dict[str, Any]:
    """Load search parameters from config file if it exists."""
    file_params = {}
    
    try:
        if os.path.exists(CONFIG_FILE_PATH):
            with open(CONFIG_FILE_PATH, 'r') as f:
                file_params = json.load(f)
                logger.info("Loaded search parameters from file", path=CONFIG_FILE_PATH)
    except Exception as e:
        logger.error("Failed to load search parameters from file", 
                     path=CONFIG_FILE_PATH, error=str(e))
    
    return file_params

def _load_env_params() -> Dict[str, Any]:
    """Load search parameters from environment variables."""
    env_params = {}
    
    # Map environment variables to parameter names
    env_mapping = {
        'SEARCH_FULLTEXT_WEIGHT': ('fulltext_weight', float),
        'SEARCH_SUMMARY_WEIGHT': ('summary_weight', float),
        'SEARCH_KEYWORD_WEIGHT': ('keyword_weight', float),
        'SEARCH_RRF_K': ('rrf_k', int),
        'SEARCH_SIMILARITY_THRESHOLD': ('similarity_threshold', float),
        'SEARCH_SIMILAR_THRESHOLD': ('similar_threshold', float),
        'SEARCH_DEFAULT_MATCH_COUNT': ('default_match_count', int),
        'SEARCH_MAX_MATCH_COUNT': ('max_match_count', int)
    }
    
    # Process each environment variable
    for env_var, (param_name, param_type) in env_mapping.items():
        if env_var in os.environ:
            try:
                env_params[param_name] = param_type(os.environ[env_var])
                logger.info(f"Using environment override for {param_name}", 
                          value=env_params[param_name], source=env_var)
            except (ValueError, TypeError):
                logger.warning(f"Invalid value for {env_var}, using default")
    
    return env_params

def save_search_params(params: Dict[str, Any]) -> bool:
    """
    Save search parameters to config file.
    
    Args:
        params: Dictionary of parameter values to save
        
    Returns:
        True if successful, False otherwise
    """
    try:
        # Ensure directory exists
        os.makedirs(os.path.dirname(CONFIG_FILE_PATH), exist_ok=True)
        
        # Merge with existing parameters if file exists
        current_params = {}
        if os.path.exists(CONFIG_FILE_PATH):
            with open(CONFIG_FILE_PATH, 'r') as f:
                current_params = json.load(f)
        
        # Update with new parameters
        updated_params = {**current_params, **params}
        
        # Write to file
        with open(CONFIG_FILE_PATH, 'w') as f:
            json.dump(updated_params, f, indent=2)
        
        logger.info("Saved search parameters to file", path=CONFIG_FILE_PATH)
        return True
    except Exception as e:
        logger.error("Failed to save search parameters", error=str(e))
        return False

# Build the actual parameters by layering:
# 1. Start with defaults
# 2. Apply file-based overrides
# 3. Apply environment variable overrides
SEARCH_PARAMS = {
    **DEFAULT_SEARCH_PARAMS,
    **_load_file_params(),
    **_load_env_params()
}

def get_search_params(overrides: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    Get search parameters with optional overrides.
    
    Args:
        overrides: Optional dictionary of parameter overrides
        
    Returns:
        Dictionary of search parameters
    """
    if overrides:
        return {**SEARCH_PARAMS, **overrides}
    return SEARCH_PARAMS.copy()  # Return a copy to prevent modification 