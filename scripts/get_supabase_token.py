"""Get a Supabase JWT token for testing."""
import sys
import os
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import httpx
from typing import Optional, Dict, Any

def get_supabase_token(
    supabase_url: str,
    email: str,
    password: str,
    api_key: Optional[str] = None
) -> Optional[str]:
    """Get a JWT token from Supabase Auth.
    
    Args:
        supabase_url: Supabase project URL (e.g., https://qifioafprrtkoiyylsqa.supabase.co)
        email: User email
        password: User password
        api_key: Supabase anon key (optional, will try to get from env)
    
    Returns:
        JWT token string or None if failed.
    """
    if not api_key:
        api_key = os.getenv("SUPABASE_ANON_KEY")
        if not api_key:
            print("[ERROR] SUPABASE_ANON_KEY not set")
            print("Get it from: Supabase Dashboard > Settings > API > anon/public key")
            return None
    
    auth_url = f"{supabase_url}/auth/v1/token?grant_type=password"
    
    headers = {
        "apikey": api_key,
        "Content-Type": "application/json"
    }
    
    payload = {
        "email": email,
        "password": password
    }
    
    try:
        print(f"Requesting token from: {auth_url}")
        response = httpx.post(auth_url, json=payload, headers=headers, timeout=10.0)
        response.raise_for_status()
        
        data = response.json()
        token = data.get("access_token")
        
        if token:
            print(f"[OK] Token obtained successfully")
            print(f"Token (first 50 chars): {token[:50]}...")
            return token
        else:
            print(f"[ERROR] No access_token in response")
            print(f"Response: {data}")
            return None
            
    except httpx.HTTPStatusError as e:
        print(f"[ERROR] HTTP error: {e.response.status_code}")
        print(f"Response: {e.response.text[:500]}")
        return None
    except Exception as e:
        print(f"[ERROR] Failed to get token: {e}")
        import traceback
        traceback.print_exc()
        return None


def get_service_role_token(
    supabase_url: str,
    service_role_key: str
) -> Optional[str]:
    """Get a service role JWT token from Supabase.
    
    This uses the service role key to create a token with admin privileges.
    
    Args:
        supabase_url: Supabase project URL
        service_role_key: Supabase service role key
    
    Returns:
        JWT token string or None if failed.
    """
    # Service role tokens are typically created by signing a JWT with the service role key
    # For testing, we can use the service role key directly or create a token
    # Note: In production, you should use proper JWT signing
    
    print("[INFO] Service role tokens should be created using proper JWT signing")
    print("[INFO] For testing, you can use the Supabase client library")
    print("[INFO] Or create a user and sign in to get a user token")
    
    return None


def decode_token_parts(token: str) -> Dict[str, Any]:
    """Decode JWT token parts without verification (for inspection).
    
    Args:
        token: JWT token string
    
    Returns:
        Dictionary with header and payload.
    """
    import base64
    import json
    
    try:
        parts = token.split(".")
        if len(parts) != 3:
            return {"error": "Invalid JWT format"}
        
        # Decode header
        header_padded = parts[0] + "=" * (4 - len(parts[0]) % 4)
        header_json = base64.urlsafe_b64decode(header_padded)
        header = json.loads(header_json)
        
        # Decode payload
        payload_padded = parts[1] + "=" * (4 - len(parts[1]) % 4)
        payload_json = base64.urlsafe_b64decode(payload_padded)
        payload = json.loads(payload_json)
        
        return {
            "header": header,
            "payload": payload
        }
    except Exception as e:
        return {"error": str(e)}


def main():
    """Main function."""
    import sys
    
    print("=" * 70)
    print("Supabase JWT Token Getter")
    print("=" * 70)
    print()
    
    supabase_url = os.getenv("SUPABASE_URL", "https://qifioafprrtkoiyylsqa.supabase.co")
    api_key = os.getenv("SUPABASE_ANON_KEY")
    
    print(f"Supabase URL: {supabase_url}")
    print(f"API Key: {'Set' if api_key else 'NOT SET'}")
    print()
    
    if len(sys.argv) < 3:
        print("Usage:")
        print("  python scripts/get_supabase_token.py <email> <password>")
        print()
        print("Or set environment variables:")
        print("  SUPABASE_URL=https://qifioafprrtkoiyylsqa.supabase.co")
        print("  SUPABASE_ANON_KEY=your-anon-key")
        print()
        print("To get your anon key:")
        print("  1. Go to Supabase Dashboard")
        print("  2. Settings > API")
        print("  3. Copy the 'anon' or 'public' key")
        return
    
    email = sys.argv[1]
    password = sys.argv[2]
    
    print(f"Attempting to sign in as: {email}")
    print()
    
    token = get_supabase_token(supabase_url, email, password, api_key)
    
    if token:
        print()
        print("=" * 70)
        print("Token Obtained Successfully!")
        print("=" * 70)
        print()
        
        # Decode token for inspection
        decoded = decode_token_parts(token)
        if "error" not in decoded:
            print("Token Header:")
            import json
            print(json.dumps(decoded["header"], indent=2))
            print()
            print("Token Payload:")
            print(json.dumps(decoded["payload"], indent=2))
            print()
            
            # Check for custom claims
            payload = decoded["payload"]
            tenant_id = payload.get("https://car.platform/tenant_id")
            roles = payload.get("https://car.platform/roles", [])
            
            print("Custom Claims:")
            print(f"  Tenant ID: {tenant_id or 'NOT SET'}")
            print(f"  Roles: {roles or 'NOT SET'}")
            print()
        
        print("=" * 70)
        print("To test validation, run:")
        print(f"  python scripts/test_supabase_jwt_validation.py {token}")
        print("=" * 70)
        print()
        print("Or save the token:")
        print(f"  $env:TEST_TOKEN = '{token}'")
    else:
        print()
        print("=" * 70)
        print("Failed to get token")
        print("=" * 70)
        print()
        print("Troubleshooting:")
        print("  1. Verify email and password are correct")
        print("  2. Check SUPABASE_ANON_KEY is set correctly")
        print("  3. Verify user exists in Supabase Auth")
        print("  4. Check Supabase project URL is correct")


if __name__ == "__main__":
    main()
