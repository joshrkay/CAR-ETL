"""Verify tenant database routing correctness."""
import os
import sys
import uuid
from typing import Optional, Dict

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from sqlalchemy import text, create_engine
    from sqlalchemy.engine import Engine
except ImportError:
    print("[ERROR] Required packages not installed. Install with:")
    print("  pip install sqlalchemy psycopg2-binary")
    sys.exit(1)


def test_tenant_resolver() -> None:
    """Test tenant resolver with multiple tenants."""
    print("=" * 70)
    print("Tenant Database Routing Verification")
    print("=" * 70)
    print()
    
    try:
        from src.services.tenant_resolver import TenantResolver, get_tenant_resolver
        from src.db.connection import get_connection_manager
        from src.db.models.control_plane import Tenant, TenantDatabase, TenantStatus, DatabaseStatus
        from src.services.encryption import EncryptionService
    except ImportError as e:
        print(f"[ERROR] Failed to import modules: {e}")
        print("Make sure you're running from the project root directory")
        sys.exit(1)
    
    # Check environment variables
    if not os.getenv("DATABASE_URL"):
        print("[ERROR] DATABASE_URL environment variable not set")
        sys.exit(1)
    
    if not os.getenv("ENCRYPTION_KEY"):
        print("[ERROR] ENCRYPTION_KEY environment variable not set")
        print("Generate with: python scripts/generate_encryption_key.py")
        sys.exit(1)
    
    print("[TEST 1] Initializing tenant resolver...")
    resolver = get_tenant_resolver()
    connection_manager = get_connection_manager()
    encryption_service = EncryptionService()
    
    print("[SUCCESS] Tenant resolver initialized")
    print()
    
    # Get test tenants from database
    print("[TEST 2] Fetching tenants from control plane...")
    try:
        with connection_manager.get_session() as session:
            tenants = session.query(Tenant).filter_by(status=TenantStatus.ACTIVE).limit(5).all()
            
            if not tenants:
                print("[WARNING] No active tenants found in database")
                print("         Create test tenants first using the tenant provisioning API")
                return
            
            print(f"[SUCCESS] Found {len(tenants)} active tenant(s)")
            print()
            
            # Test each tenant
            tenant_engines: Dict[str, Engine] = {}
            
            for i, tenant in enumerate(tenants, 1):
                tenant_id_str = str(tenant.tenant_id)
                print(f"[TEST {i + 2}] Testing tenant: {tenant_id_str}")
                print(f"         Name: {tenant.name}")
                print(f"         Environment: {tenant.environment.value}")
                
                # Resolve connection
                engine = resolver.resolve_tenant_connection(tenant_id_str)
                
                if not engine:
                    print(f"[ERROR] Failed to resolve connection for tenant {tenant_id_str}")
                    continue
                
                tenant_engines[tenant_id_str] = engine
                
                # Test connection
                try:
                    with engine.connect() as conn:
                        result = conn.execute(text("SELECT current_database()"))
                        database_name = result.scalar()
                        
                        result = conn.execute(text("SELECT version()"))
                        version = result.scalar()
                        
                        print(f"[SUCCESS] Connection established")
                        print(f"         Database: {database_name}")
                        print(f"         PostgreSQL version: {version[:50]}...")
                        
                        # Verify database name matches expected pattern
                        expected_pattern = f"car_{str(tenant.tenant_id).replace('-', '_')}"
                        if expected_pattern in database_name:
                            print(f"[SUCCESS] Database name matches expected pattern")
                        else:
                            print(f"[WARNING] Database name doesn't match expected pattern")
                            print(f"         Expected: {expected_pattern}")
                            print(f"         Actual: {database_name}")
                        
                except Exception as e:
                    print(f"[ERROR] Failed to query tenant database: {e}")
                
                print()
            
            # Test isolation: verify different tenants get different databases
            print("[TEST] Verifying tenant isolation...")
            if len(tenant_engines) >= 2:
                tenant_ids = list(tenant_engines.keys())
                engine1 = tenant_engines[tenant_ids[0]]
                engine2 = tenant_engines[tenant_ids[1]]
                
                try:
                    with engine1.connect() as conn1, engine2.connect() as conn2:
                        result1 = conn1.execute(text("SELECT current_database()"))
                        db1 = result1.scalar()
                        
                        result2 = conn2.execute(text("SELECT current_database()"))
                        db2 = result2.scalar()
                        
                        if db1 != db2:
                            print(f"[SUCCESS] Tenant isolation verified")
                            print(f"         Tenant 1 database: {db1}")
                            print(f"         Tenant 2 database: {db2}")
                        else:
                            print(f"[ERROR] Tenant isolation FAILED")
                            print(f"         Both tenants using same database: {db1}")
                except Exception as e:
                    print(f"[ERROR] Failed to verify isolation: {e}")
            else:
                print("[SKIP] Need at least 2 tenants to test isolation")
            
            print()
            
            # Test caching: same tenant should get same engine instance
            print("[TEST] Verifying cache behavior...")
            if tenant_engines:
                test_tenant_id = list(tenant_engines.keys())[0]
                engine1 = tenant_engines[test_tenant_id]
                
                # Resolve again (should be cache hit)
                engine2 = resolver.resolve_tenant_connection(test_tenant_id)
                
                if engine1 is engine2:
                    print(f"[SUCCESS] Cache working correctly (same engine instance)")
                else:
                    print(f"[WARNING] Cache may not be working (different engine instances)")
                    print("         This is acceptable if connection pooling is used")
                
                # Get cache stats
                stats = resolver.get_cache_stats()
                print(f"         Cache stats: {stats}")
            
            print()
            
            # Test invalid tenant
            print("[TEST] Testing invalid tenant handling...")
            invalid_tenant_id = "00000000-0000-0000-0000-000000000000"
            invalid_engine = resolver.resolve_tenant_connection(invalid_tenant_id)
            
            if invalid_engine is None:
                print(f"[SUCCESS] Invalid tenant correctly rejected")
            else:
                print(f"[ERROR] Invalid tenant should return None")
            
            print()
            
            # Test invalid UUID format
            print("[TEST] Testing invalid UUID format...")
            invalid_format_id = "not-a-uuid"
            invalid_format_engine = resolver.resolve_tenant_connection(invalid_format_id)
            
            if invalid_format_engine is None:
                print(f"[SUCCESS] Invalid UUID format correctly rejected")
            else:
                print(f"[ERROR] Invalid UUID format should return None")
            
            print()
            
    except Exception as e:
        print(f"[ERROR] Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    
    print("=" * 70)
    print("[RESULT] Verification complete")
    print("=" * 70)


def test_middleware_integration() -> None:
    """Test middleware integration with FastAPI."""
    print()
    print("=" * 70)
    print("Middleware Integration Test")
    print("=" * 70)
    print()
    
    try:
        from fastapi import FastAPI, Request
        from fastapi.testclient import TestClient
        from src.middleware.tenant_context import TenantContextMiddleware
        from src.dependencies import get_tenant_db, get_tenant_id
        from sqlalchemy import text
    except ImportError as e:
        print(f"[ERROR] Failed to import modules: {e}")
        return
    
    # Create test app
    app = FastAPI()
    
    @app.get("/api/v1/test-db")
    async def test_db_endpoint(
        request: Request,
        db = None,  # Will be injected
        tenant_id: str = None  # Will be injected
    ):
        """Test endpoint that uses tenant database."""
        from src.dependencies import get_tenant_db, get_tenant_id
        
        try:
            db = get_tenant_db(request)
            tenant_id = get_tenant_id(request)
            
            with db.connect() as conn:
                result = conn.execute(text("SELECT current_database()"))
                database_name = result.scalar()
            
            return {
                "tenant_id": tenant_id,
                "database": database_name,
                "status": "success"
            }
        except Exception as e:
            return {
                "error": str(e),
                "status": "failed"
            }
    
    app.add_middleware(TenantContextMiddleware)
    client = TestClient(app)
    
    print("[TEST] Testing middleware with mock JWT...")
    print("[INFO] Note: This requires a valid JWT token with tenant_id claim")
    print("       For full testing, use a real JWT token from Auth0")
    print()
    
    # Test without token
    print("[TEST] Request without Authorization header...")
    response = client.get("/api/v1/test-db")
    print(f"         Status: {response.status_code}")
    if response.status_code == 401:
        print(f"[SUCCESS] Correctly rejected request without token")
    else:
        print(f"[WARNING] Expected 401, got {response.status_code}")
    
    print()
    print("[INFO] To test with real JWT token:")
    print("       1. Generate JWT token with tenant_id claim")
    print("       2. Run: curl -H 'Authorization: Bearer <token>' http://localhost:8000/api/v1/test-db")


if __name__ == "__main__":
    test_tenant_resolver()
    test_middleware_integration()
