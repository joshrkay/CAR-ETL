"""Load test for tenant database connection caching."""
import os
import sys
import time
import uuid
import statistics
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from sqlalchemy import text
except ImportError:
    print("[ERROR] Required packages not installed. Install with:")
    print("  pip install sqlalchemy psycopg2-binary")
    sys.exit(1)


@dataclass
class LoadTestResult:
    """Result of a single load test operation."""
    tenant_id: str
    operation: str  # 'cache_hit' or 'cache_miss'
    elapsed_ms: float
    success: bool
    error: Optional[str] = None


@dataclass
class LoadTestSummary:
    """Summary of load test results."""
    total_requests: int
    successful_requests: int
    failed_requests: int
    cache_hits: int
    cache_misses: int
    avg_response_time_ms: float
    p50_response_time_ms: float
    p95_response_time_ms: float
    p99_response_time_ms: float
    max_response_time_ms: float
    min_response_time_ms: float
    cache_hit_avg_ms: float
    cache_miss_avg_ms: float
    cache_hit_rate: float


def load_test_tenant_resolver(
    tenant_ids: List[str],
    num_requests: int = 1000,
    num_threads: int = 10,
    cache_warmup: bool = True
) -> LoadTestSummary:
    """Run load test on tenant resolver caching.
    
    Args:
        tenant_ids: List of tenant IDs to test with.
        num_requests: Total number of requests to make.
        num_threads: Number of concurrent threads.
        cache_warmup: Whether to warm up cache before load test.
    
    Returns:
        LoadTestSummary with test results.
    """
    try:
        from src.services.tenant_resolver import get_tenant_resolver
    except ImportError as e:
        print(f"[ERROR] Failed to import modules: {e}")
        sys.exit(1)
    
    resolver = get_tenant_resolver()
    
    # Warm up cache if requested
    if cache_warmup:
        print("[INFO] Warming up cache...")
        for tenant_id in tenant_ids:
            resolver.resolve_tenant_connection(tenant_id)
        print("[INFO] Cache warmed up")
    
    # Clear cache stats
    resolver.invalidate_cache()
    
    results: List[LoadTestResult] = []
    cache_operations: Dict[str, str] = {}  # Track first vs subsequent calls
    
    def make_request(tenant_id: str, request_num: int) -> LoadTestResult:
        """Make a single request to resolve tenant connection."""
        start_time = time.time()
        
        try:
            # Check if this is first request for this tenant (cache miss)
            cache_key = f"{tenant_id}_{request_num}"
            is_first = tenant_id not in cache_operations
            if is_first:
                cache_operations[tenant_id] = "cache_miss"
                operation = "cache_miss"
            else:
                cache_operations[tenant_id] = "cache_hit"
                operation = "cache_hit"
            
            engine = resolver.resolve_tenant_connection(tenant_id)
            
            if engine:
                # Test connection
                with engine.connect() as conn:
                    conn.execute(text("SELECT 1"))
                
                elapsed = (time.time() - start_time) * 1000
                return LoadTestResult(
                    tenant_id=tenant_id,
                    operation=operation,
                    elapsed_ms=elapsed,
                    success=True
                )
            else:
                elapsed = (time.time() - start_time) * 1000
                return LoadTestResult(
                    tenant_id=tenant_id,
                    operation=operation,
                    elapsed_ms=elapsed,
                    success=False,
                    error="Failed to resolve connection"
                )
        except Exception as e:
            elapsed = (time.time() - start_time) * 1000
            return LoadTestResult(
                tenant_id=tenant_id,
                operation="error",
                elapsed_ms=elapsed,
                success=False,
                error=str(e)
            )
    
    # Distribute requests across tenants
    requests_per_tenant = num_requests // len(tenant_ids)
    remaining = num_requests % len(tenant_ids)
    
    print(f"[INFO] Starting load test...")
    print(f"       Total requests: {num_requests}")
    print(f"       Concurrent threads: {num_threads}")
    print(f"       Tenants: {len(tenant_ids)}")
    print()
    
    start_time = time.time()
    
    # Run load test
    with ThreadPoolExecutor(max_workers=num_threads) as executor:
        futures = []
        
        for i, tenant_id in enumerate(tenant_ids):
            requests_for_tenant = requests_per_tenant + (1 if i < remaining else 0)
            for j in range(requests_for_tenant):
                future = executor.submit(make_request, tenant_id, j)
                futures.append(future)
        
        # Collect results
        for future in as_completed(futures):
            try:
                result = future.result()
                results.append(result)
            except Exception as e:
                print(f"[ERROR] Request failed: {e}")
    
    total_time = time.time() - start_time
    
    # Calculate statistics
    successful = [r for r in results if r.success]
    failed = [r for r in results if not r.success]
    
    cache_hits = [r for r in successful if r.operation == "cache_hit"]
    cache_misses = [r for r in successful if r.operation == "cache_miss"]
    
    response_times = [r.elapsed_ms for r in successful]
    
    if response_times:
        response_times_sorted = sorted(response_times)
        n = len(response_times_sorted)
        
        summary = LoadTestSummary(
            total_requests=len(results),
            successful_requests=len(successful),
            failed_requests=len(failed),
            cache_hits=len(cache_hits),
            cache_misses=len(cache_misses),
            avg_response_time_ms=statistics.mean(response_times),
            p50_response_time_ms=response_times_sorted[n // 2] if n > 0 else 0,
            p95_response_time_ms=response_times_sorted[int(n * 0.95)] if n > 0 else 0,
            p99_response_time_ms=response_times_sorted[int(n * 0.99)] if n > 0 else 0,
            max_response_time_ms=max(response_times) if response_times else 0,
            min_response_time_ms=min(response_times) if response_times else 0,
            cache_hit_avg_ms=statistics.mean([r.elapsed_ms for r in cache_hits]) if cache_hits else 0,
            cache_miss_avg_ms=statistics.mean([r.elapsed_ms for r in cache_misses]) if cache_misses else 0,
            cache_hit_rate=(len(cache_hits) / len(successful) * 100) if successful else 0
        )
    else:
        summary = LoadTestSummary(
            total_requests=len(results),
            successful_requests=0,
            failed_requests=len(failed),
            cache_hits=0,
            cache_misses=0,
            avg_response_time_ms=0,
            p50_response_time_ms=0,
            p95_response_time_ms=0,
            p99_response_time_ms=0,
            max_response_time_ms=0,
            min_response_time_ms=0,
            cache_hit_avg_ms=0,
            cache_miss_avg_ms=0,
            cache_hit_rate=0
        )
    
    return summary, total_time


def print_load_test_results(summary: LoadTestSummary, total_time: float) -> None:
    """Print load test results in a formatted way."""
    print("=" * 70)
    print("Load Test Results - Tenant Cache Performance")
    print("=" * 70)
    print()
    
    print("Request Statistics:")
    print(f"  Total requests:        {summary.total_requests}")
    print(f"  Successful:            {summary.successful_requests} ({summary.successful_requests/summary.total_requests*100:.1f}%)")
    print(f"  Failed:                {summary.failed_requests} ({summary.failed_requests/summary.total_requests*100:.1f}%)")
    print()
    
    print("Cache Statistics:")
    print(f"  Cache hits:            {summary.cache_hits}")
    print(f"  Cache misses:          {summary.cache_misses}")
    print(f"  Cache hit rate:        {summary.cache_hit_rate:.2f}%")
    print()
    
    print("Response Time Statistics (ms):")
    print(f"  Average:               {summary.avg_response_time_ms:.2f}")
    print(f"  Median (p50):          {summary.p50_response_time_ms:.2f}")
    print(f"  p95:                   {summary.p95_response_time_ms:.2f}")
    print(f"  p99:                   {summary.p99_response_time_ms:.2f}")
    print(f"  Min:                   {summary.min_response_time_ms:.2f}")
    print(f"  Max:                   {summary.max_response_time_ms:.2f}")
    print()
    
    print("Cache Performance:")
    print(f"  Cache hit avg:         {summary.cache_hit_avg_ms:.2f} ms")
    print(f"  Cache miss avg:        {summary.cache_miss_avg_ms:.2f} ms")
    if summary.cache_miss_avg_ms > 0:
        speedup = summary.cache_miss_avg_ms / summary.cache_hit_avg_ms if summary.cache_hit_avg_ms > 0 else 0
        print(f"  Cache speedup:         {speedup:.2f}x faster")
    print()
    
    print("Throughput:")
    print(f"  Total time:            {total_time:.2f} seconds")
    print(f"  Requests/second:       {summary.total_requests/total_time:.2f}")
    print(f"  Successful req/s:      {summary.successful_requests/total_time:.2f}")
    print()
    
    # Performance targets
    print("Performance Targets:")
    target_cache_hit = 1.0  # <1ms for cache hit
    target_cache_miss = 50.0  # <50ms for cache miss
    target_overhead = 50.0  # <50ms middleware overhead
    
    cache_hit_ok = summary.cache_hit_avg_ms < target_cache_hit if summary.cache_hits > 0 else True
    cache_miss_ok = summary.cache_miss_avg_ms < target_cache_miss if summary.cache_misses > 0 else True
    avg_ok = summary.avg_response_time_ms < target_overhead
    
    print(f"  Cache hit < {target_cache_hit}ms:     {'✅ PASS' if cache_hit_ok else '❌ FAIL'}")
    print(f"  Cache miss < {target_cache_miss}ms:   {'✅ PASS' if cache_miss_ok else '❌ FAIL'}")
    print(f"  Average < {target_overhead}ms:        {'✅ PASS' if avg_ok else '❌ FAIL'}")
    print()
    
    print("=" * 70)


def test_cache_expiration() -> None:
    """Test cache expiration behavior."""
    print()
    print("=" * 70)
    print("Cache Expiration Test")
    print("=" * 70)
    print()
    
    try:
        from src.services.tenant_resolver import TenantResolver
    except ImportError as e:
        print(f"[ERROR] Failed to import modules: {e}")
        return
    
    # Create resolver with short TTL for testing
    resolver = TenantResolver(cache_ttl=2)  # 2 seconds for testing
    
    # Get a test tenant
    from src.db.connection import get_connection_manager
    from src.db.models.control_plane import Tenant, TenantStatus
    
    connection_manager = get_connection_manager()
    with connection_manager.get_session() as session:
        tenant = session.query(Tenant).filter_by(status=TenantStatus.ACTIVE).first()
        
        if not tenant:
            print("[WARNING] No active tenants found for expiration test")
            return
        
        tenant_id = str(tenant.tenant_id)
        print(f"[TEST] Testing cache expiration with tenant: {tenant_id}")
        print()
        
        # First request (cache miss)
        print("[STEP 1] First request (cache miss)...")
        start = time.time()
        engine1 = resolver.resolve_tenant_connection(tenant_id)
        elapsed1 = (time.time() - start) * 1000
        print(f"         Elapsed: {elapsed1:.2f}ms")
        print()
        
        # Second request (cache hit)
        print("[STEP 2] Second request (cache hit)...")
        start = time.time()
        engine2 = resolver.resolve_tenant_connection(tenant_id)
        elapsed2 = (time.time() - start) * 1000
        print(f"         Elapsed: {elapsed2:.2f}ms")
        print(f"         Same engine: {engine1 is engine2}")
        print()
        
        # Wait for cache expiration
        print("[STEP 3] Waiting for cache expiration (3 seconds)...")
        time.sleep(3)
        print()
        
        # Third request (cache miss after expiration)
        print("[STEP 4] Third request (cache miss after expiration)...")
        start = time.time()
        engine3 = resolver.resolve_tenant_connection(tenant_id)
        elapsed3 = (time.time() - start) * 1000
        print(f"         Elapsed: {elapsed3:.2f}ms")
        print(f"         New engine: {engine1 is not engine3}")
        print()
        
        # Verify expiration worked
        if elapsed2 < elapsed1 and elapsed3 > elapsed2:
            print("[SUCCESS] Cache expiration working correctly")
        else:
            print("[WARNING] Cache expiration may not be working as expected")
        
        print()


def main() -> None:
    """Main load test function."""
    print("=" * 70)
    print("Tenant Cache Load Test")
    print("=" * 70)
    print()
    
    # Check environment
    if not os.getenv("DATABASE_URL"):
        print("[ERROR] DATABASE_URL environment variable not set")
        sys.exit(1)
    
    if not os.getenv("ENCRYPTION_KEY"):
        print("[ERROR] ENCRYPTION_KEY environment variable not set")
        sys.exit(1)
    
    # Get test tenants
    try:
        from src.db.connection import get_connection_manager
        from src.db.models.control_plane import Tenant, TenantStatus
    except ImportError as e:
        print(f"[ERROR] Failed to import modules: {e}")
        sys.exit(1)
    
    connection_manager = get_connection_manager()
    
    print("[INFO] Fetching active tenants...")
    with connection_manager.get_session() as session:
        tenants = session.query(Tenant).filter_by(status=TenantStatus.ACTIVE).limit(5).all()
        
        if not tenants:
            print("[ERROR] No active tenants found")
            print("        Create tenants using the provisioning API first")
            sys.exit(1)
        
        tenant_ids = [str(tenant.tenant_id) for tenant in tenants]
        print(f"[SUCCESS] Found {len(tenant_ids)} tenant(s) for testing")
        print()
    
    # Run load tests with different configurations
    test_configs = [
        {"num_requests": 100, "num_threads": 5, "name": "Light Load"},
        {"num_requests": 500, "num_threads": 10, "name": "Medium Load"},
        {"num_requests": 1000, "num_threads": 20, "name": "Heavy Load"},
    ]
    
    for config in test_configs:
        print(f"[TEST] {config['name']} Test")
        print("-" * 70)
        summary, total_time = load_test_tenant_resolver(
            tenant_ids=tenant_ids,
            num_requests=config["num_requests"],
            num_threads=config["num_threads"],
            cache_warmup=True
        )
        print_load_test_results(summary, total_time)
        print()
    
    # Test cache expiration
    test_cache_expiration()


if __name__ == "__main__":
    main()
