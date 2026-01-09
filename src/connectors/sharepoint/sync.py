"""Delta sync logic for SharePoint files."""
import logging
import hashlib
from typing import Dict, Any, Optional
from datetime import datetime, timezone
from uuid import UUID, uuid4
from supabase import Client

from src.connectors.sharepoint.client import SharePointClient, SharePointClientError
from src.services.redaction import presidio_redact_bytes

logger = logging.getLogger(__name__)


class SharePointSyncError(Exception):
    """Error for SharePoint sync operations."""


class SharePointSync:
    """Handles delta sync of SharePoint files."""
    
    def __init__(
        self,
        supabase: Client,
        tenant_id: UUID,
        connector_id: UUID,
    ):
        """
        Initialize SharePoint sync handler.
        
        Args:
            supabase: Supabase client with user JWT
            tenant_id: Tenant identifier
            connector_id: Connector record ID
        """
        self.supabase = supabase
        self.tenant_id = tenant_id
        self.connector_id = connector_id
    
    async def sync_drive(
        self,
        client: SharePointClient,
        drive_id: str,
        folder_path: str = "/",
    ) -> Dict[str, Any]:
        """
        Perform delta sync of a SharePoint drive.
        
        Args:
            client: SharePoint Graph API client
            drive_id: SharePoint drive ID
            folder_path: Folder path to sync (default: root)
            
        Returns:
            Dictionary with sync statistics (files_synced, files_updated, errors)
        """
        stats = {
            "files_synced": 0,
            "files_updated": 0,
            "files_skipped": 0,
            "errors": [],
        }
        
        try:
            connector = await self._get_connector()
            config = connector.get("config", {})
            delta_token = config.get("delta_token")
            
            result = await client.get_drive_items(
                drive_id=drive_id,
                folder_path=folder_path,
                delta_token=delta_token,
            )
            
            items = result.get("items", [])
            new_delta_token = result.get("delta_token")
            
            for item in items:
                try:
                    item_stats = await self._process_sync_item(
                        client=client,
                        drive_id=drive_id,
                        item=item,
                    )
                    stats["files_synced"] += item_stats.get("synced", 0)
                    stats["files_updated"] += item_stats.get("updated", 0)
                    stats["files_skipped"] += item_stats.get("skipped", 0)
                except Exception as e:
                    error_msg = f"Failed to sync item {item.get('id', 'unknown')}: {str(e)}"
                    logger.error(error_msg, exc_info=True)
                    stats["errors"].append(error_msg)
            
            if new_delta_token:
                await self._update_delta_token(new_delta_token)
            
            await self._update_last_sync_time()
            
        except SharePointClientError as e:
            logger.error("SharePoint sync failed", exc_info=True)
            raise SharePointSyncError(f"Sync failed: {str(e)}")
        except Exception as e:
            logger.error("Unexpected error during sync", exc_info=True)
            raise SharePointSyncError(f"Sync failed: {str(e)}")
        
        return stats
    
    async def _process_sync_item(
        self,
        client: SharePointClient,
        drive_id: str,
        item: Dict[str, Any],
    ) -> Dict[str, int]:
        """
        Process a single sync item (reduces complexity of sync_drive).
        
        Returns:
            Dictionary with synced, updated, skipped counts
        """
        if item.get("deleted"):
            await self._handle_deleted_item(item)
            return {"synced": 0, "updated": 0, "skipped": 0}
        
        if "file" not in item:
            return {"synced": 0, "updated": 0, "skipped": 0}
        
        file_id = item.get("id")
        file_name = item.get("name")
        last_modified = item.get("lastModifiedDateTime")
        
        if not file_id or not file_name:
            return {"synced": 0, "updated": 0, "skipped": 0}
        
        source_path = f"sharepoint:{drive_id}:{file_id}"
        existing_doc = await self._find_existing_document(source_path)
        
        if existing_doc and self._should_skip_item(existing_doc, last_modified):
            return {"synced": 0, "updated": 0, "skipped": 1}
        
        await self._sync_file_item(
            client=client,
            drive_id=drive_id,
            item=item,
        )
        
        if existing_doc:
            return {"synced": 0, "updated": 1, "skipped": 0}
        return {"synced": 1, "updated": 0, "skipped": 0}
    
    def _should_skip_item(
        self,
        existing_doc: Dict[str, Any],
        last_modified: Optional[str],
    ) -> bool:
        """Check if item should be skipped based on modification time."""
        if not last_modified or not existing_doc.get("updated_at"):
            return False
        
        try:
            item_modified = datetime.fromisoformat(
                last_modified.replace("Z", "+00:00")
            )
            doc_modified = datetime.fromisoformat(str(existing_doc["updated_at"]))
            return item_modified <= doc_modified
        except (ValueError, AttributeError):
            return False
    
    async def _get_connector(self) -> Dict[str, Any]:
        """Get connector record from database."""
        result = (
            self.supabase.table("connectors")
            .select("*")
            .eq("id", str(self.connector_id))
            .eq("tenant_id", str(self.tenant_id))
            .maybe_single()
            .execute()
        )
        
        if not result.data:
            raise SharePointSyncError("Connector not found")
        
        return result.data
    
    async def _find_existing_document(self, source_path: str) -> Optional[Dict[str, Any]]:
        """Find existing document by source_path."""
        result = (
            self.supabase.table("documents")
            .select("*")
            .eq("tenant_id", str(self.tenant_id))
            .eq("source_type", "sharepoint")
            .eq("source_path", source_path)
            .maybe_single()
            .execute()
        )
        
        return result.data if result.data else None
    
    async def _sync_file_item(
        self,
        client: SharePointClient,
        drive_id: str,
        item: Dict[str, Any],
    ) -> None:
        """Download and store a file item from SharePoint."""
        file_id = item.get("id")
        file_name = item.get("name")
        
        if not file_id or not file_name:
            return
        
        file_content = await client.download_file(drive_id, file_id)
        
        mime_type = self._infer_mime_type(file_name)
        
        # SECURITY: Explicit redaction before persisting (defense in depth)
        redacted_content = presidio_redact_bytes(file_content, mime_type)
        
        file_hash = hashlib.sha256(redacted_content).hexdigest()
        
        source_path = f"sharepoint:{drive_id}:{file_id}"
        
        existing_doc = await self._find_existing_document(source_path)
        
        if existing_doc and existing_doc.get("file_hash") == file_hash:
            return
        
        document_id = str(uuid4()) if not existing_doc else existing_doc["id"]
        
        # Upload redacted content to Supabase Storage
        bucket_name = f"documents-{self.tenant_id}"
        storage_path = f"sharepoint/{drive_id}/{file_id}/{file_name}"
        
        try:
            # Upload to Supabase Storage bucket
            # Note: Supabase storage.upload() accepts bytes directly
            from io import BytesIO
            file_obj = BytesIO(redacted_content)
            self.supabase.storage.from_(bucket_name).upload(
                path=storage_path,
                file=file_obj,
                file_options={"content-type": mime_type, "upsert": "true"},
            )
        except Exception as e:
            logger.error(
                "Failed to upload file to storage",
                extra={
                    "tenant_id": str(self.tenant_id),
                    "document_id": document_id,
                    "storage_path": storage_path,
                    "error": str(e),
                },
                exc_info=True,
            )
            # Continue with metadata storage even if upload fails
            # The document will be marked as pending and can be retried
        
        document_data = {
            "id": document_id,
            "tenant_id": str(self.tenant_id),
            "file_hash": file_hash,
            "storage_path": storage_path,
            "original_filename": file_name,
            "mime_type": mime_type,
            "file_size_bytes": len(redacted_content),  # Use actual redacted content size
            "source_type": "sharepoint",
            "source_path": source_path,
            "status": "pending",
        }
        
        if existing_doc:
            self.supabase.table("documents").update(document_data).eq(
                "id", document_data["id"]
            ).execute()
        else:
            self.supabase.table("documents").insert(document_data).execute()
    
    async def _handle_deleted_item(self, item: Dict[str, Any]) -> None:
        """Handle deleted file item (mark document as deleted or remove)."""
        file_id = item.get("id")
        if not file_id:
            return
        
        drive_id = item.get("parentReference", {}).get("driveId")
        if not drive_id:
            return
        
        source_path = f"sharepoint:{drive_id}:{file_id}"
        existing_doc = await self._find_existing_document(source_path)
        
        if existing_doc:
            self.supabase.table("documents").update({
                "status": "failed",
                "error_message": "File deleted from SharePoint",
            }).eq("id", existing_doc["id"]).execute()
    
    async def _update_delta_token(self, delta_token: str) -> None:
        """Update delta token in connector config."""
        connector = await self._get_connector()
        config = connector.get("config", {})
        config["delta_token"] = delta_token
        
        self.supabase.table("connectors").update({
            "config": config,
        }).eq("id", str(self.connector_id)).execute()
    
    async def _update_last_sync_time(self) -> None:
        """Update last_sync_at timestamp."""
        self.supabase.table("connectors").update({
            "last_sync_at": datetime.now(timezone.utc).isoformat(),
        }).eq("id", str(self.connector_id)).execute()
    
    def _infer_mime_type(self, filename: str) -> str:
        """Infer MIME type from filename extension."""
        ext = filename.lower().split(".")[-1] if "." in filename else ""
        
        mime_types = {
            "pdf": "application/pdf",
            "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "png": "image/png",
            "jpg": "image/jpeg",
            "jpeg": "image/jpeg",
            "txt": "text/plain",
            "csv": "text/csv",
        }
        
        return mime_types.get(ext, "application/octet-stream")
