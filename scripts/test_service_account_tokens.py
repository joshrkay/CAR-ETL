"""Test service account tokens API endpoints."""
import sys
import os
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import httpx
from typing import Optional

def test_list_tokens(base_url: str = "http://localhost:8000", token: Optional[str] = None) -> None:
    """Test GET /api/v1/service-accounts/tokens endpoint.
    
    Args:
        base_url: API base URL.
        token: Admin JWT token for authentication.
    """
    if not token:
        print("ERROR: Admin JWT token required")
        print("Usage: python scripts/test_service_account_tokens.py <admin-jwt-token>")
        print("\nTo get an admin token:")
        print("1. Log in to your Auth0 application")
        print("2. Get a JWT token with Admin role")
        print("3. Use it as: python scripts/test_service_account_tokens.py <token>")
        return
    
    url = f"{base_url}/api/v1/service-accounts/tokens"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    print(f"Testing GET {url}")
    print(f"Headers: Authorization: Bearer {token[:20]}...")
    print()
    
    try:
        response = httpx.get(url, headers=headers, timeout=10.0)
        print(f"Status Code: {response.status_code}")
        print(f"Response Headers: {dict(response.headers)}")
        print()
        
        if response.status_code == 200:
            tokens = response.json()
            print(f"Success! Found {len(tokens)} token(s):")
            print()
            for token_data in tokens:
                print(f"  Token ID: {token_data.get('token_id')}")
                print(f"  Name: {token_data.get('name')}")
                print(f"  Role: {token_data.get('role')}")
                print(f"  Created By: {token_data.get('created_by')}")
                print(f"  Created At: {token_data.get('created_at')}")
                print(f"  Last Used: {token_data.get('last_used') or 'Never'}")
                print(f"  Is Revoked: {token_data.get('is_revoked')}")
                if token_data.get('revoked_at'):
                    print(f"  Revoked At: {token_data.get('revoked_at')}")
                print()
        elif response.status_code == 401:
            print("ERROR: Unauthorized")
            print("  - Token may be invalid or expired")
            print("  - Token may not have Admin role")
            print(f"  Response: {response.text}")
        elif response.status_code == 403:
            print("ERROR: Forbidden")
            print("  - Token does not have Admin role")
            print(f"  Response: {response.text}")
        else:
            print(f"ERROR: Unexpected status code")
            print(f"  Response: {response.text}")
            
    except httpx.RequestError as e:
        print(f"ERROR: Request failed: {e}")
        print("  - Is the API server running?")
        print(f"  - Check if {base_url} is correct")
    except Exception as e:
        print(f"ERROR: Unexpected error: {e}")
        import traceback
        traceback.print_exc()


def test_create_token(base_url: str = "http://localhost:8000", token: Optional[str] = None) -> None:
    """Test POST /api/v1/service-accounts/tokens endpoint.
    
    Args:
        base_url: API base URL.
        token: Admin JWT token for authentication.
    """
    if not token:
        print("ERROR: Admin JWT token required")
        return
    
    url = f"{base_url}/api/v1/service-accounts/tokens"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "name": "Test Service Account Token",
        "role": "analyst"
    }
    
    print(f"Testing POST {url}")
    print(f"Payload: {payload}")
    print()
    
    try:
        response = httpx.post(url, json=payload, headers=headers, timeout=10.0)
        print(f"Status Code: {response.status_code}")
        print()
        
        if response.status_code == 201:
            token_data = response.json()
            print("Success! Token created:")
            print(f"  Token ID: {token_data.get('token_id')}")
            print(f"  Token: {token_data.get('token')}")
            print(f"  Name: {token_data.get('name')}")
            print(f"  Role: {token_data.get('role')}")
            print(f"  Tenant ID: {token_data.get('tenant_id')}")
            print(f"  Created At: {token_data.get('created_at')}")
            print()
            print("⚠️  IMPORTANT: Save the token now - it won't be shown again!")
        else:
            print(f"ERROR: Failed to create token")
            print(f"  Response: {response.text}")
            
    except httpx.RequestError as e:
        print(f"ERROR: Request failed: {e}")
    except Exception as e:
        print(f"ERROR: Unexpected error: {e}")


def main():
    """Main test function."""
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python scripts/test_service_account_tokens.py <admin-jwt-token> [command]")
        print()
        print("Commands:")
        print("  list    - List all tokens (default)")
        print("  create  - Create a new token")
        print()
        print("Example:")
        print("  python scripts/test_service_account_tokens.py <token> list")
        print("  python scripts/test_service_account_tokens.py <token> create")
        return
    
    token = sys.argv[1]
    command = sys.argv[2] if len(sys.argv) > 2 else "list"
    
    base_url = os.getenv("API_BASE_URL", "http://localhost:8000")
    
    if command == "create":
        test_create_token(base_url, token)
    else:
        test_list_tokens(base_url, token)


if __name__ == "__main__":
    main()
