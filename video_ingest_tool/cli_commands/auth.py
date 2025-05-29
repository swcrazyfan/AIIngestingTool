"""
Authentication command class for API-friendly auth operations.

This module provides the AuthCommand class that wraps the AuthManager
functionality in a standardized command interface for use by both
CLI and API.
"""

from typing import Dict, Any, Optional
import structlog

from . import BaseCommand
from ..auth import AuthManager

logger = structlog.get_logger(__name__)


class AuthCommand(BaseCommand):
    """Command class for authentication operations.
    
    Provides a standardized interface for auth operations that can be
    used by both CLI and API endpoints.
    """
    
    def __init__(self):
        """Initialize AuthCommand with AuthManager instance."""
        self.auth_manager = AuthManager()
    
    def execute(self, action: str, **kwargs) -> Dict[str, Any]:
        """Execute authentication action with dict args, return dict result.
        
        Args:
            action: The auth action to perform ('login', 'signup', 'logout', 'status')
            **kwargs: Action-specific arguments
            
        Returns:
            Dict containing the operation result
        """
        try:
            kwargs = self.validate_args(action=action, **kwargs)
            
            if action == 'login':
                return self.login(kwargs.get('email'), kwargs.get('password'))
            elif action == 'signup':
                return self.signup(kwargs.get('email'), kwargs.get('password'))
            elif action == 'logout':
                return self.logout()
            elif action == 'status':
                return self.get_status()
            else:
                raise ValueError(f"Unknown auth action: {action}")
        except Exception as e:
            logger.error(f"Auth command failed: {str(e)}", action=action)
            return {
                "success": False,
                "error": str(e)
            }
    
    def validate_args(self, action: str, **kwargs) -> Dict[str, Any]:
        """Validate and clean arguments for auth operations.
        
        Args:
            action: The auth action being performed
            **kwargs: Arguments to validate
            
        Returns:
            Cleaned and validated arguments
        """
        if action in ['login', 'signup']:
            email = kwargs.get('email')
            password = kwargs.get('password')
            
            if not email:
                raise ValueError("Email is required")
            if not password:
                raise ValueError("Password is required")
            
            # Basic email validation
            if '@' not in email or '.' not in email:
                raise ValueError("Invalid email format")
            
        return kwargs
    
    def login(self, email: str, password: str) -> Dict[str, Any]:
        """Login with email and password.
        
        Args:
            email: User email
            password: User password
            
        Returns:
            Dict with login result and user info
        """
        try:
            if self.auth_manager.login(email, password):
                session = self.auth_manager.get_current_session()
                return {
                    "success": True,
                    "message": "Login successful",
                    "user": {
                        "email": session.get('email'),
                        "user_id": session.get('user_id')
                    }
                }
            else:
                return {
                    "success": False,
                    "error": "Invalid email or password"
                }
        except ValueError as e:
            # Handle specific auth errors
            error_msg = str(e)
            if "Invalid login credentials" in error_msg:
                return {
                    "success": False,
                    "error": "Invalid email or password"
                }
            elif "Email not confirmed" in error_msg:
                return {
                    "success": False,
                    "error": "Please confirm your email before logging in"
                }
            else:
                return {
                    "success": False,
                    "error": error_msg
                }
    
    def signup(self, email: str, password: str) -> Dict[str, Any]:
        """Create a new account.
        
        Args:
            email: User email
            password: User password
            
        Returns:
            Dict with signup result
        """
        try:
            self.auth_manager.signup(email, password)
            return {
                "success": True,
                "message": "Account created successfully. Please check your email to confirm."
            }
        except ValueError as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    def logout(self) -> Dict[str, Any]:
        """Logout current user.
        
        Returns:
            Dict with logout result
        """
        success = self.auth_manager.logout()
        
        if success:
            return {
                "success": True,
                "message": "Successfully logged out"
            }
        else:
            return {
                "success": False,
                "error": "Logout failed"
            }
    
    def get_status(self) -> Dict[str, Any]:
        """Get current authentication status from session only.
        
        Returns:
            Dict with current auth status and user info
        """
        session = self.auth_manager.get_current_session()
        
        if session:
            # Just return what we have in the session - no database calls
            user_info = {
                "email": session.get('email'),
                "user_id": session.get('user_id')
            }
            
            return {
                "success": True,
                "authenticated": True,
                "user": user_info,
                "data": {
                    "authenticated": True,
                    "user": user_info
                }
            }
        else:
            return {
                "success": True,
                "authenticated": False,
                "user": None,
                "data": {
                    "authenticated": False,
                    "user": None
                }
            }
