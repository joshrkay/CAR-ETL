"""Test Supabase audit logger configuration."""
import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Set the service role key
os.environ['SUPABASE_SERVICE_ROLE_KEY'] = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InFpZmlvYWZwcnJ0a29peXlsc3FhIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc2Nzc1OTQ3NiwiZXhwIjoyMDgzMzM1NDc2fQ.EcN2vIilunhiercdPZm_H7Gouwf0xqSXgGNDkSmP-ZY'

from src.config.supabase_config import get_supabase_config
from src.config.audit_config import get_audit_config
from src.audit.logger_factory import get_audit_logger

def main():
    print("=" * 60)
    print("Supabase Audit Logger Configuration Test")
    print("=" * 60)
    print()
    
    # Test Supabase config
    print("1. Testing Supabase Configuration...")
    supabase_config = get_supabase_config()
    print(f"   [OK] Project URL: {supabase_config.project_url}")
    print(f"   [OK] Service Role Key: {supabase_config.service_role_key[:50]}...")
    print(f"   [OK] Key Length: {len(supabase_config.service_role_key)} characters")
    print(f"   [OK] Key Format: {'JWT' if len(supabase_config.service_role_key) > 100 else 'Legacy'}")
    print()
    
    # Test Audit config
    print("2. Testing Audit Configuration...")
    audit_config = get_audit_config()
    print(f"   [OK] Storage Backend: {audit_config.audit_storage_backend}")
    print(f"   [OK] Retention Years: {audit_config.audit_retention_years}")
    print()
    
    # Test Audit Logger
    print("3. Testing Audit Logger Initialization...")
    try:
        logger = get_audit_logger()
        print(f"   [OK] Logger Type: {type(logger).__name__}")
        print(f"   [OK] Logger Initialized Successfully")
    except Exception as e:
        print(f"   [ERROR] Error: {e}")
        return 1
    print()
    
    # Test Supabase Client
    print("4. Testing Supabase Client Connection...")
    try:
        from src.db.supabase_client import get_supabase_client
        client = get_supabase_client(use_service_role=True)
        print(f"   [OK] Supabase Client Created")
        
        # Try a simple query (will fail if table doesn't exist, but that's OK)
        try:
            result = client.table('audit_logs').select('id').limit(1).execute()
            print(f"   [OK] audit_logs table exists and is accessible")
        except Exception as e:
            if 'relation' in str(e).lower() or 'does not exist' in str(e).lower():
                print(f"   [WARN] audit_logs table does not exist yet (run migration or SQL script)")
            else:
                print(f"   [WARN] Connection test: {type(e).__name__}")
    except Exception as e:
        print(f"   [ERROR] Error: {e}")
        return 1
    print()
    
    print("=" * 60)
    print("[OK] Configuration Test Complete")
    print("=" * 60)
    print()
    print("Next Steps:")
    print("1. Create audit_logs table:")
    print("   - Option A: Run 'alembic upgrade head' (requires DATABASE_URL)")
    print("   - Option B: Run scripts/create_audit_logs_table.sql in Supabase SQL Editor")
    print()
    print("2. To make service role key permanent:")
    print("   - Add to .env file: SUPABASE_SERVICE_ROLE_KEY=your-key")
    print("   - Or set as system environment variable")
    print()
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
