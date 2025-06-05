"""
Category command class for API-friendly category operations.

This module provides the CategoryCommand class that handles operations
on video categories like listing, showing stats, and filtering clips by category.
"""

from typing import Dict, Any, Optional, List, Tuple
import structlog
from urllib.parse import unquote

from . import BaseCommand
from ..database.duckdb import connection as duckdb_connection
from ..database.duckdb import crud as duckdb_crud

logger = structlog.get_logger(__name__)


class CategoryCommand(BaseCommand):
    """Command class for category operations.
    
    Provides a standardized interface for category operations that can be
    used by both CLI and API endpoints.
    """
    
    def execute(self, action: str, **kwargs) -> Dict[str, Any]:
        """Execute category operation with dict args, return dict result.
        
        Args:
            action: Category action ('list', 'show')
            **kwargs: Action-specific parameters including:
                - category: Category name for 'show' action
                - limit: Max records to return (for clips)
                - offset: Records to skip (for clips)
                - filters: Additional filters to apply
                
        Returns:
            Dict containing category data, hierarchy, or clip lists
        """
        try:
            kwargs = self.validate_args(action, **kwargs)
            
            if action == 'list':
                return self.list_categories(**kwargs)
            elif action == 'show':
                return self.show_category(**kwargs)
            else:
                return {
                    "success": False,
                    "error": f"Unknown category action: {action}. Supported actions: 'list', 'show'."
                }
                
        except Exception as e:
            logger.error(f"Category command failed: {str(e)}")
            return {
                "success": False,
                "error": f"Category operation error: {str(e)}"
            }
    
    def validate_args(self, action: str, **kwargs) -> Dict[str, Any]:
        """Validate and clean arguments for category operations.
        
        Args:
            action: The category action being performed
            **kwargs: Raw command arguments
            
        Returns:
            Dict containing validated arguments
            
        Raises:
            ValueError: If required arguments are missing or invalid
        """
        if action == 'show':
            category = kwargs.get('category', '').strip()
            if not category:
                raise ValueError(f"category is required for '{action}' action")
            # URL decode the category path
            kwargs['category'] = unquote(category)
            
        # Validate numeric parameters
        for param in ['limit', 'offset']:
            if param in kwargs:
                try:
                    kwargs[param] = int(kwargs[param])
                    if kwargs[param] < 0:
                        raise ValueError(f"{param} must be non-negative")
                except (ValueError, TypeError):
                    raise ValueError(f"{param} must be a valid non-negative integer")
        
        # Set defaults
        kwargs.setdefault('limit', 50)
        kwargs.setdefault('offset', 0)
        
        return kwargs
    
    def list_categories(self, **kwargs) -> Dict[str, Any]:
        """List all categories with video counts and hierarchy.
        
        Returns:
            Dict containing categorized hierarchy with counts
        """
        try:
            conn = duckdb_connection.get_db_connection()
            
            # Get all categories from clips
            query = """
            SELECT 
                content_category,
                COUNT(*) as clip_count,
                AVG(duration_seconds) as avg_duration,
                SUM(file_size_bytes) as total_size,
                MIN(created_at) as earliest_clip,
                MAX(created_at) as latest_clip
            FROM app_data.clips 
            WHERE content_category IS NOT NULL 
              AND TRIM(content_category) != ''
            GROUP BY content_category
            ORDER BY content_category
            """
            
            result = conn.execute(query).fetchall()
            
            if not result:
                return {
                    "success": True,
                    "data": {
                        "categories": [],
                        "total_categories": 0,
                        "total_clips": 0
                    },
                    "message": "No categories found"
                }
            
            # Build category list with statistics
            categories = []
            total_clips = 0
            
            for category_name, clip_count, avg_duration, total_size, earliest, latest in result:
                if not category_name:
                    continue
                    
                category_data = {
                    "name": category_name,
                    "clip_count": clip_count,
                    "avg_duration_seconds": round(avg_duration, 2) if avg_duration else 0,
                    "total_size_bytes": total_size or 0,
                    "earliest_clip": earliest.isoformat() if earliest else None,
                    "latest_clip": latest.isoformat() if latest else None
                }
                
                # Handle hierarchical categories (split by /)
                if '/' in category_name:
                    parts = category_name.split('/')
                    category_data["parent"] = parts[0].strip()
                    category_data["subcategory"] = '/'.join(parts[1:]).strip()
                else:
                    category_data["parent"] = None
                    category_data["subcategory"] = None
                
                categories.append(category_data)
                total_clips += clip_count
            
            return {
                "success": True,
                "data": {
                    "categories": categories,
                    "total_categories": len(categories),
                    "total_clips": total_clips
                }
            }
            
        except Exception as e:
            logger.error(f"Error listing categories: {str(e)}")
            return {
                "success": False,
                "error": f"Failed to list categories: {str(e)}"
            }
    
    def show_category(self, category: str, limit: int = 50, offset: int = 0, **kwargs) -> Dict[str, Any]:
        """Show details for a specific category including clips.
        
        Args:
            category: Category name
            limit: Maximum clips to return
            offset: Number of clips to skip
            
        Returns:
            Dict containing category details and clips
        """
        try:
            conn = duckdb_connection.get_db_connection()
            
            # Get category statistics
            stats_query = """
            SELECT 
                COUNT(*) as total_clips,
                AVG(duration_seconds) as avg_duration,
                SUM(file_size_bytes) as total_size,
                MIN(created_at) as earliest_clip,
                MAX(created_at) as latest_clip
            FROM app_data.clips 
            WHERE content_category = ?
            """
            
            stats_result = conn.execute(stats_query, [category]).fetchone()
            
            if not stats_result or stats_result[0] == 0:
                return {
                    "success": False,
                    "error": f"Category '{category}' not found or has no clips"
                }
            
            response_data = {
                "category": category,
                "stats": {
                    "total_clips": stats_result[0],
                    "avg_duration_seconds": round(stats_result[1], 2) if stats_result[1] else 0,
                    "total_size_bytes": stats_result[2] or 0,
                    "earliest_clip": stats_result[3].isoformat() if stats_result[3] else None,
                    "latest_clip": stats_result[4].isoformat() if stats_result[4] else None
                }
            }
            
            # Get clips in this category
            clips_result = duckdb_crud.list_clips_advanced_duckdb(
                filters={"content_category": category},
                limit=limit,
                offset=offset,
                conn=conn
            )
            
            if clips_result["success"]:
                response_data["clips"] = clips_result["data"]
            else:
                logger.warning(f"Failed to fetch clips for category {category}: {clips_result.get('error')}")
                response_data["clips"] = {"clips": [], "pagination": {"total": 0, "limit": limit, "offset": offset}}
            
            return {
                "success": True,
                "data": response_data
            }
            
        except Exception as e:
            logger.error(f"Error showing category {category}: {str(e)}")
            return {
                "success": False,
                "error": f"Failed to show category: {str(e)}"
            }