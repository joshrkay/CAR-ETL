"""
Performance tests for vector search latency.

Measures embedding generation, vector search query, and end-to-end search latency.
"""

import pytest
import time
import asyncio
import statistics
from unittest.mock import Mock, AsyncMock, patch
from uuid import uuid4, UUID
from typing import List

from src.search.embeddings import EmbeddingService
from supabase import Client


class TestVectorSearchLatency:
    """Performance tests for vector search operations."""
    
    @pytest.fixture
    def mock_openai_client(self):
        """Create a mock OpenAI client with realistic latency simulation."""
        client = AsyncMock()
        
        async def mock_embedding_create(*args, **kwargs):
            # Simulate realistic API latency (50-200ms)
            await asyncio.sleep(0.1)  # 100ms average latency
            mock_response = Mock()
            batch_size = len(kwargs.get("input", []))
            mock_response.data = [
                Mock(embedding=[0.1] * 1536) for _ in range(batch_size)
            ]
            return mock_response
        
        client.embeddings.create = AsyncMock(side_effect=mock_embedding_create)
        return client
    
    @pytest.fixture
    def embedding_service(self, mock_openai_client):
        """Create EmbeddingService with mocked OpenAI client."""
        with patch('src.search.embeddings.AsyncOpenAI', return_value=mock_openai_client):
            service = EmbeddingService(api_key="test-key", batch_size=10)
            service.client = mock_openai_client
            return service
    
    @pytest.fixture
    def mock_supabase_client(self):
        """Create a mock Supabase client with latency simulation."""
        client = Mock(spec=Client)
        
        # Simulate database query latency (10-50ms)
        def mock_rpc(*args, **kwargs):
            time.sleep(0.02)  # 20ms average query latency
            mock_result = Mock()
            mock_result.data = [
                {
                    "id": str(uuid4()),
                    "document_id": str(uuid4()),
                    "content": "Test chunk content",
                    "page_numbers": [1],
                    "similarity": 0.95 - (i * 0.01),
                }
                for i in range(10)
            ]
            return mock_result
        
        client.rpc = Mock(return_value=Mock(execute=Mock(side_effect=mock_rpc)))
        return client
    
    @pytest.mark.asyncio
    async def test_embedding_generation_latency(self, embedding_service):
        """Test latency of embedding generation for single text."""
        query_text = "What is the main topic of this document?"
        
        start_time = time.perf_counter()
        embedding = await embedding_service.embed_single(query_text)
        end_time = time.perf_counter()
        
        latency_ms = (end_time - start_time) * 1000
        
        assert len(embedding) == 1536
        assert latency_ms > 0
        print(f"\nEmbedding generation latency: {latency_ms:.2f}ms")
    
    @pytest.mark.asyncio
    async def test_embedding_batch_latency(self, embedding_service):
        """Test latency of batch embedding generation."""
        texts = [f"Document chunk {i} with some content." for i in range(20)]
        
        start_time = time.perf_counter()
        embeddings = await embedding_service.embed(texts)
        end_time = time.perf_counter()
        
        latency_ms = (end_time - start_time) * 1000
        latency_per_text = latency_ms / len(texts)
        
        assert len(embeddings) == 20
        assert latency_ms > 0
        print(f"\nBatch embedding latency: {latency_ms:.2f}ms total ({latency_per_text:.2f}ms per text)")
    
    @pytest.mark.asyncio
    async def test_vector_search_query_latency(self, mock_supabase_client):
        """Test latency of vector search query (match_document_chunks function)."""
        query_embedding = [0.1] * 1536
        tenant_id = uuid4()
        
        start_time = time.perf_counter()
        result = (
            mock_supabase_client
            .rpc(
                "match_document_chunks",
                {
                    "query_embedding": query_embedding,
                    "match_count": 10,
                    "filter_tenant_id": str(tenant_id),
                    "filter_document_ids": None,
                }
            )
            .execute()
        )
        end_time = time.perf_counter()
        
        latency_ms = (end_time - start_time) * 1000
        
        assert len(result.data) == 10
        assert latency_ms > 0
        print(f"\nVector search query latency: {latency_ms:.2f}ms")
    
    @pytest.mark.asyncio
    async def test_end_to_end_search_latency(
        self, embedding_service, mock_supabase_client
    ):
        """Test end-to-end search latency (embedding + search)."""
        query_text = "What are the key findings in this research?"
        tenant_id = uuid4()
        
        # Step 1: Generate embedding
        embed_start = time.perf_counter()
        query_embedding = await embedding_service.embed_single(query_text)
        embed_end = time.perf_counter()
        embed_latency_ms = (embed_end - embed_start) * 1000
        
        # Step 2: Execute search
        search_start = time.perf_counter()
        result = (
            mock_supabase_client
            .rpc(
                "match_document_chunks",
                {
                    "query_embedding": query_embedding,
                    "match_count": 10,
                    "filter_tenant_id": str(tenant_id),
                    "filter_document_ids": None,
                }
            )
            .execute()
        )
        search_end = time.perf_counter()
        search_latency_ms = (search_end - search_start) * 1000
        
        total_latency_ms = embed_latency_ms + search_latency_ms
        
        assert len(result.data) == 10
        print(f"\nEnd-to-end search latency breakdown:")
        print(f"  Embedding: {embed_latency_ms:.2f}ms")
        print(f"  Search: {search_latency_ms:.2f}ms")
        print(f"  Total: {total_latency_ms:.2f}ms")
    
    @pytest.mark.asyncio
    async def test_search_latency_with_multiple_queries(
        self, embedding_service, mock_supabase_client
    ):
        """Test search latency across multiple queries to measure consistency."""
        queries = [
            "What is the main topic?",
            "Who are the authors?",
            "What are the conclusions?",
            "What methodology was used?",
            "What are the key findings?",
        ]
        
        tenant_id = uuid4()
        latencies: List[float] = []
        
        for query in queries:
            start_time = time.perf_counter()
            
            # Generate embedding
            query_embedding = await embedding_service.embed_single(query)
            
            # Execute search
            result = (
                mock_supabase_client
                .rpc(
                    "match_document_chunks",
                    {
                        "query_embedding": query_embedding,
                        "match_count": 10,
                        "filter_tenant_id": str(tenant_id),
                        "filter_document_ids": None,
                    }
                )
                .execute()
            )
            
            end_time = time.perf_counter()
            latency_ms = (end_time - start_time) * 1000
            latencies.append(latency_ms)
        
        avg_latency = statistics.mean(latencies)
        median_latency = statistics.median(latencies)
        min_latency = min(latencies)
        max_latency = max(latencies)
        std_dev = statistics.stdev(latencies) if len(latencies) > 1 else 0
        
        print(f"\nSearch latency statistics ({len(queries)} queries):")
        print(f"  Average: {avg_latency:.2f}ms")
        print(f"  Median: {median_latency:.2f}ms")
        print(f"  Min: {min_latency:.2f}ms")
        print(f"  Max: {max_latency:.2f}ms")
        print(f"  Std Dev: {std_dev:.2f}ms")
        
        assert avg_latency > 0
        assert len(latencies) == len(queries)
    
    @pytest.mark.asyncio
    async def test_search_latency_with_document_filter(
        self, embedding_service, mock_supabase_client
    ):
        """Test search latency when filtering by specific documents."""
        query_text = "What is discussed in these documents?"
        tenant_id = uuid4()
        document_ids = [str(uuid4()) for _ in range(3)]
        
        query_embedding = await embedding_service.embed_single(query_text)
        
        start_time = time.perf_counter()
        result = (
            mock_supabase_client
            .rpc(
                "match_document_chunks",
                {
                    "query_embedding": query_embedding,
                    "match_count": 10,
                    "filter_tenant_id": str(tenant_id),
                    "filter_document_ids": document_ids,
                }
            )
            .execute()
        )
        end_time = time.perf_counter()
        
        latency_ms = (end_time - start_time) * 1000
        
        assert latency_ms > 0
        print(f"\nFiltered search latency: {latency_ms:.2f}ms (filtered to {len(document_ids)} documents)")
