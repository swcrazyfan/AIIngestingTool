"""
Clips command class for API-friendly clip operations.

This module provides the ClipsCommand class that handles operations
on individual video clips like getting details, transcripts, analysis, etc.
"""

from typing import Dict, Any, Optional
import structlog

from . import BaseCommand
from ..database.duckdb import connection as duckdb_connection
from ..database.duckdb import crud as duckdb_crud

logger = structlog.get_logger(__name__)


class ClipsCommand(BaseCommand):
    """Command class for clip operations.
    
    Provides a standardized interface for clip operations that can be
    used by both CLI and API endpoints.
    """
    
    def execute(self, action: str, **kwargs) -> Dict[str, Any]:
        """Execute clip operation with dict args, return dict result.
        
        Args:
            action: Clip action ('show', 'list')
            **kwargs: Action-specific parameters including:
                - clip_id: ID of the clip (required for 'show')
                - show_transcript: Include transcript in response (for 'show')
                - show_analysis: Include analysis in response (for 'show')
                - sort_by: Column to sort by (for 'list')
                - sort_order: 'asc' or 'desc' (for 'list')
                - limit: Max records (for 'list')
                - offset: Records to skip (for 'list')
                - filters: Dictionary of filters (for 'list')
                
        Returns:
            Dict containing the clip data and metadata or list of clips
        """
        try:
            kwargs = self.validate_args(action, **kwargs)
            
            if action == 'show':
                return self.show_clip_details(**kwargs)
            elif action == 'list':
                return self.list_clips(**kwargs)
            # 'transcript' and 'analysis' actions removed as data is consolidated in 'show'
            else:
                return {
                    "success": False,
                    "error": f"Unknown clip action: {action}. Supported actions: 'show', 'list'."
                }
                
        except Exception as e:
            logger.error(f"Clip command failed: {str(e)}")
            return {
                "success": False,
                "error": f"Clip operation error: {str(e)}"
            }
    
    def validate_args(self, action: str, **kwargs) -> Dict[str, Any]:
        """Validate and clean arguments for clip operations.
        
        Args:
            action: The clip action being performed
            **kwargs: Raw command arguments
            
        Returns:
            Dict containing validated arguments
            
        Raises:
            ValueError: If required arguments are missing or invalid
        """
        if action == 'show':
            clip_id = kwargs.get('clip_id', '').strip()
            if not clip_id:
                raise ValueError("clip_id is required for 'show' action")
            kwargs['clip_id'] = clip_id # Store stripped version
            
            show_transcript = kwargs.get('show_transcript', False)
            show_analysis = kwargs.get('show_analysis', False)
            
            if not isinstance(show_transcript, bool):
                kwargs['show_transcript'] = str(show_transcript).lower() in ['true', '1', 'yes']
            if not isinstance(show_analysis, bool):
                kwargs['show_analysis'] = str(show_analysis).lower() in ['true', '1', 'yes']

        elif action == 'list':
            kwargs['sort_by'] = kwargs.get('sort_by', 'created_at').strip()
            kwargs['sort_order'] = kwargs.get('sort_order', 'desc').strip().lower()
            if kwargs['sort_order'] not in ['asc', 'desc']:
                raise ValueError("sort_order must be 'asc' or 'desc'")
            
            try:
                kwargs['limit'] = int(kwargs.get('limit', 20))
                if kwargs['limit'] < 0: raise ValueError()
            except (ValueError, TypeError):
                raise ValueError("limit must be a non-negative integer")
            
            try:
                kwargs['offset'] = int(kwargs.get('offset', 0))
                if kwargs['offset'] < 0: raise ValueError()
            except (ValueError, TypeError):
                raise ValueError("offset must be a non-negative integer")

            filters = kwargs.get('filters')
            if filters is not None and not isinstance(filters, dict):
                try:
                    import json
                    filters = json.loads(filters) # Allow filters to be passed as JSON string
                    if not isinstance(filters, dict):
                        raise ValueError("filters must be a valid JSON object string or a dictionary")
                except (json.JSONDecodeError, TypeError):
                     raise ValueError("filters must be a valid JSON object string or a dictionary")
            kwargs['filters'] = filters # Store potentially parsed dict
        
        return kwargs
    
    def show_clip_details(self, clip_id: str, show_transcript: bool = False,
                         show_analysis: bool = False, **kwargs) -> Dict[str, Any]:
        """Get detailed information about a specific clip from DuckDB.
        Transcript and analysis data are part of the main clip record in DuckDB.
        The show_transcript and show_analysis flags can be used by the caller
        to decide how to present the data, but this method will fetch the full clip object.
        
        Args:
            clip_id: ID of the clip to get details for
            show_transcript: (Currently informational) Whether caller intends to show transcript
            show_analysis: (Currently informational) Whether caller intends to show analysis
            
        Returns:
            Dict with clip details
        """
        try:
            # AuthManager and client logic removed for DuckDB
            
            with duckdb_connection.get_db_connection() as conn:
                clip_details = duckdb_crud.get_clip_details(clip_id=clip_id, conn=conn)
            
            if not clip_details:
                return {
                    "success": False,
                    "error": "Clip not found"
                }
            
            # The clip_details from crud.get_clip_details already contains all data,
            # including what was previously in separate transcript/analysis tables.
            # For example, transcript might be in clip_details['full_transcript']
            # and AI analysis in clip_details['full_ai_analysis_json'].
            
            # The flags show_transcript and show_analysis are less about fetching
            # separate data now, and more about how the caller might want to structure
            # the final response from this command. For simplicity, we return the whole object.
            # The caller can then decide what to display.
            
            return {
                "success": True,
                "data": {"clip": clip_details}
            }
            
        except Exception as e:
            logger.error(f"Show clip details failed: {str(e)}", exc_info=True)
            return {
                "success": False,
                "error": f"Failed to get clip details: {str(e)}"
            }

    def list_clips(self, sort_by: str = "created_at", sort_order: str = "desc",
                   limit: int = 20, offset: int = 0,
                   filters: Optional[Dict[str, Any]] = None, **kwargs) -> Dict[str, Any]:
        """List clips with sorting, pagination, and filtering from DuckDB.
        
        Args:
            sort_by: Column name to sort by.
            sort_order: 'asc' or 'desc'.
            limit: Maximum number of records to return.
            offset: Number of records to skip.
            filters: Dictionary of filters to apply.
            
        Returns:
            Dict with list of clips or error.
        """
        try:
            with duckdb_connection.get_db_connection() as conn:
                clips_list = duckdb_crud.list_clips_advanced_duckdb(
                    conn=conn,
                    sort_by=sort_by,
                    sort_order=sort_order,
                    limit=limit,
                    offset=offset,
                    filters=filters
                )
            
            # To be consistent with other command outputs, we can also fetch total count
            # for pagination purposes, but this requires another query or modifying list_clips_advanced_duckdb.
            # For now, just returning the list.
            # A more advanced version could return:
            # { "success": True, "data": {"clips": clips_list, "total": total_count, "limit": limit, "offset": offset}}
            
            return {
                "success": True,
                "data": {"clips": clips_list, "limit": limit, "offset": offset, "filters": filters}
            }

        except Exception as e:
            logger.error(f"List clips failed: {str(e)}", exc_info=True)
            return {
                "success": False,
                "error": f"Failed to list clips: {str(e)}"
            }

    # get_transcript method removed as transcript data is now part of the main clip record.
    # Access via clip_details['full_transcript'] or clip_details['transcript_segments_json'].

    # get_analysis method removed as analysis data is now part of the main clip record.
    # Access via clip_details['full_ai_analysis_json'].