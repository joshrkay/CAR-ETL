"""Manual JWT generation and validation testing script."""
import json
import sys
from typing import Dict, Any, Optional
from datetime import datetime

import httpx
from jose import jwt, jwk
from jose.utils import base64url_decode

from .config import get_auth0_config


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


def get_test_token(
    domain: str,
    client_id: str,
    client_secret: str,
    audience: str
) -> Optional[str]:
    """Get a test token using client credentials flow."""
    token_url = f"https://{domain}/oauth/token"
    
    payload = {
        "client_id": client_id,
        "client_secret": client_secret,
        "audience": audience,
        "grant_type": "client_credentials"
    }
    
    try:
        print(f"[INFO] Requesting token from: {token_url}")
        response = httpx.post(token_url, json=payload, timeout=10.0)
        response.raise_for_status()
        token_data = response.json()
        return token_data.get("access_token")
    except httpx.HTTPStatusError as e:
        print(f"[ERROR] Token request failed: {e.response.status_code}")
        print(f"   Response: {e.response.text[:200]}")
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
            print(f"   Time until expiry: {exp_time - datetime.utcnow()}")
    except Exception as e:
        print(f"[ERROR] Failed to inspect token: {e}")


def test_jwt_generation() -> None:
    """Test JWT generation and validation."""
    print("=" * 60)
    print("JWT Generation and Validation Test")
    print("=" * 60)
    
    try:
        config = get_auth0_config()
    except Exception as e:
        print(f"[ERROR] Configuration error: {e}")
        print("   Make sure all required environment variables are set:")
        print("   - AUTH0_DOMAIN")
        print("   - AUTH0_MANAGEMENT_CLIENT_ID")
        print("   - AUTH0_MANAGEMENT_CLIENT_SECRET")
        print("   - AUTH0_API_IDENTIFIER")
        sys.exit(1)
    
    print(f"\n[SUCCESS] Configuration loaded:")
    print(f"   Domain: {config.domain}")
    print(f"   API Identifier: {config.api_identifier}")
    print(f"   JWKS URI: {config.jwks_uri}")
    print(f"   Algorithm: {config.algorithm}")
    
    # Get a test token
    print("\n" + "=" * 60)
    print("Step 1: Requesting Test Token")
    print("=" * 60)
    
    token = get_test_token(
        domain=config.domain,
        client_id=config.management_client_id,
        client_secret=config.management_client_secret,
        audience=config.management_api_url
    )
    
    if not token:
        print("\n[ERROR] Failed to obtain test token")
        print("   Note: This token is for Management API.")
        print("   For API resource tokens, use a different client configured for your API.")
        sys.exit(1)
    
    print(f"[SUCCESS] Token obtained: {token[:50]}...")
    
    # Inspect token
    print("\n" + "=" * 60)
    print("Step 2: Inspecting Token Structure")
    print("=" * 60)
    inspect_token(token)
    
    # Verify token
    print("\n" + "=" * 60)
    print("Step 3: Verifying Token with JWKS")
    print("=" * 60)
    
    # For Management API token, use Management API as audience
    # For API resource token, use API identifier
    payload = decode_jwt_token(
        token=token,
        jwks_uri=config.jwks_uri,
        audience=config.management_api_url
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
            else:
                print(f"   {key}: {value}")
    else:
        print("\n[ERROR] Token verification failed")
        sys.exit(1)
    
    # Test with API identifier (if different)
    if config.management_api_url != config.api_identifier:
        print("\n" + "=" * 60)
        print("Step 4: Testing with API Identifier Audience")
        print("=" * 60)
        print("   Note: Management API token won't validate against API identifier.")
        print("   This requires a token issued for the API resource.")
    
    print("\n" + "=" * 60)
    print("[SUCCESS] JWT Test Complete")
    print("=" * 60)


if __name__ == "__main__":
    test_jwt_generation()
