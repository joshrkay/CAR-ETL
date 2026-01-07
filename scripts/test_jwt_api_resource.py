"""Test JWT generation for CAR API resource (not Management API)."""
import json
import sys
from typing import Dict, Any, Optional
from datetime import datetime
from pathlib import Path

# Add src to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import httpx
from jose import jwt, jwk
from jose.utils import base64url_decode
from src.auth.config import get_auth0_config


def fetch_jwks(jwks_uri: str) -> Dict[str, Any]:
    """Fetch JWKS from Auth0."""
    try:
        response = httpx.get(jwks_uri, timeout=10.0)
        response.raise_for_status()
        return response.json()
    except httpx.RequestError as e:
        print(f"[ERROR] Failed to fetch JWKS: {e}")
        sys.exit(1)


def get_jwt_key(jwks: Dict[str, Any], kid: str) -> Optional[Dict[str, Any]]:
    """Get the key from JWKS by key ID."""
    for key in jwks.get("keys", []):
        if key.get("kid") == kid:
            return key
    return None


def decode_jwt_token(token: str, jwks_uri: str, audience: str) -> Dict[str, Any]:
    """Decode and verify JWT token."""
    try:
        # Get unverified header to find key ID
        unverified_header = jwt.get_unverified_header(token)
        kid = unverified_header.get("kid")
        
        if not kid:
            print("[ERROR] Token header missing 'kid' (key ID)")
            return {}
        
        # Fetch JWKS
        print(f"[INFO] Fetching JWKS from: {jwks_uri}")
        jwks = fetch_jwks(jwks_uri)
        
        # Find the key
        key = get_jwt_key(jwks, kid)
        if not key:
            print(f"[ERROR] Key with kid '{kid}' not found in JWKS")
            return {}
        
        # Convert JWK to RSA key
        public_key = jwk.construct(key)
        
        # Decode and verify token
        print(f"[INFO] Verifying token with audience: {audience}")
        payload = jwt.decode(
            token,
            public_key,
            algorithms=["RS256"],
            audience=audience,
            options={"verify_signature": True, "verify_aud": True, "verify_exp": True}
        )
        
        return payload
    except jwt.ExpiredSignatureError:
        print("[ERROR] Token has expired")
        return {}
    except jwt.JWTClaimsError as e:
        print(f"[ERROR] Token claims validation failed: {e}")
        return {}
    except jwt.JWTError as e:
        print(f"[ERROR] JWT validation failed: {e}")
        return {}
    except Exception as e:
        print(f"[ERROR] Unexpected error: {e}")
        return {}


def get_api_token(
    domain: str,
    client_id: str,
    client_secret: str,
    audience: str
) -> Optional[str]:
    """Get a token for the API resource using client credentials flow."""
    token_url = f"https://{domain}/oauth/token"
    
    payload = {
        "client_id": client_id,
        "client_secret": client_secret,
        "audience": audience,
        "grant_type": "client_credentials"
    }
    
    try:
        print(f"[INFO] Requesting token from: {token_url}")
        print(f"[INFO] Audience: {audience}")
        response = httpx.post(token_url, json=payload, timeout=10.0)
        response.raise_for_status()
        token_data = response.json()
        return token_data.get("access_token")
    except httpx.HTTPStatusError as e:
        print(f"[ERROR] Token request failed: {e.response.status_code}")
        print(f"   Response: {e.response.text[:500]}")
        return None
    except httpx.RequestError as e:
        print(f"[ERROR] Network error: {e}")
        return None


def inspect_token(token: str) -> None:
    """Inspect token structure without verification."""
    try:
        parts = token.split(".")
        if len(parts) != 3:
            print("[ERROR] Invalid JWT format (should have 3 parts)")
            return
        
        header = json.loads(base64url_decode(parts[0]).decode("utf-8"))
        payload = json.loads(base64url_decode(parts[1]).decode("utf-8"))
        
        print("\n[INFO] Token Structure:")
        print(f"   Header: {json.dumps(header, indent=2)}")
        print(f"   Payload: {json.dumps(payload, indent=2)}")
        
        # Decode expiration
        if "exp" in payload:
            exp_time = datetime.fromtimestamp(payload["exp"])
            print(f"   Expires: {exp_time.isoformat()}")
            time_until = exp_time - datetime.utcnow()
            print(f"   Time until expiry: {time_until}")
    except Exception as e:
        print(f"[ERROR] Failed to inspect token: {e}")


