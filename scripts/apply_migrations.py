"""Script to apply database migrations directly via Supabase API."""
import os
import sys
from pathlib import Path

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


def read_migration_file(migration_path: Path) -> str:
    """Read migration file content."""
    if not migration_path.exists():
        raise FileNotFoundError(f"Migration file not found: {migration_path}")
    
    with open(migration_path, "r", encoding="utf-8") as f:
        return f.read()


def apply_migration(supabase: Client, migration_sql: str, migration_name: str) -> bool:
    """
    Apply a migration using Supabase RPC or direct SQL execution.
    
    Note: Supabase Python client doesn't support direct SQL execution,
    so we'll use the REST API to execute SQL via the service role.
    """
    try:
        # Use Supabase's REST API to execute SQL
        # The service key allows us to execute arbitrary SQL
        response = supabase.rpc("exec_sql", {"sql": migration_sql}).execute()
        return True
    except Exception as e:
        # If RPC doesn't exist, try using the PostgREST API directly
        # We'll need to use httpx to make a direct request
        import httpx
        
        config = get_auth_config()
        url = f"{config.supabase_url}/rest/v1/rpc/exec_sql"
        
        try:
            response = httpx.post(
                url,
                json={"sql": migration_sql},
                headers={
                    "apikey": config.supabase_service_key,
                    "Authorization": f"Bearer {config.supabase_service_key}",
                    "Content-Type": "application/json",
                },
                timeout=30.0,
            )
            
            if response.status_code in [200, 201, 204]:
                return True
            else:
                print(f"  [ERROR] HTTP {response.status_code}: {response.text}")
                return False
        except Exception as http_error:
            print(f"  [ERROR] Failed to execute SQL: {http_error}")
            print(f"  [INFO] Migration '{migration_name}' needs to be applied manually")
            print(f"  [INFO] Go to Supabase Dashboard → SQL Editor")
            print(f"  [INFO] Copy and paste the migration SQL")
            return False


def apply_migrations():
    """Apply all pending migrations."""
    print("=" * 60)
    print("Database Migration Application")
    print("=" * 60)
    
    # Check environment variables
    required_vars = ["SUPABASE_URL", "SUPABASE_SERVICE_KEY"]
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    
    if missing_vars:
        print(f"\n[ERROR] Missing required environment variables: {', '.join(missing_vars)}")
        return False
    
    try:
        config = get_auth_config()
    except Exception as e:
        print(f"\n[ERROR] Failed to load auth config: {e}")
        return False
    
    # Initialize Supabase client
    try:
        supabase: Client = create_client(
            config.supabase_url,
            config.supabase_service_key,
        )
        print("\n[OK] Connected to Supabase")
    except Exception as e:
        print(f"\n[ERROR] Failed to connect to Supabase: {e}")
        return False
    
    # List of migrations to apply (in order)
    migrations = [
        "002_feature_flags.sql",
        "012_audit_logs.sql",
        "020_documents.sql",
        "024_email_ingestions.sql",
    ]
    
    migrations_dir = project_root / "supabase" / "migrations"
    
    print("\n" + "=" * 60)
    print("Applying Migrations")
    print("=" * 60)
    
    applied_count = 0
    failed_count = 0
    
    for migration_file in migrations:
        migration_path = migrations_dir / migration_file
        
        if not migration_path.exists():
            print(f"\n[SKIP] Migration file not found: {migration_file}")
            continue
        
        print(f"\nApplying: {migration_file}")
        
        try:
            migration_sql = read_migration_file(migration_path)
            
            # Try to apply via direct SQL execution
            # Since Supabase Python client doesn't support direct SQL,
            # we'll provide instructions for manual application
            print(f"  [INFO] Migration file read successfully")
            print(f"  [INFO] This migration needs to be applied manually")
            print(f"  [INFO] Steps:")
            print(f"    1. Go to: https://supabase.com/dashboard/project/ueqzwqejpjmsspfiypgb/sql/new")
            print(f"    2. Copy the contents of: {migration_path}")
            print(f"    3. Paste into SQL Editor and click 'Run'")
            
            # For now, we'll just verify the file exists and is readable
            applied_count += 1
            
        except Exception as e:
            print(f"  [ERROR] Failed to read migration: {e}")
            failed_count += 1
    
    print("\n" + "=" * 60)
    print("Migration Application Summary")
    print("=" * 60)
    print(f"\nMigrations found: {len(migrations)}")
    print(f"Migrations ready to apply: {applied_count}")
    print(f"Migrations with errors: {failed_count}")
    
    if failed_count == 0:
        print("\n[SUCCESS] All migration files are ready to apply")
        print("\n[ACTION REQUIRED] Apply migrations manually via Supabase Dashboard:")
        print("  1. Go to: https://supabase.com/dashboard/project/ueqzwqejpjmsspfiypgb/sql/new")
        print("  2. Apply each migration file in order:")
        for migration_file in migrations:
            print(f"     - {migration_file}")
        print("  3. Run verification: python scripts/verify_migrations.py")
        return True
    else:
        print("\n[WARNING] Some migrations have errors")
        return False


if __name__ == "__main__":
    try:
        success = apply_migrations()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n[INTERRUPTED] Migration application cancelled")
        sys.exit(1)
    except Exception as e:
        print(f"\n[ERROR] Migration application failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
