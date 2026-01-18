"""
Delta sync logic for Google Drive files.

Ingestion Plane: Emits normalized ingestion references/events.
Does NOT download file bytes - downstream will fetch.
"""
import logging
from typing import Dict, Any, List, Optional, Set, cast
from uuid import UUID

from src.connectors.google_drive.client import (
    GoogleDriveClient,
    GoogleDriveClientError,
    TokenRevokedError,
    RateLimitError,
)
from src.connectors.google_drive.interfaces import (
    TokenStore,
    ConnectorConfigStore,
    SyncStateStore,
    IngestionEmitter,
)

logger = logging.getLogger(__name__)


class GoogleDriveSyncError(Exception):
    """Error for Google Drive sync operations."""
    pass


class GoogleDriveSync:
    """Handles delta sync of Google Drive files using Changes API."""
    
    def __init__(
        self,
        tenant_id: UUID,
        connector_id: UUID,
        token_store: TokenStore,
        config_store: ConnectorConfigStore,
        state_store: SyncStateStore,
        emitter: IngestionEmitter,
    ):
        """
        Initialize Google Drive sync handler.
        
        Args:
            tenant_id: Tenant identifier
            connector_id: Connector identifier
            token_store: Token storage interface
            config_store: Configuration storage interface
            state_store: Sync state storage interface
            emitter: Ingestion event emitter
        """
        self.tenant_id = tenant_id
        self.connector_id = connector_id
        self.token_store = token_store
        self.config_store = config_store
        self.state_store = state_store
        self.emitter = emitter
    
    async def sync(
        self,
        client: GoogleDriveClient,
    ) -> Dict[str, Any]:
        """
        Perform delta sync using Changes API.
        
        Handles:
        - Multiple folder selection
        - Shared drive support
        - Incremental sync with checkpointing
        - Idempotent replay
        - Token revocation detection
        - Rate limit handling
        - Invalid token fallback to full resync
        
        Returns:
            Dictionary with sync statistics
        """
        stats = {
            "files_emitted": 0,
            "deletions_emitted": 0,
            "files_skipped": 0,
            "errors": [],
            "needs_reauth": False,
        }
        
        try:
            # Get configuration
            folder_ids = await self.config_store.get_folder_ids(
                self.tenant_id,
                self.connector_id,
            )
            shared_drive_ids = await self.config_store.get_shared_drive_ids(
                self.tenant_id,
                self.connector_id,
            )
            
            # If no folders selected, sync root of all drives
            if not folder_ids:
                folder_ids_with_none: List[Optional[str]] = [None]  # None means root
            else:
                folder_ids_with_none = folder_ids  # type: ignore[assignment]
            
            # If no shared drives specified, sync all (empty list)
            if shared_drive_ids:
                drives_to_sync: List[Optional[str]] = shared_drive_ids  # type: ignore[assignment]
            else:
                drives_to_sync = [None]
            
            # Track processed file IDs for idempotency
            processed_file_ids: Set[str] = set()
            
            for drive_id in drives_to_sync:
                try:
                    drive_stats = await self._sync_drive(
                        client=client,
                        drive_id=drive_id,
                        folder_ids=folder_ids_with_none,
                        processed_file_ids=processed_file_ids,
                    )
                    stats["files_emitted"] += drive_stats["files_emitted"]
                    stats["deletions_emitted"] += drive_stats["deletions_emitted"]
                    stats["files_skipped"] += drive_stats["files_skipped"]
                    errors_list = cast(List[str], stats["errors"])
                    drive_errors = cast(List[str], drive_stats["errors"])
                    errors_list.extend(drive_errors)
                except TokenRevokedError:
                    logger.error(
                        "Token revoked during sync",
                        extra={
                            "tenant_id": str(self.tenant_id),
                            "connector_id": str(self.connector_id),
                            "drive_id": drive_id,
                        },
                    )
                    await self.token_store.mark_needs_reauth(
                        self.tenant_id,
                        self.connector_id,
                    )
                    stats["needs_reauth"] = True
                    errors_list = cast(List[str], stats["errors"])
                    errors_list.append(f"Token revoked for drive {drive_id}")
                    break
                except RateLimitError as e:
                    logger.warning(
                        "Rate limit exceeded",
                        extra={
                            "tenant_id": str(self.tenant_id),
                            "connector_id": str(self.connector_id),
                            "drive_id": drive_id,
                        },
                    )
                    errors_list = cast(List[str], stats["errors"])
                    errors_list.append(f"Rate limit exceeded for drive {drive_id}: {str(e)}")
                    # Continue with other drives
                    continue
                except GoogleDriveClientError as e:
                    error_msg = f"Drive API error for drive {drive_id}: {str(e)}"
                    logger.error(
                        error_msg,
                        extra={
                            "tenant_id": str(self.tenant_id),
                            "connector_id": str(self.connector_id),
                            "drive_id": drive_id,
                        },
                    )
                    errors_list = cast(List[str], stats["errors"])
                    errors_list.append(error_msg)
                    continue
            
            # Update sync status
            if stats["needs_reauth"]:
                await self.state_store.update_last_sync(
                    self.tenant_id,
                    self.connector_id,
                    "needs_reauth",
                    "Token revoked, re-authentication required",
                )
            elif stats["errors"]:
                errors_list = cast(List[str], stats["errors"])
                await self.state_store.update_last_sync(
                    self.tenant_id,
                    self.connector_id,
                    "error",
                    f"{len(errors_list)} errors during sync",
                )
            else:
                await self.state_store.update_last_sync(
                    self.tenant_id,
                    self.connector_id,
                    "success",
                )
            
        except Exception as e:
            logger.error(
                "Unexpected error during sync",
                exc_info=True,
                extra={
                    "tenant_id": str(self.tenant_id),
                    "connector_id": str(self.connector_id),
                },
            )
            await self.state_store.update_last_sync(
                self.tenant_id,
                self.connector_id,
                "error",
                str(e),
            )
            raise GoogleDriveSyncError(f"Sync failed: {str(e)}")
        
        return stats
    
    async def _sync_drive(
        self,
        client: GoogleDriveClient,
        drive_id: Optional[str],
        folder_ids: List[Optional[str]],
        processed_file_ids: Set[str],
    ) -> Dict[str, Any]:
        """
        Sync a single drive (or my_drive if drive_id is None).
        
        Returns:
            Statistics for this drive
        """
        stats: Dict[str, Any] = {
            "files_emitted": 0,
            "deletions_emitted": 0,
            "files_skipped": 0,
            "errors": [],
        }
        
        # Get or initialize page token
        page_token = await self.state_store.get_page_token(
            self.tenant_id,
            self.connector_id,
            drive_id,
        )
        
        if not page_token:
            try:
                start_token = await client.get_start_page_token(drive_id=drive_id)
                page_token = start_token
            except GoogleDriveClientError as e:
                error_text = str(e).lower()
                if "invalid" in error_text or "expired" in error_text:
                    # Token invalidated - fall back to full resync
                    logger.warning(
                        "Start page token invalid, performing full resync",
                        extra={
                            "tenant_id": str(self.tenant_id),
                            "connector_id": str(self.connector_id),
                            "drive_id": drive_id,
                        },
                    )
                    start_token = await client.get_start_page_token(drive_id=drive_id)
                    page_token = start_token
                else:
                    raise
        
        # Process changes
        while page_token:
            try:
                result = await client.get_changes(
                    page_token=page_token,
                    drive_id=drive_id,
                )
                
                changes = result.get("changes", [])
                next_page_token = result.get("next_page_token")
                new_start_token = result.get("start_page_token")
                
                for change in changes:
                    try:
                        change_stats = await self._process_change(
                            client=client,
                            change=change,
                            folder_ids=folder_ids,
                            drive_id=drive_id,
                            processed_file_ids=processed_file_ids,
                        )
                        stats["files_emitted"] += change_stats.get("emitted", 0)
                        stats["deletions_emitted"] += change_stats.get("deleted", 0)
                        stats["files_skipped"] += change_stats.get("skipped", 0)
                    except Exception as e:
                        file_id = change.get("file", {}).get("id", "unknown")
                        error_msg = f"Failed to process change {file_id}: {str(e)}"
                        logger.error(
                            error_msg,
                            extra={
                                "tenant_id": str(self.tenant_id),
                                "connector_id": str(self.connector_id),
                                "file_id": file_id,
                            },
                        )
                        errors_list = cast(List[str], stats["errors"])
                    errors_list.append(error_msg)
                
                # Update checkpoint
                if next_page_token:
                    page_token = next_page_token
                elif new_start_token:
                    page_token = new_start_token
                    await self.state_store.save_page_token(
                        self.tenant_id,
                        self.connector_id,
                        new_start_token,
                        drive_id,
                    )
                    break
                else:
                    break
                    
            except (TokenRevokedError, RateLimitError):
                raise
            except GoogleDriveClientError as e:
                error_text = str(e).lower()
                if "invalid" in error_text and "token" in error_text:
                    # Token invalidated - reset and retry
                    logger.warning(
                        "Page token invalidated, resetting checkpoint",
                        extra={
                            "tenant_id": str(self.tenant_id),
                            "connector_id": str(self.connector_id),
                            "drive_id": drive_id,
                        },
                    )
                    start_token = await client.get_start_page_token(drive_id=drive_id)
                    page_token = start_token
                else:
                    raise
        
        # Save final checkpoint
        if page_token:
            await self.state_store.save_page_token(
                self.tenant_id,
                self.connector_id,
                page_token,
                drive_id,
            )
        
        return stats
    
    async def _process_change(
        self,
        client: GoogleDriveClient,
        change: Dict[str, Any],
        folder_ids: List[Optional[str]],
        drive_id: Optional[str],
        processed_file_ids: Set[str],
    ) -> Dict[str, int]:
        """
        Process a single change event (idempotent).
        
        Returns:
            Dictionary with emitted, deleted, skipped counts
        """
        change_type = change.get("changeType")
        file_data = change.get("file")
        
        if not file_data:
            return {"emitted": 0, "deleted": 0, "skipped": 0}
        
        file_id = file_data.get("id")
        if not file_id:
            return {"emitted": 0, "deleted": 0, "skipped": 0}
        
        # Idempotency: skip if already processed in this sync run
        if file_id in processed_file_ids:
            return {"emitted": 0, "deleted": 0, "skipped": 1}
        
        processed_file_ids.add(file_id)
        
        # Handle deletions
        if change_type == "remove" or change.get("removed", False) or file_data.get("trashed", False):
            source_path = self._build_source_path(drive_id, file_id)
            await self.emitter.emit_deletion_reference(
                tenant_id=self.tenant_id,
                file_id=file_id,
                drive_id=drive_id,
                source_path=source_path,
            )
            return {"emitted": 0, "deleted": 1, "skipped": 0}
        
        # Skip folders
        mime_type = file_data.get("mimeType", "")
        if mime_type == "application/vnd.google-apps.folder":
            return {"emitted": 0, "deleted": 0, "skipped": 0}
        
        # Filter by folder selection
        file_parents = file_data.get("parents", [])
        if folder_ids and not any(
            folder_id is None or folder_id in file_parents
            for folder_id in folder_ids
        ):
            return {"emitted": 0, "deleted": 0, "skipped": 0}
        
        # Emit file reference (no download - downstream will fetch)
        file_name = file_data.get("name", "")
        file_size = int(file_data.get("size", 0))
        modified_time = file_data.get("modifiedTime", "")
        
        if not file_name or not modified_time:
            return {"emitted": 0, "deleted": 0, "skipped": 0}
        
        source_path = self._build_source_path(drive_id, file_id)
        
        await self.emitter.emit_file_reference(
            tenant_id=self.tenant_id,
            file_id=file_id,
            file_name=file_name,
            mime_type=mime_type or "application/octet-stream",
            file_size=file_size,
            modified_time=modified_time,
            drive_id=drive_id,
            folder_ids=file_parents,
            source_path=source_path,
        )
        
        return {"emitted": 1, "deleted": 0, "skipped": 0}
    
    def _build_source_path(self, drive_id: Optional[str], file_id: str) -> str:
        """Build unique source path identifier."""
        drive_key = drive_id or "my_drive"
        return f"google_drive:{drive_key}:{file_id}"
