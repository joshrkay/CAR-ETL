"""
Tests for hybrid search functionality.

Tests RRF algorithm, search modes, highlighting, and API endpoint.
"""

from typing import Any, Generator
import pytest
from unittest.mock import Mock, AsyncMock
from uuid import uuid4, UUID
from pydantic import ValidationError

from src.search.hybrid import HybridSearchService, SearchResult
from src.search.highlighter import SearchHighlighter
from src.search.reranker import SearchReranker
from supabase import Client


class TestSearchHighlighter:
    """Unit tests for SearchHighlighter."""

    @pytest.fixture
    def highlighter(self) -> Any:
        """Create SearchHighlighter instance."""
        return SearchHighlighter(snippet_length=100, max_highlights=3)

    def test_highlight_single_term(self, highlighter) -> None:
        """Test highlighting a single query term."""
        content = "This is a test document about rental agreements and base rent calculations."
        query = "rent"

        highlights = highlighter.highlight(content, query)

        assert len(highlights) > 0
        assert "<mark>" in highlights[0]
        assert "</mark>" in highlights[0]
        # Should match "rental" and "rent" (case insensitive)
        assert highlights[0].count("<mark>") >= 1

    def test_highlight_multiple_terms(self, highlighter) -> None:
        """Test highlighting multiple query terms."""
        content = "The lease agreement includes base rent and escalation clauses."
        query = "lease base rent"

        highlights = highlighter.highlight(content, query)

        assert len(highlights) > 0
        snippet = highlights[0]
        assert "<mark>lease</mark>" in snippet.lower()
        assert "<mark>base</mark>" in snippet.lower()
        assert "<mark>rent</mark>" in snippet.lower()

    def test_highlight_no_matches(self, highlighter) -> None:
        """Test that no highlights are returned when query doesn't match."""
        content = "This is a document about commercial properties."
        query = "residential leases"

        highlights = highlighter.highlight(content, query)

        # Should return empty list if no matches
        assert len(highlights) == 0

    def test_highlight_case_insensitive(self, highlighter) -> None:
        """Test that highlighting is case insensitive."""
        content = "The RENT includes utilities. Rent is due monthly."
        query = "rent"

        highlights = highlighter.highlight(content, query)

        assert len(highlights) > 0
        # Should match both "RENT" and "Rent"
        assert highlights[0].count("<mark>") >= 2

    def test_highlight_snippet_length(self, highlighter) -> None:
        """Test that snippets are limited to configured length."""
        content = "a " * 500  # Very long content
        query = "a"

        highlights = highlighter.highlight(content, query)

        assert len(highlights) > 0
        # Snippet should be shorter than full content
        assert len(highlights[0]) < len(content)

    def test_highlight_max_snippets(self, highlighter) -> None:
        """Test that number of snippets is limited."""
        # Create content with many matches far apart
        content = " ".join([f"Section {i}: important rent information." for i in range(10)])
        query = "rent"

        highlights = highlighter.highlight(content, query)

        # Should be limited to max_highlights
        assert len(highlights) <= highlighter.max_highlights

    def test_highlight_empty_inputs(self, highlighter) -> None:
        """Test handling of empty inputs."""
        assert highlighter.highlight("", "query") == []
        assert highlighter.highlight("content", "") == []
        assert highlighter.highlight("", "") == []

    def test_extract_query_terms_removes_stop_words(self, highlighter) -> None:
        """Test that common stop words are filtered out."""
        query = "the lease and the rent"

        terms = highlighter._extract_query_terms(query)

        # Should remove "the" and "and"
        assert "the" not in terms
        assert "and" not in terms
        assert "lease" in terms
        assert "rent" in terms


