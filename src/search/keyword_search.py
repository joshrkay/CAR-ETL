"""
Keyword Search Service - Understanding Plane

Provides PostgreSQL full-text search over document chunks.
"""

import logging
from dataclasses import dataclass
from typing import List, Optional, cast
from uuid import UUID

from supabase import Client

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class KeywordSearchResult:
    """Result row for keyword search."""

    id: UUID
    document_id: UUID
    content: str
    page_numbers: List[int]
    rank: float


class KeywordSearchService:
    """Service for keyword-based search over document chunks."""

    def __init__(self, supabase_client: Client):
        """
        Initialize keyword search service.

        Args:
            supabase_client: Supabase client (with user JWT or service_role)
        """
        self.client = supabase_client

    async def search_chunks(
        self,
        query_text: str,
        match_count: int = 20,
        tenant_id: Optional[UUID] = None,
    ) -> List[KeywordSearchResult]:
        """
        Search document chunks using PostgreSQL full-text search.

        Args:
            query_text: Query string for full-text search.
            match_count: Maximum number of matches to return.
            tenant_id: Optional tenant ID used to scope results when this service
                is called with a trusted service_role Supabase client.

        Returns:
            List of keyword search results.

        Security:
            - When using a client authenticated with a user JWT, callers MUST pass
              ``tenant_id=None``. In that case, tenant scoping must be enforced by
              the database layer based on claims in the JWT, and any
              ``filter_tenant_id`` parameter sent to the database should be
              ignored or validated against the JWT.
            - The ``tenant_id`` parameter MUST NOT be taken from untrusted
              end-user input or used to "switch tenants" on behalf of a user.
              It is intended only for backend-internal use with service_role
              credentials, after the application has performed appropriate
              authorization checks to ensure the caller is allowed to access
              the specified tenant.

        Raises:
            ValueError: If query_text is empty or match_count < 1.
            Exception: If search fails.
        """
        if not query_text or not query_text.strip():
            raise ValueError("query_text must be a non-empty string")

        if match_count < 1:
            raise ValueError("match_count must be >= 1")

        params = {
            "query_text": query_text,
            "match_count": match_count,
        }

        if tenant_id is not None:
            params["filter_tenant_id"] = str(tenant_id)

        try:
            result = self.client.rpc("search_chunks_keyword", params).execute()
            rows = result.data or []
        except Exception as exc:
            logger.error(
                "Keyword search failed",
                extra={
                    "tenant_id": str(tenant_id) if tenant_id else None,
                    "match_count": match_count,
                    "error": str(exc),
                },
            )
            raise

        return [self._parse_result(row) for row in rows]

    def _parse_result(self, row: dict[str, object]) -> KeywordSearchResult:
        """Parse a search result row into a KeywordSearchResult."""
        page_numbers = cast(list[int], row.get("page_numbers") or [])
        return KeywordSearchResult(
            id=UUID(str(row["id"])),
            document_id=UUID(str(row["document_id"])),
            content=str(row["content"]),
            page_numbers=list(row.get("page_numbers") or []),
            rank=float(row["rank"]),
        )
