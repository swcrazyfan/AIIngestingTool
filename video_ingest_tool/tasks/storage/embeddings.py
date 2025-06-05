"""
Embeddings generation step for the video ingest tool.

This module handles the generation and storage of vector embeddings
for video metadata to enable semantic search functionality.
"""

from typing import Any, Dict, List, Optional
from dotenv import load_dotenv
from prefect import task

# Load environment variables from .env file (required for Prefect workers)
load_dotenv()

@task
def generate_text_embeddings_step(data: Dict[str, Any], logger=None) -> Dict[str, Any]:
    """
    Generate vector embeddings for text content (summary and keywords) and return them.
    
    Args:
        data: Pipeline data containing the 'model' (VideoIngestOutput)
        logger: Optional logger
        
    Returns:
        A dictionary containing the generated text embeddings:
        {
            'text_embeddings_generated': bool,
            'data': {
                'summary_embedding': Optional[List[float]],
                'keyword_embedding': Optional[List[float]],
                'text_metadata': Dict[str, Any] # Token counts, truncation info
            }
        }
        or an error structure if failed.
    """
    from ...embeddings import prepare_embedding_content, generate_embeddings
    
    output_model = data.get('model')
    if not output_model:
        if logger:
            logger.error("No output model (VideoIngestOutput) found for text embedding generation")
        return {
            'text_embeddings_failed': True,
            'reason': 'no_output_model'
        }
    
    try:
        # Prepare text content for summary and keyword embeddings
        if logger:
            logger.info("Starting text embedding generation - preparing content")
        
        summary_content, keyword_content, prep_metadata = prepare_embedding_content(output_model)
        
        if logger:
            logger.info(
                f"Prepared embedding content - Summary: {prep_metadata.get('summary_tokens')} tokens, "
                f"Keywords: {prep_metadata.get('keyword_tokens')} tokens"
            )

        # Generate summary and keyword embeddings
        if logger:
            logger.info("Generating text embeddings")
            
        s_emb, k_emb = None, None
        if summary_content and keyword_content:
            s_emb, k_emb = generate_embeddings(
                summary_content,
                keyword_content,
                logger=logger
            )
        elif summary_content: # Only summary content available
             s_emb, _ = generate_embeddings(summary_content, "", logger=logger) # Pass empty string for keyword
             if logger: logger.warning("Keyword content was empty, generated keyword embedding from empty string.")
        elif keyword_content: # Only keyword content available
             _, k_emb = generate_embeddings("", keyword_content, logger=logger) # Pass empty string for summary
             if logger: logger.warning("Summary content was empty, generated summary embedding from empty string.")
        else:
            if logger:
                logger.warning("Both summary and keyword content are empty. Skipping text embedding generation.")

        if logger:
            logger.info(f"Generated text embeddings - Summary: {len(s_emb) if s_emb else 0}D, Keyword: {len(k_emb) if k_emb else 0}D")
        
        text_embeddings_results = {
            'summary_embedding': s_emb,
            'keyword_embedding': k_emb,
            'text_metadata': prep_metadata # Contains token counts and truncation info for summary/keyword
        }

        if logger:
            logger.info("Successfully generated text embeddings (summary, keyword).")
        
        return {
            'text_embeddings_generated': True,
            'data': text_embeddings_results
        }
        
    except Exception as e:
        error_msg = str(e)
        if logger:
            logger.error(f"Text embedding generation failed with error: {error_msg}", exc_info=True)
        return {
            'text_embeddings_failed': True,
            'error': error_msg,
            'exception_type': type(e).__name__
        }

