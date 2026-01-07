"""Verify control plane migration using Python (when connection works)."""
import os
import sys
from typing import List, Tuple

try:
    from src.db.connection import get_connection_manager
    from src.db.models.control_plane import Tenant, TenantDatabase, SystemConfig
    from sqlalchemy import text
except ImportError as e:
    print(f"[ERROR] Import failed: {e}")
    print("[INFO] Make sure you're running from the project root")
    sys.exit(1)


def verify_schema(manager) -> Tuple[bool, List[str]]:
    """Verify control_plane schema exists."""
    issues = []
    try:
        with manager.engine.connect() as conn:
            result = conn.execute(text("""
                SELECT schema_name 
                FROM information_schema.schemata 
                WHERE schema_name = 'control_plane'
            """))
            if result.fetchone():
                print("[✓] control_plane schema exists")
                return True, issues
            else:
                issues.append("control_plane schema missing")
                print("[✗] control_plane schema missing")
                return False, issues
    except Exception as e:
        issues.append(f"Schema check failed: {e}")
        print(f"[✗] Schema check failed: {e}")
        return False, issues


def verify_tables(manager) -> Tuple[bool, List[str]]:
    """Verify all required tables exist."""
    issues = []
    required_tables = ['tenants', 'tenant_databases', 'system_config']
    found_tables = []
    
    try:
        with manager.engine.connect() as conn:
            result = conn.execute(text("""
                SELECT tablename 
                FROM pg_tables 
                WHERE schemaname = 'control_plane'
            """))
            found_tables = [row[0] for row in result]
            
        for table in required_tables:
            if table in found_tables:
                print(f"[✓] Table '{table}' exists")
            else:
                issues.append(f"Table '{table}' missing")
                print(f"[✗] Table '{table}' missing")
        
        return len(issues) == 0, issues
    except Exception as e:
        issues.append(f"Table check failed: {e}")
        print(f"[✗] Table check failed: {e}")
        return False, issues


def verify_seed_data(manager) -> Tuple[bool, List[str]]:
    """Verify seed data (system_admin tenant) exists."""
    issues = []
    try:
        with manager.get_session() as session:
            tenant = session.query(Tenant).filter_by(name="system_admin").first()
            if tenant:
                print(f"[✓] Seed data exists: system_admin tenant (ID: {tenant.tenant_id})")
                print(f"    Environment: {tenant.environment}, Status: {tenant.status}")
                return True, issues
            else:
                issues.append("system_admin tenant missing")
                print("[✗] system_admin tenant missing")
                return False, issues
    except Exception as e:
        issues.append(f"Seed data check failed: {e}")
        print(f"[✗] Seed data check failed: {e}")
        return False, issues


def verify_alembic_versions(manager) -> Tuple[bool, List[str]]:
    """Verify Alembic version table and migrations."""
    issues = []
    try:
        with manager.engine.connect() as conn:
            # Check if alembic_version table exists
            result = conn.execute(text("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_schema = 'control_plane' 
                    AND table_name = 'alembic_version'
                )
            """))
            if not result.fetchone()[0]:
                issues.append("alembic_version table missing")
                print("[✗] alembic_version table missing")
                return False, issues
            
            # Check versions
            result = conn.execute(text("""
                SELECT version_num 
                FROM control_plane.alembic_version 
                ORDER BY version_num
            """))
            versions = [row[0] for row in result]
            
            expected_versions = ['001_control_plane', '002_seed_data']
            for version in expected_versions:
                if version in versions:
                    print(f"[✓] Migration '{version}' marked as applied")
                else:
                    issues.append(f"Migration '{version}' not marked as applied")
                    print(f"[✗] Migration '{version}' not marked as applied")
            
            return len(issues) == 0, issues
    except Exception as e:
        issues.append(f"Alembic version check failed: {e}")
        print(f"[✗] Alembic version check failed: {e}")
        return False, issues


def main():
    """Run all verification checks."""
    print("=" * 60)
    print("Control Plane Migration Verification")
    print("=" * 60)
    print()
    
    # Check DATABASE_URL
    if not os.getenv("DATABASE_URL"):
        print("[ERROR] DATABASE_URL environment variable not set")
        print("\nSet it with:")
        print('  $env:DATABASE_URL="postgresql://postgres:[PASSWORD]@db.qifioafprrtkoiyylsqa.supabase.co:5432/postgres?sslmode=require"')
        sys.exit(1)
    
    try:
        manager = get_connection_manager()
        print("[INFO] Database connection established")
        print()
    except Exception as e:
        print(f"[ERROR] Failed to connect to database: {e}")
        print("\n[NOTE] If connection fails, verify migration manually in Supabase SQL Editor")
        print("       See: MIGRATION_GUIDE.md")
        sys.exit(1)
    
    all_passed = True
    all_issues = []
    
    # Run checks
    print("Running verification checks...")
    print()
    
    passed, issues = verify_schema(manager)
    all_passed = all_passed and passed
    all_issues.extend(issues)
    print()
    
    passed, issues = verify_tables(manager)
    all_passed = all_passed and passed
    all_issues.extend(issues)
    print()
    
    passed, issues = verify_seed_data(manager)
    all_passed = all_passed and passed
    all_issues.extend(issues)
    print()
    
    passed, issues = verify_alembic_versions(manager)
    all_passed = all_passed and passed
    all_issues.extend(issues)
    print()
    
    # Summary
    print("=" * 60)
    if all_passed:
        print("[SUCCESS] All verification checks passed!")
        print("Control plane database is ready to use.")
    else:
        print("[WARNING] Some checks failed:")
        for issue in all_issues:
            print(f"  - {issue}")
        print("\n[INFO] If you ran the migration manually, make sure:")
        print("  1. All SQL from run_migrations_manually.sql was executed")
        print("  2. mark_migrations_applied.sql was executed")
        print("  3. See MIGRATION_GUIDE.md for details")
    print("=" * 60)
    
    sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    main()
