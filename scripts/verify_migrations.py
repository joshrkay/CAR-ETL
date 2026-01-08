"""Script to verify database migrations are applied."""
import os
import sys
from pathlib import Path
from typing import Dict, List, Tuple

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Load environment variables
try:
    from dotenv import load_dotenv
    env_path = project_root / ".env"
    if env_path.exists():
        load_dotenv(env_path)
    else:
        load_dotenv()
except ImportError:
    pass

from supabase import create_client, Client
from src.auth.config import get_auth_config


# Required tables and their key columns for verification
REQUIRED_TABLES = {
    "tenants": ["id", "slug", "name", "status"],
    "tenant_users": ["user_id", "tenant_id", "roles"],
    "documents": [
        "id",
        "tenant_id",
        "file_hash",
        "storage_path",
        "original_filename",
        "mime_type",
        "file_size_bytes",
        "source_type",
    ],
    "email_ingestions": [
        "id",
        "tenant_id",
        "from_address",
        "to_address",
        "subject",
        "body_document_id",
        "attachment_count",
        "received_at",
    ],
    "feature_flags": ["id", "name", "enabled_default"],
    "audit_logs": ["id", "tenant_id", "user_id", "event_type", "action"],
}

# Mapping of table names to their migration files
TABLE_MIGRATIONS = {
    "tenants": "003_tenants.sql",
    "tenant_users": "004_tenant_users.sql",
    "documents": "020_documents.sql",
    "email_ingestions": "024_email_ingestions.sql",
    "feature_flags": "002_feature_flags.sql",
    "audit_logs": "012_audit_logs.sql",
}


def check_table_exists(supabase: Client, table_name: str) -> Tuple[bool, str]:
    """
    Check if a table exists in the database.
    
    Args:
        supabase: Supabase client
        table_name: Name of the table to check
        
    Returns:
        Tuple of (exists: bool, error_message: str)
    """
    try:
        # Try to query the table with a limit 1 to see if it exists
        result = supabase.table(table_name).select("*").limit(1).execute()
        return True, ""
    except Exception as e:
        error_msg = str(e)
        # Check if error is about table not existing
        if "Could not find the table" in error_msg or "PGRST205" in error_msg:
            return False, f"Table '{table_name}' does not exist"
        else:
            return False, f"Error checking table '{table_name}': {error_msg}"


def check_table_columns(supabase: Client, table_name: str, required_columns: List[str]) -> Tuple[bool, List[str]]:
    """
    Check if a table has the required columns.
    
    Args:
        supabase: Supabase client
        table_name: Name of the table
        required_columns: List of required column names
        
    Returns:
        Tuple of (all_columns_exist: bool, missing_columns: List[str])
    """
    try:
        # Try to select all required columns
        # If any column is missing, this will fail
        columns_str = ", ".join(required_columns)
        result = supabase.table(table_name).select(columns_str).limit(1).execute()
        return True, []
    except Exception as e:
        error_msg = str(e)
        # Parse which columns are missing from the error
        missing = []
        for col in required_columns:
            if col in error_msg or f"column \"{col}\"" in error_msg.lower():
                missing.append(col)
        
        # If we can't parse, assume all are missing
        if not missing:
            return False, required_columns
        
        return False, missing


def check_rls_enabled(supabase: Client, table_name: str) -> Tuple[bool, str]:
    """
    Check if Row Level Security (RLS) is enabled on a table.
    
    Args:
        supabase: Supabase client
        table_name: Name of the table
        
    Returns:
        Tuple of (rls_enabled: bool, message: str)
    """
    try:
        # Try to query without proper tenant context
        # If RLS is enabled and we don't have proper context, this should fail
        # But we're using service_role, so it should work
        # Instead, we'll check by trying to query with a filter that would fail RLS
        result = supabase.table(table_name).select("*").limit(1).execute()
        
        # If we get here with service_role, RLS might be enabled but bypassed
        # We can't easily check RLS status via API, so we'll just note it
        return True, "RLS status cannot be verified via API (service_role bypasses RLS)"
    except Exception as e:
        return False, f"Error checking RLS: {str(e)}"