def test_jwt_for_api() -> None:
    """Test JWT generation for CAR API resource."""
    print("=" * 60)
    print("JWT Generation Test for CAR API Resource")
    print("=" * 60)
    
    try:
        config = get_auth0_config()
    except Exception as e:
        print(f"[ERROR] Configuration error: {e}")
        print("   Make sure all required environment variables are set")
        sys.exit(1)
    
    print(f"\n[SUCCESS] Configuration loaded:")
    print(f"   Domain: {config.domain}")
    print(f"   API Identifier: {config.api_identifier}")
    print(f"   JWKS URI: {config.jwks_uri}")
    print(f"   Algorithm: {config.algorithm}")
    
    # Get client credentials for API resource
    print("\n" + "=" * 60)
    print("Step 1: Client Credentials")
    print("=" * 60)
    print("\nTo test JWT generation for the API resource, you need:")
    print("1. A Machine-to-Machine application configured for 'CAR API'")
    print("2. The 'CAR API' resource must exist in Auth0")
    print("3. Client ID and Secret for that application")
    print()
    print("If you don't have a client for CAR API yet:")
    print("1. Go to https://manage.auth0.com")
    print("2. Applications > Create Application")
    print("3. Type: Machine to Machine Applications")
    print("4. Authorize for 'CAR API' (not Management API)")
    print("5. Grant scopes: read:documents, write:documents, admin")
    print()
    
    # Try to get client credentials from environment or prompt
    api_client_id = None
    api_client_secret = None
    
    import os
    api_client_id = os.getenv("AUTH0_API_CLIENT_ID")
    api_client_secret = os.getenv("AUTH0_API_CLIENT_SECRET")
    
    if not api_client_id or not api_client_secret:
        print("[INFO] API client credentials not found in environment")
        print("   Set these environment variables to test:")
        print("   AUTH0_API_CLIENT_ID=your-api-client-id")
        print("   AUTH0_API_CLIENT_SECRET=your-api-client-secret")
        print()
        print("Or test manually with curl:")
        print(f"   curl -X POST https://{config.domain}/oauth/token \\")
        print(f"     -H 'Content-Type: application/json' \\")
        print(f"     -d '{{")
        print(f"       \"client_id\": \"YOUR_CLIENT_ID\",")
        print(f"       \"client_secret\": \"YOUR_CLIENT_SECRET\",")
        print(f"       \"audience\": \"{config.api_identifier}\",")
        print(f"       \"grant_type\": \"client_credentials\"")
        print(f"     }}'")
        print()
        print("=" * 60)
        print("Manual JWT Testing Instructions")
        print("=" * 60)
        print("\n1. Get a token using the curl command above")
        print("2. Decode the token at: https://jwt.io")
        print("3. Verify the token structure and claims")
        print("4. Test the JWKS endpoint:")
        print(f"   curl {config.jwks_uri}")
        return
    
    print(f"[SUCCESS] API client credentials found")
    print(f"   Client ID: {api_client_id[:20]}...")
    
    # Get a test token
    print("\n" + "=" * 60)
    print("Step 2: Requesting Token for API Resource")
    print("=" * 60)
    
    token = get_api_token(
        domain=config.domain,
        client_id=api_client_id,
        client_secret=api_client_secret,
        audience=config.api_identifier
    )
    
    if not token:
        print("\n[ERROR] Failed to obtain token")
        print("   Make sure:")
        print("   1. The 'CAR API' resource exists in Auth0")
        print("   2. Your client is authorized for 'CAR API'")
        print("   3. Client credentials are correct")
        sys.exit(1)
    
    print(f"[SUCCESS] Token obtained: {token[:50]}...")
    
    # Inspect token
    print("\n" + "=" * 60)
    print("Step 3: Inspecting Token Structure")
    print("=" * 60)
    inspect_token(token)
    
    # Verify token
    print("\n" + "=" * 60)
    print("Step 4: Verifying Token with JWKS")
    print("=" * 60)
    
    payload = decode_jwt_token(
        token=token,
        jwks_uri=config.jwks_uri,
        audience=config.api_identifier
    )
    
    if payload:
        print("\n[SUCCESS] Token verified successfully!")
        print(f"\n[INFO] Verified Claims:")
        for key, value in payload.items():
            if key == "exp":
                exp_time = datetime.fromtimestamp(value)
                print(f"   {key}: {value} ({exp_time.isoformat()})")
            elif key == "iat":
                iat_time = datetime.fromtimestamp(value)
                print(f"   {key}: {value} ({iat_time.isoformat()})")
            elif key == "scope":
                print(f"   {key}: {value}")
            else:
                print(f"   {key}: {value}")
    else:
        print("\n[ERROR] Token verification failed")
        sys.exit(1)
    
    print("\n" + "=" * 60)
    print("[SUCCESS] JWT Test Complete")
    print("=" * 60)


if __name__ == "__main__":
    test_jwt_for_api()
