"""
Chunk Storage Service - Understanding Plane

Stores document chunks with embeddings, enforcing redaction before persistence.
This service must be used for all chunk storage operations.
"""

import logging
from typing import Any
from uuid import UUID

from src.services.redaction import presidio_redact
from supabase import Client

logger = logging.getLogger(__name__)


class ChunkStorageService:
    """
    Service for storing document chunks with embeddings.

    SECURITY: Enforces explicit redaction before persistence (defense in depth).
    All content is redacted before being stored in document_chunks table.
    """

    def __init__(self, supabase_client: Client):
        """
        Initialize chunk storage service.

        Args:
            supabase_client: Supabase client (with user JWT or service_role)
        """
        self.client = supabase_client

    async def store_chunks(
        self,
        tenant_id: UUID,
        document_id: UUID,
        chunks: list[dict[str, Any]],
    ) -> list[str]:
        """
        Store document chunks with embeddings.

        SECURITY: Explicitly redacts content before persisting (defense in depth).

        Args:
            tenant_id: Tenant identifier
            document_id: Document identifier
            chunks: List of chunk dictionaries with keys:
                - chunk_index: int
                - content: str (will be redacted)
                - embedding: List[float] (1536 dimensions)
                - token_count: int
                - page_numbers: Optional[List[int]]
                - section_header: Optional[str]
                - metadata: Optional[dict]
                - extraction_id: Optional[UUID]

        Returns:
            List of chunk IDs that were stored

        Raises:
            Exception: If storage fails
        """
        stored_ids: list[str] = []

        for chunk in chunks:
            # SECURITY: Explicit redaction before persisting (defense in depth)
            redacted_content = presidio_redact(chunk["content"])

            chunk_data = {
                "tenant_id": str(tenant_id),
                "document_id": str(document_id),
                "chunk_index": chunk["chunk_index"],
                "content": redacted_content,  # Redacted content
                "embedding": chunk["embedding"],
                "token_count": chunk["token_count"],
                "page_numbers": chunk.get("page_numbers"),
                "section_header": chunk.get("section_header"),
                "metadata": chunk.get("metadata", {}),
            }

            if "extraction_id" in chunk and chunk["extraction_id"]:
                chunk_data["extraction_id"] = str(chunk["extraction_id"])

            result = self.client.table("document_chunks").insert(chunk_data).execute()

            if not result.data:
                raise Exception(f"Failed to store chunk {chunk['chunk_index']}")

            stored_ids.append(result.data[0]["id"])

            logger.debug(
                "Stored document chunk",
                extra={
                    "tenant_id": str(tenant_id),
                    "document_id": str(document_id),
                    "chunk_index": chunk["chunk_index"],
                    "chunk_id": result.data[0]["id"],
                },
            )

        logger.info(
            "Stored document chunks",
            extra={
                "tenant_id": str(tenant_id),
                "document_id": str(document_id),
                "chunk_count": len(stored_ids),
            },
        )

        return stored_ids
