"""
Duplicate check step for the video ingest pipeline.

Checks for duplicate files in the database.
"""

from typing import Any, Dict
from prefect import task

@task
def check_duplicate_step(data: Dict[str, Any], logger=None, force_reprocess: bool = False) -> Dict[str, Any]:
    """
    Check if a file with the same checksum already exists in the database.
    
    Args:
        data: Pipeline data containing checksum and file info
        logger: Optional logger
        force_reprocess: If True, skip duplicate check and proceed with processing
        
    Returns:
        Dict with duplicate check results
    """
    if force_reprocess:
        if logger:
            logger.info("Force reprocess enabled - skipping duplicate check")
        return {
            'is_duplicate': False,
            'duplicate_check_skipped': True,
            'reason': 'force_reprocess'
        }
    
    from ...auth import AuthManager
    
    # Check if database storage is enabled (duplicate check only makes sense with database)
    auth_manager = AuthManager()
    if not auth_manager.get_current_session():
        if logger:
            logger.info("No authentication - skipping duplicate check")
        return {
            'is_duplicate': False,
            'duplicate_check_skipped': True,
            'reason': 'not_authenticated'
        }
    
    checksum = data.get('checksum')
    if not checksum:
        if logger:
            logger.warning("No checksum available for duplicate check")
        return {
            'is_duplicate': False,
            'duplicate_check_skipped': True,
            'reason': 'no_checksum'
        }
    
    try:
        client = auth_manager.get_authenticated_client()
        if not client:
            if logger:
                logger.warning("No authenticated client - skipping duplicate check")
            return {
                'is_duplicate': False,
                'duplicate_check_skipped': True,
                'reason': 'no_client'
            }
        
        # Query database for existing file with same checksum
        result = client.table('clips').select('id, file_name, file_path, processed_at').eq('file_checksum', checksum).execute()
        
        if result.data:
            existing_file = result.data[0]
            if logger:
                logger.info(f"Found duplicate file in database", 
                           existing_id=existing_file['id'],
                           existing_file=existing_file['file_name'],
                           existing_path=existing_file['file_path'],
                           processed_at=existing_file['processed_at'])
            
            return {
                'is_duplicate': True,
                'existing_clip_id': existing_file['id'],
                'existing_file_name': existing_file['file_name'],
                'existing_file_path': existing_file['file_path'],
                'existing_processed_at': existing_file['processed_at']
            }
        else:
            if logger:
                logger.info("No duplicate found - proceeding with processing")
            return {
                'is_duplicate': False
            }
            
    except Exception as e:
        if logger:
            logger.warning(f"Duplicate check failed: {str(e)} - proceeding with processing")
        return {
            'is_duplicate': False,
            'duplicate_check_failed': True,
            'error': str(e)
        } 