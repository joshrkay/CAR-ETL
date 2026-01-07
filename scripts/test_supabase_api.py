"""Test Supabase API connection using the configured keys."""
import os
import sys
from typing import Optional

try:
    import httpx
except ImportError:
    print("[ERROR] httpx not installed. Install with: pip install httpx")
    sys.exit(1)


def test_supabase_api() -> bool:
    """Test Supabase REST API connection."""
    url = os.getenv("SUPABASE_URL")
    anon_key = os.getenv("SUPABASE_ANON_KEY")
    service_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    
    if not url or not anon_key or not service_key:
        print("[ERROR] Supabase environment variables not set")
        print("\nSet them with:")
        print('  $env:SUPABASE_URL="https://qifioafprrtkoiyylsqa.supabase.co"')
        print('  $env:SUPABASE_ANON_KEY="sb_publishable_PhKpWt7-UWeydaiqe99LDg_OSnuK7a0"')
        print('  $env:SUPABASE_SERVICE_ROLE_KEY="sb_secret_SDH3fH1Nl69oxRGNBPy91g_MhFHDYpm"')
        print("\nOr run: .\\scripts\\setup_env_vars.ps1")
        return False
    
    print("[INFO] Testing Supabase API connection...")
    print(f"[INFO] URL: {url}")
    print(f"[INFO] Anon Key: {anon_key[:30]}...")
    print(f"[INFO] Service Key: {service_key[:30]}...")
    print()
    
    # Test REST API endpoint
    api_url = f"{url}/rest/v1/"
    
    try:
        print("[TEST] Testing REST API endpoint...")
        with httpx.Client(timeout=10.0) as client:
            response = client.get(
                api_url,
                headers={
                    "apikey": anon_key,
                    "Authorization": f"Bearer {anon_key}"
                }
            )
            
            if response.status_code == 200:
                print("[SUCCESS] REST API connection works!")
                print(f"[INFO] Response: {response.text[:100]}...")
            else:
                print(f"[WARNING] REST API returned status {response.status_code}")
                print(f"[INFO] Response: {response.text[:200]}")
        
        # Test with service role key (has admin access)
        print()
        print("[TEST] Testing with Service Role key...")
        with httpx.Client(timeout=10.0) as client:
            response = client.get(
                api_url,
                headers={
                    "apikey": service_key,
                    "Authorization": f"Bearer {service_key}"
                }
            )
            
            if response.status_code == 200:
                print("[SUCCESS] Service Role key works!")
            else:
                print(f"[WARNING] Service Role key returned status {response.status_code}")
        
        print()
        print("[SUCCESS] Supabase API keys are configured and working!")
        print()
        print("[NOTE] These keys are for Supabase REST API, NOT for database migrations.")
        print("       For database migrations, you still need the PostgreSQL connection string.")
        print("       See: MIGRATION_GUIDE.md")
        return True
        
    except httpx.ConnectError as e:
        print(f"[ERROR] Connection failed: {e}")
        print("[INFO] Check your internet connection and Supabase URL")
        return False
    except httpx.TimeoutException:
        print("[ERROR] Connection timeout")
        print("[INFO] Check your internet connection")
        return False
    except Exception as e:
        print(f"[ERROR] Unexpected error: {e}")
        return False


if __name__ == "__main__":
    success = test_supabase_api()
    sys.exit(0 if success else 1)
