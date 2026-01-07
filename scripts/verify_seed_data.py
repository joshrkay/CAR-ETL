"""Verify seed data (system_admin tenant) was inserted correctly."""
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

try:
    from src.db.connection import get_connection_manager
    from src.db.models.control_plane import Tenant, TenantDatabase, SystemConfig
    from sqlalchemy import text
except ImportError as e:
    print(f"[ERROR] Import failed: {e}")
    print("[INFO] Make sure you're running from the project root")
    sys.exit(1)


def verify_seed_data():
    """Verify system_admin tenant seed data exists."""
    print("=" * 60)
    print("Verifying Seed Data (system_admin tenant)")
    print("=" * 60)
    print()
    
    # Check DATABASE_URL
    if not os.getenv("DATABASE_URL"):
        print("[ERROR] DATABASE_URL environment variable not set")
        print("\n[INFO] If connection fails, use SQL queries in Supabase SQL Editor:")
        print("       See: scripts/verify_seed_data.sql")
        print("\nSet DATABASE_URL with:")
        print('  $env:DATABASE_URL="postgresql://postgres:[PASSWORD]@db.qifioafprrtkoiyylsqa.supabase.co:5432/postgres?sslmode=require"')
        sys.exit(1)
    
    try:
        manager = get_connection_manager()
        print("[INFO] Database connection established")
        print()
    except Exception as e:
        print(f"[ERROR] Failed to connect to database: {e}")
        print("\n[INFO] Connection failed. Use SQL queries in Supabase SQL Editor instead:")
        print("       See: scripts/verify_seed_data.sql")
        print("\nOr run these queries directly in Supabase SQL Editor:")
        print()
        print("-- Check if system_admin tenant exists")
        print("SELECT * FROM control_plane.tenants WHERE name = 'system_admin';")
        print()
        print("-- Check all tenants")
        print("SELECT tenant_id, name, environment, status, created_at FROM control_plane.tenants;")
        sys.exit(1)
    
    # Verify schema exists
    print("[TEST] Checking control_plane schema...")
    try:
        with manager.engine.connect() as conn:
            result = conn.execute(text("""
                SELECT schema_name 
                FROM information_schema.schemata 
                WHERE schema_name = 'control_plane'
            """))
            if result.fetchone():
                print("[SUCCESS] control_plane schema exists")
            else:
                print("[ERROR] control_plane schema not found")
                print("[INFO] Run the migration first: scripts/run_migrations_manually.sql")
                return False
    except Exception as e:
        print(f"[ERROR] Schema check failed: {e}")
        return False
    print()
    
    # Verify tenants table exists
    print("[TEST] Checking tenants table...")
    try:
        with manager.engine.connect() as conn:
            result = conn.execute(text("""
                SELECT tablename 
                FROM pg_tables 
                WHERE schemaname = 'control_plane' AND tablename = 'tenants'
            """))
            if result.fetchone():
                print("[SUCCESS] tenants table exists")
            else:
                print("[ERROR] tenants table not found")
                return False
    except Exception as e:
        print(f"[ERROR] Table check failed: {e}")
        return False
    print()
    
    # Verify system_admin tenant exists
    print("[TEST] Checking system_admin tenant...")
    try:
        with manager.get_session() as session:
            tenant = session.query(Tenant).filter_by(name="system_admin").first()
            
            if tenant:
                print("[SUCCESS] system_admin tenant found!")
                print()
                print("Tenant Details:")
                print(f"  Tenant ID: {tenant.tenant_id}")
                print(f"  Name: {tenant.name}")
                print(f"  Environment: {tenant.environment.value}")
                print(f"  Status: {tenant.status.value}")
                print(f"  Created At: {tenant.created_at}")
                print(f"  Updated At: {tenant.updated_at}")
                print()
                
                # Verify expected values
                checks_passed = True
                if tenant.environment.value != "production":
                    print(f"[WARNING] Expected environment='production', got '{tenant.environment.value}'")
                    checks_passed = False
                
                if tenant.status.value != "active":
                    print(f"[WARNING] Expected status='active', got '{tenant.status.value}'")
                    checks_passed = False
                
                if checks_passed:
                    print("[SUCCESS] All seed data checks passed!")
                    return True
                else:
                    print("[WARNING] Seed data exists but has unexpected values")
                    return False
            else:
                print("[ERROR] system_admin tenant not found")
                print("[INFO] Run the seed migration: scripts/mark_migrations_applied.sql")
                print("       Or check if migration 002_seed_data was applied")
                return False
                
    except Exception as e:
        print(f"[ERROR] Failed to query tenant: {e}")
        return False
    
    print()
    print("=" * 60)
    if tenant:
        print("[SUCCESS] Seed data verification complete!")
    else:
        print("[ERROR] Seed data verification failed")
    print("=" * 60)


if __name__ == "__main__":
    success = verify_seed_data()
    sys.exit(0 if success else 1)
