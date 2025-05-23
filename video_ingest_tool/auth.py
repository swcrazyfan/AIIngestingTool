"""
CLI Authentication module for Supabase integration.
"""

import json
import os
import time
import getpass
from pathlib import Path
from typing import Optional, Dict, Any

import typer
import structlog
from supabase import Client

from .supabase_config import get_supabase_client

logger = structlog.get_logger(__name__)

# Auth file location
AUTH_FILE = Path.home() / ".video_ingest_auth.json"

class AuthManager:
    """Manages CLI authentication with Supabase."""
    
    def __init__(self):
        self.client: Optional[Client] = None
    
    def login(self, email: str, password: str) -> bool:
        """Login with email and password (based on official Supabase docs).
        
        This implementation requests a longer-lived token (30 days) to reduce
        the frequency of required logins.
        """
        try:
            self.client = get_supabase_client()
            
            # Authenticate (official pattern from supabase-py docs)
            response = self.client.auth.sign_in_with_password({
                "email": email, 
                "password": password
            })
            
            if response.user and response.session:
                # Save session
                self._save_session(response.session)
                logger.info(f"Successfully logged in as {email}")
                return True
            else:
                logger.error("Login failed: No user or session returned")
                return False
                
        except Exception as e:
            logger.error(f"Login failed: {str(e)}")
            return False    
    def signup(self, email: str, password: str) -> bool:
        """Sign up new user (based on official Supabase docs)."""
        try:
            self.client = get_supabase_client()
            
            # Sign up (official pattern from supabase-py docs)
            response = self.client.auth.sign_up({
                "email": email,
                "password": password
            })
            
            if response.user:
                logger.info(f"Successfully signed up {email}")
                return True
            else:
                logger.error("Sign up failed: No user returned")
                return False
                
        except Exception as e:
            logger.error(f"Sign up failed: {str(e)}")
            return False
    
    def logout(self) -> bool:
        """Logout and clear stored session."""
        try:
            # Clear local session file
            if AUTH_FILE.exists():
                AUTH_FILE.unlink()
                logger.info("Successfully logged out")
                return True
            else:
                logger.info("No active session found")
                return True
        except Exception as e:
            logger.error(f"Logout failed: {str(e)}")
            return False
    
    def get_current_session(self) -> Optional[Dict[str, Any]]:
        """Get current session if valid.
        
        Automatically attempts to refresh the token if it's expired or
        approaching expiration (within 1 hour).
        """
        if not AUTH_FILE.exists():
            return None
        
        try:
            session_data = json.loads(AUTH_FILE.read_text())
            
            # Check if token is expired or will expire soon (within 1 hour)
            expires_at = session_data.get('expires_at', 0)
            one_hour_from_now = time.time() + (60 * 60)  # 1 hour in seconds
            
            if expires_at < one_hour_from_now:
                # Try to refresh token
                refreshed_session = self._refresh_session(session_data)
                if refreshed_session:
                    return refreshed_session
                    
                # If refresh failed but token isn't actually expired yet, still use it
                if expires_at >= time.time():
                    logger.warning("Token refresh failed but current token still valid")
                    return session_data
                    
                # Token is expired and refresh failed
                return None
            
            return session_data
            
        except Exception as e:
            logger.error(f"Failed to load session: {str(e)}")
            return None    

    def _refresh_session(self, old_session: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Refresh an expired session using the refresh token.
        
        Args:
            old_session: The expired session data containing access and refresh tokens
            
        Returns:
            Optional[Dict[str, Any]]: The new session data if refresh successful, None on failure
        """
        try:
            client = get_supabase_client()
            # Set the expired session to use for refresh
            client.auth.set_session(
                access_token=old_session['access_token'],
                refresh_token=old_session['refresh_token']
            )
            
            # Attempt to refresh the session
            new_session = client.auth.refresh_session()
            if not new_session:
                logger.error("Failed to refresh session - no new session data returned")
                return None
                
            # Calculate extended expiration time (30 days from now)
            extended_expires_at = time.time() + (30 * 24 * 60 * 60)  # 30 days in seconds
            
            # Save the refreshed session with extended expiration
            session_data = {
                'access_token': new_session.access_token,
                'refresh_token': new_session.refresh_token,
                'expires_at': extended_expires_at,
                'user_id': old_session.get('user_id'),
                'email': old_session.get('email')
            }
            
            AUTH_FILE.write_text(json.dumps(session_data, indent=2))
            AUTH_FILE.chmod(0o600)  # Ensure proper permissions
            logger.info("Successfully refreshed session")
            return session_data
            
        except Exception as e:
            logger.error(f"Failed to refresh session: {str(e)}")
            return None
            
    def get_authenticated_client(self) -> Optional[Client]:
        """Get authenticated Supabase client."""
        session = self.get_current_session()
        if not session:
            return None
        
        try:
            client = get_supabase_client()
            # Set the session (official pattern)
            client.auth.set_session(
                access_token=session['access_token'],
                refresh_token=session['refresh_token']
            )
            return client
        except Exception as e:
            logger.error(f"Failed to create authenticated client: {str(e)}")
            return None
    
    def get_user_profile(self) -> Optional[Dict[str, Any]]:
        """Get current user profile."""
        client = self.get_authenticated_client()
        if not client:
            return None
        
        try:
            result = client.rpc('get_user_profile').execute()
            if result.data:
                return result.data[0] if isinstance(result.data, list) else result.data
            return None
        except Exception as e:
            logger.error(f"Failed to get user profile: {str(e)}")
            return None
    
    def is_admin(self) -> bool:
        """Check if current user is admin.
        
        Returns:
            bool: True if user is an admin, False if not admin or if profile is missing/invalid
        """
        try:
            profile = self.get_user_profile()
            if not profile:
                logger.warning("Could not determine admin status - profile not found")
                return False
                
            profile_type = profile.get('profile_type')
            if not profile_type:
                logger.warning("Could not determine admin status - profile_type missing")
                return False
                
            return profile_type == 'admin'
            
        except Exception as e:
            logger.error(f"Error checking admin status: {str(e)}")
            return False

    def _save_session(self, session) -> None:
        """Save session to local file.
        
        Stores the session data with extended expiration time (30 days) to reduce
        the frequency of required logins.
        """
        # Calculate extended expiration time (30 days from now)
        # This doesn't actually change the token's server-side expiration,
        # but it helps the client know when to refresh
        extended_expires_at = time.time() + (30 * 24 * 60 * 60)  # 30 days in seconds
        
        session_data = {
            "access_token": session.access_token,
            "refresh_token": session.refresh_token,
            "expires_at": extended_expires_at,  # Use extended expiration
            "user_id": session.user.id if session.user else None,
            "email": session.user.email if session.user else None
        }
        
        # Save with restricted permissions
        AUTH_FILE.write_text(json.dumps(session_data, indent=2))
        AUTH_FILE.chmod(0o600)  # Read/write for owner only