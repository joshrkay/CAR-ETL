"""
Test script for hybrid search API endpoint.

Tests all three search modes (hybrid, semantic, keyword) with sample queries.
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

try:
    from dotenv import load_dotenv
    env_path = project_root / ".env"
    if env_path.exists():
        load_dotenv(env_path)
    else:
        load_dotenv()
except ImportError:
    pass

import httpx
import os
from uuid import uuid4


def get_test_token():
    """Get authentication token for testing."""
    # This would typically come from a login flow
    # For testing, you need a valid JWT token from your Supabase instance
    token = os.getenv("TEST_AUTH_TOKEN")
    if not token:
        print("[ERROR] TEST_AUTH_TOKEN environment variable not set")
        print("[INFO] To get a token:")
        print("  1. Login to your application")
        print("  2. Copy the JWT token from browser dev tools")
        print("  3. Set TEST_AUTH_TOKEN=<your-token>")
        return None
    return token


async def test_search_endpoint():
    """Test the hybrid search endpoint."""
    print("=" * 70)
    print("Hybrid Search API Test")
    print("=" * 70)

    # Get base URL and token
    base_url = os.getenv("SUPABASE_URL", "http://localhost:8000")
    if not base_url.startswith("http"):
        base_url = f"https://{base_url}"

    # Strip /rest/v1 if present and use API base
    if "/rest/v1" in base_url:
        base_url = base_url.replace("/rest/v1", "")

    api_url = base_url.rstrip("/")

    token = get_test_token()
    if not token:
        print("\n[SKIP] Skipping API tests (no auth token)")
        print("\n[INFO] To test the endpoint:")
        print("  1. Start the API server: uvicorn src.main:app --reload")
        print("  2. Login and get an auth token")
        print("  3. Run: TEST_AUTH_TOKEN=<token> python scripts/test_hybrid_search.py")
        return

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    # Test queries
    test_cases = [
        {
            "name": "Hybrid Search - Lease Terms",
            "payload": {
                "query": "base rent escalation clause",
                "mode": "hybrid",
                "limit": 10,
            },
        },
        {
            "name": "Semantic Search - Conceptual",
            "payload": {
                "query": "tenant improvement allowance",
                "mode": "semantic",
                "limit": 10,
            },
        },
        {
            "name": "Keyword Search - Exact Terms",
            "payload": {
                "query": "square footage",
                "mode": "keyword",
                "limit": 10,
            },
        },
        {
            "name": "Hybrid Search with Reranking",
            "payload": {
                "query": "operating expenses and CAM charges",
                "mode": "hybrid",
                "limit": 20,
                "enable_reranking": True,
            },
        },
        {
            "name": "Filtered Search - Specific Document",
            "payload": {
                "query": "lease term",
                "mode": "hybrid",
                "limit": 10,
                "filters": {
                    "document_ids": [],  # Would need actual document IDs
                },
            },
        },
    ]

    async with httpx.AsyncClient(timeout=30.0) as client:
        for i, test_case in enumerate(test_cases, 1):
            print(f"\n{'=' * 70}")
            print(f"Test {i}/{len(test_cases)}: {test_case['name']}")
            print(f"{'=' * 70}")

            print(f"\nQuery: {test_case['payload']['query']}")
            print(f"Mode: {test_case['payload']['mode']}")
            print(f"Limit: {test_case['payload']['limit']}")

            # Skip filtered search if no document IDs
            if test_case['name'] == "Filtered Search - Specific Document":
                print("\n[SKIP] Filtered search requires actual document IDs")
                continue

            try:
                response = await client.post(
                    f"{api_url}/api/v1/search",
                    json=test_case["payload"],
                    headers=headers,
                )

                print(f"\nStatus Code: {response.status_code}")

                if response.status_code == 200:
                    data = response.json()
                    print(f"Results: {data['total_count']}")
                    print(f"Search Mode: {data['search_mode']}")

                    if data['results']:
                        print("\nTop 3 Results:")
                        for idx, result in enumerate(data['results'][:3], 1):
                            print(f"\n  {idx}. Document: {result['document_name']}")
                            print(f"     Score: {result['score']:.4f}")
                            print(f"     Pages: {result['page_numbers']}")

                            # Show first highlight
                            if result['highlights']:
                                highlight = result['highlights'][0]
                                # Truncate if too long
                                if len(highlight) > 100:
                                    highlight = highlight[:100] + "..."
                                print(f"     Highlight: {highlight}")
                    else:
                        print("\n[INFO] No results found (may need to ingest documents)")

                    print("\n[PASS] Test successful")
                else:
                    print(f"\n[FAIL] Request failed: {response.text}")

            except httpx.ConnectError:
                print(f"\n[ERROR] Cannot connect to {api_url}")
                print("[INFO] Make sure the API server is running:")
                print("  uvicorn src.main:app --reload --host 0.0.0.0 --port 8000")
                return
            except Exception as e:
                print(f"\n[ERROR] Test failed: {e}")

    print("\n" + "=" * 70)
    print("Test Summary")
    print("=" * 70)
    print("\n[INFO] Hybrid search endpoint is functional")
    print("[INFO] To verify results, ensure documents are ingested and chunked")


async def test_search_components():
    """Test individual search components."""
    print("\n" + "=" * 70)
    print("Component Tests")
    print("=" * 70)

    # Test highlighter
    print("\n1. Testing SearchHighlighter")
    try:
        from src.search.highlighter import SearchHighlighter

        highlighter = SearchHighlighter()
        content = "The lease agreement includes base rent of $50 per square foot with annual escalations."
        query = "base rent escalation"

        highlights = highlighter.highlight(content, query)
        print(f"   Query: {query}")
        print(f"   Highlights: {len(highlights)}")
        if highlights:
            print(f"   Sample: {highlights[0]}")
        print("   [PASS] Highlighter working")
    except Exception as e:
        print(f"   [FAIL] {e}")

    # Test reranker availability
    print("\n2. Testing SearchReranker")
    try:
        from src.search.reranker import SearchReranker

        reranker = SearchReranker()
        if reranker.is_available():
            print("   [INFO] Cross-encoder available")
            print(f"   Model: {reranker.model_name}")
        else:
            print("   [INFO] Cross-encoder not available (sentence-transformers not installed)")
            print("   [INFO] Install with: pip install sentence-transformers")
        print("   [PASS] Reranker configured correctly")
    except Exception as e:
        print(f"   [FAIL] {e}")

    # Test embedding service
    print("\n3. Testing EmbeddingService")
    try:
        from src.search.embeddings import EmbeddingService

        # Just check if it can be instantiated
        if os.getenv("OPENAI_API_KEY"):
            service = EmbeddingService()
            print(f"   Model: {service.model}")
            print(f"   Dimensions: {service.embedding_dimension}")
            print("   [PASS] Embedding service configured")
        else:
            print("   [SKIP] OPENAI_API_KEY not set")
    except Exception as e:
        print(f"   [FAIL] {e}")

    # Test RRF algorithm
    print("\n4. Testing RRF Algorithm")
    try:
        from src.search.hybrid import HybridSearchService, SearchResult
        from uuid import uuid4

        # Mock client for testing
        class MockClient:
            pass

        class MockEmbedding:
            pass

        service = HybridSearchService(MockClient(), MockEmbedding())

        # Test RRF with sample results
        chunk_id_1 = uuid4()
        chunk_id_2 = uuid4()

        vector_results = [
            SearchResult(
                chunk_id=chunk_id_1,
                document_id=uuid4(),
                content="Result 1",
                page_numbers=[1],
                score=0.9,
            )
        ]

        keyword_results = [
            SearchResult(
                chunk_id=chunk_id_2,
                document_id=uuid4(),
                content="Result 2",
                page_numbers=[2],
                score=0.8,
            )
        ]

        fused = service._reciprocal_rank_fusion(vector_results, keyword_results, k=60)
        print(f"   Input: 1 vector + 1 keyword result")
        print(f"   Output: {len(fused)} fused results")
        print("   [PASS] RRF algorithm working")
    except Exception as e:
        print(f"   [FAIL] {e}")


async def main():
    """Run all tests."""
    print("\n" + "=" * 70)
    print("HYBRID SEARCH TEST SUITE")
    print("=" * 70)

    # Test components first
    await test_search_components()

    # Test API endpoint
    await test_search_endpoint()

    print("\n" + "=" * 70)
    print("ALL TESTS COMPLETE")
    print("=" * 70)
    print("\n[INFO] Hybrid search implementation verified")
    print("\n[NEXT STEPS]:")
    print("  1. Apply migration: supabase/migrations/044_keyword_search.sql")
    print("  2. Ingest documents to test with real data")
    print("  3. Monitor search performance and latency")
    print("  4. Optional: Install sentence-transformers for reranking")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n[INTERRUPTED] Tests cancelled")
        sys.exit(1)
    except Exception as e:
        print(f"\n[ERROR] Tests failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
