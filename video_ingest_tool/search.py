"""
Search utilities for video catalog using hybrid search.

Provides functions for semantic search, full-text search, and hybrid search
combining both approaches using Reciprocal Rank Fusion (RRF).
"""

import os
from typing import List, Dict, Any, Optional, Tuple, Literal
import structlog

# AuthManager removed as authentication is being phased out for local DuckDB
# from .auth import AuthManager
from .embeddings import generate_embeddings
from .search_config import get_search_params
from .database.duckdb import connection as duckdb_connection # For DuckDB connection
from .database.duckdb import search_logic as duckdb_search_logic # For DuckDB search functions
from .database.duckdb import crud as duckdb_crud # For listing/filtering if needed

logger = structlog.get_logger(__name__)

def prepare_search_embeddings(query: str) -> Tuple[str, str]:
    """
    Prepare search query for embedding generation.
    
    Args:
        query: Search query text
        
    Returns:
        Tuple of (summary_content, keyword_content)
    """
    # For search queries, we use the query as both summary and keyword content
    # This ensures we get meaningful embeddings for comparison
    summary_content = f"Video content about: {query}"
    keyword_content = query
    
    return summary_content, keyword_content

SearchType = Literal["semantic", "fulltext", "hybrid", "transcripts", "similar"]
SortField = Literal["processed_at", "file_name", "duration_seconds", "created_at"]
SortOrder = Literal["ascending", "descending"]

