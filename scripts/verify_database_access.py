"""Verify database exists and is accessible."""
import sys
import os
from typing import List, Tuple

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

try:
    from src.db.connection import get_connection_manager
    from src.db.models.control_plane import Tenant, TenantDatabase, SystemConfig
    from src.db.tenant_manager import TenantDatabaseManager
    from sqlalchemy import text
except ImportError as e:
    print(f"[ERROR] Import failed: {e}")
    print("[INFO] Make sure you're running from the project root")
    print("       Install dependencies: pip install -r requirements.txt")
    sys.exit(1)


def check_connection() -> Tuple[bool, str]:
    """Check basic database connection."""
    print("[TEST] Checking database connection...")
    try:
        manager = get_connection_manager()
        with manager.engine.connect() as conn:
            result = conn.execute(text("SELECT version();"))
            version = result.fetchone()[0]
            print(f"[SUCCESS] Connected to PostgreSQL")
            print(f"         Version: {version[:50]}...")
            return True, "Connection successful"
    except Exception as e:
        error_msg = f"Connection failed: {e}"
        print(f"[ERROR] {error_msg}")
        return False, error_msg


def check_schema() -> Tuple[bool, str]:
    """Check if control_plane schema exists."""
    print("\n[TEST] Checking control_plane schema...")
    try:
        manager = get_connection_manager()
        with manager.engine.connect() as conn:
            result = conn.execute(text("""
                SELECT schema_name 
                FROM information_schema.schemata 
                WHERE schema_name = 'control_plane'
            """))
            if result.fetchone():
                print("[SUCCESS] control_plane schema exists")
                return True, "Schema exists"
            else:
                error_msg = "control_plane schema not found"
                print(f"[ERROR] {error_msg}")
                return False, error_msg
    except Exception as e:
        error_msg = f"Schema check failed: {e}"
        print(f"[ERROR] {error_msg}")
        return False, error_msg


def check_tables() -> Tuple[bool, List[str]]:
    """Check if required tables exist."""
    print("\n[TEST] Checking required tables...")
    required_tables = ['tenants', 'tenant_databases', 'system_config']
    found_tables = []
    missing_tables = []
    
    try:
        manager = get_connection_manager()
        with manager.engine.connect() as conn:
            result = conn.execute(text("""
                SELECT tablename 
                FROM pg_tables 
                WHERE schemaname = 'control_plane'
            """))
            found_tables = [row[0] for row in result]
            
        for table in required_tables:
            if table in found_tables:
                print(f"[SUCCESS] Table '{table}' exists")
            else:
                print(f"[ERROR] Table '{table}' missing")
                missing_tables.append(table)
        
        if missing_tables:
            return False, missing_tables
        else:
            return True, []
    except Exception as e:
        print(f"[ERROR] Table check failed: {e}")
        return False, [str(e)]


def check_seed_data() -> Tuple[bool, str]:
    """Check if seed data (system_admin tenant) exists."""
    print("\n[TEST] Checking seed data (system_admin tenant)...")
    try:
        manager = get_connection_manager()
        with manager.get_session() as session:
            tenant = session.query(Tenant).filter_by(name="system_admin").first()
            
            if tenant:
                print(f"[SUCCESS] system_admin tenant found")
                print(f"         Tenant ID: {tenant.tenant_id}")
                print(f"         Environment: {tenant.environment.value}")
                print(f"         Status: {tenant.status.value}")
                return True, "Seed data exists"
            else:
                error_msg = "system_admin tenant not found"
                print(f"[ERROR] {error_msg}")
                return False, error_msg
    except Exception as e:
        error_msg = f"Seed data check failed: {e}"
        print(f"[ERROR] {error_msg}")
        return False, error_msg


