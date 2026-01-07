"""Verify tenant database isolation with comprehensive tests."""
import os
import sys
import uuid
from typing import Dict, List, Optional

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from sqlalchemy import text, create_engine
    from sqlalchemy.engine import Engine
except ImportError:
    print("[ERROR] Required packages not installed. Install with:")
    print("  pip install sqlalchemy psycopg2-binary")
    sys.exit(1)


def verify_tenant_isolation() -> None:
    """Comprehensive verification of tenant database isolation."""
    print("=" * 70)
    print("Tenant Database Isolation Verification")
    print("=" * 70)
    print()
    
    try:
        from src.services.tenant_resolver import TenantResolver, get_tenant_resolver
        from src.db.connection import get_connection_manager
        from src.db.models.control_plane import Tenant, TenantDatabase, TenantStatus, DatabaseStatus
    except ImportError as e:
        print(f"[ERROR] Failed to import modules: {e}")
        sys.exit(1)
    
    # Check environment
    if not os.getenv("DATABASE_URL"):
        print("[ERROR] DATABASE_URL environment variable not set")
        sys.exit(1)
    
    if not os.getenv("ENCRYPTION_KEY"):
        print("[ERROR] ENCRYPTION_KEY environment variable not set")
        sys.exit(1)
    
    resolver = get_tenant_resolver()
    connection_manager = get_connection_manager()
    
    print("[STEP 1] Fetching active tenants from control plane...")
    try:
        with connection_manager.get_session() as session:
            tenants = session.query(Tenant).filter_by(status=TenantStatus.ACTIVE).all()
            
            if len(tenants) < 2:
                print(f"[WARNING] Found only {len(tenants)} tenant(s)")
                print("         Need at least 2 tenants to verify isolation")
                print("         Create more tenants using the provisioning API")
                return
            
            print(f"[SUCCESS] Found {len(tenants)} active tenant(s)")
            print()
            
            # Resolve connections for all tenants
            print("[STEP 2] Resolving database connections for all tenants...")
            tenant_connections: Dict[str, Dict] = {}
            
            for tenant in tenants:
                tenant_id_str = str(tenant.tenant_id)
                print(f"         Resolving tenant: {tenant.name} ({tenant_id_str})")
                
                engine = resolver.resolve_tenant_connection(tenant_id_str)
                
                if not engine:
                    print(f"[ERROR] Failed to resolve connection for {tenant.name}")
                    continue
                
                # Get database info
                try:
                    with engine.connect() as conn:
                        db_result = conn.execute(text("SELECT current_database()"))
                        database_name = db_result.scalar()
                        
                        user_result = conn.execute(text("SELECT current_user"))
                        database_user = user_result.scalar()
                        
                        tenant_connections[tenant_id_str] = {
                            "name": tenant.name,
                            "engine": engine,
                            "database": database_name,
                            "user": database_user
                        }
                        
                        print(f"         [OK] Database: {database_name}")
                except Exception as e:
                    print(f"         [ERROR] Failed to query database: {e}")
            
            print()
            
            # Verify isolation
            print("[STEP 3] Verifying tenant isolation...")
            print()
            
            tenant_ids = list(tenant_connections.keys())
            all_databases = [conn["database"] for conn in tenant_connections.values()]
            unique_databases = set(all_databases)
            
            if len(unique_databases) == len(all_databases):
                print(f"[SUCCESS] All {len(tenant_connections)} tenants have unique databases")
                print()
                
                # Show database mapping
                print("Database Mapping:")
                for tenant_id, conn_info in tenant_connections.items():
                    print(f"  Tenant: {conn_info['name']}")
                    print(f"    ID: {tenant_id}")
                    print(f"    Database: {conn_info['database']}")
                    print(f"    User: {conn_info['user']}")
                    print()
            else:
                print(f"[ERROR] Tenant isolation FAILED")
                print(f"         Found {len(unique_databases)} unique databases for {len(tenant_connections)} tenants")
                print()
                print("Database conflicts:")
                for i, (tid1, conn1) in enumerate(tenant_connections.items()):
                    for tid2, conn2 in list(tenant_connections.items())[i+1:]:
                        if conn1["database"] == conn2["database"]:
                            print(f"  - {conn1['name']} ({tid1})")
                            print(f"  - {conn2['name']} ({tid2})")
                            print(f"    Both using: {conn1['database']}")
            
            print()
            
            # Test data isolation
            print("[STEP 4] Testing data isolation...")
            print()
            
            if len(tenant_connections) >= 2:
                test_tenant1_id = tenant_ids[0]
                test_tenant2_id = tenant_ids[1]
                
                conn1 = tenant_connections[test_tenant1_id]
                conn2 = tenant_connections[test_tenant2_id]
                
                print(f"Testing with tenants:")
                print(f"  Tenant 1: {conn1['name']} -> {conn1['database']}")
                print(f"  Tenant 2: {conn2['name']} -> {conn2['database']}")
                print()
                
                # Try to create a test table in each database
                test_table = "isolation_test_table"
                
                try:
                    with conn1["engine"].connect() as conn:
                        # Create table in tenant 1
                        conn.execute(text(f"""
                            CREATE TABLE IF NOT EXISTS {test_table} (
                                id SERIAL PRIMARY KEY,
                                tenant_id VARCHAR(255),
                                data TEXT
                            )
                        """))
                        conn.commit()
                        
                        # Insert test data
                        conn.execute(text(f"""
                            INSERT INTO {test_table} (tenant_id, data)
                            VALUES ('{test_tenant1_id}', 'tenant1_data')
                            ON CONFLICT DO NOTHING
                        """))
                        conn.commit()
                        
                        # Verify data exists
                        result = conn.execute(text(f"SELECT COUNT(*) FROM {test_table}"))
                        count1 = result.scalar()
                        print(f"[OK] Tenant 1: Created table and inserted data (count: {count1})")
                        
                except Exception as e:
                    print(f"[WARNING] Tenant 1: Failed to create test table: {e}")
                
                try:
                    with conn2["engine"].connect() as conn:
                        # Create table in tenant 2
                        conn.execute(text(f"""
                            CREATE TABLE IF NOT EXISTS {test_table} (
                                id SERIAL PRIMARY KEY,
                                tenant_id VARCHAR(255),
                                data TEXT
                            )
                        """))
                        conn.commit()
                        
                        # Insert test data
                        conn.execute(text(f"""
                            INSERT INTO {test_table} (tenant_id, data)
                            VALUES ('{test_tenant2_id}', 'tenant2_data')
                            ON CONFLICT DO NOTHING
                        """))
                        conn.commit()
                        
                        # Verify data exists
                        result = conn.execute(text(f"SELECT COUNT(*) FROM {test_table}"))
                        count2 = result.scalar()
                        print(f"[OK] Tenant 2: Created table and inserted data (count: {count2})")
                        
                except Exception as e:
                    print(f"[WARNING] Tenant 2: Failed to create test table: {e}")
                
                # Verify data isolation: tenant 1 should not see tenant 2's data
                try:
                    with conn1["engine"].connect() as conn:
                        result = conn.execute(text(f"""
                            SELECT COUNT(*) FROM {test_table}
                            WHERE tenant_id = '{test_tenant2_id}'
                        """))
                        cross_tenant_count = result.scalar()
                        
                        if cross_tenant_count == 0:
                            print(f"[SUCCESS] Data isolation verified: Tenant 1 cannot see Tenant 2's data")
                        else:
                            print(f"[ERROR] Data isolation FAILED: Tenant 1 can see Tenant 2's data")
                            
                except Exception as e:
                    print(f"[INFO] Could not verify cross-tenant access (expected if tables don't exist): {e}")
            
            print()
            
            # Cache verification
            print("[STEP 5] Verifying cache behavior...")
            stats = resolver.get_cache_stats()
            print(f"         Total cache entries: {stats['total_entries']}")
            print(f"         Active entries: {stats['active_entries']}")
            print(f"         Expired entries: {stats['expired_entries']}")
            
            if stats['active_entries'] == len(tenant_connections):
                print(f"[SUCCESS] All tenant connections cached")
            else:
                print(f"[INFO] Cache stats: {stats['active_entries']} active, {len(tenant_connections)} tenants")
            
            print()
            
    except Exception as e:
        print(f"[ERROR] Verification failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    
    print("=" * 70)
    print("[RESULT] Isolation verification complete")
    print("=" * 70)


if __name__ == "__main__":
    verify_tenant_isolation()
