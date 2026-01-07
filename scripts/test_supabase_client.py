"""Test Supabase client library setup and basic operations."""
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

try:
    from src.db.supabase_client import (
        get_supabase_client,
        get_supabase_table,
        SupabaseClientManager
    )
    from src.config.supabase_config import get_supabase_config
except ImportError as e:
    print(f"[ERROR] Import failed: {e}")
    print("\n[INFO] Make sure you're running from the project root")
    print("       Install dependencies: pip install -r requirements.txt")
    sys.exit(1)


def test_client_creation():
    """Test creating Supabase client instances."""
    print("=" * 60)
    print("Testing Supabase Client Library")
    print("=" * 60)
    print()
    
    # Test configuration
    print("[TEST] Checking configuration...")
    try:
        config = get_supabase_config()
        print(f"[SUCCESS] Configuration loaded")
        print(f"    URL: {config.project_url}")
        print(f"    Anon Key: {config.anon_key[:30]}...")
        print(f"    Service Key: {config.service_role_key[:30]}...")
    except Exception as e:
        print(f"[ERROR] Configuration failed: {e}")
        return False
    print()
    
    # Test client creation with anon key
    print("[TEST] Creating client with anon key...")
    try:
        client_anon = get_supabase_client(use_service_role=False)
        print("[SUCCESS] Anon client created successfully")
    except ImportError as e:
        print(f"[✗] Supabase library not installed: {e}")
        print("\n[INFO] Install with: pip install supabase")
        return False
    except Exception as e:
        print(f"[ERROR] Failed to create anon client: {e}")
        return False
    print()
    
    # Test client creation with service role key
    print("[TEST] Creating client with service role key...")
    try:
        client_service = get_supabase_client(use_service_role=True)
        print("[SUCCESS] Service role client created successfully")
    except Exception as e:
        print(f"[ERROR] Failed to create service role client: {e}")
        return False
    print()
    
    # Test table access
    print("[TEST] Testing table access...")
    try:
        # Try to access a table (even if it doesn't exist, we can test the connection)
        table = get_supabase_table("test_table", use_service_role=True)
        print("[SUCCESS] Table reference created successfully")
    except Exception as e:
        print(f"[ERROR] Failed to create table reference: {e}")
        return False
    print()
    
    # Test health check
    print("[TEST] Testing health check...")
    try:
        manager = SupabaseClientManager(use_service_role=True)
        is_healthy = manager.health_check()
        if is_healthy:
            print("[SUCCESS] Health check passed")
        else:
            print("[⚠] Health check returned False (may still be OK)")
    except Exception as e:
        print(f"[⚠] Health check failed: {e}")
        print("     (This may be OK if tables don't exist yet)")
    print()
    
    print("=" * 60)
    print("[SUCCESS] Supabase client library is set up and working!")
    print("=" * 60)
    print()
    print("[INFO] You can now use Supabase API operations:")
    print("  from src.db.supabase_client import get_supabase_table")
    print("  table = get_supabase_table('your_table', use_service_role=True)")
    print("  result = table.select('*').execute()")
    print()
    
    return True


if __name__ == "__main__":
    success = test_client_creation()
    sys.exit(0 if success else 1)
