"""
Store video metadata and analysis in the database.

This module handles storing processed video data in the Supabase database.
"""

from typing import Any, Dict

from ...pipeline.registry import register_step

@register_step(
    name="database_storage", 
    enabled=False,  # Disabled by default
    description="Store video metadata and analysis in Supabase database"
)
def database_storage_step(data: Dict[str, Any], logger=None) -> Dict[str, Any]:
    """
    Store video data in Supabase database.
    
    Args:
        data: Pipeline data containing the output model
        logger: Optional logger
        
    Returns:
        Dict with database storage results
    """
    from ...auth import AuthManager
    from ...database_storage import store_video_in_database
    
    # Check authentication
    auth_manager = AuthManager()
    if not auth_manager.get_current_session():
        if logger:
            logger.warning("Skipping database storage - not authenticated")
        return {
            'database_storage_skipped': True,
            'reason': 'not_authenticated'
        }
    
    output = data.get('output')
    if not output:
        if logger:
            logger.error("No output model found for database storage")
        return {
            'database_storage_failed': True,
            'reason': 'no_output_model'
        }
    
    try:
        result = store_video_in_database(output, logger)
        if logger:
            logger.info(f"Successfully stored video in database: {result.get('clip_id')}")
        return result
        
    except Exception as e:
        if logger:
            logger.error(f"Database storage failed: {str(e)}")
        return {
            'database_storage_failed': True,
            'error': str(e)
        } 