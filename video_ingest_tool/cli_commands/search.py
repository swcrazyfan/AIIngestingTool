"""
Search command class for API-friendly search operations.

This module provides the SearchCommand class that wraps the VideoSearcher
functionality in a standardized command interface for use by both
CLI and API.
"""

from typing import Dict, Any, Optional, List
import structlog

from . import BaseCommand
from ..search import VideoSearcher, format_search_results, SearchType, SortField, SortOrder

logger = structlog.get_logger(__name__)


class SearchCommand(BaseCommand):
    """Command class for search operations.
    
    Provides a standardized interface for search operations that can be
    used by both CLI and API endpoints.
    """
    
    def __init__(self):
        """Initialize SearchCommand with VideoSearcher instance."""
        self.searcher = VideoSearcher()
    
    def execute(self, **kwargs) -> Dict[str, Any]:
        """Execute search with dict args, return dict result.
        
        Args:
            **kwargs: Search parameters including:
                - query: Search query text (required for search operations)
                - search_type: Type of search ('semantic', 'fulltext', 'hybrid', 'transcripts', 'similar')
                - action: Search action ('search', 'list', 'similar', 'stats')
                - match_count/limit: Number of results to return
                - clip_id: For similar search
                - sort_by: For list operations
                - sort_order: For list operations
                - filters: Optional filters dict
                - weights: Optional search weights
                
        Returns:
            Dict containing the search results and metadata
        """
        try:
            kwargs = self.validate_args(**kwargs)
            action = kwargs.get('action', 'search')
            
            if action == 'search':
                return self.search(**kwargs)
            elif action == 'list':
                return self.list_videos(**kwargs)
            elif action == 'recent':
                return self.list_recent(**kwargs)
            elif action == 'similar':
                return self.find_similar(**kwargs)
            # 'stats' action removed as user-specific stats are being phased out
            else:
                return {
                    "success": False,
                    "error": f"Unknown search action: {action}"
                }
                
        except Exception as e:
            logger.error(f"Search command failed: {str(e)}")
            return {
                "success": False,
                "error": f"Search error: {str(e)}"
            }
    
    def validate_args(self, **kwargs) -> Dict[str, Any]:
        """Validate and clean arguments for search operations.
        
        Args:
            **kwargs: Raw command arguments
            
        Returns:
            Dict containing validated arguments
            
        Raises:
            ValueError: If required arguments are missing or invalid
        """
        action = kwargs.get('action', 'search')
        
        # Validate based on action
        if action == 'search':
            query = kwargs.get('query', '').strip()
            if not query:
                raise ValueError("Query is required for search operations")
            
            search_type_input = kwargs.get('search_type', 'hybrid').lower()
            
            # Map API/user-friendly search types to internal SearchType enum or recognized strings
            if search_type_input == 'all':
                kwargs['search_type'] = 'hybrid' # 'all' from API maps to 'hybrid'
            elif search_type_input == 'keyword':
                kwargs['search_type'] = 'fulltext' # 'keyword' from API maps to 'fulltext'
            elif search_type_input in ['semantic', 'fulltext', 'hybrid', 'transcripts']:
                kwargs['search_type'] = search_type_input # Already a valid internal type
            else:
                raise ValueError(f"Invalid search type: {search_type_input}. Valid types are 'all', 'keyword', 'semantic', 'fulltext', 'hybrid', 'transcripts'.")
                
        elif action == 'similar':
            clip_id = kwargs.get('clip_id', '').strip()
            if not clip_id:
                raise ValueError("clip_id is required for similar search")
                
        elif action == 'list':
            sort_by = kwargs.get('sort_by', 'processed_at')
            if sort_by not in ['processed_at', 'file_name', 'duration_seconds', 'created_at']:
                raise ValueError(f"Invalid sort_by field: {sort_by}")
                
            sort_order = kwargs.get('sort_order', 'descending')
            if sort_order not in ['ascending', 'descending']:
                raise ValueError(f"Invalid sort_order: {sort_order}")
        
        # Validate numeric parameters
        if 'match_count' in kwargs:
            try:
                kwargs['match_count'] = int(kwargs['match_count'])
                if kwargs['match_count'] <= 0:
                    raise ValueError("match_count must be positive")
            except (ValueError, TypeError):
                raise ValueError("match_count must be a positive integer")
                
        if 'limit' in kwargs:
            try:
                kwargs['limit'] = int(kwargs['limit'])
                if kwargs['limit'] <= 0:
                    raise ValueError("limit must be positive")
            except (ValueError, TypeError):
                raise ValueError("limit must be a positive integer")
                
        if 'offset' in kwargs:
            try:
                kwargs['offset'] = int(kwargs['offset'])
                if kwargs['offset'] < 0:
                    raise ValueError("offset must be non-negative")
            except (ValueError, TypeError):
                raise ValueError("offset must be a non-negative integer")
        
        return kwargs
    
    def search(self, query: str, search_type: str = 'hybrid',
               filters: Optional[Dict[str, Any]] = None, weights: Optional[Dict[str, float]] = None,
               limit: Optional[int] = None, # Added limit from kwargs
               match_count: Optional[int] = None, # Keep match_count for direct calls
               **kwargs) -> Dict[str, Any]:
        """Perform search operation.
        
        Args:
            query: Search query text
            search_type: Type of search to perform
            filters: Optional filters
            weights: Optional search weights
            limit: Number of results to return (often from API query params)
            match_count: Number of results to return (alternative to limit)
            
        Returns:
            Dict with search results and metadata
        """
        # Prioritize limit if provided (usually from API), else use match_count, else default.
        effective_match_count = limit if limit is not None else match_count if match_count is not None else 20

        try:
            results = self.searcher.search(
                query=query,
                search_type=search_type,
                match_count=effective_match_count,
                filters=filters,
                weights=weights
            )
            
            # Format results for API response
            formatted_results = format_search_results(results, search_type, show_scores=True)
            
            return {
                "success": True,
                "data": {
                    "results": formatted_results,
                    "total": len(formatted_results),
                    "query": query,
                    "search_type": search_type,
                    "match_count": effective_match_count
                }
            }
            
        except Exception as e:
            logger.error(f"Search failed: {str(e)}")
            return {
                "success": False,
                "error": f"Search failed: {str(e)}"
            }
    
    def list_videos(self, sort_by: str = 'processed_at', sort_order: str = 'descending',
                    limit: int = 20, offset: int = 0, filters: Optional[Dict[str, Any]] = None,
                    **kwargs) -> Dict[str, Any]:
        """List videos with sorting and filtering.
        
        Args:
            sort_by: Field to sort by
            sort_order: Sort order ('ascending' or 'descending')
            limit: Number of results to return
            offset: Offset for pagination
            filters: Optional filters
            
        Returns:
            Dict with video list and metadata
        """
        try:
            results = self.searcher.list_videos(
                sort_by=sort_by,
                sort_order=sort_order,
                limit=limit,
                offset=offset,
                filters=filters
            )
            
            return {
                "success": True,
                "data": {
                    "results": results,
                    "total": len(results),
                    "sort_by": sort_by,
                    "sort_order": sort_order,
                    "limit": limit,
                    "offset": offset
                }
            }
            
        except Exception as e:
            logger.error(f"List videos failed: {str(e)}")
            return {
                "success": False,
                "error": f"List videos failed: {str(e)}"
            }
    
    def find_similar(self, clip_id: str, match_count: int = 5, 
                     similarity_threshold: Optional[float] = None, **kwargs) -> Dict[str, Any]:
        """Find similar clips.
        
        Args:
            clip_id: ID of the source clip
            match_count: Number of similar clips to return
            similarity_threshold: Minimum similarity score
            
        Returns:
            Dict with similar clips and metadata
        """
        try:
            results = self.searcher.find_similar(
                clip_id=clip_id,
                match_count=match_count,
                similarity_threshold=similarity_threshold
            )
            
            # Format results for API response
            formatted_results = format_search_results(results, 'similar', show_scores=True)
            
            return {
                "success": True,
                "data": {
                    "results": formatted_results,
                    "total": len(formatted_results),
                    "clip_id": clip_id,
                    "match_count": match_count,
                    "similarity_threshold": similarity_threshold
                }
            }
            
        except Exception as e:
            logger.error(f"Similar search failed: {str(e)}")
            return {
                "success": False,
                "error": f"Similar search failed: {str(e)}"
            }
    
    def list_recent(self, limit: int = 20, **kwargs) -> Dict[str, Any]:
        """List recent videos (special case of list_videos sorted by processed_at desc).
        
        Args:
            limit: Number of recent videos to return
            
        Returns:
            Dict with recent videos and metadata
        """
        return self.list_videos(
            sort_by='processed_at',
            sort_order='descending', 
            limit=limit,
            offset=0,
            **kwargs
        )
    
    # get_stats method removed as user-specific stats are being phased out.
    # The corresponding 'stats' action has also been removed from the execute method.