class TestHybridSearchService:
    """Unit tests for HybridSearchService."""

    @pytest.fixture
    def mock_supabase_client(self) -> Any:
        """Create a mock Supabase client."""
        client = Mock(spec=Client)
        client.rpc = Mock(return_value=client)
        client.execute = Mock(return_value=Mock(data=[]))
        return client

    @pytest.fixture
    def mock_embedding_service(self) -> Any:
        """Create a mock EmbeddingService."""
        service = AsyncMock()
        service.embed_single = AsyncMock(return_value=[0.1] * 1536)
        return service

    @pytest.fixture
    def hybrid_service(self, mock_supabase_client, mock_embedding_service) -> Any:
        """Create HybridSearchService with mocked dependencies."""
        return HybridSearchService(
            supabase_client=mock_supabase_client,
            embedding_service=mock_embedding_service,
            rrf_k=60,
        )

    @pytest.mark.asyncio
    async def test_search_semantic_mode(self, hybrid_service, mock_supabase_client) -> None:
        """Test semantic search mode calls vector search function."""
        mock_results = [
            {
                "id": str(uuid4()),
                "document_id": str(uuid4()),
                "content": "Test content",
                "page_numbers": [1],
                "similarity": 0.95,
            }
        ]
        mock_supabase_client.rpc.return_value.execute.return_value.data = mock_results

        results = await hybrid_service.search(
            query="test query",
            mode="semantic",
            limit=10,
        )

        assert len(results) == 1
        assert results[0].score == 0.95
        # Should call match_document_chunks (vector search)
        mock_supabase_client.rpc.assert_called_once()
        call_args = mock_supabase_client.rpc.call_args
        assert call_args[0][0] == "match_document_chunks"

    @pytest.mark.asyncio
    async def test_search_keyword_mode(self, hybrid_service, mock_supabase_client) -> None:
        """Test keyword search mode calls keyword search function."""
        mock_results = [
            {
                "id": str(uuid4()),
                "document_id": str(uuid4()),
                "content": "Test content with keywords",
                "page_numbers": [1],
                "rank": 0.85,
            }
        ]
        mock_supabase_client.rpc.return_value.execute.return_value.data = mock_results

        results = await hybrid_service.search(
            query="test keywords",
            mode="keyword",
            limit=10,
        )

        assert len(results) == 1
        assert results[0].score == 0.85
        # Should call match_document_chunks_keyword
        mock_supabase_client.rpc.assert_called_once()
        call_args = mock_supabase_client.rpc.call_args
        assert call_args[0][0] == "match_document_chunks_keyword"

    @pytest.mark.asyncio
    async def test_search_hybrid_mode(self, hybrid_service, mock_supabase_client) -> None:
        """Test hybrid mode combines vector and keyword results."""
        vector_result_id = str(uuid4())
        keyword_result_id = str(uuid4())
        both_result_id = str(uuid4())

        # Mock vector search results
        vector_results = [
            {
                "id": vector_result_id,
                "document_id": str(uuid4()),
                "content": "Vector result",
                "page_numbers": [1],
                "similarity": 0.9,
            },
            {
                "id": both_result_id,
                "document_id": str(uuid4()),
                "content": "Both results",
                "page_numbers": [2],
                "similarity": 0.8,
            },
        ]

        # Mock keyword search results
        keyword_results = [
            {
                "id": keyword_result_id,
                "document_id": str(uuid4()),
                "content": "Keyword result",
                "page_numbers": [3],
                "rank": 0.85,
            },
            {
                "id": both_result_id,
                "document_id": str(uuid4()),
                "content": "Both results",
                "page_numbers": [2],
                "rank": 0.75,
            },
        ]

        # Configure mock to return different results for different functions
        def mock_rpc_side_effect(function_name: str, *args: Any, **kwargs: Any) -> Any:
            if function_name == "match_document_chunks":
                mock_supabase_client.execute.return_value.data = vector_results
            elif function_name == "match_document_chunks_keyword":
                mock_supabase_client.execute.return_value.data = keyword_results
            return mock_supabase_client

        mock_supabase_client.rpc.side_effect = mock_rpc_side_effect

        results = await hybrid_service.search(
            query="test query",
            mode="hybrid",
            limit=10,
        )

        # Should combine results using RRF
        # Result that appears in both should rank highest
        assert len(results) == 3
        # The result that appears in both lists should have highest RRF score
        assert results[0].chunk_id == UUID(both_result_id)

    @pytest.mark.asyncio
    async def test_search_with_document_filter(self, hybrid_service, mock_supabase_client) -> None:
        """Test search with document ID filter."""
        doc_id = uuid4()
        mock_results = [
            {
                "id": str(uuid4()),
                "document_id": str(doc_id),
                "content": "Filtered content",
                "page_numbers": [1],
                "similarity": 0.9,
            }
        ]
        mock_supabase_client.rpc.return_value.execute.return_value.data = mock_results

        results = await hybrid_service.search(
            query="test query",
            mode="semantic",
            limit=10,
            filter_document_ids=[doc_id],
        )

        assert len(results) == 1
        # Verify filter was passed to RPC call
        call_args = mock_supabase_client.rpc.call_args
        assert call_args[1]["filter_document_ids"] == [str(doc_id)]

    @pytest.mark.asyncio
    async def test_search_invalid_query(self, hybrid_service) -> None:
        """Test that empty query raises ValueError."""
        with pytest.raises(ValueError, match="non-empty string"):
            await hybrid_service.search(query="", mode="hybrid", limit=10)

        with pytest.raises(ValueError, match="non-empty string"):
            await hybrid_service.search(query="   ", mode="hybrid", limit=10)

    @pytest.mark.asyncio
    async def test_search_invalid_mode(self, hybrid_service) -> None:
        """Test that invalid search mode raises ValueError."""
        with pytest.raises(ValueError, match="Invalid search mode"):
            await hybrid_service.search(query="test", mode="invalid", limit=10)

    def test_reciprocal_rank_fusion(self, hybrid_service) -> None:
        """Test RRF algorithm combines rankings correctly."""
        chunk_id_1 = uuid4()
        chunk_id_2 = uuid4()
        chunk_id_3 = uuid4()

        vector_results = [
            SearchResult(
                chunk_id=chunk_id_1,
                document_id=uuid4(),
                content="Result 1",
                page_numbers=[1],
                score=0.9,
            ),
            SearchResult(
                chunk_id=chunk_id_2,
                document_id=uuid4(),
                content="Result 2",
                page_numbers=[2],
                score=0.8,
            ),
        ]

        keyword_results = [
            SearchResult(
                chunk_id=chunk_id_2,
                document_id=uuid4(),
                content="Result 2",
                page_numbers=[2],
                score=0.85,
            ),
            SearchResult(
                chunk_id=chunk_id_3,
                document_id=uuid4(),
                content="Result 3",
                page_numbers=[3],
                score=0.75,
            ),
        ]

        fused = hybrid_service._reciprocal_rank_fusion(
            vector_results,
            keyword_results,
            k=60,
        )

        # Result 2 appears in both, so should rank highest
        assert fused[0].chunk_id == chunk_id_2
        # Should have all 3 unique results
        assert len(fused) == 3

    def test_reciprocal_rank_fusion_empty_lists(self, hybrid_service) -> None:
        """Test RRF handles empty result lists."""
        result = hybrid_service._reciprocal_rank_fusion([], [], k=60)
        assert len(result) == 0

        # One empty list
        vector_results = [
            SearchResult(
                chunk_id=uuid4(),
                document_id=uuid4(),
                content="Result",
                page_numbers=[1],
                score=0.9,
            )
        ]
        result = hybrid_service._reciprocal_rank_fusion(vector_results, [], k=60)
        assert len(result) == 1


