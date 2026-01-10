"""
Hybrid Search Service - Understanding Plane

Combines vector (semantic) and keyword (lexical) search using Reciprocal Rank Fusion.
Provides significantly better search results than either method alone.
"""

import logging
from dataclasses import dataclass
from typing import Any, Literal
from uuid import UUID

from src.search.embeddings import EmbeddingService
from supabase import Client

logger = logging.getLogger(__name__)

SearchMode = Literal["hybrid", "semantic", "keyword"]


@dataclass
class SearchResult:
    """Single search result with metadata."""

    chunk_id: UUID
    document_id: UUID
    content: str
    page_numbers: list[int] | None
    score: float
    metadata: dict[str, Any] | None = None


class HybridSearchService:
    """
    Service for hybrid search combining vector and keyword search.

    Uses Reciprocal Rank Fusion (RRF) to combine rankings from both methods.
    RRF is simple, effective, and doesn't require parameter tuning.
    """

    def __init__(
        self,
        supabase_client: Client,
        embedding_service: EmbeddingService,
        rrf_k: int = 60,
    ):
        """
        Initialize hybrid search service.

        Args:
            supabase_client: Supabase client with user JWT (for tenant isolation)
            embedding_service: Service for generating query embeddings
            rrf_k: RRF constant (default 60, standard value from literature)
        """
        self.client = supabase_client
        self.embedding_service = embedding_service
        self.rrf_k = rrf_k

    async def search(
        self,
        query: str,
        mode: SearchMode = "hybrid",
        limit: int = 20,
        filter_document_ids: list[UUID] | None = None,
    ) -> list[SearchResult]:
        """
        Search document chunks using specified mode.

        SECURITY: Tenant isolation enforced by database functions.
        Database functions extract tenant_id from JWT token.

        Args:
            query: Search query text
            mode: Search mode (hybrid, semantic, or keyword)
            limit: Maximum number of results to return
            filter_document_ids: Optional list of document IDs to filter

        Returns:
            List of SearchResult objects sorted by relevance score

        Raises:
            ValueError: If query is empty or mode is invalid
        """
        if not query or not query.strip():
            raise ValueError("Query must be a non-empty string")

        if mode not in ("hybrid", "semantic", "keyword"):
            raise ValueError(f"Invalid search mode: {mode}")

        # Execute search based on mode
        if mode == "hybrid":
            return await self._hybrid_search(query, limit, filter_document_ids)
        elif mode == "semantic":
            return await self._vector_search(query, limit, filter_document_ids)
        else:  # keyword
            return await self._keyword_search(query, limit, filter_document_ids)

    async def _vector_search(
        self,
        query: str,
        limit: int,
        filter_document_ids: list[UUID] | None,
    ) -> list[SearchResult]:
        """
        Perform semantic search using vector embeddings.

        Args:
            query: Search query text
            limit: Maximum number of results
            filter_document_ids: Optional document ID filter

        Returns:
            List of SearchResult objects sorted by similarity
        """
        # Generate query embedding
        query_embedding = await self.embedding_service.embed_single(query)

        # Convert UUID list to string list for RPC call
        doc_ids = [str(doc_id) for doc_id in filter_document_ids] if filter_document_ids else None

        # Call vector search function
        result = self.client.rpc(
            "match_document_chunks",
            {
                "query_embedding": query_embedding,
                "match_count": limit,
                "filter_document_ids": doc_ids,
            }
        ).execute()

        # Convert to SearchResult objects
        return [
            SearchResult(
                chunk_id=UUID(row["id"]),
                document_id=UUID(row["document_id"]),
                content=row["content"],
                page_numbers=row.get("page_numbers"),
                score=float(row["similarity"]),
            )
            for row in result.data
        ]

    async def _keyword_search(
        self,
        query: str,
        limit: int,
        filter_document_ids: list[UUID] | None,
    ) -> list[SearchResult]:
        """
        Perform keyword search using PostgreSQL full-text search.

        Args:
            query: Search query text
            limit: Maximum number of results
            filter_document_ids: Optional document ID filter

        Returns:
            List of SearchResult objects sorted by text rank
        """
        # Convert UUID list to string list for RPC call
        doc_ids = [str(doc_id) for doc_id in filter_document_ids] if filter_document_ids else None

        # Call keyword search function
        result = self.client.rpc(
            "match_document_chunks_keyword",
            {
                "query_text": query,
                "match_count": limit,
                "filter_document_ids": doc_ids,
            }
        ).execute()

        # Convert to SearchResult objects
        return [
            SearchResult(
                chunk_id=UUID(row["id"]),
                document_id=UUID(row["document_id"]),
                content=row["content"],
                page_numbers=row.get("page_numbers"),
                score=float(row["rank"]),
            )
            for row in result.data
        ]

    async def _hybrid_search(
        self,
        query: str,
        limit: int,
        filter_document_ids: list[UUID] | None,
    ) -> list[SearchResult]:
        """
        Perform hybrid search using Reciprocal Rank Fusion.

        Combines vector and keyword search results using RRF algorithm.
        RRF gives equal weight to both ranking methods.

        Args:
            query: Search query text
            limit: Maximum number of results
            filter_document_ids: Optional document ID filter

        Returns:
            List of SearchResult objects sorted by combined RRF score
        """
        # Fetch more results from each method to improve RRF quality
        fetch_limit = limit * 2

        # Run both searches in parallel (if possible)
        # For now, run sequentially since we're using async
        vector_results = await self._vector_search(query, fetch_limit, filter_document_ids)
        keyword_results = await self._keyword_search(query, fetch_limit, filter_document_ids)

        # Apply Reciprocal Rank Fusion
        fused_results = self._reciprocal_rank_fusion(
            vector_results,
            keyword_results,
            k=self.rrf_k,
        )

        # Return top N results
        return fused_results[:limit]

    def _reciprocal_rank_fusion(
        self,
        vector_results: list[SearchResult],
        keyword_results: list[SearchResult],
        k: int = 60,
    ) -> list[SearchResult]:
        """
        Combine rankings using Reciprocal Rank Fusion.

        RRF formula: score = sum(1 / (k + rank))
        where rank starts at 1 for the top result.

        Args:
            vector_results: Results from vector search
            keyword_results: Results from keyword search
            k: RRF constant (default 60)

        Returns:
            Combined results sorted by RRF score (descending)
        """
        scores: dict[UUID, float] = {}
        result_map: dict[UUID, SearchResult] = {}

        # Add scores from vector results
        for rank, result in enumerate(vector_results):
            chunk_id = result.chunk_id
            scores[chunk_id] = scores.get(chunk_id, 0.0) + 1.0 / (k + rank + 1)
            result_map[chunk_id] = result

        # Add scores from keyword results
        for rank, result in enumerate(keyword_results):
            chunk_id = result.chunk_id
            scores[chunk_id] = scores.get(chunk_id, 0.0) + 1.0 / (k + rank + 1)
            # Store result if not already stored (prefer vector result for content)
            if chunk_id not in result_map:
                result_map[chunk_id] = result

        # Sort by combined score (descending)
        sorted_ids = sorted(scores.items(), key=lambda x: x[1], reverse=True)

        # Build final result list with RRF scores
        combined_results = []
        for chunk_id, rrf_score in sorted_ids:
            result = result_map[chunk_id]
            # Update score to RRF score
            combined_results.append(
                SearchResult(
                    chunk_id=result.chunk_id,
                    document_id=result.document_id,
                    content=result.content,
                    page_numbers=result.page_numbers,
                    score=rrf_score,
                    metadata=result.metadata,
                )
            )

        logger.debug(
            "Applied Reciprocal Rank Fusion",
            extra={
                "vector_count": len(vector_results),
                "keyword_count": len(keyword_results),
                "fused_count": len(combined_results),
                "k": k,
            },
        )

        return combined_results