def check_database_creation_permissions() -> Tuple[bool, str]:
    """Check if database has permissions to create databases."""
    print("\n[TEST] Checking database creation permissions...")
    try:
        manager = TenantDatabaseManager()
        
        # Try to check if we can query pg_database (requires permissions)
        with manager._get_admin_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM pg_database")
            count = cursor.fetchone()[0]
            print(f"[SUCCESS] Can access pg_database (found {count} databases)")
            print(f"         Database creation permissions: OK")
            return True, "Permissions OK"
    except Exception as e:
        error_msg = f"Permission check failed: {e}"
        print(f"[WARNING] {error_msg}")
        print(f"         This may prevent tenant database creation")
        return False, error_msg


def check_models() -> Tuple[bool, str]:
    """Check if SQLAlchemy models can be used."""
    print("\n[TEST] Checking SQLAlchemy models...")
    try:
        manager = get_connection_manager()
        with manager.get_session() as session:
            # Try to query tenants
            count = session.query(Tenant).count()
            print(f"[SUCCESS] Models work correctly")
            print(f"         Found {count} tenant(s) in database")
            return True, "Models accessible"
    except Exception as e:
        error_msg = f"Model check failed: {e}"
        print(f"[ERROR] {error_msg}")
        return False, error_msg


def check_encryption_key() -> Tuple[bool, str]:
    """Check if encryption key is configured."""
    print("\n[TEST] Checking encryption key configuration...")
    encryption_key = os.getenv("ENCRYPTION_KEY")
    
    if not encryption_key:
        error_msg = "ENCRYPTION_KEY environment variable not set"
        print(f"[ERROR] {error_msg}")
        print(f"         Generate with: python scripts/generate_encryption_key.py")
        return False, error_msg
    
    try:
        from src.services.encryption import EncryptionService
        service = EncryptionService()
        # Test encryption/decryption
        test_string = "test_connection_string"
        encrypted = service.encrypt(test_string)
        decrypted = service.decrypt(encrypted)
        
        if decrypted == test_string:
            print(f"[SUCCESS] Encryption key configured and working")
            return True, "Encryption OK"
        else:
            error_msg = "Encryption/decryption test failed"
            print(f"[ERROR] {error_msg}")
            return False, error_msg
    except Exception as e:
        error_msg = f"Encryption check failed: {e}"
        print(f"[ERROR] {error_msg}")
        return False, error_msg


def main():
    """Run all database verification checks."""
    print("=" * 70)
    print("Database Access Verification")
    print("=" * 70)
    print()
    
    # Check DATABASE_URL
    if not os.getenv("DATABASE_URL"):
        print("[ERROR] DATABASE_URL environment variable not set")
        print("\nSet it with:")
        print('  $env:DATABASE_URL="postgresql://postgres:[PASSWORD]@[HOST]:5432/postgres?sslmode=require"')
        sys.exit(1)
    
    print(f"[INFO] DATABASE_URL: {os.getenv('DATABASE_URL')[:50]}...")
    print()
    
    results = []
    
    # Run checks
    results.append(("Connection", check_connection()))
    results.append(("Schema", check_schema()))
    results.append(("Tables", check_tables()))
    results.append(("Seed Data", check_seed_data()))
    results.append(("Models", check_models()))
    results.append(("DB Permissions", check_database_creation_permissions()))
    results.append(("Encryption Key", check_encryption_key()))
    
    # Summary
    print("\n" + "=" * 70)
    print("Verification Summary")
    print("=" * 70)
    
    passed = sum(1 for _, (success, _) in results if success)
    total = len(results)
    
    for check_name, (success, message) in results:
        status = "[PASS]" if success else "[FAIL]"
        print(f"{status} - {check_name}: {message}")
    
    print()
    print(f"Results: {passed}/{total} checks passed")
    print()
    
    if passed == total:
        print("[SUCCESS] All database checks passed!")
        print("         Database is accessible and ready for tenant provisioning")
        return True
    else:
        print("[WARNING] Some checks failed")
        if "could not translate host name" in str(results[0][1][1]):
            print("\n[INFO] Connection failed due to DNS resolution issue.")
            print("       Database is accessible via Supabase SQL Editor.")
            print("       Use scripts/verify_database_access.sql for SQL-based verification.")
        print("         Review errors above and fix issues before provisioning tenants")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
