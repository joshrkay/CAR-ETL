"""
Script to test vector search latency.

Run this script to measure actual search latency with your Supabase database.
Requires OPENAI_API_KEY and Supabase credentials in environment.
"""

import asyncio
import os
import statistics
import sys
import time

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.auth.client import create_service_client
from src.search.embeddings import EmbeddingService
from supabase import Client


async def test_embedding_latency(service: EmbeddingService, num_tests: int = 5):
    """Test embedding generation latency."""
    print("\n" + "=" * 60)
    print("Testing Embedding Generation Latency")
    print("=" * 60)

    test_queries = [
        "What is the main topic of this document?",
        "Who are the authors?",
        "What are the conclusions?",
        "What methodology was used?",
        "What are the key findings?",
    ]

    latencies: list[float] = []

    for i, query in enumerate(test_queries[:num_tests], 1):
        start_time = time.perf_counter()
        embedding = await service.embed_single(query)
        end_time = time.perf_counter()

        latency_ms = (end_time - start_time) * 1000
        latencies.append(latency_ms)

        print(f"Query {i}: {latency_ms:.2f}ms")
        assert len(embedding) == 1536

    avg_latency = statistics.mean(latencies)
    median_latency = statistics.median(latencies)
    min_latency = min(latencies)
    max_latency = max(latencies)

    print("\nStatistics:")
    print(f"  Average: {avg_latency:.2f}ms")
    print(f"  Median: {median_latency:.2f}ms")
    print(f"  Min: {min_latency:.2f}ms")
    print(f"  Max: {max_latency:.2f}ms")

    return latencies


async def test_search_latency(
    supabase: Client,
    embedding_service: EmbeddingService,
    tenant_id: str,
    num_tests: int = 5,
):
    """Test vector search query latency."""
    print("\n" + "=" * 60)
    print("Testing Vector Search Query Latency")
    print("=" * 60)

    test_queries = [
        "What is the main topic?",
        "Who are the authors?",
        "What are the conclusions?",
        "What methodology was used?",
        "What are the key findings?",
    ]

    latencies: list[float] = []

    for i, query_text in enumerate(test_queries[:num_tests], 1):
        # Generate embedding
        query_embedding = await embedding_service.embed_single(query_text)

        # Execute search
        start_time = time.perf_counter()
        result = (
            supabase.rpc(
                "match_document_chunks",
                {
                    "query_embedding": query_embedding,
                    "match_count": 10,
                    "filter_document_ids": None,
                }
            )
            .execute()
        )
        end_time = time.perf_counter()

        latency_ms = (end_time - start_time) * 1000
        latencies.append(latency_ms)

        print(f"Query {i}: {latency_ms:.2f}ms (found {len(result.data)} results)")

    if latencies:
        avg_latency = statistics.mean(latencies)
        median_latency = statistics.median(latencies)
        min_latency = min(latencies)
        max_latency = max(latencies)

        print("\nStatistics:")
        print(f"  Average: {avg_latency:.2f}ms")
        print(f"  Median: {median_latency:.2f}ms")
        print(f"  Min: {min_latency:.2f}ms")
        print(f"  Max: {max_latency:.2f}ms")

    return latencies


async def test_end_to_end_latency(
    supabase: Client,
    embedding_service: EmbeddingService,
    tenant_id: str,
    num_tests: int = 5,
):
    """Test end-to-end search latency (embedding + search)."""
    print("\n" + "=" * 60)
    print("Testing End-to-End Search Latency")
    print("=" * 60)

    test_queries = [
        "What is the main topic?",
        "Who are the authors?",
        "What are the conclusions?",
        "What methodology was used?",
        "What are the key findings?",
    ]

    total_latencies: list[float] = []
    embed_latencies: list[float] = []
    search_latencies: list[float] = []

    for i, query_text in enumerate(test_queries[:num_tests], 1):
        # Generate embedding
        embed_start = time.perf_counter()
        query_embedding = await embedding_service.embed_single(query_text)
        embed_end = time.perf_counter()
        embed_latency_ms = (embed_end - embed_start) * 1000
        embed_latencies.append(embed_latency_ms)

        # Execute search
        search_start = time.perf_counter()
        result = (
            supabase.rpc(
                "match_document_chunks",
                {
                    "query_embedding": query_embedding,
                    "match_count": 10,
                    "filter_document_ids": None,
                }
            )
            .execute()
        )
        search_end = time.perf_counter()
        search_latency_ms = (search_end - search_start) * 1000
        search_latencies.append(search_latency_ms)

        total_latency_ms = embed_latency_ms + search_latency_ms
        total_latencies.append(total_latency_ms)

        print(
            f"Query {i}: Total={total_latency_ms:.2f}ms "
            f"(Embed={embed_latency_ms:.2f}ms, Search={search_latency_ms:.2f}ms) "
            f"[{len(result.data)} results]"
        )

    if total_latencies:
        print("\nTotal Latency Statistics:")
        print(f"  Average: {statistics.mean(total_latencies):.2f}ms")
        print(f"  Median: {statistics.median(total_latencies):.2f}ms")
        print(f"  Min: {min(total_latencies):.2f}ms")
        print(f"  Max: {max(total_latencies):.2f}ms")

        print("\nEmbedding Latency Statistics:")
        print(f"  Average: {statistics.mean(embed_latencies):.2f}ms")
        print(f"  Median: {statistics.median(embed_latencies):.2f}ms")

        print("\nSearch Latency Statistics:")
        print(f"  Average: {statistics.mean(search_latencies):.2f}ms")
        print(f"  Median: {statistics.median(search_latencies):.2f}ms")

    return total_latencies, embed_latencies, search_latencies


async def main():
    """Run all latency tests."""
    print("Vector Search Latency Test")
    print("=" * 60)

    # Check for required environment variables
    if not os.getenv("OPENAI_API_KEY"):
        print("ERROR: OPENAI_API_KEY environment variable is required")
        sys.exit(1)

    # Initialize services
    embedding_service = EmbeddingService()
    supabase = create_service_client()

    # Get tenant ID (use first tenant or create test tenant)
    # For testing, you may want to use a specific tenant ID
    tenant_id = os.getenv("TEST_TENANT_ID")
    if not tenant_id:
        print("WARNING: TEST_TENANT_ID not set. Using service role client.")
        print("Note: Search tests require a valid tenant_id with document_chunks.")
        tenant_id = None

    try:
        # Test 1: Embedding latency
        await test_embedding_latency(embedding_service, num_tests=5)

        # Test 2: Search latency (if tenant_id provided)
        if tenant_id:
            await test_search_latency(
                supabase, embedding_service, tenant_id, num_tests=5
            )

            # Test 3: End-to-end latency
            await test_end_to_end_latency(
                supabase, embedding_service, tenant_id, num_tests=5
            )
        else:
            print("\n" + "=" * 60)
            print("Skipping search tests (TEST_TENANT_ID not set)")
            print("=" * 60)

        print("\n" + "=" * 60)
        print("Latency tests completed successfully!")
        print("=" * 60)

    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
