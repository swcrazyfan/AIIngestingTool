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
            - 'ai_thumbnail_metadata': simplified AI thumbnail metadata (timestamp, reason, rank, path only)
            
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
    
    # Get simplified AI thumbnail metadata (timestamp, reason, rank, path only - no descriptions)
    ai_thumbnail_metadata = data.get('ai_thumbnail_metadata', [])
    
    # Verify simplified metadata structure
    if ai_thumbnail_metadata:
        sample_thumb = ai_thumbnail_metadata[0] if ai_thumbnail_metadata else {}
        logger.info(f"AI thumbnail metadata structure verification",
            has_timestamp=bool(sample_thumb.get('timestamp')),
            has_reason=bool(sample_thumb.get('reason')),
            has_rank=bool(sample_thumb.get('rank')),
            has_path=bool(sample_thumb.get('path')),
            total_thumbnails=len(ai_thumbnail_metadata)
        )
    
    # Store embeddings in the model if we have embeddings data
    if data.get('embeddings_generated') and 'data' in data:
        embeddings_data = data['data']
        logger.info("Found embeddings data, will be embedded in the model")
        
        # Update the model's embeddings attribute with the generated embeddings
        if embeddings_data:
            # Import the embeddings model
            from ...models import Embeddings
            
            # Extract image embeddings with correct keys (ranks 1, 2, 3)
            image_embeddings = embeddings_data.get('image_embeddings', {})
            
            # Create embeddings data object from the generated embeddings
            embeddings_obj = Embeddings(
                summary_embedding=embeddings_data.get('summary_embedding'),
                keyword_embedding=embeddings_data.get('keyword_embedding'),
                thumbnail_1_embedding=image_embeddings.get(1),  # Fixed: use rank 1
                thumbnail_2_embedding=image_embeddings.get(2),  # Fixed: use rank 2
                thumbnail_3_embedding=image_embeddings.get(3)   # Fixed: use rank 3
            )
            output_model.embeddings = embeddings_obj
            logger.info(f"Successfully embedded embeddings data in model. Thumbnail embeddings: {len([e for e in [image_embeddings.get(1), image_embeddings.get(2), image_embeddings.get(3)] if e is not None])}/3")
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
        
        # Prepare clip data for database (now handles simplified AI thumbnail metadata)
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