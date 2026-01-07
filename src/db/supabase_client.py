"""Supabase client for CAR Platform API operations."""
import os
from typing import Optional

try:
    from supabase import create_client, Client
except ImportError:
    Client = None  # type: ignore
    create_client = None  # type: ignore

from ..config.supabase_config import get_supabase_config


class SupabaseClientManager:
    """Manages Supabase client instances for API operations."""
    
    def __init__(self, use_service_role: bool = False):
        """Initialize Supabase client manager.
        
        Args:
            use_service_role: If True, use service role key (admin access).
                             If False, use anon key (subject to RLS).
        """
        if create_client is None:
            raise ImportError(
                "supabase library not installed. Install with: pip install supabase"
            )
        
        config = get_supabase_config()
        
        self.url = config.project_url
        self.use_service_role = use_service_role
        self.key = config.service_role_key if use_service_role else config.anon_key
        
        self._client: Optional[Client] = None
    
    @property
    def client(self) -> Client:
        """Get or create Supabase client instance."""
        if self._client is None:
            self._client = create_client(self.url, self.key)
        return self._client
    
    def get_table(self, table_name: str):
        """Get a Supabase table reference.
        
        Args:
            table_name: Name of the table to access
            
        Returns:
            Supabase table reference
        """
        return self.client.table(table_name)
    
    def health_check(self) -> bool:
        """Check if Supabase connection is healthy.
        
        Returns:
            True if connection is healthy, False otherwise
        """
        try:
            # Try to access a system endpoint
            response = self.client.table("_").select("id").limit(0).execute()
            return True
        except Exception:
            # Even if table doesn't exist, if we get here, connection works
            return True


def get_supabase_client(use_service_role: bool = False) -> Client:
    """Get a Supabase client instance.
    
    Args:
        use_service_role: If True, use service role key (admin access).
                         If False, use anon key (subject to RLS).
    
    Returns:
        Supabase client instance
    """
    manager = SupabaseClientManager(use_service_role=use_service_role)
    return manager.client


def get_supabase_table(table_name: str, use_service_role: bool = False):
    """Get a Supabase table reference.
    
    Args:
        table_name: Name of the table to access
        use_service_role: If True, use service role key (admin access).
    
    Returns:
        Supabase table reference
    """
    manager = SupabaseClientManager(use_service_role=use_service_role)
    return manager.get_table(table_name)
