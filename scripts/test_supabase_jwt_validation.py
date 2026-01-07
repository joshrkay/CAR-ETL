"""Test Supabase JWT validation."""
import sys
import os
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import httpx
from typing import Optional, Dict, Any

def test_jwks_fetch(jwks_uri: str) -> bool:
    """Test fetching JWKS from Supabase.
    
    Args:
        jwks_uri: JWKS URI endpoint.
    
    Returns:
        True if successful, False otherwise.
    """
    print(f"Testing JWKS fetch from: {jwks_uri}")
    print("-" * 70)
    
    try:
        response = httpx.get(jwks_uri, timeout=10.0)
        response.raise_for_status()
        jwks = response.json()
        
        print(f"[OK] JWKS fetched successfully")
        print(f"     Keys found: {len(jwks.get('keys', []))}")
        
        for i, key in enumerate(jwks.get('keys', []), 1):
            print(f"\n     Key {i}:")
            print(f"       Algorithm: {key.get('alg')}")
            print(f"       Key Type: {key.get('kty')}")
            print(f"       Key ID: {key.get('kid')}")
            if key.get('kty') == 'EC':
                print(f"       Curve: {key.get('crv')}")
        
        return True
    except httpx.RequestError as e:
        print(f"[ERROR] Failed to fetch JWKS: {e}")
        return False
    except Exception as e:
        print(f"[ERROR] Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_jwt_validator_config() -> bool:
    """Test JWT validator configuration.
    
    Returns:
        True if configuration is valid, False otherwise.
    """
    print("\n" + "=" * 70)
    print("Testing JWT Validator Configuration")
    print("=" * 70)
    
    try:
        from src.auth.config import Auth0Config, get_auth0_config
        
        print("\n1. Loading configuration...")
        config = get_auth0_config()
        
        print(f"   [OK] Configuration loaded")
        print(f"   Domain: {config.domain}")
        print(f"   Algorithm: {config.algorithm}")
        print(f"   JWKS URI: {config.jwks_uri}")
        print(f"   API Identifier: {config.api_identifier}")
        
        # Validate algorithm
        if config.algorithm not in ["RS256", "ES256"]:
            print(f"   [ERROR] Unsupported algorithm: {config.algorithm}")
            return False
        
        if config.algorithm == "ES256":
            print(f"   [OK] Using ES256 (Supabase/Elliptic Curve)")
        else:
            print(f"   [OK] Using RS256 (Auth0/RSA)")
        
        # Validate JWKS URI
        if not config.jwks_uri:
            print(f"   [ERROR] JWKS URI not set")
            return False
        
        if "supabase.co" in config.jwks_uri:
            print(f"   [OK] JWKS URI points to Supabase")
        elif "auth0.com" in config.jwks_uri or "auth0" in config.domain:
            print(f"   [OK] JWKS URI points to Auth0")
        else:
            print(f"   [WARN] JWKS URI format not recognized")
        
        return True
        
    except Exception as e:
        print(f"[ERROR] Configuration error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_jwt_validation(token: Optional[str] = None) -> bool:
    """Test JWT token validation.
    
    Args:
        token: JWT token to validate. If not provided, shows instructions.
    
    Returns:
        True if validation successful, False otherwise.
    """
    print("\n" + "=" * 70)
    print("Testing JWT Token Validation")
    print("=" * 70)
    
    if not token:
        print("\n[INFO] No token provided. To test validation:")
        print("  1. Get a JWT token from Supabase")
        print("  2. Run: python scripts/test_supabase_jwt_validation.py <token>")
        print("\nTo get a Supabase token:")
        print("  - Use Supabase Auth API")
        print("  - Or use Supabase client library")
        print("  - Token should include custom claims:")
        print("    * https://car.platform/tenant_id")
        print("    * https://car.platform/roles")
        return False
    
    try:
        from src.auth.jwt_validator import JWTValidator, get_jwt_validator, JWTValidationError
        
        print(f"\n1. Initializing JWT validator...")
        validator = get_jwt_validator()
        print(f"   [OK] Validator initialized")
        
        print(f"\n2. Validating token...")
        print(f"   Token (first 50 chars): {token[:50]}...")
        
        try:
            claims = validator.extract_claims(token)
            print(f"   [OK] Token validated successfully")
            
            print(f"\n3. Extracted Claims:")
            print(f"   Tenant ID: {claims.tenant_id}")
            print(f"   User ID: {claims.user_id}")
            print(f"   Email: {claims.email}")
            print(f"   Roles: {claims.roles}")
            
            if claims.tenant_id:
                print(f"   [OK] Tenant ID found in claims")
            else:
                print(f"   [WARN] Tenant ID not found in claims")
            
            if claims.roles:
                print(f"   [OK] Roles found: {', '.join(claims.roles)}")
            else:
                print(f"   [WARN] No roles found in claims")
            
            return True
            
        except JWTValidationError as e:
            print(f"   [ERROR] Token validation failed: {e}")
            return False
        except Exception as e:
            print(f"   [ERROR] Unexpected error: {e}")
            import traceback
            traceback.print_exc()
            return False
            
    except Exception as e:
        print(f"[ERROR] Failed to initialize validator: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_jwks_key_construction() -> bool:
    """Test constructing signing key from JWKS.
    
    Returns:
        True if successful, False otherwise.
    """
    print("\n" + "=" * 70)
    print("Testing JWKS Key Construction")
    print("=" * 70)
    
    try:
        from src.auth.config import get_auth0_config
        from src.auth.jwt_validator import JWTValidator
        from jose import jwk
        
        config = get_auth0_config()
        validator = JWTValidator(config)
        
        print(f"\n1. Fetching JWKS...")
        jwks = validator._fetch_jwks()
        print(f"   [OK] JWKS fetched")
        
        print(f"\n2. Testing key construction...")
        keys = jwks.get("keys", [])
        
        if not keys:
            print(f"   [ERROR] No keys found in JWKS")
            return False
        
        for i, key_data in enumerate(keys, 1):
            print(f"\n   Key {i}:")
            print(f"     Algorithm: {key_data.get('alg')}")
            print(f"     Key Type: {key_data.get('kty')}")
            
            try:
                key = jwk.construct(key_data)
                print(f"     [OK] Key constructed successfully")
                print(f"     Key type: {type(key)}")
            except Exception as e:
                print(f"     [ERROR] Failed to construct key: {e}")
                return False
        
        return True
        
    except Exception as e:
        print(f"[ERROR] Key construction test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Main test function."""
    import sys
    
    print("=" * 70)
    print("Supabase JWT Validation Test")
    print("=" * 70)
    
    # Check environment variables
    print("\nChecking environment variables...")
    domain = os.getenv("AUTH0_DOMAIN", "NOT SET")
    algorithm = os.getenv("AUTH0_ALGORITHM", "NOT SET")
    jwks_uri = os.getenv("AUTH0_JWKS_URI", "NOT SET")
    
    print(f"  AUTH0_DOMAIN: {domain}")
    print(f"  AUTH0_ALGORITHM: {algorithm}")
    print(f"  AUTH0_JWKS_URI: {jwks_uri}")
    
    if domain == "NOT SET" or algorithm == "NOT SET":
        print("\n[WARN] Environment variables not set.")
        print("Set them before running tests:")
        print("  $env:AUTH0_DOMAIN = 'qifioafprrtkoiyylsqa.supabase.co'")
        print("  $env:AUTH0_ALGORITHM = 'ES256'")
        print("  $env:AUTH0_JWKS_URI = 'https://qifioafprrtkoiyylsqa.supabase.co/auth/v1/.well-known/jwks.json'")
        print()
    
    # Test JWKS fetch
    if jwks_uri != "NOT SET":
        test_jwks_fetch(jwks_uri)
    else:
        # Use default Supabase JWKS URI
        default_jwks = "https://qifioafprrtkoiyylsqa.supabase.co/auth/v1/.well-known/jwks.json"
        print(f"\n[INFO] Using default Supabase JWKS URI: {default_jwks}")
        test_jwks_fetch(default_jwks)
    
    # Test configuration
    test_jwt_validator_config()
    
    # Test key construction
    test_jwks_key_construction()
    
    # Test token validation if provided
    token = sys.argv[1] if len(sys.argv) > 1 else None
    test_jwt_validation(token)
    
    print("\n" + "=" * 70)
    print("Test Complete")
    print("=" * 70)


if __name__ == "__main__":
    main()
