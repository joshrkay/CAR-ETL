"""Tests for keyword search functionality."""

import sys
from pathlib import Path
from unittest.mock import Mock
from uuid import UUID, uuid4

import pytest
from supabase import Client

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from src.search.keyword_search import KeywordSearchResult, KeywordSearchService


class TestKeywordSearchService:
    """Unit tests for KeywordSearchService."""

    @pytest.fixture
    def mock_supabase_client(self):
        """Create a mock Supabase client."""
        client = Mock(spec=Client)
        client.rpc = Mock(return_value=client)
        client.execute = Mock(return_value=Mock(data=[]))
        return client

    def test_search_chunks_with_tenant_id(self, mock_supabase_client):
        """Search should include tenant filter when provided."""
        tenant_id = uuid4()
        document_id = uuid4()
        mock_supabase_client.rpc.return_value.execute.return_value.data = [
            {
                "id": str(uuid4()),
                "document_id": str(document_id),
                "content": "matched content",
                "page_numbers": [1, 2],
                "rank": 0.42,
            }
        ]

        service = KeywordSearchService(mock_supabase_client)
        results = asyncio.run(
            service.search_chunks(
                query_text="lease terms",
                match_count=5,
                tenant_id=tenant_id,
            )
        )

        assert len(results) == 1
        assert isinstance(results[0], KeywordSearchResult)
        assert results[0].document_id == document_id
        mock_supabase_client.rpc.assert_called_once_with(
            "search_chunks_keyword",
            {
                "query_text": "lease terms",
                "match_count": 5,
                "filter_tenant_id": str(tenant_id),
            },
        )

    def test_search_chunks_without_tenant_id(self, mock_supabase_client):
        """Search should omit tenant filter when not provided."""
        mock_supabase_client.rpc.return_value.execute.return_value.data = []

        service = KeywordSearchService(mock_supabase_client)
        results = asyncio.run(service.search_chunks(query_text="rent", match_count=3))

        assert results == []
        mock_supabase_client.rpc.assert_called_once_with(
            "search_chunks_keyword",
            {
                "query_text": "rent",
                "match_count": 3,
            },
        )

    @pytest.mark.asyncio
    async def test_search_chunks_requires_query(self, mock_supabase_client):
        """Search should require non-empty query text."""
        service = KeywordSearchService(mock_supabase_client)

        with pytest.raises(ValueError, match="query_text must be a non-empty string"):
            service.search_chunks(query_text=" ")

    @pytest.mark.asyncio
    async def test_search_chunks_requires_positive_match_count(self, mock_supabase_client):
        """Search should require match_count >= 1."""
        service = KeywordSearchService(mock_supabase_client)

        with pytest.raises(ValueError, match="match_count must be >= 1"):
            asyncio.run(service.search_chunks(query_text="terms", match_count=0))

    def test_parse_result_defaults_page_numbers(self, mock_supabase_client):
        """Parse should default page_numbers to empty list when missing."""
        service = KeywordSearchService(mock_supabase_client)
        row = {
            "id": str(uuid4()),
            "document_id": str(uuid4()),
            "content": "content",
            "rank": 1.0,
        }

        result = service._parse_result(row)

        assert isinstance(result.id, UUID)
        assert result.page_numbers == []

    def test_search_chunks_handles_rpc_exception(self, mock_supabase_client):
        """Search should log and re-raise exceptions from RPC call."""
        mock_supabase_client.rpc.return_value.execute.side_effect = Exception(
            "Database connection error"
        )

        service = KeywordSearchService(mock_supabase_client)

        with pytest.raises(Exception, match="Database connection error"):
            service.search_chunks(query_text="test query", match_count=5)
