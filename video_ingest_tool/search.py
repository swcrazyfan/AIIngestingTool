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
        client = self._get_authenticated_client()
        user_id = self._get_current_user_id()
        
        if search_type == "semantic":
            return self._semantic_search(client, user_id, query, match_count, weights)
        elif search_type == "fulltext":
            return self._fulltext_search(client, user_id, query, match_count)
        elif search_type == "hybrid":
            return self._hybrid_search(client, user_id, query, match_count, weights)
        elif search_type == "transcripts":
            return self._transcript_search(client, user_id, query, match_count)
        else:
            raise ValueError(f"Unsupported search type: {search_type}")
    
    def find_similar(
        self,
        clip_id: str,
        match_count: int = 5,
        similarity_threshold: float = 0.5
    ) -> List[Dict[str, Any]]:
        """
        Find clips similar to a given clip.
        
        Args:
            clip_id: ID of the source clip
            match_count: Number of similar clips to return
            similarity_threshold: Minimum similarity score
            
        Returns:
            List of similar clips
        """
        client = self._get_authenticated_client()
        user_id = self._get_current_user_id()
        
        try:
            result = client.rpc('find_similar_clips', {
                'source_clip_id': clip_id,
                'user_id_filter': user_id,
                'match_count': match_count,
                'similarity_threshold': similarity_threshold
            }).execute()
            
            return result.data if result.data else []
            
        except Exception as e:
            logger.error(f"Similar search failed: {str(e)}")
            raise
    
    def _semantic_search(
        self,
        client,
        user_id: str,
        query: str,
        match_count: int,
        weights: Optional[Dict[str, float]] = None
    ) -> List[Dict[str, Any]]:
        """Perform semantic search using vector embeddings."""
        try:
            # Prepare content for embedding
            summary_content, keyword_content = prepare_search_embeddings(query)
            
            # Generate embeddings
            summary_embedding, keyword_embedding = generate_embeddings(
                summary_content, keyword_content, logger
            )
            
            # Set default weights (only semantic search parameters)
            search_params = {
                'summary_weight': weights.get('summary_weight', 1.0) if weights else 1.0,
                'keyword_weight': weights.get('keyword_weight', 0.8) if weights else 0.8,
                'similarity_threshold': weights.get('similarity_threshold', 0.0) if weights else 0.0
            }
            
            # Execute semantic search
            result = client.rpc('semantic_search_clips', {
                'query_summary_embedding': summary_embedding,
                'query_keyword_embedding': keyword_embedding,
                'user_id_filter': user_id,
                'match_count': match_count,
                **search_params
            }).execute()
            
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
                'query_text': query,
                'user_id_filter': user_id,
                'match_count': match_count
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
        weights: Optional[Dict[str, float]] = None
    ) -> List[Dict[str, Any]]:
        """Perform hybrid search combining full-text and semantic search."""
        try:
            # Prepare content for embedding
            summary_content, keyword_content = prepare_search_embeddings(query)
            
            # Generate embeddings
            summary_embedding, keyword_embedding = generate_embeddings(
                summary_content, keyword_content, logger
            )
            
            # Set default weights for RRF
            search_params = {
                'fulltext_weight': weights.get('fulltext_weight', 1.0) if weights else 1.0,
                'summary_weight': weights.get('summary_weight', 1.0) if weights else 1.0,
                'keyword_weight': weights.get('keyword_weight', 0.8) if weights else 0.8,
                'rrf_k': weights.get('rrf_k', 50) if weights else 50
            }
            
            # Execute hybrid search
            result = client.rpc('hybrid_search_clips', {
                'query_text': query,
                'query_summary_embedding': summary_embedding,
                'query_keyword_embedding': keyword_embedding,
                'user_id_filter': user_id,
                'match_count': match_count,
                **search_params
            }).execute()
            
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