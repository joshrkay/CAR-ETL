"""
Search Routes - Understanding Plane

Provides hybrid, semantic, and keyword search over document chunks.
Combines vector and keyword search using Reciprocal Rank Fusion (RRF).
"""

import logging
from typing import Annotated, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Request, status
from pydantic import BaseModel, Field
from supabase import Client

from src.auth.models import AuthContext
from src.dependencies import get_current_user, get_supabase_client
from src.search.hybrid import HybridSearchService, SearchMode
from src.search.embeddings import EmbeddingService
from src.search.highlighter import SearchHighlighter
from src.search.reranker import SearchReranker

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/v1/search",
    tags=["search"],
)


class SearchFilters(BaseModel):
    """Search filter parameters."""

    document_ids: Optional[List[UUID]] = Field(
        None,
        description="Filter by specific document IDs",
    )
    document_types: Optional[List[str]] = Field(
        None,
        description="Filter by document types (e.g., 'lease', 'rent_roll')",
    )
    date_range: Optional[dict] = Field(
        None,
        description="Filter by date range (e.g., {'start': '2024-01-01', 'end': '2024-12-31'})",
    )


class SearchRequest(BaseModel):
    """Search request parameters."""

    query: str = Field(
        ...,
        description="Search query text",
        min_length=1,
        max_length=1000,
    )
    mode: SearchMode = Field(
        "hybrid",
        description="Search mode: 'hybrid' (vector + keyword), 'semantic' (vector only), or 'keyword' (text only)",
    )
    filters: Optional[SearchFilters] = Field(
        None,
        description="Optional filters for documents",
    )
    limit: int = Field(
        20,
        description="Maximum number of results to return",
        ge=1,
        le=100,
    )
    enable_reranking: bool = Field(
        False,
        description="Enable cross-encoder reranking for improved relevance (slower)",
    )


class SearchResultItem(BaseModel):
    """Single search result."""

    chunk_id: str
    document_id: str
    document_name: str
    content: str
    page_numbers: Optional[List[int]]
    score: float
    highlights: List[str]


class SearchResponse(BaseModel):
    """Search response with results and metadata."""

    results: List[SearchResultItem]
    total_count: int
    search_mode: str


@router.post(
    "",
    response_model=SearchResponse,
    status_code=status.HTTP_200_OK,
    summary="Search document chunks",
    description="""
    Search document chunks using hybrid, semantic, or keyword search.

    **Search Modes:**
    - `hybrid`: Combines vector and keyword search using Reciprocal Rank Fusion (recommended)
    - `semantic`: Vector similarity search only (good for conceptual queries)
    - `keyword`: Full-text search only (good for exact term matching)

    **Security:**
    - Requires authentication
    - Tenant isolation enforced via RLS
    - Only searches documents accessible to the user's tenant

    **Performance:**
    - Hybrid search provides best results but is slower than single methods
    - Reranking improves relevance but adds latency (use for critical queries)
    - Results are limited to 100 per request for performance

    **Highlighting:**
    - Query terms are wrapped in `<mark>` tags for UI rendering
    - Snippets are generated around matches for better context
    """,
)
async def search_documents(
    request: Request,
    search_request: SearchRequest,
    auth: Annotated[AuthContext, Depends(get_current_user)],
    supabase: Annotated[Client, Depends(get_supabase_client)],
) -> SearchResponse:
    """
    Search document chunks using hybrid, semantic, or keyword search.

    This endpoint:
    1. Validates search request and user authentication
    2. Executes search using specified mode (hybrid/semantic/keyword)
    3. Optionally reranks results using cross-encoder
    4. Generates highlighted snippets around matches
    5. Enriches results with document metadata
    6. Returns ranked results

    Args:
        request: FastAPI request object
        search_request: Search parameters (query, mode, filters, limit)
        auth: Authenticated user context
        supabase: Supabase client with user JWT (for tenant isolation)

    Returns:
        SearchResponse with results, count, and metadata

    Raises:
        Exception: If search fails or query is invalid, including errors from
            embedding, search, or database services.
    """
    logger.info(
        "Search request received",
        extra={
            "tenant_id": str(auth.tenant_id),
            "user_id": str(auth.user_id),
            "query_length": len(search_request.query),
            "mode": search_request.mode,
            "limit": search_request.limit,
        },
    )

    # Initialize services
    embedding_service = EmbeddingService()
    hybrid_service = HybridSearchService(
        supabase_client=supabase,
        embedding_service=embedding_service,
    )
    highlighter = SearchHighlighter()

    # Apply filters (if any)
    filter_doc_ids = None
    if search_request.filters and search_request.filters.document_ids:
        filter_doc_ids = search_request.filters.document_ids

    # TODO: Implement document_types and date_range filters
    # These require additional database queries to map types/dates to document IDs

    # Execute search
    results = await hybrid_service.search(
        query=search_request.query,
        mode=search_request.mode,
        limit=search_request.limit,
        filter_document_ids=filter_doc_ids,
    )

    # Optional: Rerank results using cross-encoder
    if search_request.enable_reranking:
        reranker = SearchReranker()
        if reranker.is_available():
            results = reranker.rerank(search_request.query, results)
            logger.debug(
                "Results reranked using cross-encoder",
                extra={"results_count": len(results)},
            )
        else:
            logger.warning("Reranking requested but cross-encoder unavailable")

    # Enrich results with document metadata and highlights
    # Batch-fetch document metadata to avoid N+1 query pattern
    enriched_results = []

    # Collect unique document IDs from search results
    document_ids = list({str(result.document_id) for result in results})

    documents_by_id = {}
    if document_ids:
        doc_response = (
            supabase.table("documents")
            .select("id, original_filename")
            .in_("id", document_ids)
            .execute()
        )
        if doc_response.data:
            documents_by_id = {
                doc["id"]: doc.get("original_filename", "Unknown")
                for doc in doc_response.data
            }

    for result in results:
        # Resolve document name from pre-fetched metadata
        document_name = documents_by_id.get(str(result.document_id), "Unknown")

        # Generate highlights
        highlights = highlighter.highlight(result.content, search_request.query)

        # Build result item
        enriched_results.append(
            SearchResultItem(
                chunk_id=str(result.chunk_id),
                document_id=str(result.document_id),
                document_name=document_name,
                content=result.content,
                page_numbers=result.page_numbers,
                score=round(result.score, 4),
                highlights=highlights if highlights else [result.content[:200] + "..."],
            )
        )

    logger.info(
        "Search completed successfully",
        extra={
            "tenant_id": str(auth.tenant_id),
            "results_count": len(enriched_results),
            "mode": search_request.mode,
        },
    )

    return SearchResponse(
        results=enriched_results,
        total_count=len(enriched_results),
        search_mode=search_request.mode,
    )