class TestSearchReranker:
    """Unit tests for SearchReranker."""

    def test_reranker_graceful_degradation(self) -> None:
        """Test that reranker gracefully degrades if model unavailable."""
        reranker = SearchReranker()

        # If cross-encoder not available, should return original results
        if not reranker.is_available():
            results = [
                SearchResult(
                    chunk_id=uuid4(),
                    document_id=uuid4(),
                    content="Test",
                    page_numbers=[1],
                    score=0.9,
                )
            ]
            reranked = reranker.rerank("query", results)
            assert reranked == results

    def test_reranker_single_result(self) -> None:
        """Test that single result is returned unchanged."""
        reranker = SearchReranker()

        results = [
            SearchResult(
                chunk_id=uuid4(),
                document_id=uuid4(),
                content="Test",
                page_numbers=[1],
                score=0.9,
            )
        ]

        reranked = reranker.rerank("query", results)
        assert len(reranked) == 1
        assert reranked[0].chunk_id == results[0].chunk_id

    def test_reranker_empty_results(self) -> None:
        """Test that empty results list returns empty."""
        reranker = SearchReranker()
        reranked = reranker.rerank("query", [])
        assert len(reranked) == 0


class TestSearchAPI:
    """Integration tests for search API endpoint."""

    @pytest.fixture
    def mock_supabase_client(self) -> Any:
        """Create a mock Supabase client."""
        client = Mock(spec=Client)
        client.rpc = Mock(return_value=client)
        client.table = Mock(return_value=client)
        client.select = Mock(return_value=client)
        client.eq = Mock(return_value=client)
        client.single = Mock(return_value=client)
        client.execute = Mock(return_value=Mock(data=[]))
        return client

    @pytest.mark.asyncio
    async def test_search_api_request_validation(self) -> None:
        """Test that search API validates request parameters."""
        from src.api.routes.search import SearchRequest

        # Valid request
        request = SearchRequest(
            query="test query",
            mode="hybrid",
            limit=20,
        )
        assert request.query == "test query"
        assert request.mode == "hybrid"

        # Invalid mode should fail validation
        with pytest.raises(ValidationError):
            SearchRequest(query="test", mode="invalid_mode", limit=20)

        # Limit too high should fail validation
        with pytest.raises(ValidationError):
            SearchRequest(query="test", mode="hybrid", limit=200)

        # Limit too low should fail validation
        with pytest.raises(ValidationError):
            SearchRequest(query="test", mode="hybrid", limit=0)


