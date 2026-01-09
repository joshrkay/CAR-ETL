"""
Supabase-backed implementations of storage interfaces.

These implementations use Supabase but are isolated behind interfaces
to maintain architectural boundaries.
"""
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone
from uuid import UUID
from supabase import Client

from src.connectors.google_drive.interfaces import (
    TokenStore,
    ConnectorConfigStore,
    SyncStateStore,
)

logger = logging.getLogger(__name__)


class SupabaseTokenStore(TokenStore):
    """Supabase implementation of TokenStore."""
    
    def __init__(self, supabase: Client):
        """
        Initialize token store.
        
        Args:
            supabase: Supabase client
        """
        self.supabase = supabase
    
    async def get_tokens(self, tenant_id: UUID, connector_id: UUID) -> Optional[Dict[str, Any]]:
        """Retrieve tokens from connector config."""
        result = (
            self.supabase.table("connectors")
            .select("config")
            .eq("id", str(connector_id))
            .eq("tenant_id", str(tenant_id))
            .maybe_single()
            .execute()
        )
        
        if not result.data:
            return None
        
        config = result.data.get("config", {})
        access_token = config.get("access_token")
        
        if not access_token:
            return None
        
        return {
            "access_token": access_token,
            "refresh_token": config.get("refresh_token"),
            "expires_at": config.get("expires_at"),
        }
    
    async def save_tokens(
        self,
        tenant_id: UUID,
        connector_id: UUID,
        access_token: str,
        refresh_token: Optional[str],
        expires_at: Optional[datetime],
    ) -> None:
        """Save tokens to connector config."""
        result = (
            self.supabase.table("connectors")
            .select("config")
            .eq("id", str(connector_id))
            .eq("tenant_id", str(tenant_id))
            .maybe_single()
            .execute()
        )
        
        if not result.data:
            raise ValueError(f"Connector {connector_id} not found")
        
        config = result.data.get("config", {})
        config["access_token"] = access_token
        if refresh_token:
            config["refresh_token"] = refresh_token
        if expires_at:
            config["expires_at"] = expires_at.isoformat()
        
        self.supabase.table("connectors").update({
            "config": config,
        }).eq("id", str(connector_id)).execute()
    
    async def mark_needs_reauth(self, tenant_id: UUID, connector_id: UUID) -> None:
        """Mark connector as needing re-authentication."""
        self.supabase.table("connectors").update({
            "status": "needs_reauth",
        }).eq("id", str(connector_id)).eq("tenant_id", str(tenant_id)).execute()


class SupabaseConnectorConfigStore(ConnectorConfigStore):
    """Supabase implementation of ConnectorConfigStore."""
    
    def __init__(self, supabase: Client):
        """
        Initialize config store.
        
        Args:
            supabase: Supabase client
        """
        self.supabase = supabase
    
    async def get_config(self, tenant_id: UUID, connector_id: UUID) -> Dict[str, Any]:
        """Retrieve connector configuration."""
        result = (
            self.supabase.table("connectors")
            .select("config")
            .eq("id", str(connector_id))
            .eq("tenant_id", str(tenant_id))
            .maybe_single()
            .execute()
        )
        
        if not result.data:
            raise ValueError(f"Connector {connector_id} not found")
        
        return result.data.get("config", {})
    
    async def save_config(
        self,
        tenant_id: UUID,
        connector_id: UUID,
        config: Dict[str, Any],
    ) -> None:
        """Save connector configuration."""
        self.supabase.table("connectors").update({
            "config": config,
        }).eq("id", str(connector_id)).eq("tenant_id", str(tenant_id)).execute()
    
    async def get_folder_ids(self, tenant_id: UUID, connector_id: UUID) -> List[str]:
        """Get selected folder IDs."""
        config = await self.get_config(tenant_id, connector_id)
        return config.get("folder_ids", [])
    
    async def set_folder_ids(
        self,
        tenant_id: UUID,
        connector_id: UUID,
        folder_ids: List[str],
    ) -> None:
        """Set selected folder IDs."""
        config = await self.get_config(tenant_id, connector_id)
        config["folder_ids"] = folder_ids
        await self.save_config(tenant_id, connector_id, config)
    
    async def get_shared_drive_ids(self, tenant_id: UUID, connector_id: UUID) -> List[str]:
        """Get shared drive IDs (empty list means all)."""
        config = await self.get_config(tenant_id, connector_id)
        return config.get("shared_drive_ids", [])


class SupabaseSyncStateStore(SyncStateStore):
    """Supabase implementation of SyncStateStore."""
    
    def __init__(self, supabase: Client):
        """
        Initialize sync state store.
        
        Args:
            supabase: Supabase client
        """
        self.supabase = supabase
    
    async def get_page_token(
        self,
        tenant_id: UUID,
        connector_id: UUID,
        drive_id: Optional[str],
    ) -> Optional[str]:
        """Get stored page token."""
        config = await self._get_config(tenant_id, connector_id)
        
        if drive_id:
            drive_tokens = config.get("drive_tokens", {})
            return drive_tokens.get(drive_id)
        
        return config.get("page_token")
    
    async def save_page_token(
        self,
        tenant_id: UUID,
        connector_id: UUID,
        page_token: str,
        drive_id: Optional[str],
    ) -> None:
        """Save page token."""
        config = await self._get_config(tenant_id, connector_id)
        
        if drive_id:
            if "drive_tokens" not in config:
                config["drive_tokens"] = {}
            config["drive_tokens"][drive_id] = page_token
        else:
            config["page_token"] = page_token
        
        await self._save_config(tenant_id, connector_id, config)
    
    async def update_last_sync(
        self,
        tenant_id: UUID,
        connector_id: UUID,
        status: str,
        error_message: Optional[str] = None,
    ) -> None:
        """Update last sync timestamp and status."""
        update_data = {
            "last_sync_at": datetime.now(timezone.utc).isoformat(),
            "status": status,
        }
        
        if error_message:
            config = await self._get_config(tenant_id, connector_id)
            config["last_sync_error"] = error_message
            update_data["config"] = config
        
        self.supabase.table("connectors").update(update_data).eq(
            "id", str(connector_id)
        ).eq("tenant_id", str(tenant_id)).execute()
    
    async def _get_config(self, tenant_id: UUID, connector_id: UUID) -> Dict[str, Any]:
        """Internal helper to get config."""
        result = (
            self.supabase.table("connectors")
            .select("config")
            .eq("id", str(connector_id))
            .eq("tenant_id", str(tenant_id))
            .maybe_single()
            .execute()
        )
        
        if not result.data:
            raise ValueError(f"Connector {connector_id} not found")
        
        return result.data.get("config", {})
    
    async def _save_config(
        self,
        tenant_id: UUID,
        connector_id: UUID,
        config: Dict[str, Any],
    ) -> None:
        """Internal helper to save config."""
        self.supabase.table("connectors").update({
            "config": config,
        }).eq("id", str(connector_id)).eq("tenant_id", str(tenant_id)).execute()
