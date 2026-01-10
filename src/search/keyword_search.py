"""
Keyword Search Service - Understanding Plane

Provides PostgreSQL full-text search over document chunks.
"""

import logging
from dataclasses import dataclass
from typing import List, cast
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
    ) -> List[KeywordSearchResult]:
        """
        Search document chunks using PostgreSQL full-text search.

        Args:
            query_text: Query string for full-text search.
            match_count: Maximum number of matches to return.

        Returns:
            List of keyword search results.

        Security:
            - Tenant isolation is enforced by the database function, which extracts
              the tenant_id from the JWT token using public.tenant_id().
            - The tenant_id cannot be overridden by callers, ensuring absolute
              tenant isolation as required by .cursorrules.

        Raises:
            ValueError: If query_text is empty or match_count < 1
            Exception: If search fails
        """
        if not query_text or not query_text.strip():
            raise ValueError("query_text must be a non-empty string")

        if match_count < 1:
            raise ValueError("match_count must be >= 1")

        params = {
            "query_text": query_text,
            "match_count": match_count,
        }

        try:
            result = self.client.rpc("search_chunks_keyword", params).execute()
            rows = result.data or []
        except Exception as exc:
            logger.error(
                "Keyword search failed",
                extra={
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
            page_numbers=page_numbers,
            rank=float(cast(float | int | str, row["rank"])),
        )