class TestSearchPropertyBased:
    """
    Property-based tests for search edge cases.

    Verifies correct handling of:
    - Special characters in queries
    - Very long queries
    - Unicode characters
    - Empty/whitespace queries
    """

    @pytest.fixture
    def highlighter(self) -> Any:
        """Create SearchHighlighter for property tests."""
        return SearchHighlighter()

    def test_highlight_special_characters(self, highlighter) -> None:
        """Test highlighting with special regex characters."""
        content = "Price: $1,000 per month. Contact: user@example.com"
        query = "$1,000 user@example.com"

        # Should not crash on special regex characters
        highlights = highlighter.highlight(content, query)
        assert isinstance(highlights, list)

    def test_highlight_unicode(self, highlighter) -> None:
        """Test highlighting with unicode characters."""
        content = "租赁协议 Lease Agreement 🏠 Property"
        query = "Lease Property"

        highlights = highlighter.highlight(content, query)
        assert len(highlights) > 0
        assert "<mark>" in highlights[0]

    def test_highlight_very_long_query(self, highlighter) -> None:
        """Test highlighting with very long query."""
        query = "test " * 100  # Very long query
        content = "This is a test document with test content."

        # Should handle long queries without crashing
        highlights = highlighter.highlight(content, query)
        assert isinstance(highlights, list)

    def test_rrf_algorithm_properties(self) -> None:
        """Test mathematical properties of RRF algorithm."""
        from src.search.hybrid import HybridSearchService

        mock_client = Mock()
        mock_embedding = Mock()
        service = HybridSearchService(mock_client, mock_embedding)

        # Test: RRF score decreases with rank
        chunk_ids = [uuid4() for _ in range(5)]
        vector_results = [
            SearchResult(
                chunk_id=chunk_id,
                document_id=uuid4(),
                content=f"Result {i}",
                page_numbers=[i],
                score=1.0 - (i * 0.1),
            )
            for i, chunk_id in enumerate(chunk_ids)
        ]

        fused = service._reciprocal_rank_fusion(vector_results, [], k=60)

        # Scores should be in descending order
        for i in range(len(fused) - 1):
            assert fused[i].score >= fused[i + 1].score

    def test_rrf_symmetry(self) -> None:
        """Test that RRF is symmetric (order of inputs doesn't matter)."""
        from src.search.hybrid import HybridSearchService

        mock_client = Mock()
        mock_embedding = Mock()
        service = HybridSearchService(mock_client, mock_embedding)

        results_a = [
            SearchResult(
                chunk_id=uuid4(),
                document_id=uuid4(),
                content="A",
                page_numbers=[1],
                score=0.9,
            )
        ]

        results_b = [
            SearchResult(
                chunk_id=uuid4(),
                document_id=uuid4(),
                content="B",
                page_numbers=[2],
                score=0.8,
            )
        ]

        # Order shouldn't matter for RRF scores
        fused_1 = service._reciprocal_rank_fusion(results_a, results_b, k=60)
        fused_2 = service._reciprocal_rank_fusion(results_b, results_a, k=60)

        # Both should have same chunks (different order possible)
        chunk_ids_1 = {r.chunk_id for r in fused_1}
        chunk_ids_2 = {r.chunk_id for r in fused_2}
        assert chunk_ids_1 == chunk_ids_2
