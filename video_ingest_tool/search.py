"""
Search utilities for video catalog using hybrid search.

Provides functions for semantic search, full-text search, and hybrid search
combining both approaches using Reciprocal Rank Fusion (RRF).
"""

import os
from typing import List, Dict, Any, Optional, Tuple, Literal
import structlog

from .auth import AuthManager
from .embeddings import generate_embeddings
from .search_config import get_search_params

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
        self.auth_manager = AuthManager()
    
    def _get_authenticated_client(self):
        """Get authenticated Supabase client."""
        client = self.auth_manager.get_authenticated_client()
        if not client:
            raise ValueError("Authentication required for search operations")
        return client
    
    def _get_current_user_id(self):
        """Get current authenticated user ID."""
        session = self.auth_manager.get_current_session()
        if not session:
            raise ValueError("Authentication required")
        return session.get('user_id')
    
    def search(
        self,
        query: str,
        search_type: SearchType = "hybrid",
        match_count: int = 10,
        filters: Optional[Dict[str, Any]] = None,
        weights: Optional[Dict[str, float]] = None
    ) -> List[Dict[str, Any]]:
        """
        Perform search across video catalog.
        
        Args:
            query: Search query text
            search_type: Type of search to perform
            match_count: Number of results to return
            filters: Optional filters (camera_make, content_category, etc.)
            weights: Optional search weights for hybrid search
            
        Returns:
            List of matching video clips with metadata
        """
        # Get search parameters from centralized config, with optional overrides
        search_params = get_search_params(weights)
        
        client = self._get_authenticated_client()
        user_id = self._get_current_user_id()
        
        # Enforce max match count
        max_count = search_params.get('max_match_count', 100)
        if match_count > max_count:
            logger.warning(f"Requested match count {match_count} exceeds maximum {max_count}, limiting results")
            match_count = max_count
        
        if search_type == "semantic":
            return self._semantic_search(client, user_id, query, match_count, search_params)
        elif search_type == "fulltext":
            return self._fulltext_search(client, user_id, query, match_count)
        elif search_type == "hybrid":
            return self._hybrid_search(client, user_id, query, match_count, search_params)
        elif search_type == "transcripts":
            return self._transcript_search(client, user_id, query, match_count)
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
        
        client = self._get_authenticated_client()
        user_id = self._get_current_user_id()
        
        try:
            result = client.rpc('find_similar_clips', {
                'source_clip_id': clip_id,
                'user_id_filter': user_id,
                'match_count': match_count,
                'similarity_threshold': threshold
            }).execute()
            
            return result.data if result.data else []
            
        except Exception as e:
            logger.error(f"Similar search failed: {str(e)}")
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
        client = self._get_authenticated_client()
        user_id = self._get_current_user_id()
        filters = filters or {}

        try:
            query = client.from_("clips").select("*", count="exact").eq("user_id", user_id)

            # Apply filters
            if "date_start" in filters:
                query = query.gte("processed_at", filters["date_start"])
            if "date_end" in filters:
                query = query.lte("processed_at", filters["date_end"])
            
            # Add other specific field filters if needed, e.g.:
            # if "content_category" in filters:
            #     query = query.eq("content_category", filters["content_category"])

            is_descending = sort_order == "descending"
            query = query.order(sort_by, desc=is_descending).limit(limit).offset(offset)
            
            result = query.execute()
            return result.data if result.data else []

        except Exception as e:
            logger.error("Failed to list videos", error=str(e), sort_by=sort_by, sort_order=sort_order, filters=filters)
            # Optionally, re-raise or return an empty list based on desired error handling
            raise
    
    def _semantic_search(
        self,
        client,
        user_id: str,
        query: str,
        match_count: int,
        search_params: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Perform semantic search using vector embeddings."""
        summary_content, keyword_content = prepare_search_embeddings(query)
        
        # Call generate_embeddings once with both content types and unpack the tuple
        query_summary_embedding, query_keyword_embedding = generate_embeddings(summary_content, keyword_content)
        
        # Get parameters from the search_params dictionary
        rpc_params = {
            'p_query_summary_embedding': query_summary_embedding,
            'p_query_keyword_embedding': query_keyword_embedding,
            'p_user_id_filter': user_id,
            'p_match_count': match_count,
            'p_summary_weight': search_params.get('summary_weight', 1.0),
            'p_keyword_weight': search_params.get('keyword_weight', 0.8),
            'p_similarity_threshold': search_params.get('similarity_threshold', 0.4)
        }

        try:
            # Modified to avoid logging full embeddings
            logger.info("Performing semantic search", 
                        limit=match_count, 
                        query=query, 
                        search_type="semantic",
                        weights={k: v for k, v in search_params.items() if k in ['summary_weight', 'keyword_weight', 'similarity_threshold']})
            
            result = client.rpc('semantic_search_clips', rpc_params).execute()
            
            return result.data if result.data else []
            
        except Exception as e:
            logger.error(f"Semantic search failed: {str(e)}")
            raise
    
    def _fulltext_search(
        self,
        client,
        user_id: str,
        query: str,
        match_count: int
    ) -> List[Dict[str, Any]]:
        """Perform full-text search."""
        try:
            result = client.rpc('fulltext_search_clips', {
                'p_query_text': query,
                'p_user_id_filter': user_id,
                'p_match_count': match_count
            }).execute()
            
            return result.data if result.data else []
            
        except Exception as e:
            logger.error(f"Full-text search failed: {str(e)}")
            raise
    
    def _hybrid_search(
        self,
        client,
        user_id: str,
        query: str,
        match_count: int,
        search_params: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Perform hybrid search combining full-text and semantic search."""
        summary_content, keyword_content = prepare_search_embeddings(query)

        query_summary_embedding, query_keyword_embedding = generate_embeddings(summary_content, keyword_content)
        
        # Prepare parameters for the RPC call with 'p_' prefix
        rpc_params = {
            'p_query_text': query,
            'p_query_summary_embedding': query_summary_embedding,
            'p_query_keyword_embedding': query_keyword_embedding,
            'p_user_id_filter': user_id,
            'p_match_count': match_count,
            'p_fulltext_weight': search_params.get('fulltext_weight', 2.5),
            'p_summary_weight': search_params.get('summary_weight', 1.0),
            'p_keyword_weight': search_params.get('keyword_weight', 0.8),
            'p_rrf_k': int(search_params.get('rrf_k', 50)),
            'p_summary_threshold': search_params.get('similarity_threshold', 0.4),
            'p_keyword_threshold': search_params.get('similarity_threshold', 0.4)
        }

        try:
            # Modified to avoid logging full embeddings and log the parameters being used
            logger.info("Performing hybrid search", 
                        limit=match_count, 
                        query=query, 
                        search_type="hybrid",
                        weights={k: v for k, v in search_params.items() 
                                 if k in ['fulltext_weight', 'summary_weight', 'keyword_weight', 
                                         'rrf_k', 'similarity_threshold']})
            
            result = client.rpc('hybrid_search_clips', rpc_params).execute()

            return result.data if result.data else []
            
        except Exception as e:
            logger.error(f"Hybrid search failed: {str(e)}")
            raise
    
    def _transcript_search(
        self,
        client,
        user_id: str,
        query: str,
        match_count: int
    ) -> List[Dict[str, Any]]:
        """Perform search specifically on transcripts."""
        try:
            result = client.rpc('search_transcripts', {
                'query_text': query,
                'user_id_filter': user_id,
                'match_count': match_count,
                'min_content_length': 50
            }).execute()
            
            return result.data if result.data else []
            
        except Exception as e:
            logger.error(f"Transcript search failed: {str(e)}")
            raise
    
    def get_user_stats(self) -> Dict[str, Any]:
        """Get user statistics for the video catalog."""
        client = self._get_authenticated_client()
        
        try:
            result = client.rpc('get_user_stats').execute()
            return result.data[0] if result.data else {}
            
        except Exception as e:
            logger.error(f"Failed to get user stats: {str(e)}")
            return {}


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