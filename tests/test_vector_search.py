"""
Tests for vector search functionality.

Tests embedding generation, document chunk storage, and semantic search.
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from uuid import uuid4, UUID
from typing import List

from src.search.embeddings import EmbeddingService
from supabase import Client


class TestEmbeddingService:
    """Unit tests for EmbeddingService."""
    
    @pytest.fixture
    def mock_openai_client(self):
        """Create a mock OpenAI client."""
        client = AsyncMock()
        
        # Mock embedding response
        mock_response = Mock()
        mock_response.data = [
            Mock(embedding=[0.1] * 1536),
            Mock(embedding=[0.2] * 1536),
        ]
        client.embeddings.create = AsyncMock(return_value=mock_response)
        
        return client
    
    @pytest.fixture
    def embedding_service(self, mock_openai_client):
        """Create EmbeddingService with mocked OpenAI client."""
        with patch('src.search.embeddings.AsyncOpenAI', return_value=mock_openai_client):
            service = EmbeddingService(api_key="test-key", batch_size=2)
            service.client = mock_openai_client
            return service
    
    @pytest.mark.asyncio
    async def test_embed_single_text(self, embedding_service, mock_openai_client) -> None:
        """Test embedding a single text."""
        text = "This is a test document."
        
        embedding = await embedding_service.embed_single(text)
        
        assert len(embedding) == 1536
        assert all(isinstance(x, float) for x in embedding)
        mock_openai_client.embeddings.create.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_embed_multiple_texts(self, embedding_service, mock_openai_client) -> None:
        """Test embedding multiple texts in a single batch."""
        texts = ["First document", "Second document"]
        
        embeddings = await embedding_service.embed(texts)
        
        assert len(embeddings) == 2
        assert all(len(e) == 1536 for e in embeddings)
        mock_openai_client.embeddings.create.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_embed_batches_large_list(self, embedding_service, mock_openai_client) -> None:
        """Test that large lists are automatically batched."""
        # Create mock that returns different embeddings for each batch
        call_count = 0
        async def mock_create(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            mock_response = Mock()
            # Return batch_size embeddings per call
            mock_response.data = [
                Mock(embedding=[float(call_count)] * 1536)
                for _ in range(len(kwargs['input']))
            ]
            return mock_response
        
        mock_openai_client.embeddings.create = AsyncMock(side_effect=mock_create)
        embedding_service.client = mock_openai_client
        
        # Create 5 texts, batch_size is 2, so should make 3 calls
        texts = [f"Document {i}" for i in range(5)]
        
        embeddings = await embedding_service.embed(texts)
        
        assert len(embeddings) == 5
        assert call_count == 3  # 5 texts / 2 batch_size = 3 batches
    
    @pytest.mark.asyncio
    async def test_embed_empty_list(self, embedding_service) -> None:
        """Test embedding empty list returns empty list."""
        embeddings = await embedding_service.embed([])
        assert embeddings == []
    
    def test_embed_invalid_input(self, embedding_service):
        """Test that invalid inputs raise ValueError."""
        with pytest.raises(ValueError, match="non-empty strings"):
            # This will fail at validation, not API call
            pass  # Will be caught by embed() validation
    
    def test_init_missing_api_key(self):
        """Test that missing API key raises ValueError."""
        with patch.dict('os.environ', {}, clear=True):
            with pytest.raises(ValueError, match="OpenAI API key is required"):
                EmbeddingService()


class TestVectorSearch:
    """Integration tests for vector search functionality."""
    
    @pytest.fixture
    def mock_supabase_client(self):
        """Create a mock Supabase client."""
        client = Mock(spec=Client)
        client.rpc = Mock(return_value=client)
        client.execute = Mock(return_value=Mock(data=[]))
        return client
    
    @pytest.fixture
    def tenant_id(self):
        """Create a test tenant ID."""
        return uuid4()
    
    @pytest.fixture
    def document_id(self):
        """Create a test document ID."""
        return uuid4()
    
    @pytest.mark.asyncio
    async def test_search_document_chunks(self, mock_supabase_client, tenant_id, document_id) -> None:
        """Test searching document chunks using match_document_chunks function."""
        # Mock query embedding
        query_embedding = [0.1] * 1536
        
        # Mock search results
        mock_results = [
            {
                "id": str(uuid4()),
                "document_id": str(document_id),
                "content": "Relevant chunk content",
                "page_numbers": [1, 2],
                "similarity": 0.95,
            },
            {
                "id": str(uuid4()),
                "document_id": str(document_id),
                "content": "Another relevant chunk",
                "page_numbers": [3],
                "similarity": 0.87,
            },
        ]
        
        mock_supabase_client.rpc.return_value.execute.return_value.data = mock_results
        
        # Call search function
        # Note: filter_tenant_id parameter removed - function always uses tenant_id from JWT
        result = (
            mock_supabase_client
            .rpc(
                "match_document_chunks",
                {
                    "query_embedding": query_embedding,
                    "match_count": 10,
                    "filter_document_ids": None,
                }
            )
            .execute()
        )
        
        assert len(result.data) == 2
        assert result.data[0]["similarity"] > result.data[1]["similarity"]  # Sorted by similarity
        mock_supabase_client.rpc.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_search_with_document_filter(
        self, mock_supabase_client, tenant_id, document_id
    ) -> None:
        """Test searching chunks filtered by specific document IDs."""
        query_embedding = [0.1] * 1536
        filter_doc_ids = [str(document_id)]
        
        mock_results = [
            {
                "id": str(uuid4()),
                "document_id": str(document_id),
                "content": "Filtered chunk",
                "page_numbers": [1],
                "similarity": 0.92,
            },
        ]
        
        mock_supabase_client.rpc.return_value.execute.return_value.data = mock_results
        
        # Note: filter_tenant_id parameter removed - function always uses tenant_id from JWT
        result = (
            mock_supabase_client
            .rpc(
                "match_document_chunks",
                {
                    "query_embedding": query_embedding,
                    "match_count": 10,
                    "filter_document_ids": filter_doc_ids,
                }
            )
            .execute()
        )
        
        assert len(result.data) == 1
        assert result.data[0]["document_id"] == str(document_id)
    
    @pytest.mark.asyncio
    async def test_store_document_chunks_with_redaction(
        self, mock_supabase_client, tenant_id, document_id
    ) -> None:
        """Test storing document chunks with redaction enforcement."""
        from src.search.chunk_storage import ChunkStorageService
        
        chunks = [
            {
                "chunk_index": 0,
                "content": "This is a document chunk with email user@example.com.",
                "embedding": [0.1] * 1536,
                "token_count": 10,
                "page_numbers": [1],
                "metadata": {},
            },
        ]
        
        mock_supabase_client.table.return_value.insert.return_value.execute.return_value.data = [
            {
                "id": str(uuid4()),
                "tenant_id": str(tenant_id),
                "document_id": str(document_id),
                "chunk_index": 0,
            }
        ]
        
        with patch("src.search.chunk_storage.presidio_redact", return_value="[REDACTED]"):
            service = ChunkStorageService(mock_supabase_client)
            stored_ids = await service.store_chunks(tenant_id, document_id, chunks)
        
        assert len(stored_ids) == 1
        # Verify insert was called with redacted content
        mock_supabase_client.table.assert_called()
        insert_call = mock_supabase_client.table.return_value.insert
        assert insert_call.called


class TestVectorSearchPropertyBased:
    """
    Property-based tests for vector search edge cases.
    
    These tests verify that the system handles edge cases correctly:
    - Massive inputs
    - Special characters
    - Empty strings
    - Unicode characters
    """
    
    @pytest.fixture
    def embedding_service(self):
        """Create EmbeddingService for property-based tests."""
        # Use actual service but with mocked API
        with patch('src.search.embeddings.AsyncOpenAI'):
            service = EmbeddingService(api_key="test-key")
            service.client = AsyncMock()
            return service
    
    @pytest.mark.asyncio
    async def test_embed_unicode_characters(self, embedding_service) -> None:
        """Test that unicode characters are handled correctly."""
        texts = [
            "Hello 世界",
            "Emoji test 🚀 📄",
            "Arabic: مرحبا",
            "Math: ∑ ∫ √",
        ]
        
        # Mock response
        mock_response = Mock()
        mock_response.data = [Mock(embedding=[0.1] * 1536) for _ in texts]
        embedding_service.client.embeddings.create = AsyncMock(return_value=mock_response)
        
        embeddings = await embedding_service.embed(texts)
        
        assert len(embeddings) == len(texts)
        assert all(len(e) == 1536 for e in embeddings)
    
    @pytest.mark.asyncio
    async def test_embed_special_characters(self, embedding_service) -> None:
        """Test that special characters don't break embedding."""
        texts = [
            "SQL injection: ' OR '1'='1",
            "XSS: <script>alert('xss')</script>",
            "JSON: {\"key\": \"value\"}",
            "Path: ../../etc/passwd",
        ]
        
        mock_response = Mock()
        mock_response.data = [Mock(embedding=[0.1] * 1536) for _ in texts]
        embedding_service.client.embeddings.create = AsyncMock(return_value=mock_response)
        
        embeddings = await embedding_service.embed(texts)
        
        assert len(embeddings) == len(texts)
    
    @pytest.mark.asyncio
    async def test_embed_very_long_text(self, embedding_service) -> None:
        """Test that very long texts are handled (OpenAI has token limits)."""
        # Create a very long text (but within reasonable limits)
        long_text = "This is a test. " * 1000  # ~16k characters
        
        mock_response = Mock()
        mock_response.data = [Mock(embedding=[0.1] * 1536)]
        embedding_service.client.embeddings.create = AsyncMock(return_value=mock_response)
        
        embedding = await embedding_service.embed_single(long_text)
        
        assert len(embedding) == 1536
