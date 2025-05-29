"""
Store video metadata and analysis in the database.

This module handles storing processed video data in the Supabase database.
"""

from typing import Any, Dict

from ...pipeline.registry import register_step
from prefect import task

@register_step(
    name="database_storage", 
    enabled=True,  # Enabled by default
    description="Store video metadata and analysis in Supabase database"
)
@task
def database_storage_step(data: Dict[str, Any], logger=None) -> Dict[str, Any]:
    """
    Store video data in Supabase database.
    
    Args:
        data: Pipeline data containing the output model and AI thumbnail metadata
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
    
    output = data.get('model')
    if not output:
        if logger:
            logger.error("No output model found for database storage")
        return {
            'database_storage_failed': True,
            'reason': 'no_output_model'
        }
    
    # Get AI thumbnail metadata for storage
    ai_thumbnail_metadata = data.get('ai_thumbnail_metadata', [])
    
    try:
        # Pass AI thumbnail metadata to the storage function
        result = store_video_in_database(output, logger, ai_thumbnail_metadata)
        if logger:
            logger.info(f"Successfully stored video in database: {result.get('clip_id')}")
            if ai_thumbnail_metadata:
                logger.info(f"Included {len(ai_thumbnail_metadata)} AI thumbnails in database record")
        return result
        
    except Exception as e:
        if logger:
            logger.error(f"Database storage failed: {str(e)}")
        return {
            'database_storage_failed': True,
            'error': str(e)
        } 