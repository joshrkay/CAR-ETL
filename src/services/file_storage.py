"""
File Storage Service - Ingestion Plane

Handles file uploads to Supabase Storage with tenant isolation.
Enforces append-only storage (immutable artifacts).
"""

import hashlib
import logging
from io import BytesIO
from uuid import UUID

from supabase import Client

logger = logging.getLogger(__name__)


class StorageUploadError(Exception):
    """Error during file storage upload."""
    pass


class FileStorageService:
    """Service for uploading files to Supabase Storage."""

    def __init__(self, supabase_client: Client):
        """
        Initialize file storage service.

        Args:
            supabase_client: Supabase client with appropriate permissions
        """
        self.client = supabase_client

    def upload_file(
        self,
        content: bytes,
        storage_path: str,
        tenant_id: UUID,
        mime_type: str,
    ) -> None:
        """
        Upload file content to Supabase Storage.

        Files are stored in tenant-isolated buckets following the pattern:
        - Bucket: documents-{tenant_id}
        - Path: {storage_path}

        Args:
            content: File content bytes
            storage_path: Path within bucket (e.g., "uploads/{document_id}/{filename}")
            tenant_id: Tenant identifier for bucket selection
            mime_type: MIME type for content-type header

        Raises:
            StorageUploadError: If upload fails
        """
        bucket_name = f"documents-{tenant_id}"

        try:
            file_obj = BytesIO(content)
            self.client.storage.from_(bucket_name).upload(
                path=storage_path,
                file=file_obj,
                file_options={"content-type": mime_type, "upsert": "true"},
            )

            logger.info(
                "File uploaded to storage",
                extra={
                    "tenant_id": str(tenant_id),
                    "bucket_name": bucket_name,
                    "storage_path": storage_path,
                    "file_size": len(content),
                },
            )

        except Exception as e:
            logger.error(
                "Failed to upload file to storage",
                extra={
                    "tenant_id": str(tenant_id),
                    "bucket_name": bucket_name,
                    "storage_path": storage_path,
                    "error": str(e),
                },
                exc_info=True,
            )
            raise StorageUploadError(f"Failed to upload file to storage: {str(e)}") from e

    def calculate_file_hash(self, content: bytes) -> str:
        """
        Calculate SHA-256 hash of file content.

        Args:
            content: File content bytes

        Returns:
            Hexadecimal hash string (64 characters)
        """
        return hashlib.sha256(content).hexdigest()
