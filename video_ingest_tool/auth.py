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
        """Login with email and password (based on official Supabase docs)."""
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
        """Get current session if valid."""
        if not AUTH_FILE.exists():
            return None
        
        try:
            session_data = json.loads(AUTH_FILE.read_text())
            
            # Check if token is expired
            expires_at = session_data.get('expires_at', 0)
            if expires_at < time.time():
                # Try to refresh token
                return self._refresh_session(session_data)
            
            return session_data
            
        except Exception as e:
            logger.error(f"Failed to load session: {str(e)}")
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
        """Check if current user is admin."""
        profile = self.get_user_profile()
        return profile and profile.get('profile_type') == 'admin'
    
    def _save_session(self, session) -> None:
        """Save session to local file."""
        session_data = {
            "access_token": session.access_token,
            "refresh_token": session.refresh_token,
            "expires_at": session.expires_at,
            "user_id": session.user.id if session.user else None,
            "email": session.user.email if session.user else None
        }
        
        # Save with restricted permissions
        AUTH_FILE.write_text(json.dumps(session_data, indent=2))
        AUTH_FILE.chmod(0o600)  # Read/write for owner only