"""
Database storage step for the video ingest tool.

This module handles storing VideoIngestOutput models and associated data
(embeddings, thumbnails, etc.) to the DuckDB database.
"""

from typing import Any, Dict, Optional
from prefect import task
import structlog

logger = structlog.get_logger(__name__)

@task(tags=["database_storage_step"])
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
    from ...database.duckdb.schema import create_fts_index_for_clips
    
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
    # Updated to handle separate text and image embedding results
    text_embeddings_available = data.get('text_embeddings_generated', False)
    image_embeddings_available = data.get('image_embeddings_generated', False)
    
    embeddings_data = None
    
    if text_embeddings_available or image_embeddings_available:
        logger.info("Found embedding data from separate embedding steps")
        
        # Extract text embeddings if available
        # Text embeddings are now stored in 'text_embeddings_data' key
        summary_embedding = None
        keyword_embedding = None
        
        if text_embeddings_available:
            # Try to get text embeddings from the separate data key
            text_data = data.get('text_embeddings_data', {})
            if text_data and ('summary_embedding' in text_data or 'keyword_embedding' in text_data):
                summary_embedding = text_data.get('summary_embedding')
                keyword_embedding = text_data.get('keyword_embedding')
                logger.info("Extracted text embeddings from 'text_embeddings_data' key")
            else:
                logger.warning("text_embeddings_generated=True but no text embeddings found in 'text_embeddings_data' key")
        
        # Extract image embeddings if available  
        image_embedding_data = {}
        if image_embeddings_available:
            # Image embeddings are now stored in 'image_embeddings_data' key
            image_data = data.get('image_embeddings_data', {})
            if image_data and 'image_embeddings' in image_data:
                image_embedding_data = image_data.get('image_embeddings', {})
                logger.info("Extracted image embeddings from 'image_embeddings_data' key")
            else:
                logger.warning("image_embeddings_generated=True but no image embeddings found in 'image_embeddings_data' key")
            
        # Combine embeddings into the format expected by the model
        combined_embeddings = {
            'summary_embedding': summary_embedding,
            'keyword_embedding': keyword_embedding,
            'image_embeddings': image_embedding_data
        }
        
        embeddings_data = combined_embeddings
        
        # Update the model's embeddings attribute with the generated embeddings
        if embeddings_data and any([summary_embedding, keyword_embedding, image_embedding_data]):
            # Import the embeddings model
            from ...models import Embeddings
            
            # Create embeddings data object from the generated embeddings
            embeddings_obj = Embeddings(
                summary_embedding=summary_embedding,
                keyword_embedding=keyword_embedding,
                thumbnail_1_embedding=image_embedding_data.get(1),  # Use rank 1
                thumbnail_2_embedding=image_embedding_data.get(2),  # Use rank 2
                thumbnail_3_embedding=image_embedding_data.get(3)   # Use rank 3
            )
            output_model.embeddings = embeddings_obj
            
            # Log what we found
            text_count = sum(1 for e in [summary_embedding, keyword_embedding] if e is not None)
            image_count = len([e for e in [image_embedding_data.get(1), image_embedding_data.get(2), image_embedding_data.get(3)] if e is not None])
            logger.info(f"Successfully embedded embeddings data in model. Text embeddings: {text_count}/2, Image embeddings: {image_count}/3")
    else:
        logger.info("No embeddings data found from either text or image embedding steps, storing without embeddings")
    
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
            
            # Rebuild FTS index after successful upsert
            try:
                logger.info(f"Rebuilding FTS index for app_data.clips after upserting clip ID: {stored_clip_id}")
                create_fts_index_for_clips(conn)
                logger.info(f"Successfully rebuilt FTS index for app_data.clips.")
            except Exception as fts_e:
                logger.error(f"Failed to rebuild FTS index after upserting clip ID: {stored_clip_id}", error=str(fts_e), exc_info=True)
                # Decide if this is critical. For now, log error and continue.
                # The main operation (upsert) was successful.

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