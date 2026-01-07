"""Test script to verify Auth0 Management API connection."""
import sys
from pathlib import Path

# Add src to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.auth.config import get_auth0_config
from src.auth.auth0_client import Auth0ManagementClient, Auth0TokenError, Auth0APIError


def test_connection() -> None:
    """Test Auth0 Management API connection."""
    print("=" * 60)
    print("Auth0 Connection Test")
    print("=" * 60)
    print()
    
    # Load configuration
    try:
        config = get_auth0_config()
        print("[SUCCESS] Configuration loaded")
        print(f"  Domain: {config.domain}")
        print(f"  Client ID: {config.management_client_id[:20]}...")
        print(f"  API Identifier: {config.api_identifier}")
        print()
    except Exception as e:
        print(f"[ERROR] Configuration failed: {e}")
        print("\nMake sure these environment variables are set:")
        print("  - AUTH0_DOMAIN")
        print("  - AUTH0_MANAGEMENT_CLIENT_ID")
        print("  - AUTH0_MANAGEMENT_CLIENT_SECRET")
        print("  - AUTH0_DATABASE_CONNECTION_NAME")
        sys.exit(1)
    
    # Test token acquisition
    print("=" * 60)
    print("Step 1: Testing Token Acquisition")
    print("=" * 60)
    
    try:
        client = Auth0ManagementClient(config)
        token = client._get_access_token()
        
        print("[SUCCESS] Token acquired successfully")
        print(f"  Token preview: {token[:50]}...")
        print(f"  Token length: {len(token)} characters")
        print()
    except Auth0TokenError as e:
        print(f"[ERROR] Token acquisition failed: {e}")
        print()
        
        error_str = str(e)
        if "access_denied" in error_str or "Service not enabled" in error_str:
            print("The error indicates the Management API service is not enabled.")
            print()
            print("Possible causes:")
            print("  1. Management API is not enabled for this Auth0 tenant")
            print("  2. The tenant type doesn't support Management API")
            print("  3. The client needs to be authorized for Management API")
            print()
            print("To fix:")
            print("  1. Go to https://manage.auth0.com")
            print("  2. Navigate to Applications > Applications")
            print("  3. Find your application (Client ID shown above)")
            print("  4. Go to 'APIs' tab")
            print("  5. Look for 'Auth0 Management API' in the dropdown")
            print("  6. If it's not listed, Management API may not be available for this tenant")
            print("  7. If it is listed, select it and toggle 'Authorize'")
            print("  8. Grant required permissions and click 'Authorize'")
            print()
            print("Note: Some Auth0 tenant types (like free/dev) may have")
            print("      restrictions on Management API access.")
        else:
            print("Possible causes:")
            print("  1. Client ID or Secret is incorrect")
            print("  2. Client is not authorized for Auth0 Management API")
            print("  3. Client doesn't have required permissions")
            print()
            print("To fix:")
            print("  1. Go to https://manage.auth0.com")
            print("  2. Applications > Your Application")
            print("  3. Go to 'APIs' tab")
            print("  4. Select 'Auth0 Management API'")
            print("  5. Toggle 'Authorize'")
            print("  6. Grant required permissions")
            print("  7. Click 'Authorize'")
        sys.exit(1)
    except Exception as e:
        print(f"[ERROR] Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    
    # Test connectivity
    print("=" * 60)
    print("Step 2: Testing Management API Connectivity")
    print("=" * 60)
    
    try:
        is_connected = client.verify_connectivity()
        if is_connected:
            print("[SUCCESS] Connected to Auth0 Management API")
            print(f"  Management API URL: {config.management_api_url}")
            print()
        else:
            print("[ERROR] Connectivity check failed")
            sys.exit(1)
    except Exception as e:
        print(f"[ERROR] Connectivity test failed: {e}")
        sys.exit(1)
    
    # Test API endpoints
    print("=" * 60)
    print("Step 3: Testing API Endpoints")
    print("=" * 60)
    
    try:
        # Test getting connections
        print("[INFO] Testing: Get database connections...")
        connections = get_database_connections(config, client)
        print(f"[SUCCESS] Found {len(connections)} database connection(s)")
        for conn in connections[:3]:  # Show first 3
            print(f"  - {conn.get('name', 'Unknown')} ({conn.get('id', 'N/A')})")
        if len(connections) > 3:
            print(f"  ... and {len(connections) - 3} more")
        print()
    except Exception as e:
        print(f"[WARN] Could not fetch connections: {e}")
        print("  This might be a permissions issue")
        print()
    
    try:
        # Test getting resource servers (APIs)
        print("[INFO] Testing: Get resource servers (APIs)...")
        apis = get_resource_servers(config, client)
        print(f"[SUCCESS] Found {len(apis)} resource server(s)")
        for api in apis[:3]:  # Show first 3
            print(f"  - {api.get('name', 'Unknown')} ({api.get('identifier', 'N/A')})")
        if len(apis) > 3:
            print(f"  ... and {len(apis) - 3} more")
        print()
    except Exception as e:
        print(f"[WARN] Could not fetch resource servers: {e}")
        print("  This might be a permissions issue")
        print()
    
    # Summary
    print("=" * 60)
    print("[SUCCESS] All Connection Tests Passed!")
    print("=" * 60)
    print()
    print("Your Auth0 Management API client is properly configured.")
    print("You can now run the setup script:")
    print("  python scripts/setup_auth0.py")
    print()


def get_database_connections(config, client):
    """Get database connections."""
    import httpx
    
    token = client._get_access_token()
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    response = httpx.get(
        f"{config.management_api_url}/connections",
        headers=headers,
        params={"strategy": "auth0"},
        timeout=30.0
    )
    response.raise_for_status()
    return response.json()


def get_resource_servers(config, client):
    """Get resource servers (APIs)."""
    import httpx
    
    token = client._get_access_token()
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    response = httpx.get(
        f"{config.management_api_url}/resource-servers",
        headers=headers,
        timeout=30.0
    )
    response.raise_for_status()
    return response.json()


if __name__ == "__main__":
    test_connection()
