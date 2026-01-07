"""Test JWT claims extraction and validation."""
import os
import sys
from typing import Dict, Any, Optional

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from jose import jwt
    import httpx
except ImportError:
    print("[ERROR] Required packages not installed. Install with:")
    print("  pip install python-jose[cryptography] httpx")
    sys.exit(1)


def fetch_jwks(jwks_uri: str) -> Dict[str, Any]:
    """Fetch JWKS from Auth0."""
    try:
        response = httpx.get(jwks_uri, timeout=10.0)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"[ERROR] Failed to fetch JWKS: {e}")
        return {}


def get_jwt_key(jwks: Dict[str, Any], kid: str) -> Optional[Dict[str, Any]]:
    """Find key by kid in JWKS."""
    for key in jwks.get("keys", []):
        if key.get("kid") == kid:
            return key
    return None


def decode_jwt_token(token: str, jwks_uri: str, audience: str) -> Dict[str, Any]:
    """Decode and verify JWT token."""
    from jose import jwk
    
    try:
        # Get unverified header
        unverified_header = jwt.get_unverified_header(token)
        kid = unverified_header.get("kid")
        
        if not kid:
            print("[ERROR] Token header missing 'kid'")
            return {}
        
        # Fetch JWKS
        print(f"[INFO] Fetching JWKS from: {jwks_uri}")
        jwks = fetch_jwks(jwks_uri)
        
        if not jwks:
            print("[ERROR] Failed to fetch JWKS")
            return {}
        
        # Find key
        key = get_jwt_key(jwks, kid)
        if not key:
            print(f"[ERROR] Key with kid '{kid}' not found")
            return {}
        
        # Construct public key
        public_key = jwk.construct(key)
        
        # Decode token
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


def get_token(
    domain: str,
    client_id: str,
    client_secret: str,
    audience: str,
    username: Optional[str] = None,
    password: Optional[str] = None
) -> Optional[str]:
    """Get JWT token from Auth0."""
    token_url = f"https://{domain}/oauth/token"
    
    # Use password grant if credentials provided, otherwise client credentials
    if username and password:
        payload = {
            "client_id": client_id,
            "client_secret": client_secret,
            "audience": audience,
            "grant_type": "password",
            "username": username,
            "password": password
        }
    else:
        payload = {
            "client_id": client_id,
            "client_secret": client_secret,
            "audience": audience,
            "grant_type": "client_credentials"
        }
    
    try:
        response = httpx.post(token_url, json=payload, timeout=10.0)
        response.raise_for_status()
        token_data = response.json()
        return token_data.get("access_token")
    except Exception as e:
        print(f"[ERROR] Failed to get token: {e}")
        if hasattr(e, 'response') and e.response:
            print(f"[ERROR] Response: {e.response.text[:500]}")
        return None


def test_jwt_claims() -> None:
    """Test JWT claims extraction."""
    print("=" * 70)
    print("JWT Claims Verification Test")
    print("=" * 70)
    print()
    
    # Get configuration from environment
    domain = os.getenv("AUTH0_DOMAIN")
    client_id = os.getenv("AUTH0_CLIENT_ID")
    client_secret = os.getenv("AUTH0_CLIENT_SECRET")
    audience = os.getenv("AUTH0_API_IDENTIFIER", "https://api.car-platform.com")
    
    if not domain or not client_id or not client_secret:
        print("[ERROR] Missing required environment variables:")
        print("  - AUTH0_DOMAIN")
        print("  - AUTH0_CLIENT_ID")
        print("  - AUTH0_CLIENT_SECRET")
        print()
        print("Optional:")
        print("  - AUTH0_API_IDENTIFIER (defaults to https://api.car-platform.com)")
        print()
        print("For user login (to test custom claims):")
        print("  - AUTH0_USERNAME")
        print("  - AUTH0_PASSWORD")
        return
    
    jwks_uri = f"https://{domain}/.well-known/jwks.json"
    
    # Get token
    print("[TEST 1] Getting JWT token...")
    username = os.getenv("AUTH0_USERNAME")
    password = os.getenv("AUTH0_PASSWORD")
    
    token = get_token(domain, client_id, client_secret, audience, username, password)
    
    if not token:
        print("[ERROR] Failed to get token")
        return
    
    print("[SUCCESS] Token obtained")
    print()
    
    # Decode token
    print("[TEST 2] Decoding and verifying token...")
    payload = decode_jwt_token(token, jwks_uri, audience)
    
    if not payload:
        print("[ERROR] Failed to decode token")
        return
    
    print("[SUCCESS] Token decoded and verified")
    print()
    
    # Check claims
    print("[TEST 3] Checking custom claims...")
    print()
    
    tenant_id_claim = "https://car.platform/tenant_id"
    roles_claim = "https://car.platform/roles"
    
    tenant_id = payload.get(tenant_id_claim)
    roles = payload.get(roles_claim, [])
    
    # Standard claims
    user_id = payload.get("sub")
    email = payload.get("email")
    exp = payload.get("exp")
    iat = payload.get("iat")
    
    print("Token Claims:")
    print(f"  User ID (sub): {user_id}")
    print(f"  Email: {email}")
    print(f"  Issued At (iat): {iat}")
    print(f"  Expires At (exp): {exp}")
    if exp and iat:
        duration = exp - iat
        print(f"  Duration: {duration} seconds ({duration // 60} minutes)")
    print()
    
    print("Custom Claims:")
    print(f"  {tenant_id_claim}: {tenant_id}")
    print(f"  {roles_claim}: {roles}")
    print()
    
    # Validation
    print("[TEST 4] Validating claims...")
    print()
    
    all_passed = True
    
    if tenant_id:
        print(f"[SUCCESS] tenant_id claim present: {tenant_id}")
    else:
        print("[WARNING] tenant_id claim missing")
        print("         User may not have app_metadata.tenant_id set")
        all_passed = False
    
    if isinstance(roles, list):
        print(f"[SUCCESS] roles claim is array: {roles}")
        if roles:
            print(f"         User has {len(roles)} role(s): {', '.join(roles)}")
        else:
            print("         User has no roles (empty array)")
    else:
        print(f"[ERROR] roles claim is not an array: {type(roles)}")
        all_passed = False
    
    # Check token expiration (should be 1 hour = 3600 seconds)
    if exp and iat:
        duration = exp - iat
        if duration == 3600:
            print(f"[SUCCESS] Token expiration is 1 hour ({duration} seconds)")
        else:
            print(f"[WARNING] Token expiration is {duration} seconds, expected 3600 (1 hour)")
    
    print()
    print("=" * 70)
    if all_passed:
        print("[RESULT] All tests PASSED")
    else:
        print("[RESULT] Some tests FAILED - check warnings above")
    print("=" * 70)


if __name__ == "__main__":
    test_jwt_claims()
