"""
Embeddings generation step for the video ingest tool.

Registered as a step in the flows registry.

This module handles the generation and storage of vector embeddings
for video metadata to enable semantic search functionality.
"""

from typing import Any, Dict, List, Optional

from ...flows.registry import register_step
from prefect import task

@register_step(
    name="generate_embeddings", 
    enabled=True,  # Enabled by default
    description="Generate vector embeddings for semantic search"
)
@task
def generate_embeddings_step(data: Dict[str, Any], logger=None) -> Dict[str, Any]:
    """
    Generate and store vector embeddings for semantic search.
    
    Args:
        data: Pipeline data containing the output model, clip_id, and ai_thumbnail_metadata
        logger: Optional logger
        
    Returns:
        Dict with embedding generation results
    """
    from ...auth import AuthManager
    from ...embeddings import prepare_embedding_content, generate_embeddings, store_embeddings
    from ...embeddings_image import batch_generate_thumbnail_embeddings, generate_thumbnail_embedding
    
    # Check authentication
    auth_manager = AuthManager()
    if not auth_manager.get_current_session():
        if logger:
            logger.warning("Skipping embedding generation - not authenticated")
        return {
            'embeddings_skipped': True,
            'reason': 'not_authenticated'
        }
    
    # Get clip_id from database storage results
    clip_id = data.get('clip_id')
    if not clip_id:
        if logger:
            logger.error("No clip_id found for embedding generation")
        return {
            'embeddings_failed': True,
            'reason': 'no_clip_id'
        }
    
    # Get output model
    output = data.get('model')
    if not output:
        if logger:
            logger.error("No output model found for embedding generation")
        return {
            'embeddings_failed': True,
            'reason': 'no_output_model'
        }
    
    try:
        # Prepare embedding content using the existing function
        summary_content, keyword_content, metadata = prepare_embedding_content(output)
        
        if logger:
            logger.info(f"Prepared embedding content - Summary: {metadata['summary_tokens']} tokens, Keywords: {metadata['keyword_tokens']} tokens")
        
        # Generate embeddings
        summary_embedding, keyword_embedding = generate_embeddings(
            summary_content, keyword_content, logger
        )
        
        # Process AI thumbnail embeddings if available
        ai_thumbnail_metadata = data.get('ai_thumbnail_metadata', [])
        thumbnail_embeddings = {}
        thumbnail_descriptions = {}
        thumbnail_reasons = {}
        
        if ai_thumbnail_metadata:
            if logger:
                logger.info(f"Processing embeddings for {len(ai_thumbnail_metadata)} AI thumbnails")
                
            # Generate embeddings for all thumbnails
            thumbnail_embeddings = batch_generate_thumbnail_embeddings(
                ai_thumbnail_metadata,
                logger=logger
            )
            
            # Extract descriptions and reasons
            for thumbnail in ai_thumbnail_metadata:
                rank = thumbnail.get('rank')
                description = thumbnail.get('description')
                reason = thumbnail.get('reason')
                
                if rank and description:
                    thumbnail_descriptions[rank] = description
                
                if rank and reason:
                    thumbnail_reasons[rank] = reason
        
        # Store embeddings in database
        original_content = f"Summary: {summary_content}\nKeywords: {keyword_content}"
        store_embeddings(
            clip_id=clip_id,
            summary_embedding=summary_embedding,
            keyword_embedding=keyword_embedding,
            summary_content=summary_content,
            original_content=original_content,
            metadata=metadata,
            thumbnail_embeddings=thumbnail_embeddings,
            thumbnail_descriptions=thumbnail_descriptions,
            thumbnail_reasons=thumbnail_reasons,
            logger=logger
        )
        
        if logger:
            logger.info(f"Successfully generated and stored embeddings for clip: {clip_id}")
            if thumbnail_embeddings:
                logger.info(f"Generated and stored embeddings for {len(thumbnail_embeddings)} AI thumbnails")
        
        return {
            'embeddings_generated': True,
            'clip_id': clip_id,
            'summary_tokens': metadata['summary_tokens'],
            'keyword_tokens': metadata['keyword_tokens'],
            'thumbnail_embeddings_count': len(thumbnail_embeddings),
            'truncation_applied': metadata['summary_truncation'] != 'none' or metadata['keyword_truncation'] != 'none'
        }
        
    except Exception as e:
        if logger:
            logger.error(f"Embedding generation failed: {str(e)}")
        return {
            'embeddings_failed': True,
            'error': str(e)
        } 