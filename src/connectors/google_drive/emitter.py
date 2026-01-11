"""
Ingestion event emitter for Google Drive connector.

Emits normalized ingestion references/events for downstream processing.
This is part of the Ingestion Plane - it only emits references, not raw data.
"""
import logging
from typing import Optional, List, Dict, Any, cast
from uuid import UUID, uuid4
from supabase import Client

from src.connectors.google_drive.interfaces import IngestionEmitter
from src.services.redaction import presidio_redact

logger = logging.getLogger(__name__)


class SupabaseIngestionEmitter(IngestionEmitter):
    """Supabase-backed ingestion event emitter."""
    
    def __init__(self, supabase: Client):
        """
        Initialize ingestion emitter.
        
        Args:
            supabase: Supabase client
        """
        self.supabase = supabase
    
    async def emit_file_reference(
        self,
        tenant_id: UUID,
        file_id: str,
        file_name: str,
        mime_type: str,
        file_size: int,
        modified_time: str,
        drive_id: Optional[str],
        folder_ids: List[str],
        source_path: str,
    ) -> str:
        """
        Emit file reference event.
        
        SECURITY: Redact file name before persisting (defense in depth).
        """
        # Redact filename before persisting
        redacted_filename = presidio_redact(file_name)
        
        ingestion_data: Dict[str, Any] = {
            "id": str(uuid4()),
            "tenant_id": str(tenant_id),
            "source_type": "google_drive",
            "source_path": source_path,
            "file_id": file_id,
            "file_name": redacted_filename,
            "mime_type": mime_type,
            "file_size_bytes": file_size,
            "modified_time": modified_time,
            "drive_id": drive_id,
            "folder_ids": folder_ids,
            "status": "pending",
            "created_at": modified_time,
        }
        
        # Store in a connector-specific ingestion table or documents table
        # For now, using documents table as ingestion reference
        result = self.supabase.table("documents").insert(ingestion_data).execute()
        
        if not result.data:
            raise ValueError("Failed to emit file reference")
        
        data_list = cast(List[Dict[str, Any]], result.data)
        ingestion_id = cast(str, data_list[0]["id"])
        
        logger.info(
            "File reference emitted",
            extra={
                "tenant_id": str(tenant_id),
                "ingestion_id": ingestion_id,
                "file_id": file_id,
                "source_path": source_path,
            },
        )
        
        return ingestion_id
    
    async def emit_deletion_reference(
        self,
        tenant_id: UUID,
        file_id: str,
        drive_id: Optional[str],
        source_path: str,
    ) -> None:
        """
        Emit file deletion reference event.

        IMMUTABILITY: Documents table remains unchanged.
        Deletion is logged in document_source_deletions table.
        """
        # Find existing document by source_path
        result = (
            self.supabase.table("documents")
            .select("id")
            .eq("tenant_id", str(tenant_id))
            .eq("source_type", "google_drive")
            .eq("source_path", source_path)
            .maybe_single()
            .execute()
        )

        if result.data:
            # Type narrowing: result.data is not None after the check above
            assert result.data is not None
            data = cast(Dict[str, Any], result.data)

            # Log deletion without mutating documents table
            deletion_data = {
                "tenant_id": str(tenant_id),
                "document_id": data["id"],
                "source_type": "google_drive",
                "source_path": source_path,
                "deletion_reason": "File deleted from Google Drive",
            }

            try:
                self.supabase.table("document_source_deletions").insert(
                    deletion_data
                ).execute()

                logger.info(
                    "Deletion reference emitted",
                    extra={
                        "tenant_id": str(tenant_id),
                        "file_id": file_id,
                        "source_path": source_path,
                    },
                )
            except Exception as e:
                logger.error(
                    "Failed to log source deletion",
                    extra={
                        "tenant_id": str(tenant_id),
                        "document_id": data["id"],
                        "error": str(e),
                    },
                    exc_info=True,
                )


# Alias for backward compatibility and clarity in tests
GoogleDriveEventEmitter = SupabaseIngestionEmitter