@task
def generate_image_embeddings_step(data: Dict[str, Any], logger=None) -> Dict[str, Any]:
    """
    Generate vector embeddings for AI thumbnail images and return them.
    
    Args:
        data: Pipeline data containing 'ai_thumbnail_metadata'
        logger: Optional logger
        
    Returns:
        A dictionary containing the generated image embeddings:
        {
            'image_embeddings_generated': bool,
            'data': {
                'image_embeddings': Dict[str, List[float]], # thumbnail_path: embedding
                'image_metadata': Dict[str, Any] # Processing info
            }
        }
        or an error structure if failed.
    """
    from ...embeddings_image import batch_generate_thumbnail_embeddings
    
    ai_thumbnail_metadata = data.get('ai_thumbnail_metadata', [])
    
    try:
        # Generate AI thumbnail/image embeddings
        if logger:
            logger.info(f"Processing image embeddings for {len(ai_thumbnail_metadata) if ai_thumbnail_metadata else 0} AI thumbnails")
            
        image_embeddings_dict = {}
        thumbnail_count = 0
        
        if ai_thumbnail_metadata:
            image_embeddings_dict = batch_generate_thumbnail_embeddings(
                ai_thumbnail_metadata, # expects list of dicts with 'thumbnail_path'
                logger=logger
            )
            thumbnail_count = len(image_embeddings_dict)
            if logger:
                logger.info(f"Generated embeddings for {thumbnail_count} AI thumbnails")
        else:
            if logger:
                logger.info("No AI thumbnail metadata provided for embedding generation.")

        image_embeddings_results = {
            'image_embeddings': image_embeddings_dict,
            'image_metadata': {
                'thumbnail_embeddings_count': thumbnail_count
            }
        }

        if logger:
            logger.info("Successfully generated image embeddings for AI thumbnails.")
        
        return {
            'image_embeddings_generated': True,
            'data': image_embeddings_results
        }
        
    except Exception as e:
        error_msg = str(e)
        if logger:
            logger.error(f"Image embedding generation failed with error: {error_msg}", exc_info=True)
        return {
            'image_embeddings_failed': True,
            'error': error_msg,
            'exception_type': type(e).__name__
        }

# Keep the original function for backward compatibility, but mark as deprecated
@task
def generate_embeddings_step(data: Dict[str, Any], logger=None) -> Dict[str, Any]:
    """
    DEPRECATED: Use generate_text_embeddings_step and generate_image_embeddings_step instead.
    
    Generate vector embeddings for semantic search (summary, keyword, images) and return them.
    This version does not store embeddings directly but returns them for later processing.
    
    Args:
        data: Pipeline data containing the 'model' (VideoIngestOutput)
              and 'ai_thumbnail_metadata'.
        logger: Optional logger
        
    Returns:
        A dictionary containing the generated embeddings:
        {
            'summary_embedding': Optional[List[float]],
            'keyword_embedding': Optional[List[float]],
            'image_embeddings': Dict[str, List[float]], # thumbnail_path: embedding
            'metadata': Dict[str, Any] # Token counts, truncation info for summary/keyword
        }
        or an error structure if failed.
    """
    if logger:
        logger.warning("generate_embeddings_step is deprecated. Use generate_text_embeddings_step and generate_image_embeddings_step instead.")
    
    # Call both new steps and combine results
    text_result = generate_text_embeddings_step(data, logger)
    image_result = generate_image_embeddings_step(data, logger)
    
    # Check for failures
    if text_result.get('text_embeddings_failed') or image_result.get('image_embeddings_failed'):
        return {
            'embeddings_failed': True,
            'text_error': text_result.get('error') if text_result.get('text_embeddings_failed') else None,
            'image_error': image_result.get('error') if image_result.get('image_embeddings_failed') else None
        }
    
    # Combine successful results in the old format
    combined_results = {
        'summary_embedding': text_result['data'].get('summary_embedding'),
        'keyword_embedding': text_result['data'].get('keyword_embedding'),
        'image_embeddings': image_result['data'].get('image_embeddings', {}),
        'metadata': {
            **text_result['data'].get('text_metadata', {}),
            **image_result['data'].get('image_metadata', {})
        }
    }
    
    return {
        'embeddings_generated': True,
        'data': combined_results
    }