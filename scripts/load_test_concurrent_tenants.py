"""Load test for concurrent tenant requests to verify thread safety."""
import os
import sys
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict
from collections import defaultdict

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_concurrent_tenant_requests() -> None:
    """Test concurrent requests for different tenants."""
    print("=" * 70)
    print("Concurrent Tenant Requests Load Test")
    print("=" * 70)
    print()
    
    try:
        from src.services.tenant_resolver import get_tenant_resolver
        from src.db.connection import get_connection_manager
        from src.db.models.control_plane import Tenant, TenantStatus
        from sqlalchemy import text
    except ImportError as e:
        print(f"[ERROR] Failed to import modules: {e}")
        sys.exit(1)
    
    # Check environment
    if not os.getenv("DATABASE_URL") or not os.getenv("ENCRYPTION_KEY"):
        print("[ERROR] Environment variables not set")
        sys.exit(1)
    
    # Get tenants
    connection_manager = get_connection_manager()
    with connection_manager.get_session() as session:
        tenants = session.query(Tenant).filter_by(status=TenantStatus.ACTIVE).limit(10).all()
        
        if len(tenants) < 2:
            print("[WARNING] Need at least 2 tenants for concurrent test")
            return
        
        tenant_ids = [str(tenant.tenant_id) for tenant in tenants]
        print(f"[INFO] Testing with {len(tenant_ids)} tenants")
        print()
    
    resolver = get_tenant_resolver()
    
    # Test concurrent requests
    num_requests_per_tenant = 50
    num_threads = 20
    
    print(f"[TEST] Concurrent requests test")
    print(f"       Requests per tenant: {num_requests_per_tenant}")
    print(f"       Concurrent threads: {num_threads}")
    print(f"       Total requests: {len(tenant_ids) * num_requests_per_tenant}")
    print()
    
    results: Dict[str, List[float]] = defaultdict(list)
    errors: List[str] = []
    
    def make_request(tenant_id: str) -> None:
        """Make a request for a tenant."""
        start = time.time()
        try:
            engine = resolver.resolve_tenant_connection(tenant_id)
            if engine:
                with engine.connect() as conn:
                    conn.execute(text("SELECT current_database()"))
                elapsed = (time.time() - start) * 1000
                results[tenant_id].append(elapsed)
            else:
                errors.append(f"Failed to resolve {tenant_id}")
        except Exception as e:
            errors.append(f"Error for {tenant_id}: {e}")
    
    start_time = time.time()
    
    with ThreadPoolExecutor(max_workers=num_threads) as executor:
        futures = []
        for tenant_id in tenant_ids:
            for _ in range(num_requests_per_tenant):
                future = executor.submit(make_request, tenant_id)
                futures.append(future)
        
        for future in as_completed(futures):
            try:
                future.result()
            except Exception as e:
                errors.append(f"Future error: {e}")
    
    total_time = time.time() - start_time
    
    # Print results
    print("Results by Tenant:")
    print("-" * 70)
    
    for tenant_id, times in results.items():
        if times:
            avg = sum(times) / len(times)
            min_time = min(times)
            max_time = max(times)
            print(f"Tenant: {tenant_id[:36]}...")
            print(f"  Requests: {len(times)}")
            print(f"  Avg time: {avg:.2f}ms")
            print(f"  Min time: {min_time:.2f}ms")
            print(f"  Max time: {max_time:.2f}ms")
            print()
    
    print("Summary:")
    print("-" * 70)
    total_requests = sum(len(times) for times in results.values())
    print(f"Total successful requests: {total_requests}")
    print(f"Total errors: {len(errors)}")
    print(f"Total time: {total_time:.2f}s")
    print(f"Throughput: {total_requests/total_time:.2f} req/s")
    print()
    
    if errors:
        print(f"Errors ({len(errors)}):")
        for error in errors[:10]:  # Show first 10 errors
            print(f"  - {error}")
        if len(errors) > 10:
            print(f"  ... and {len(errors) - 10} more errors")
    
    # Verify thread safety (no data corruption)
    print()
    print("Thread Safety Check:")
    print("-" * 70)
    
    # Check cache stats
    stats = resolver.get_cache_stats()
    print(f"Cache entries: {stats['total_entries']}")
    print(f"Active entries: {stats['active_entries']}")
    
    # Verify each tenant got correct database
    print()
    print("Database Verification:")
    print("-" * 70)
    
    tenant_databases = {}
    for tenant_id in tenant_ids:
        engine = resolver.resolve_tenant_connection(tenant_id)
        if engine:
            with engine.connect() as conn:
                result = conn.execute(text("SELECT current_database()"))
                db_name = result.scalar()
                tenant_databases[tenant_id] = db_name
    
    # Check uniqueness
    unique_dbs = set(tenant_databases.values())
    if len(unique_dbs) == len(tenant_databases):
        print("[SUCCESS] All tenants have unique databases")
    else:
        print("[ERROR] Some tenants share databases!")
        for tenant_id, db_name in tenant_databases.items():
            print(f"  {tenant_id[:36]}... -> {db_name}")
    
    print()
    print("=" * 70)


if __name__ == "__main__":
    test_concurrent_tenant_requests()
