"""
Database storage step for the video ingest tool.

This module handles storing VideoIngestOutput models and associated data
(embeddings, thumbnails, etc.) to the DuckDB database.
"""

from typing import Any, Dict, Optional
from prefect import task
import structlog

logger = structlog.get_logger(__name__)

@task
def database_storage_step(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Store video metadata and embeddings in DuckDB database.
    
    Args:
        data: Pipeline data containing:
            - 'model': VideoIngestOutput instance
            - 'embeddings_generated': bool (optional)
            - 'data': embeddings data dict (optional)
            
    Returns:
        Dict with storage results
    """
    from ...database.duckdb.connection import get_db_connection
    from ...database.duckdb.mappers import prepare_clip_data_for_db
    from ...database.duckdb.crud import upsert_clip_data
    
    output_model = data.get('model')
    if not output_model:
        logger.error("No output model found for database storage")
        return {
            'database_storage_failed': True,
            'reason': 'no_output_model'
        }
    
    # Get AI thumbnail metadata if available
    ai_thumbnail_metadata = data.get('ai_thumbnail_metadata', [])
    
    # Store embeddings in the model if we have embeddings data
    if data.get('embeddings_generated') and 'data' in data:
        embeddings_data = data['data']
        logger.info("Found embeddings data, will be embedded in the model")
        
        # Update the model's embeddings attribute with the generated embeddings
        if hasattr(output_model, 'embeddings') and embeddings_data:
            # Import the embeddings model
            from ...models import Embeddings
            
            # Create embeddings data object from the generated embeddings
            embeddings_obj = Embeddings(
                summary_embedding=embeddings_data.get('summary_embedding'),
                keyword_embedding=embeddings_data.get('keyword_embedding'),
                thumbnail_1_embedding=embeddings_data.get('image_embeddings', {}).get('thumbnail_1'),
                thumbnail_2_embedding=embeddings_data.get('image_embeddings', {}).get('thumbnail_2'),
                thumbnail_3_embedding=embeddings_data.get('image_embeddings', {}).get('thumbnail_3')
            )
            output_model.embeddings = embeddings_obj
            logger.info("Successfully embedded embeddings data in model")
    else:
        logger.info("No embeddings data found, storing without embeddings")
    
    conn = None
    try:
        # Get database connection
        conn = get_db_connection()
        if not conn:
            logger.error("Failed to get database connection")
            return {
                'database_storage_failed': True,
                'reason': 'connection_failed'
            }
        
        # Prepare clip data for database
        clip_data = prepare_clip_data_for_db(output_model, ai_thumbnail_metadata)
        if not clip_data:
            logger.error("Failed to prepare clip data for database")
            return {
                'database_storage_failed': True,
                'reason': 'data_preparation_failed'
            }
        
        # Store in database
        stored_clip_id = upsert_clip_data(clip_data, conn)
        if stored_clip_id:
            logger.info(f"Successfully stored clip data with ID: {stored_clip_id}")
            return {
                'database_storage_success': True,
                'clip_id': stored_clip_id,
                'stored_embeddings': embeddings_data is not None
            }
        else:
            logger.error("Failed to store clip data in database")
            return {
                'database_storage_failed': True,
                'reason': 'upsert_failed'
            }
            
    except Exception as e:
        logger.error(f"Database storage failed with exception: {str(e)}", exc_info=True)
        return {
            'database_storage_failed': True,
            'reason': 'exception',
            'error': str(e)
        }
    finally:
        # Close connection if needed (depending on your connection management)
        if conn:
            try:
                conn.close()
            except Exception:
                pass 