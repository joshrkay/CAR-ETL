"""Test JWT generation with new client credentials."""
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
        import traceback
        traceback.print_exc()
        return {}


def get_token(domain: str, client_id: str, client_secret: str, audience: str) -> Optional[str]:
    """Get a JWT token using client credentials flow."""
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
        error_text = e.response.text[:500] if e.response.text else "No error details"
        print(f"   Response: {error_text}")
        
        # Try to parse error
        try:
            error_json = e.response.json()
            if "error_description" in error_json:
                print(f"   Error: {error_json.get('error')}")
                print(f"   Description: {error_json.get('error_description')}")
        except:
            pass
        
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
        
        print("\n[INFO] Token Structure (Unverified):")
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


def main() -> None:
    """Main test function."""
    print("=" * 60)
    print("JWT Generation Test - New Client Credentials")
    print("=" * 60)
    print()
    
    # New credentials
    domain = "dev-khx88c3lu7wz2dxx.us.auth0.com"
    client_id = "bjtGWwmdLFUfpHZRN3FCirQxUeIGDFBq"
    client_secret = "2RzMIQKW5HKXt8uNL_3QM-pLZCUKXoljudDk8yqz1O85W9irUxBgHHCKH3OZI3dq"
    api_audience = "https://api.car-platform.com"
    jwks_uri = f"https://{domain}/.well-known/jwks.json"
    
    print("[INFO] Using credentials:")
    print(f"   Domain: {domain}")
    print(f"   Client ID: {client_id[:20]}...")
    print(f"   Audience: {api_audience}")
    print()
    
    # Test CAR API token
    print("=" * 60)
    print("Testing CAR API Token Generation")
    print("=" * 60)
    
    token = get_token(domain, client_id, client_secret, api_audience)
    
    if not token:
        print("\n[ERROR] Failed to obtain token")
        print("\nPossible causes:")
        print("  1. CAR API resource doesn't exist in Auth0")
        print("  2. Client is not authorized for CAR API")
        print("  3. Client credentials are incorrect")
        print("\nTo fix:")
        print("  1. Create CAR API resource in Auth0 Dashboard")
        print("  2. Authorize this client for CAR API")
        print("  3. Grant required scopes")
        sys.exit(1)
    
    print(f"[SUCCESS] Token obtained: {token[:50]}...")
    
    # Inspect token
    print("\n" + "=" * 60)
    print("Token Inspection")
    print("=" * 60)
    inspect_token(token)
    
    # Verify token
    print("\n" + "=" * 60)
    print("Token Verification with JWKS")
    print("=" * 60)
    
    payload = decode_jwt_token(token, jwks_uri, api_audience)
    
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
                scopes = value.split() if isinstance(value, str) else value
                print(f"   {key}: {', '.join(scopes)}")
            elif key == "aud":
                print(f"   {key}: {value}")
            elif key == "iss":
                print(f"   {key}: {value}")
            else:
                print(f"   {key}: {value}")
        
        print("\n" + "=" * 60)
        print("[SUCCESS] JWT Generation and Validation Complete!")
        print("=" * 60)
        print("\n[INFO] Summary:")
        print("  ✓ Token generated successfully")
        print("  ✓ Token structure is valid")
        print("  ✓ Token signature verified with JWKS")
        print("  ✓ Token audience matches API identifier")
        print("  ✓ RS256 algorithm confirmed")
        
        if "scope" in payload:
            scopes = payload["scope"].split() if isinstance(payload["scope"], str) else payload["scope"]
            print(f"  ✓ Scopes: {', '.join(scopes)}")
    else:
        print("\n[ERROR] Token verification failed")
        sys.exit(1)


if __name__ == "__main__":
    main()
