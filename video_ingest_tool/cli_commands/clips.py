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
            action: Clip action ('show', 'list', 'delete')
            **kwargs: Action-specific parameters including:
                - clip_id: ID of the clip (required for 'show', 'delete')
                - show_transcript: Include transcript in response (for 'show')
                - show_analysis: Include analysis in response (for 'show')
                - sort_by: Column to sort by (for 'list')
                - sort_order: 'asc' or 'desc' (for 'list')
                - limit: Max records (for 'list')
                - offset: Records to skip (for 'list')
                - filters: Dictionary of filters (for 'list')
                - confirm: Force confirmation for delete (for 'delete')
                
        Returns:
            Dict containing the clip data and metadata or list of clips
        """
        try:
            kwargs = self.validate_args(action, **kwargs)
            
            if action == 'show':
                return self.show_clip_details(**kwargs)
            elif action == 'list':
                return self.list_clips(**kwargs)
            elif action == 'delete':
                return self.delete_clip(**kwargs)
            # 'transcript' and 'analysis' actions removed as data is consolidated in 'show'
            else:
                return {
                    "success": False,
                    "error": f"Unknown clip action: {action}. Supported actions: 'show', 'list', 'delete'."
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
        if action in ['show', 'delete']:
            clip_id = kwargs.get('clip_id', '').strip()
            if not clip_id:
                raise ValueError(f"clip_id is required for '{action}' action")
            kwargs['clip_id'] = clip_id # Store stripped version
            
            if action == 'show':
                show_transcript = kwargs.get('show_transcript', False)
                show_analysis = kwargs.get('show_analysis', False)
            
                if not isinstance(show_transcript, bool):
                    kwargs['show_transcript'] = str(show_transcript).lower() in ['true', '1', 'yes']
                if not isinstance(show_analysis, bool):
                    kwargs['show_analysis'] = str(show_analysis).lower() in ['true', '1', 'yes']
            
            elif action == 'delete':
                confirm = kwargs.get('confirm', False)
                if not isinstance(confirm, bool):
                    kwargs['confirm'] = str(confirm).lower() in ['true', '1', 'yes']

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

    def delete_clip(self, clip_id: str, confirm: bool = False, **kwargs) -> Dict[str, Any]:
        """Delete a specific clip from the database.
        
        Args:
            clip_id: ID of the clip to delete
            confirm: Force confirmation for deletion
            
        Returns:
            Dict with success status and message
        """
        try:
            # First check if the clip exists
            with duckdb_connection.get_db_connection() as conn:
                clip_details = duckdb_crud.get_clip_details(clip_id=clip_id, conn=conn)
                
                if not clip_details:
                    return {
                        "success": False,
                        "error": "Clip not found"
                    }
                
                # For CLI usage, we might want to require confirmation
                # For API usage, the confirmation would typically come from the frontend
                if not confirm:
                    return {
                        "success": False,
                        "error": "Deletion requires confirmation. Set confirm=True to proceed.",
                        "requires_confirmation": True,
                        "clip": {
                            "id": clip_id,
                            "file_name": clip_details.get('file_name', 'Unknown'),
                            "duration_seconds": clip_details.get('duration_seconds', 0)
                        }
                    }
                
                # Attempt to delete the clip
                deletion_success = duckdb_crud.delete_clip_by_id(clip_id=clip_id, conn=conn)
                
                if deletion_success:
                    logger.info(f"Successfully deleted clip {clip_id} ({clip_details.get('file_name', 'Unknown')})")
                    return {
                        "success": True,
                        "message": f"Successfully deleted clip '{clip_details.get('file_name', clip_id)}'",
                        "data": {
                            "deleted_clip_id": clip_id,
                            "file_name": clip_details.get('file_name', 'Unknown')
                        }
                    }
                else:
                    return {
                        "success": False,
                        "error": "Failed to delete clip from database"
                    }
                    
        except Exception as e:
            logger.error(f"Delete clip failed: {str(e)}", exc_info=True)
            return {
                "success": False,
                "error": f"Failed to delete clip: {str(e)}"
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

    def add_re_analysis_command(self, subparsers):
        """Add re-analysis command for updating clip descriptions with consistent vocabulary."""
        reanalyze_parser = subparsers.add_parser(
            'reanalyze',
            help='Re-analyze existing clips with updated vocabulary for consistency'
        )
        reanalyze_parser.add_argument(
            '--clip-ids',
            nargs='+',
            help='Specific clip IDs to re-analyze (if not provided, will analyze clips with inconsistent descriptions)'
        )
        reanalyze_parser.add_argument(
            '--batch-size',
            type=int,
            default=5,
            help='Number of clips to process in parallel (default: 5)'
        )
        reanalyze_parser.add_argument(
            '--similarity-threshold',
            type=float,
            default=0.8,
            help='Similarity threshold for detecting inconsistent descriptions (default: 0.8)'
        )
        reanalyze_parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be re-analyzed without actually doing it'
        )
        reanalyze_parser.set_defaults(func=self.reanalyze_clips)

    def reanalyze_clips(self, args):
        """Re-analyze clips with consistent vocabulary."""
        from ..video_processor.analysis import VideoAnalyzer
        from ..database.duckdb_ops import DuckDBManager
        import os
        from concurrent.futures import ThreadPoolExecutor, as_completed
        
        # Initialize database connection
        db_manager = DuckDBManager()
        conn = db_manager.get_connection()
        
        # Get Gemini API key
        api_key = os.getenv('GEMINI_API_KEY')
        if not api_key:
            self.console.print("❌ GEMINI_API_KEY not found in environment", style="red")
            return
        
        # Initialize analyzer with database connection for reference examples
        analyzer = VideoAnalyzer(api_key=api_key, db_connection=conn)
        
        try:
            if args.clip_ids:
                # Re-analyze specific clips
                clip_ids = args.clip_ids
                clips_query = """
                SELECT id, file_path, content_summary, ai_selected_thumbnails_json 
                FROM app_data.clips 
                WHERE id = ANY(?)
                """
                clips = conn.execute(clips_query, [clip_ids]).fetchall()
            else:
                # Find clips that might need re-analysis (older or inconsistent descriptions)
                clips_query = """
                SELECT id, file_path, content_summary, ai_selected_thumbnails_json 
                FROM app_data.clips 
                WHERE content_summary IS NOT NULL 
                AND (
                    content_summary LIKE '%man%' OR 
                    content_summary LIKE '%woman%' OR
                    content_summary LIKE '%messy%' OR
                    content_summary LIKE '%long-sleeved%' OR
                    created_at < datetime('now', '-7 days')
                )
                ORDER BY created_at ASC
                LIMIT 20
                """
                clips = conn.execute(clips_query).fetchall()
            
            if not clips:
                self.console.print("No clips found for re-analysis", style="yellow")
                return
            
            self.console.print(f"Found {len(clips)} clips for potential re-analysis", style="blue")
            
            if args.dry_run:
                self.console.print("DRY RUN - Would re-analyze:", style="yellow")
                for clip_id, file_path, summary, _ in clips:
                    self.console.print(f"  • {clip_id}: {os.path.basename(file_path)}")
                    self.console.print(f"    Current: {summary[:80]}...")
                return
            
            # Re-analyze clips
            success_count = 0
            error_count = 0
            
            with ThreadPoolExecutor(max_workers=args.batch_size) as executor:
                # Submit analysis tasks
                future_to_clip = {
                    executor.submit(self._reanalyze_single_clip, analyzer, conn, clip_data): clip_data 
                    for clip_data in clips
                }
                
                # Process results as they complete
                for future in as_completed(future_to_clip):
                    clip_data = future_to_clip[future]
                    try:
                        result = future.result()
                        if result:
                            success_count += 1
                            self.console.print(f"✅ Re-analyzed: {os.path.basename(clip_data[1])}", style="green")
                        else:
                            error_count += 1
                            self.console.print(f"❌ Failed: {os.path.basename(clip_data[1])}", style="red")
                    except Exception as e:
                        error_count += 1
                        self.console.print(f"❌ Error: {os.path.basename(clip_data[1])} - {str(e)}", style="red")
            
            self.console.print(f"\n📊 Re-analysis complete:", style="blue")
            self.console.print(f"  • Success: {success_count}")
            self.console.print(f"  • Errors: {error_count}")
            
        except Exception as e:
            self.console.print(f"❌ Re-analysis failed: {str(e)}", style="red")
        finally:
            db_manager.close_connection()
    
    def _reanalyze_single_clip(self, analyzer, conn, clip_data):
        """Re-analyze a single clip and update the database."""
        clip_id, file_path, old_summary, old_thumbnails = clip_data
        
        try:
            # Check if file exists
            if not os.path.exists(file_path):
                self.console.print(f"⚠️  File not found: {file_path}", style="yellow")
                return False
            
            # Perform new analysis
            analysis_result = analyzer.analyze_video(file_path)
            
            if 'error' in analysis_result:
                return False
            
            # Extract updated fields
            new_summary = analysis_result.get('summary', {}).get('overall', '')
            new_condensed = analysis_result.get('summary', {}).get('condensed_summary', '')
            new_keywords = analysis_result.get('summary', {}).get('key_activities', [])
            new_thumbnails = analysis_result.get('visual_analysis', {}).get('keyframe_analysis', {}).get('recommended_thumbnails', [])
            
            # Update database
            update_query = """
            UPDATE app_data.clips 
            SET 
                content_summary = ?,
                condensed_summary = ?,
                content_tags = ?,
                ai_selected_thumbnails_json = ?,
                full_ai_analysis_json = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """
            
            import json
            conn.execute(update_query, [
                new_summary,
                new_condensed,
                json.dumps(new_keywords),
                json.dumps(new_thumbnails),
                json.dumps(analysis_result),
                clip_id
            ])
            
            return True
            
        except Exception as e:
            self.console.print(f"Error re-analyzing {clip_id}: {str(e)}", style="red")
            return False

    def setup_parsers(self, subparsers):
        """Set up the clips command parsers."""
        clips_parser = subparsers.add_parser('clips', help='Video clips management')
        clips_subparsers = clips_parser.add_subparsers(dest='clips_command')
        
        # List clips command
        list_parser = clips_subparsers.add_parser('list', help='List video clips')
        list_parser.add_argument('--limit', type=int, default=10, help='Number of clips to show')
        list_parser.add_argument('--offset', type=int, default=0, help='Offset for pagination')
        list_parser.add_argument('--format', choices=['table', 'json'], default='table', help='Output format')
        list_parser.add_argument('--sort-by', choices=['created_at', 'file_size', 'duration'], default='created_at', help='Sort by field')
        list_parser.add_argument('--sort-order', choices=['asc', 'desc'], default='desc', help='Sort order')
        list_parser.set_defaults(func=self.list_clips)
        
        # Show clip details command  
        show_parser = clips_subparsers.add_parser('show', help='Show detailed clip information')
        show_parser.add_argument('clip_id', help='Clip ID to show details for')
        show_parser.add_argument('--format', choices=['table', 'json'], default='table', help='Output format')
        show_parser.add_argument('--include-analysis', action='store_true', help='Include full AI analysis JSON')
        show_parser.set_defaults(func=self.show_clip)
        
        # Delete clip command
        delete_parser = clips_subparsers.add_parser('delete', help='Delete a clip and its files')
        delete_parser.add_argument('clip_id', help='Clip ID to delete')
        delete_parser.add_argument('--force', action='store_true', help='Skip confirmation prompt')
        delete_parser.add_argument('--keep-files', action='store_true', help='Keep video files, only remove from database')
        delete_parser.set_defaults(func=self.delete_clip)
        
        # Add re-analysis command
        self.add_re_analysis_command(clips_subparsers)