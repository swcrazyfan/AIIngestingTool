"""
Base command class and exports for CLI commands.

This module provides the BaseCommand abstract base class and exports
all command classes for use by CLI and API.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any


class BaseCommand(ABC):
    """Base class for all CLI commands that can be used by API.
    
    All command classes should inherit from this base class and implement
    the execute method to return standardized dictionary responses.
    """
    
    @abstractmethod
    def execute(self, **kwargs) -> Dict[str, Any]:
        """Execute command with dict args, return dict result.
        
        Args:
            **kwargs: Command-specific arguments
            
        Returns:
            Dict containing success status and either data or error message
            Format: {"success": bool, "data": Any} or {"success": bool, "error": str}
        """
        pass


# Import all command classes
# from .auth import AuthCommand # Removed as AuthCommand is deprecated
from .search import SearchCommand
from .ingest import IngestCommand
from .system import SystemCommand
from .clips import ClipsCommand

# Export all command classes
__all__ = [
    'BaseCommand',
    # 'AuthCommand',  # Removed
    'SearchCommand',
    'IngestCommand',
    'SystemCommand',
    'ClipsCommand'
]