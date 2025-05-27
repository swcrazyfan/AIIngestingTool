"""
Generate vector embeddings for semantic search.

This module handles the generation and storage of vector embeddings
for video metadata to enable semantic search functionality.
"""

from typing import Any, Dict

from ...pipeline.registry import register_step

@register_step(
    name="generate_embeddings", 
    enabled=False,  # Disabled by default
    description="Generate vector embeddings for semantic search"
)
def generate_embeddings_step(data: Dict[str, Any], logger=None) -> Dict[str, Any]:
    """
    Generate and store vector embeddings for semantic search.
    
    Args:
        data: Pipeline data containing the output model and clip_id
        logger: Optional logger
        
    Returns:
        Dict with embedding generation results
    """
    from ...auth import AuthManager
    from ...embeddings import prepare_embedding_content, generate_embeddings, store_embeddings
    
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
    output = data.get('output')
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
        
        # Store embeddings in database
        original_content = f"Summary: {summary_content}\nKeywords: {keyword_content}"
        store_embeddings(
            clip_id=clip_id,
            summary_embedding=summary_embedding,
            keyword_embedding=keyword_embedding,
            summary_content=summary_content,
            keyword_content=keyword_content,
            original_content=original_content,
            metadata=metadata,
            logger=logger
        )
        
        if logger:
            logger.info(f"Successfully generated and stored embeddings for clip: {clip_id}")
        
        return {
            'embeddings_generated': True,
            'clip_id': clip_id,
            'summary_tokens': metadata['summary_tokens'],
            'keyword_tokens': metadata['keyword_tokens'],
            'truncation_applied': metadata['summary_truncation'] != 'none' or metadata['keyword_truncation'] != 'none'
        }
        
    except Exception as e:
        if logger:
            logger.error(f"Embedding generation failed: {str(e)}")
        return {
            'embeddings_failed': True,
            'error': str(e)
        } 