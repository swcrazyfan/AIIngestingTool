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
        # For now, we'll skip the actual database duplicate check since auth was removed
        # TODO: Implement direct database connection without auth when needed
        if logger:
            logger.info("Database duplicate check temporarily disabled - proceeding with processing")
        return {
            'is_duplicate': False,
            'duplicate_check_skipped': True,
            'reason': 'auth_removed'
        }
            
    except Exception as e:
        if logger:
            logger.warning(f"Duplicate check failed: {str(e)} - proceeding with processing")
        return {
            'is_duplicate': False,
            'duplicate_check_failed': True,
            'error': str(e)
        } 