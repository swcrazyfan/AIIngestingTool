"""
Clips command class for API-friendly clip operations.

This module provides the ClipsCommand class that handles operations
on individual video clips like getting details, transcripts, analysis, etc.
"""

from typing import Dict, Any, Optional
import structlog

from . import BaseCommand

logger = structlog.get_logger(__name__)


class ClipsCommand(BaseCommand):
    """Command class for clip operations.
    
    Provides a standardized interface for clip operations that can be
    used by both CLI and API endpoints.
    """
    
    def execute(self, action: str, **kwargs) -> Dict[str, Any]:
        """Execute clip operation with dict args, return dict result.
        
        Args:
            action: Clip action ('show', 'transcript', 'analysis')
            **kwargs: Action-specific parameters including:
                - clip_id: ID of the clip (required for all actions)
                - show_transcript: Include transcript in response (for 'show')
                - show_analysis: Include analysis in response (for 'show')
                
        Returns:
            Dict containing the clip data and metadata
        """
        try:
            kwargs = self.validate_args(action, **kwargs)
            
            if action == 'show':
                return self.show_clip_details(**kwargs)
            elif action == 'transcript':
                return self.get_transcript(**kwargs)
            elif action == 'analysis':
                return self.get_analysis(**kwargs)
            else:
                return {
                    "success": False,
                    "error": f"Unknown clip action: {action}"
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
        # All clip operations require clip_id
        clip_id = kwargs.get('clip_id', '').strip()
        if not clip_id:
            raise ValueError("clip_id is required for clip operations")
        
        # Validate action-specific parameters
        if action == 'show':
            # show_transcript and show_analysis should be booleans
            show_transcript = kwargs.get('show_transcript', False)
            show_analysis = kwargs.get('show_analysis', False)
            
            if not isinstance(show_transcript, bool):
                kwargs['show_transcript'] = str(show_transcript).lower() in ['true', '1', 'yes']
            if not isinstance(show_analysis, bool):
                kwargs['show_analysis'] = str(show_analysis).lower() in ['true', '1', 'yes']
        
        return kwargs
    
    def show_clip_details(self, clip_id: str, show_transcript: bool = False, 
                         show_analysis: bool = False, **kwargs) -> Dict[str, Any]:
        """Get detailed information about a specific clip.
        
        Args:
            clip_id: ID of the clip to get details for
            show_transcript: Whether to include transcript in response
            show_analysis: Whether to include analysis in response
            
        Returns:
            Dict with clip details and optional transcript/analysis
        """
        try:
            from ..auth import AuthManager
            
            # Check authentication
            auth_manager = AuthManager()
            if not auth_manager.get_current_session():
                return {
                    "success": False,
                    "error": "Authentication required"
                }
            
            # Get authenticated client
            client = auth_manager.get_authenticated_client()
            
            # Get clip details
            clip_result = client.table('clips').select('*').eq('id', clip_id).execute()
            
            if not clip_result.data:
                return {
                    "success": False,
                    "error": "Clip not found"
                }
            
            clip = clip_result.data[0]
            response_data = {"clip": clip}
            
            # Get transcript if requested
            if show_transcript:
                transcript_result = client.table('transcripts').select('*').eq('clip_id', clip_id).execute()
                transcript = transcript_result.data[0] if transcript_result.data else None
                response_data["transcript"] = transcript
            
            # Get analysis if requested
            if show_analysis:
                analysis_result = client.table('analysis').select('*').eq('clip_id', clip_id).execute()
                analysis = analysis_result.data[0] if analysis_result.data else None
                response_data["analysis"] = analysis
            
            return {
                "success": True,
                "data": response_data
            }
            
        except Exception as e:
            logger.error(f"Show clip details failed: {str(e)}")
            return {
                "success": False,
                "error": f"Failed to get clip details: {str(e)}"
            }
    
    def get_transcript(self, clip_id: str, **kwargs) -> Dict[str, Any]:
        """Get transcript for a specific clip.
        
        Args:
            clip_id: ID of the clip to get transcript for
            
        Returns:
            Dict with transcript data
        """
        try:
            from ..auth import AuthManager
            
            # Check authentication
            auth_manager = AuthManager()
            if not auth_manager.get_current_session():
                return {
                    "success": False,
                    "error": "Authentication required"
                }
            
            # Get authenticated client
            client = auth_manager.get_authenticated_client()
            
            # Get transcript
            transcript_result = client.table('transcripts').select('*').eq('clip_id', clip_id).execute()
            transcript = transcript_result.data[0] if transcript_result.data else None
            
            if not transcript:
                return {
                    "success": False,
                    "error": "Transcript not found for this clip"
                }
            
            return {
                "success": True,
                "data": {"transcript": transcript}
            }
            
        except Exception as e:
            logger.error(f"Get transcript failed: {str(e)}")
            return {
                "success": False,
                "error": f"Failed to get transcript: {str(e)}"
            }
    
    def get_analysis(self, clip_id: str, **kwargs) -> Dict[str, Any]:
        """Get analysis for a specific clip.
        
        Args:
            clip_id: ID of the clip to get analysis for
            
        Returns:
            Dict with analysis data
        """
        try:
            from ..auth import AuthManager
            
            # Check authentication
            auth_manager = AuthManager()
            if not auth_manager.get_current_session():
                return {
                    "success": False,
                    "error": "Authentication required"
                }
            
            # Get authenticated client
            client = auth_manager.get_authenticated_client()
            
            # Get analysis
            analysis_result = client.table('analysis').select('*').eq('clip_id', clip_id).execute()
            analysis = analysis_result.data[0] if analysis_result.data else None
            
            if not analysis:
                return {
                    "success": False,
                    "error": "Analysis not found for this clip"
                }
            
            return {
                "success": True,
                "data": {"analysis": analysis}
            }
            
        except Exception as e:
            logger.error(f"Get analysis failed: {str(e)}")
            return {
                "success": False,
                "error": f"Failed to get analysis: {str(e)}"
            } 