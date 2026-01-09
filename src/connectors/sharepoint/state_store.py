"""Temporary state storage for OAuth flows."""
import logging
from typing import Optional, Dict
from datetime import datetime, timedelta, timezone
from supabase import Client

logger = logging.getLogger(__name__)


class OAuthStateStore:
    """Stores OAuth state with tenant_id for callback validation."""
    
    def __init__(self, supabase: Client):
        """
        Initialize state store.
        
        Args:
            supabase: Supabase client (service role for cross-tenant access)
        """
        self.supabase = supabase
    
    async def store_state(
        self,
        state: str,
        tenant_id: str,
        expires_in_seconds: int = 600,
    ) -> None:
        """
        Store OAuth state with tenant_id.
        
        Args:
            state: OAuth state parameter
            tenant_id: Tenant identifier
            expires_in_seconds: State expiration time (default: 10 minutes)
        """
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in_seconds)
        
        try:
            self.supabase.table("oauth_states").insert({
                "state": state,
                "tenant_id": tenant_id,
                "expires_at": expires_at.isoformat(),
            }).execute()
        except Exception as e:
            logger.error("Failed to store OAuth state", exc_info=True)
            raise
    
    async def get_tenant_id(self, state: str) -> Optional[str]:
        """
        Retrieve tenant_id for OAuth state.
        
        Args:
            state: OAuth state parameter
            
        Returns:
            Tenant ID if state is valid and not expired, None otherwise
        """
        try:
            result = (
                self.supabase.table("oauth_states")
                .select("tenant_id, expires_at")
                .eq("state", state)
                .maybe_single()
                .execute()
            )
            
            if not result.data:
                return None
            
            expires_at = datetime.fromisoformat(result.data["expires_at"].replace("Z", "+00:00"))
            
            if datetime.now(timezone.utc) > expires_at:
                self.supabase.table("oauth_states").delete().eq("state", state).execute()
                return None
            
            tenant_id = result.data["tenant_id"]
            
            self.supabase.table("oauth_states").delete().eq("state", state).execute()
            
            return tenant_id
            
        except Exception as e:
            logger.error("Failed to retrieve OAuth state", exc_info=True)
            return None
