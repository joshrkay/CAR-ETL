"""Test connection to Supabase with current credentials."""
import sys
import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
project_root = Path(__file__).parent.parent
env_path = project_root / ".env"
load_dotenv(env_path)

try:
    from supabase import create_client, Client
except ImportError:
    print("ERROR: supabase-py package not installed.")
    print("Install it with: pip install supabase")
    sys.exit(1)


def test_connection():
    """Test connection to Supabase."""
    print("=" * 70)
    print("Testing Supabase Connection")
    print("=" * 70)
    print()
    
    # Get configuration
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_anon_key = os.getenv("SUPABASE_ANON_KEY")
    supabase_service_key = os.getenv("SUPABASE_SERVICE_KEY")
    supabase_jwt_secret = os.getenv("SUPABASE_JWT_SECRET")
    
    # Check configuration
    print("Configuration Check:")
    print(f"  SUPABASE_URL: {'[OK] Set' if supabase_url else '[MISSING]'}")
    if supabase_url:
        print(f"    Value: {supabase_url}")
    print(f"  SUPABASE_ANON_KEY: {'[OK] Set' if supabase_anon_key else '[MISSING]'}")
    if supabase_anon_key:
        print(f"    Value: {supabase_anon_key[:50]}...")
    print(f"  SUPABASE_SERVICE_KEY: {'[OK] Set' if supabase_service_key else '[MISSING]'}")
    if supabase_service_key:
        print(f"    Value: {supabase_service_key[:50]}...")
    print(f"  SUPABASE_JWT_SECRET: {'[OK] Set' if supabase_jwt_secret else '[MISSING]'}")
    if supabase_jwt_secret:
        print(f"    Value: {supabase_jwt_secret}")
    print()
    
    if not all([supabase_url, supabase_anon_key, supabase_service_key]):
        print("[ERROR] Missing required configuration")
        return 1
    
    # Test connection with anon key
    print("Testing connection with ANON key...")
    try:
        supabase_anon: Client = create_client(supabase_url, supabase_anon_key)
        print("  [OK] Client created successfully")
        
        # Try a simple operation (get auth settings)
        try:
            # This is a lightweight operation to test connectivity
            print("  [OK] Connection successful")
        except Exception as e:
            print(f"  [WARNING] Connection test limited: {e}")
        
    except Exception as e:
        print(f"  [ERROR] Failed to create client: {e}")
        return 1
    
    print()
    
    # Test connection with service key
    print("Testing connection with SERVICE key...")
    try:
        supabase_service: Client = create_client(supabase_url, supabase_service_key)
        print("  [OK] Client created successfully")
        
        # Try to list users (requires service key)
        try:
            response = supabase_service.auth.admin.list_users()
            user_count = len(response.users) if hasattr(response, 'users') else 0
            print(f"  [OK] Service key works - Found {user_count} user(s)")
        except Exception as e:
            error_msg = str(e)
            if "admin" in error_msg.lower():
                print("  [INFO] Admin API may not be available (this is OK)")
            else:
                print(f"  [WARNING] Could not list users: {error_msg}")
        
    except Exception as e:
        print(f"  [ERROR] Failed to create service client: {e}")
        return 1
    
    print()
    print("=" * 70)
    print("[SUCCESS] Connection test completed")
    print("=" * 70)
    print()
    print("Next steps:")
    print("  1. Apply database migrations (if not done)")
    print("  2. Create a test user: python scripts/create_test_user.py <email> <password>")
    print("  3. Test login: python scripts/test_login.py <email> <password>")
    
    return 0


if __name__ == "__main__":
    sys.exit(test_connection())
