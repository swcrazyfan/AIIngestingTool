"""
Supabase configuration and client management for AI Ingesting Tool.
"""

import os
from typing import Optional
from supabase import create_client, Client
from supabase.client import ClientOptions
import structlog
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

logger = structlog.get_logger(__name__)

# Load environment variables
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

def get_supabase_client(use_service_role: bool = False) -> Client:
    """
    Get Supabase client instance.
    
    Args:
        use_service_role: Use service role key instead of anon key
        
    Returns:
        Configured Supabase client
        
    Raises:
        ValueError: If required environment variables are not set
    """
    if not SUPABASE_URL:
        raise ValueError("SUPABASE_URL environment variable not set")
    
    key = SUPABASE_SERVICE_ROLE_KEY if use_service_role else SUPABASE_ANON_KEY
    if not key:
        key_type = "SUPABASE_SERVICE_ROLE_KEY" if use_service_role else "SUPABASE_ANON_KEY"
        raise ValueError(f"{key_type} environment variable not set")
    
    # Configure client options (based on official docs)
    options = ClientOptions(
        auto_refresh_token=True,
        persist_session=True
    )
    
    client = create_client(SUPABASE_URL, key, options)
    return client
def verify_connection() -> bool:
    """
    Verify connection to Supabase.
    
    Returns:
        True if connection successful
    """
    try:
        client = get_supabase_client()
        # Test connection with a simple query to check if we can reach the database
        result = client.table('user_profiles').select('count').execute()
        logger.info("Supabase connection verified")
        return True
    except Exception as e:
        logger.error(f"Supabase connection failed: {str(e)}")
        return False

def get_database_status() -> dict:
    """
    Get database status and basic information.
    
    Returns:
        Dictionary with database status information
    """
    try:
        client = get_supabase_client()
        
        # Check if core tables exist
        tables_to_check = ['user_profiles', 'clips', 'segments', 'analysis', 'vectors', 'transcripts']
        table_status = {}
        
        for table in tables_to_check:
            try:
                result = client.table(table).select('count').execute()
                table_status[table] = 'exists'
            except Exception:
                table_status[table] = 'missing'
        
        return {
            'connection': 'success',
            'tables': table_status,
            'url': SUPABASE_URL
        }
    except Exception as e:
        return {
            'connection': 'failed',
            'error': str(e),
            'url': SUPABASE_URL
        }
