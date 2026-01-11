"""
Supabase-backed implementations of storage interfaces.

These implementations use Supabase but are isolated behind interfaces
to maintain architectural boundaries.
"""
import logging
from datetime import UTC, datetime
from typing import Any, cast
from uuid import UUID

from src.connectors.google_drive.interfaces import (
    ConnectorConfigStore,
    SyncStateStore,
    TokenStore,
)
from supabase import Client

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

    async def get_tokens(self, tenant_id: UUID, connector_id: UUID) -> dict[str, Any] | None:
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

        # Type narrowing: result.data is not None after the check above
        assert result.data is not None
        data = cast(dict[str, Any], result.data)
        config = cast(dict[str, Any], data.get("config", {}))
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
        refresh_token: str | None,
        expires_at: datetime | None,
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

        # Type narrowing: result.data is not None after the check above
        assert result.data is not None
        data = cast(dict[str, Any], result.data)
        config = cast(dict[str, Any], data.get("config", {}))
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

    async def get_config(self, tenant_id: UUID, connector_id: UUID) -> dict[str, Any]:
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

        # Type narrowing: result.data is not None after the check above
        assert result.data is not None
        data = cast(dict[str, Any], result.data)
        config = data.get("config", {})
        return cast(dict[str, Any], config)

    async def save_config(
        self,
        tenant_id: UUID,
        connector_id: UUID,
        config: dict[str, Any],
    ) -> None:
        """Save connector configuration."""
        self.supabase.table("connectors").update({
            "config": config,
        }).eq("id", str(connector_id)).eq("tenant_id", str(tenant_id)).execute()

    async def get_folder_ids(self, tenant_id: UUID, connector_id: UUID) -> list[str]:
        """Get selected folder IDs."""
        config = await self.get_config(tenant_id, connector_id)
        folder_ids = config.get("folder_ids", [])
        return cast(list[str], folder_ids)

    async def set_folder_ids(
        self,
        tenant_id: UUID,
        connector_id: UUID,
        folder_ids: list[str],
    ) -> None:
        """Set selected folder IDs."""
        config = await self.get_config(tenant_id, connector_id)
        config["folder_ids"] = folder_ids
        await self.save_config(tenant_id, connector_id, config)

    async def get_shared_drive_ids(self, tenant_id: UUID, connector_id: UUID) -> list[str]:
        """Get shared drive IDs (empty list means all)."""
        config = await self.get_config(tenant_id, connector_id)
        drive_ids = config.get("shared_drive_ids", [])
        return cast(list[str], drive_ids)


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
        drive_id: str | None,
    ) -> str | None:
        """Get stored page token."""
        config = await self._get_config(tenant_id, connector_id)

        if drive_id:
            drive_tokens = config.get("drive_tokens", {})
            token = drive_tokens.get(drive_id) if isinstance(drive_tokens, dict) else None
            return cast(str | None, token)

        return config.get("page_token")

    async def save_page_token(
        self,
        tenant_id: UUID,
        connector_id: UUID,
        page_token: str,
        drive_id: str | None,
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
        error_message: str | None = None,
    ) -> None:
        """Update last sync timestamp and status."""
        update_data: dict[str, Any] = {
            "last_sync_at": datetime.now(UTC).isoformat(),
            "status": status,
        }

        if error_message:
            config_dict = await self._get_config(tenant_id, connector_id)
            config_dict["last_sync_error"] = error_message
            update_data["config"] = config_dict

        self.supabase.table("connectors").update(update_data).eq(
            "id", str(connector_id)
        ).eq("tenant_id", str(tenant_id)).execute()

    async def _get_config(self, tenant_id: UUID, connector_id: UUID) -> dict[str, Any]:
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

        # Type narrowing: result.data is not None after the check above
        assert result.data is not None
        data = cast(dict[str, Any], result.data)
        config = data.get("config", {})
        return cast(dict[str, Any], config)

    async def _save_config(
        self,
        tenant_id: UUID,
        connector_id: UUID,
        config: dict[str, Any],
    ) -> None:
        """Internal helper to save config."""
        self.supabase.table("connectors").update({
            "config": config,
        }).eq("id", str(connector_id)).eq("tenant_id", str(tenant_id)).execute()
