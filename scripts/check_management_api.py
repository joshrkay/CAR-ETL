"""Script to check if Management API is enabled and provide guidance."""
import sys
from pathlib import Path

# Add src to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import httpx
from src.auth.config import get_auth0_config


def check_management_api() -> None:
    """Check if Management API is accessible."""
    print("=" * 60)
    print("Management API Availability Check")
    print("=" * 60)
    print()
    
    try:
        config = get_auth0_config()
        print("[SUCCESS] Configuration loaded")
        print(f"  Domain: {config.domain}")
        print(f"  Management API URL: {config.management_api_url}")
        print()
    except Exception as e:
        print(f"[ERROR] Configuration failed: {e}")
        sys.exit(1)
    
    # Try to get a token
    print("=" * 60)
    print("Step 1: Testing Token Endpoint")
    print("=" * 60)
    
    token_url = config.token_url
    print(f"[INFO] Token URL: {token_url}")
    
    # Test with dummy credentials to see what error we get
    test_payload = {
        "client_id": config.management_client_id,
        "client_secret": config.management_client_secret,
        "audience": config.management_api_url,
        "grant_type": "client_credentials"
    }
    
    try:
        response = httpx.post(token_url, json=test_payload, timeout=10.0)
        print(f"[INFO] Response status: {response.status_code}")
        
        if response.status_code == 200:
            print("[SUCCESS] Management API is ENABLED and accessible!")
            print("  Your client credentials are working.")
            print()
            print("Next step: Run the setup script")
            print("  python scripts/setup_auth0.py")
            return
        elif response.status_code == 403:
            error_data = response.json() if response.text else {}
            error_desc = error_data.get("error_description", "")
            
            print(f"[ERROR] Access denied (403)")
            print(f"  Error: {error_data.get('error', 'unknown')}")
            print(f"  Description: {error_desc}")
            print()
            
            if "Service not enabled" in error_desc:
                print("=" * 60)
                print("Management API is NOT ENABLED")
                print("=" * 60)
                print()
                print("To enable Management API:")
                print("1. Go to https://manage.auth0.com")
                print("2. Navigate to Applications > Applications")
                print("3. Find your application:")
                print(f"   Client ID: {config.management_client_id}")
                print("4. Go to 'APIs' tab")
                print("5. Look for 'Auth0 Management API' in dropdown")
                print("6. If it's there:")
                print("   - Select 'Auth0 Management API'")
                print("   - Toggle 'Authorize' to ON")
                print("   - Grant required permissions")
                print("   - Click 'Authorize'")
                print("7. If it's NOT in the list:")
                print("   - Management API may not be available for your plan")
                print("   - Check Settings > Subscription")
                print("   - You may need to upgrade your Auth0 plan")
                print()
                print("See docs/ENABLE_MANAGEMENT_API.md for detailed instructions")
            else:
                print("The client may not be authorized for Management API.")
                print("Follow the steps above to authorize it.")
        elif response.status_code == 401:
            print("[ERROR] Authentication failed (401)")
            print("  Possible causes:")
            print("  - Client ID is incorrect")
            print("  - Client Secret is incorrect")
            print("  - Check your credentials in the Auth0 Dashboard")
        else:
            print(f"[ERROR] Unexpected status: {response.status_code}")
            print(f"  Response: {response.text[:200]}")
            
    except httpx.RequestError as e:
        print(f"[ERROR] Network error: {e}")
        print("  Check your internet connection and Auth0 domain")
    
    print()
    print("=" * 60)
    print("For detailed instructions, see:")
    print("  docs/ENABLE_MANAGEMENT_API.md")
    print("=" * 60)


if __name__ == "__main__":
    check_management_api()
