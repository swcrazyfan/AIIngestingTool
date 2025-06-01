"""
Embeddings generation step for the video ingest tool.

This module handles the generation and storage of vector embeddings
for video metadata to enable semantic search functionality.
"""

from typing import Any, Dict, List, Optional
from prefect import task

@task
def generate_embeddings_step(data: Dict[str, Any], logger=None) -> Dict[str, Any]:
    """
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
    from ...embeddings import prepare_embedding_content, generate_embeddings
    from ...embeddings_image import batch_generate_thumbnail_embeddings
    
    output_model = data.get('model')
    if not output_model:
        if logger:
            logger.error("No output model (VideoIngestOutput) found for embedding generation")
        return {
            'embeddings_failed': True,
            'reason': 'no_output_model'
        }
        
    ai_thumbnail_metadata = data.get('ai_thumbnail_metadata', [])
    
    embeddings_results = {
        'summary_embedding': None,
        'keyword_embedding': None,
        'image_embeddings': {},
        'metadata': {}
    }
    
    try:
        # 1. Prepare text content for summary and keyword embeddings
        if logger:
            logger.info("Starting embedding generation - preparing content")
        
        summary_content, keyword_content, prep_metadata = prepare_embedding_content(output_model)
        embeddings_results['metadata'].update(prep_metadata) # prep_metadata contains token counts and truncation for summary/keyword
        
        if logger:
            logger.info(
                f"Prepared embedding content - Summary: {prep_metadata.get('summary_tokens')} tokens, "
                f"Keywords: {prep_metadata.get('keyword_tokens')} tokens"
            )

        # 2. Generate summary and keyword embeddings
        # Ensure content is not empty before passing to generate_embeddings,
        # as the reverted generate_embeddings expects non-optional strings.
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

        embeddings_results['summary_embedding'] = s_emb
        embeddings_results['keyword_embedding'] = k_emb
        
        if logger:
            logger.info(f"Generated text embeddings - Summary: {len(s_emb) if s_emb else 0}D, Keyword: {len(k_emb) if k_emb else 0}D")
        
        # 3. Generate AI thumbnail/image embeddings
        # batch_generate_thumbnail_embeddings returns Dict[str, List[float]]
        # where key is thumbnail_path
        if logger:
            logger.info(f"Processing image embeddings for {len(ai_thumbnail_metadata) if ai_thumbnail_metadata else 0} AI thumbnails")
            
        if ai_thumbnail_metadata:
            image_embeddings_dict = batch_generate_thumbnail_embeddings(
                ai_thumbnail_metadata, # expects list of dicts with 'thumbnail_path'
                logger=logger
            )
            embeddings_results['image_embeddings'] = image_embeddings_dict
            embeddings_results['metadata']['thumbnail_embeddings_count'] = len(image_embeddings_dict)
            if logger:
                logger.info(f"Generated embeddings for {len(image_embeddings_dict)} AI thumbnails")
        else:
            embeddings_results['metadata']['thumbnail_embeddings_count'] = 0
            if logger:
                logger.info("No AI thumbnail metadata provided for embedding generation.")

        if logger:
            logger.info("Successfully generated all requested embeddings (summary, keyword, images).")
        
        return {
            'embeddings_generated': True,
            'data': embeddings_results
        }
        
    except Exception as e:
        error_msg = str(e)
        if logger:
            logger.error(f"Embedding generation failed with error: {error_msg}", exc_info=True)
        return {
            'embeddings_failed': True,
            'error': error_msg,
            'exception_type': type(e).__name__,
            'details': embeddings_results # return any partial results
        }