def verify_migrations() -> Dict[str, any]:
    """
    Verify all required migrations are applied.
    
    Returns:
        Dictionary with verification results
    """
    print("=" * 60)
    print("Database Migration Verification")
    print("=" * 60)
    
    # Check environment variables
    required_vars = ["SUPABASE_URL", "SUPABASE_SERVICE_KEY"]
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    
    if missing_vars:
        print(f"\n[ERROR] Missing required environment variables: {', '.join(missing_vars)}")
        return {"success": False, "error": "Missing environment variables"}
    
    try:
        config = get_auth_config()
    except Exception as e:
        print(f"\n[ERROR] Failed to load auth config: {e}")
        return {"success": False, "error": str(e)}
    
    # Initialize Supabase client
    try:
        supabase: Client = create_client(
            config.supabase_url,
            config.supabase_service_key,
        )
        print("\n[OK] Connected to Supabase")
    except Exception as e:
        print(f"\n[ERROR] Failed to connect to Supabase: {e}")
        return {"success": False, "error": str(e)}
    
    results = {
        "success": True,
        "tables": {},
        "missing_tables": [],
        "missing_columns": {},
    }
    
    print("\n" + "=" * 60)
    print("Checking Required Tables")
    print("=" * 60)
    
    # Check each required table
    for table_name, required_columns in REQUIRED_TABLES.items():
        print(f"\nChecking table: {table_name}")
        
        # Check if table exists
        exists, error_msg = check_table_exists(supabase, table_name)
        
        if not exists:
            print(f"  [MISSING] {error_msg}")
            results["missing_tables"].append(table_name)
            results["tables"][table_name] = {
                "exists": False,
                "error": error_msg,
            }
            continue
        
        print(f"  [OK] Table exists")
        
        # Check if required columns exist
        columns_ok, missing_cols = check_table_columns(supabase, table_name, required_columns)
        
        if not columns_ok:
            print(f"  [WARNING] Missing columns: {', '.join(missing_cols)}")
            results["missing_columns"][table_name] = missing_cols
        else:
            print(f"  [OK] All required columns present")
        
        # Check RLS (informational)
        rls_ok, rls_msg = check_rls_enabled(supabase, table_name)
        if rls_ok:
            print(f"  [INFO] {rls_msg}")
        
        results["tables"][table_name] = {
            "exists": True,
            "columns_ok": columns_ok,
            "missing_columns": missing_cols,
        }
    
    # Summary
    print("\n" + "=" * 60)
    print("Verification Summary")
    print("=" * 60)
    
    total_tables = len(REQUIRED_TABLES)
    existing_tables = total_tables - len(results["missing_tables"])
    tables_with_issues = len(results["missing_columns"])
    
    print(f"\nTotal tables checked: {total_tables}")
    print(f"Tables found: {existing_tables}")
    print(f"Tables missing: {len(results['missing_tables'])}")
    print(f"Tables with missing columns: {tables_with_issues}")
    
    if results["missing_tables"]:
        print(f"\n[MISSING TABLES]")
        for table in results["missing_tables"]:
            print(f"  - {table}")
            # Suggest migration file
            migration_file = TABLE_MIGRATIONS.get(table, "unknown_migration.sql")
            print(f"    Migration file: supabase/migrations/{migration_file}")
            print(f"    Run: supabase db push (or apply migration manually)")
    
    if results["missing_columns"]:
        print(f"\n[TABLES WITH MISSING COLUMNS]")
        for table, missing_cols in results["missing_columns"].items():
            print(f"  - {table}: {', '.join(missing_cols)}")
    
    # Check specific migrations
    print("\n" + "=" * 60)
    print("Migration Status")
    print("=" * 60)
    
    # Email ingestion migration (024)
    email_ingestions_ok = "email_ingestions" not in results["missing_tables"]
    print(f"\nEmail Ingestion Migration (024_email_ingestions.sql):")
    if email_ingestions_ok:
        print("  [OK] email_ingestions table exists")
    else:
        print("  [MISSING] Run: supabase/migrations/024_email_ingestions.sql")
    
    # Documents migration (020)
    documents_ok = "documents" not in results["missing_tables"]
    print(f"\nDocuments Migration (020_documents.sql):")
    if documents_ok:
        print("  [OK] documents table exists")
    else:
        print("  [MISSING] Run: supabase/migrations/020_documents.sql")
    
    # Overall success
    if not results["missing_tables"] and not results["missing_columns"]:
        print("\n" + "=" * 60)
        print("[SUCCESS] All migrations are applied correctly!")
        print("=" * 60)
        results["success"] = True
    else:
        print("\n" + "=" * 60)
        print("[WARNING] Some migrations are missing or incomplete")
        print("=" * 60)
        results["success"] = False
    
    return results


if __name__ == "__main__":
    try:
        results = verify_migrations()
        sys.exit(0 if results["success"] else 1)
    except KeyboardInterrupt:
        print("\n\n[INTERRUPTED] Verification cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n[ERROR] Verification failed with exception: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
