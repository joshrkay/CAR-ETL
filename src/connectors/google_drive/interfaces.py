"""
Storage and emission interfaces for Google Drive connector.

These interfaces abstract storage implementations to maintain clean architecture
and enable testability without hardcoding Supabase or other storage backends.
"""
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any
from uuid import UUID


class TokenStore(ABC):
    """Interface for OAuth token storage and retrieval."""

    @abstractmethod
    async def get_tokens(self, tenant_id: UUID, connector_id: UUID) -> dict[str, Any] | None:
        """
        Retrieve access and refresh tokens for a connector.

        Args:
            tenant_id: Tenant identifier
            connector_id: Connector identifier

        Returns:
            Dictionary with access_token, refresh_token, expires_at, or None if not found
        """
        pass

    @abstractmethod
    async def save_tokens(
        self,
        tenant_id: UUID,
        connector_id: UUID,
        access_token: str,
        refresh_token: str | None,
        expires_at: datetime | None,
    ) -> None:
        """
        Save OAuth tokens for a connector.

        Args:
            tenant_id: Tenant identifier
            connector_id: Connector identifier
            access_token: OAuth access token
            refresh_token: Optional refresh token
            expires_at: Optional token expiration time
        """
        pass

    @abstractmethod
    async def mark_needs_reauth(self, tenant_id: UUID, connector_id: UUID) -> None:
        """
        Mark connector as needing re-authentication.

        Args:
            tenant_id: Tenant identifier
            connector_id: Connector identifier
        """
        pass


class ConnectorConfigStore(ABC):
    """Interface for connector configuration storage."""

    @abstractmethod
    async def get_config(self, tenant_id: UUID, connector_id: UUID) -> dict[str, Any]:
        """
        Retrieve connector configuration.

        Args:
            tenant_id: Tenant identifier
            connector_id: Connector identifier

        Returns:
            Configuration dictionary
        """
        pass

    @abstractmethod
    async def save_config(
        self,
        tenant_id: UUID,
        connector_id: UUID,
        config: dict[str, Any],
    ) -> None:
        """
        Save connector configuration.

        Args:
            tenant_id: Tenant identifier
            connector_id: Connector identifier
            config: Configuration dictionary
        """
        pass

    @abstractmethod
    async def get_folder_ids(self, tenant_id: UUID, connector_id: UUID) -> list[str]:
        """
        Get selected folder IDs for sync.

        Args:
            tenant_id: Tenant identifier
            connector_id: Connector identifier

        Returns:
            List of folder IDs to sync
        """
        pass

    @abstractmethod
    async def set_folder_ids(
        self,
        tenant_id: UUID,
        connector_id: UUID,
        folder_ids: list[str],
    ) -> None:
        """
        Set selected folder IDs for sync.

        Args:
            tenant_id: Tenant identifier
            connector_id: Connector identifier
            folder_ids: List of folder IDs to sync
        """
        pass

    @abstractmethod
    async def get_shared_drive_ids(self, tenant_id: UUID, connector_id: UUID) -> list[str]:
        """
        Get shared drive IDs to sync (optional, empty list means all).

        Args:
            tenant_id: Tenant identifier
            connector_id: Connector identifier

        Returns:
            List of shared drive IDs, or empty list for all drives
        """
        pass


class SyncStateStore(ABC):
    """Interface for sync state and checkpoint storage."""

    @abstractmethod
    async def get_page_token(
        self,
        tenant_id: UUID,
        connector_id: UUID,
        drive_id: str | None,
    ) -> str | None:
        """
        Get stored page token for incremental sync.

        Args:
            tenant_id: Tenant identifier
            connector_id: Connector identifier
            drive_id: Optional shared drive ID

        Returns:
            Page token string or None if not found
        """
        pass

    @abstractmethod
    async def save_page_token(
        self,
        tenant_id: UUID,
        connector_id: UUID,
        page_token: str,
        drive_id: str | None,
    ) -> None:
        """
        Save page token for incremental sync checkpoint.

        Args:
            tenant_id: Tenant identifier
            connector_id: Connector identifier
            page_token: Page token from Changes API
            drive_id: Optional shared drive ID
        """
        pass

    @abstractmethod
    async def update_last_sync(
        self,
        tenant_id: UUID,
        connector_id: UUID,
        status: str,
        error_message: str | None = None,
    ) -> None:
        """
        Update last sync timestamp and status.

        Args:
            tenant_id: Tenant identifier
            connector_id: Connector identifier
            status: Sync status (success, error, needs_reauth)
            error_message: Optional error message
        """
        pass


class IngestionEmitter(ABC):
    """Interface for emitting ingestion events to downstream processing."""

    @abstractmethod
    async def emit_file_reference(
        self,
        tenant_id: UUID,
        file_id: str,
        file_name: str,
        mime_type: str,
        file_size: int,
        modified_time: str,
        drive_id: str | None,
        folder_ids: list[str],
        source_path: str,
    ) -> str:
        """
        Emit a file reference event for ingestion.

        This does NOT download file bytes. Downstream will fetch bytes.

        Args:
            tenant_id: Tenant identifier
            file_id: Google Drive file ID
            file_name: File name (redacted if needed)
            mime_type: MIME type
            file_size: File size in bytes
            modified_time: ISO format modification time
            drive_id: Optional shared drive ID
            folder_ids: List of parent folder IDs
            source_path: Unique source path identifier

        Returns:
            Ingestion event ID
        """
        pass

    @abstractmethod
    async def emit_deletion_reference(
        self,
        tenant_id: UUID,
        file_id: str,
        drive_id: str | None,
        source_path: str,
    ) -> None:
        """
        Emit a file deletion reference event.

        Args:
            tenant_id: Tenant identifier
            file_id: Google Drive file ID
            drive_id: Optional shared drive ID
            source_path: Unique source path identifier
        """
        pass
