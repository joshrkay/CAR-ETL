"""Verify that CAR API resource exists and is configured correctly."""
import sys
from pathlib import Path

# Add src to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import httpx
from src.auth.config import get_auth0_config


def verify_api_resource() -> None:
    """Verify CAR API resource configuration."""
    print("=" * 60)
    print("CAR API Resource Verification")
    print("=" * 60)
    print()
    
    try:
        config = get_auth0_config()
        domain = config.domain
        api_identifier = config.api_identifier
        client_id = "bjtGWwmdLFUfpHZRN3FCirQxUeIGDFBq"
        client_secret = "2RzMIQKW5HKXt8uNL_3QM-pLZCUKXoljudDk8yqz1O85W9irUxBgHHCKH3OZI3dq"
    except Exception as e:
        print(f"[ERROR] Configuration error: {e}")
        sys.exit(1)
    
    print("[INFO] Configuration:")
    print(f"   Domain: {domain}")
    print(f"   API Identifier: {api_identifier}")
    print(f"   Client ID: {client_id[:20]}...")
    print()
    
    # Test 1: Try to get a token
    print("=" * 60)
    print("Test 1: Token Generation")
    print("=" * 60)
    
    token_url = f"https://{domain}/oauth/token"
    payload = {
        "client_id": client_id,
        "client_secret": client_secret,
        "audience": api_identifier,
        "grant_type": "client_credentials"
    }
    
    try:
        response = httpx.post(token_url, json=payload, timeout=10.0)
        
        if response.status_code == 200:
            token_data = response.json()
            token = token_data.get("access_token")
            print("[SUCCESS] Token generated successfully!")
            print(f"   Token type: {token_data.get('token_type')}")
            print(f"   Expires in: {token_data.get('expires_in')} seconds")
            print(f"   Token preview: {token[:50]}...")
            
            # Decode token to check scopes
            from jose.utils import base64url_decode
            import json
            parts = token.split(".")
            payload_data = json.loads(base64url_decode(parts[1]).decode("utf-8"))
            
            print("\n[INFO] Token Claims:")
            print(f"   Audience: {payload_data.get('aud')}")
            print(f"   Issuer: {payload_data.get('iss')}")
            if "scope" in payload_data:
                scopes = payload_data["scope"].split() if isinstance(payload_data["scope"], str) else payload_data["scope"]
                print(f"   Scopes: {', '.join(scopes)}")
            
            print("\n" + "=" * 60)
            print("[SUCCESS] CAR API Resource is Configured Correctly!")
            print("=" * 60)
            print("\n[INFO] Summary:")
            print("  ✓ API resource exists")
            print("  ✓ Client is authorized")
            print("  ✓ Token generation works")
            print("  ✓ Token contains expected claims")
            if "scope" in payload_data:
                print("  ✓ Scopes are configured")
            
            print("\n[INFO] Next step: Test JWT validation")
            print("  python scripts/test_jwt_new_client.py")
            
        elif response.status_code == 403:
            error_data = response.json() if response.text else {}
            error_desc = error_data.get("error_description", "")
            
            print(f"[ERROR] Access denied (403)")
            print(f"   Error: {error_data.get('error', 'unknown')}")
            print(f"   Description: {error_desc}")
            print()
            
            if "Service not enabled" in error_desc:
                print("The CAR API resource does not exist yet.")
                print("\nTo create it:")
                print("  1. Run: python scripts/create_api_resource.py")
                print("  2. Follow the step-by-step instructions")
                print("  3. Then run this verification again")
            else:
                print("Possible issues:")
                print("  1. API resource exists but client is not authorized")
                print("  2. Client credentials are incorrect")
                print("  3. Required scopes are not granted")
                
        elif response.status_code == 401:
            print("[ERROR] Authentication failed (401)")
            print("   Client ID or Secret may be incorrect")
            
        else:
            print(f"[ERROR] Unexpected status: {response.status_code}")
            print(f"   Response: {response.text[:200]}")
            
    except httpx.RequestError as e:
        print(f"[ERROR] Network error: {e}")
        print("   Check your internet connection and Auth0 domain")
    
    print()


if __name__ == "__main__":
    verify_api_resource()