class VideoSearcher:
    """
    Video search utility class for performing various types of searches.
    """
    
    def __init__(self):
        # self.auth_manager = AuthManager() # Removed
        pass # No specific initialization needed for now
    
    # _get_authenticated_client method removed
    # _get_current_user_id method removed
    
    def search(
        self,
        query: str,
        search_type: SearchType = "hybrid",
        match_count: int = 10,
        filters: Optional[Dict[str, Any]] = None, # Filters might be handled differently with DuckDB
        weights: Optional[Dict[str, float]] = None
    ) -> List[Dict[str, Any]]:
        """
        Perform search across video catalog using DuckDB.
        
        Args:
            query: Search query text
            search_type: Type of search to perform
            match_count: Number of results to return
            filters: Optional filters (TODO: define how these apply to DuckDB queries)
            weights: Optional search weights for hybrid search
            
        Returns:
            List of matching video clips with metadata
        """
        search_params = get_search_params(weights)
        
        # client = self._get_authenticated_client() # Removed
        # user_id = self._get_current_user_id() # Removed
        
        max_count = search_params.get('max_match_count', 100)
        if match_count > max_count:
            logger.warning(f"Requested match count {match_count} exceeds maximum {max_count}, limiting results")
            match_count = max_count
        
        # Connection will be established within each specific search method for now
        # or refactored to be passed if a single connection per VideoSearcher call is preferred.
        
        if search_type == "semantic":
            return self._semantic_search(query, match_count, search_params, filters) # client and user_id removed
        elif search_type == "fulltext":
            return self._fulltext_search(query, match_count, filters) # client and user_id removed
        elif search_type == "hybrid":
            return self._hybrid_search(query, match_count, search_params, filters) # client and user_id removed
        elif search_type == "transcripts":
            return self._transcript_search(query, match_count, filters) # client and user_id removed
        else:
            raise ValueError(f"Unsupported search type: {search_type}")
    
    def find_similar(
        self,
        clip_id: str,
        match_count: int = 5,
        similarity_threshold: Optional[float] = None
    ) -> List[Dict[str, Any]]:
        """
        Find clips similar to a given clip.
        
        Args:
            clip_id: ID of the source clip
            match_count: Number of similar clips to return
            similarity_threshold: Minimum similarity score (optional)
            
        Returns:
            List of similar clips
        """
        # Get parameters from centralized config
        search_params = get_search_params()
        
        # Use provided threshold or default from config
        threshold = similarity_threshold
        if threshold is None:
            threshold = search_params.get('similar_threshold', 0.65)
        
        try:
            with duckdb_connection.get_db_connection() as con:
                logger.info("Calling duckdb_search_logic.find_similar_clips_duckdb", source_clip_id=clip_id, match_count=match_count, threshold=threshold)
                results = duckdb_search_logic.find_similar_clips_duckdb(
                    con, # Pass con as positional argument
                    source_clip_id=clip_id,
                    match_count=match_count,
                    # Assuming the duckdb function handles the threshold internally or has a similar param
                    # The current duckdb_search_logic.find_similar_clips_duckdb signature might need adjustment
                    # if it expects different/more parameters (e.g. weights, mode) as per duckdb_migration_plan.md
                    # For now, passing what's available and aligns with the old RPC call's intent.
                    # The plan mentions: mode ('text' | 'visual' | 'combined'), various weights.
                    # These are not currently passed from SearchCommand.find_similar.
                    # This might be a point for future enhancement or alignment.
                    # Passing threshold directly if the duckdb function supports it.
                    # Let's assume it takes similarity_threshold for now.
                    similarity_threshold=threshold
                )
            return results
            
        except Exception as e:
            logger.error(f"Similar search failed with DuckDB: {str(e)}")
            raise
    
    def list_videos(
        self,
        sort_by: SortField = "processed_at",
        sort_order: SortOrder = "descending",
        limit: int = 20,
        offset: int = 0,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        List videos from the catalog with sorting and filtering.

        Args:
            sort_by: Field to sort by (e.g., 'processed_at', 'file_name').
            sort_order: 'ascending' or 'descending'.
            limit: Number of videos to return.
            offset: Offset for pagination.
            filters: Dictionary of filters to apply. 
                     Supported filters:
                        'date_start': ISO format string for processed_at >= value
                        'date_end': ISO format string for processed_at <= value

        Returns:
            List of video objects.
        """
        filters = filters or {}

        try:
            with duckdb_connection.get_db_connection() as con:
                logger.info("Calling duckdb_crud.list_clips_advanced_duckdb", sort_by=sort_by, sort_order=sort_order, limit=limit, offset=offset, filters=filters)
                results = duckdb_crud.list_clips_advanced_duckdb(
                    conn=con,
                    sort_by=sort_by,
                    sort_order=sort_order,
                    limit=limit,
                    offset=offset,
                    filters=filters
                )
            return results

        except Exception as e:
            logger.error("Failed to list videos with DuckDB", error=str(e), sort_by=sort_by, sort_order=sort_order, filters=filters)
            raise
    
    def _semantic_search(
        self,
        query: str,
        match_count: int,
        search_params: Dict[str, Any],
        filters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """Perform semantic search using vector embeddings with DuckDB."""
        summary_content, keyword_content = prepare_search_embeddings(query)
        
        query_summary_embedding, query_keyword_embedding = generate_embeddings(summary_content, keyword_content)
        
        duckdb_params = {
            'query_summary_embedding': query_summary_embedding,
            'query_keyword_embedding': query_keyword_embedding,
            'match_count': match_count,
            'summary_weight': search_params.get('summary_weight', 1.0),
            'keyword_weight': search_params.get('keyword_weight', 0.8),
            'similarity_threshold': search_params.get('similarity_threshold', 0.4)
            # Filters are not currently passed to duckdb_search_logic.semantic_search_clips_duckdb
        }

        try:
            logger.info("Performing DUCKDB semantic search",
                        limit=match_count,
                        query=query,
                        search_type="semantic",
                        weights={k: v for k, v in duckdb_params.items() if 'weight' in k or 'threshold' in k})
            
            with duckdb_connection.get_db_connection() as con:
                results = duckdb_search_logic.semantic_search_clips_duckdb(con, **duckdb_params) # Pass con as positional
            return results
            
        except Exception as e:
            logger.error(f"Semantic search failed with DuckDB: {str(e)}")
            raise
    
    def _fulltext_search(
        self,
        query: str,
        match_count: int,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """Perform full-text search with DuckDB."""
        try:
            logger.info("Performing DUCKDB full-text search", query=query, limit=match_count)
            with duckdb_connection.get_db_connection() as con:
                # Filters are not currently passed to duckdb_search_logic.fulltext_search_clips_duckdb
                results = duckdb_search_logic.fulltext_search_clips_duckdb(
                    query_text=query, # Correct order
                    conn=con,
                    match_count=match_count
                )
            return results
            
        except Exception as e:
            logger.error(f"Full-text search failed with DuckDB: {str(e)}")
            raise
    
    def _hybrid_search(
        self,
        query: str,
        match_count: int,
        search_params: Dict[str, Any],
        filters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """Perform hybrid search combining full-text and semantic search with DuckDB."""
        summary_content, keyword_content = prepare_search_embeddings(query)

        query_summary_embedding, query_keyword_embedding = generate_embeddings(summary_content, keyword_content)
        
        duckdb_params = {
            'query_text': query,
            'query_summary_embedding': query_summary_embedding,
            'query_keyword_embedding': query_keyword_embedding,
            'match_count': match_count,
            'fts_weight': search_params.get('fulltext_weight', 2.5), # Changed key from fulltext_weight to fts_weight
            'summary_weight': search_params.get('summary_weight', 1.0),
            'keyword_weight': search_params.get('keyword_weight', 0.8),
            'rrf_k': int(search_params.get('rrf_k', 50)), # Ensure rrf_k is int
            'similarity_threshold': search_params.get('similarity_threshold', 0.4)
            # Filters are not currently passed to duckdb_search_logic.hybrid_search_clips_duckdb
        }

        try:
            logger.info("Performing DUCKDB hybrid search",
                        limit=match_count,
                        query=query,
                        search_type="hybrid",
                        weights={k: v for k, v in duckdb_params.items()
                                 if 'weight' in k or 'threshold' in k or 'rrf_k' in k})
            
            with duckdb_connection.get_db_connection() as con:
                # Ensure 'conn' is not in duckdb_params to avoid conflict if it was accidentally added
                if 'conn' in duckdb_params:
                    logger.warning("Unexpected 'conn' in duckdb_params for hybrid_search, removing.")
                    del duckdb_params['conn']
                
                # Explicitly pass conn, then unpack other params.
                # hybrid_search_clips_duckdb expects: query_text, query_summary_embedding, query_keyword_embedding, conn, ...
                # duckdb_params contains query_text, query_summary_embedding, query_keyword_embedding, etc.
                
                # Extract query_text for positional argument, remove from duckdb_params to avoid duplication
                q_text = duckdb_params.pop('query_text')
                q_summary_emb = duckdb_params.pop('query_summary_embedding')
                q_keyword_emb = duckdb_params.pop('query_keyword_embedding')

                results = duckdb_search_logic.hybrid_search_clips_duckdb(
                    q_text,
                    q_summary_emb,
                    q_keyword_emb,
                    conn=con, # conn is now correctly passed to the 'conn' parameter
                    **duckdb_params # The rest of the params like match_count, weights, etc.
                )
            return results
            
        except Exception as e:
            logger.error(f"Hybrid search failed with DuckDB: {str(e)}")
            raise
    
    def _transcript_search(
        self,
        query: str,
        match_count: int,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """Perform search specifically on transcripts with DuckDB."""
        try:
            logger.info("Performing DUCKDB transcript search", query=query, limit=match_count)
            with duckdb_connection.get_db_connection() as con:
                # Filters are not currently passed to duckdb_search_logic.search_transcripts_duckdb
                results = duckdb_search_logic.search_transcripts_duckdb(
                    query_text=query, # Correct order
                    conn=con,
                    match_count=match_count
                )
            return results
            
        except Exception as e:
            logger.error(f"Transcript search failed with DuckDB: {str(e)}")
            raise
    
    # get_user_stats method removed as it's user-specific and not applicable to local DuckDB.


def format_search_results(
    results: List[Dict[str, Any]], 
    search_type: SearchType,
    show_scores: bool = True
) -> List[Dict[str, Any]]:
    """
    Format search results for display.
    
    Args:
        results: Raw search results
        search_type: Type of search performed
        show_scores: Whether to include similarity/ranking scores
        
    Returns:
        Formatted results for display
    """
    formatted_results = []
    
    for result in results:
        formatted = {
            'id': result.get('id'),
            'file_name': result.get('file_name'),
            'local_path': result.get('local_path'),
            'content_summary': result.get('content_summary'),
            'content_tags': result.get('content_tags', []),
            'duration_seconds': result.get('duration_seconds'),
            'camera_make': result.get('camera_make'),
            'camera_model': result.get('camera_model'),
            'content_category': result.get('content_category'),
            'processed_at': result.get('processed_at')
        }
        
        # Add search-specific fields
        if search_type == "semantic" and show_scores:
            formatted.update({
                'summary_similarity': result.get('summary_similarity'),
                'keyword_similarity': result.get('keyword_similarity'),
                'combined_similarity': result.get('combined_similarity')
            })
        elif search_type == "hybrid" and show_scores:
            formatted.update({
                'similarity_score': result.get('similarity_score'),
                'search_rank': result.get('search_rank'),
                'match_type': result.get('match_type')
            })
        elif search_type == "fulltext" and show_scores:
            formatted.update({
                'fts_rank': result.get('fts_rank')
            })
        elif search_type == "transcripts":
            formatted.update({
                'clip_id': result.get('clip_id'),
                'full_text': result.get('full_text'),
                'transcript_preview': result.get('transcript_preview'),
                'fts_rank': result.get('fts_rank') if show_scores else None
            })
        elif search_type == "similar" and show_scores:
            formatted.update({
                'similarity_score': result.get('similarity_score')
            })
        
        formatted_results.append(formatted)
    
    return formatted_results


def format_duration(seconds: float) -> str:
    """Format duration in seconds to human-readable format."""
    if not seconds:
        return "Unknown"
    
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    
    if hours > 0:
        return f"{hours}h {minutes}m {secs}s"
    elif minutes > 0:
        return f"{minutes}m {secs}s"
    else:
        return f"{secs}s"


def format_file_size(bytes_size: int) -> str:
    """Format file size in bytes to human-readable format."""
    if not bytes_size:
        return "Unknown"
    
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if bytes_size < 1024.0:
            return f"{bytes_size:.1f} {unit}"
        bytes_size /= 1024.0
    
    return f"{bytes_size:.1f} PB"