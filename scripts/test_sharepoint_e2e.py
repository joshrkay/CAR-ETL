"""
End-to-End Test Script for SharePoint Connector

This script tests the SharePoint connector with a real server instance.
Requires:
- Running FastAPI server (uvicorn src.main:app --reload)
- Valid Azure AD credentials in .env
- Database migration 025_connectors.sql applied
"""
import os
import sys
from pathlib import Path
import asyncio
from uuid import uuid4

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Load environment variables
try:
    from dotenv import load_dotenv
    env_path = project_root / ".env"
    if env_path.exists():
        load_dotenv(env_path)
    else:
        load_dotenv()
except ImportError:
    pass

import httpx
import jwt
from datetime import datetime, timedelta
from supabase import create_client, Client
from src.auth.config import get_auth_config


def create_test_jwt(tenant_id: str, user_id: str, config) -> str:
    """Create a test JWT token."""
    payload = {
        "sub": user_id,
        "email": "test@example.com",
        "app_metadata": {
            "tenant_id": tenant_id,
            "roles": ["Analyst"],
            "tenant_slug": "test-tenant",
        },
        "exp": int((datetime.utcnow() + timedelta(hours=1)).timestamp()),
    }
    return jwt.encode(payload, config.supabase_jwt_secret, algorithm="HS256")


async def test_sharepoint_e2e_async():
    """Run end-to-end test of SharePoint connector (async)."""
    config = get_auth_config()
    base_url = os.getenv("API_BASE_URL", "http://localhost:8000")
    
    # Create JWT token
    tenant_id = str(uuid4())
    user_id = str(uuid4())
    token = create_test_jwt(tenant_id, user_id, config)
    headers = {"Authorization": f"Bearer {token}"}
    
    # Test 1: Start OAuth flow
    print("\n2. Testing OAuth flow initiation...")
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{base_url}/api/v1/connectors/sharepoint/auth",
                headers=headers,
                timeout=10.0,
            )
            
            if response.status_code == 200:
                data = response.json()
                print(f"   [OK] OAuth URL generated")
                print(f"   State: {data.get('state', 'N/A')[:20]}...")
                print(f"   URL: {data.get('authorization_url', 'N/A')[:80]}...")
            else:
                print(f"   [ERROR] Failed: {response.status_code}")
                print(f"   Response: {response.text}")
                return False
    except Exception as e:
        print(f"   [ERROR] Error: {e}")
        return False
    
    # Test 2: Check connector was created
    print("\n3. Verifying connector creation...")
    try:
        result = supabase.table("connectors").select("*").eq(
            "tenant_id", tenant_id
        ).eq("type", "sharepoint").execute()
        
        if result.data:
            print(f"   [OK] Connector exists: {result.data[0]['id']}")
        else:
            print("   ⚠️  Connector not found (may be created on first OAuth call)")
    except Exception as e:
        print(f"   ⚠️  Error checking connector: {e}")
    
    # Test 3: Test encryption
    print("\n4. Testing encryption...")
    try:
        from src.utils.encryption import encrypt_value, decrypt_value
        
        test_token = "test-access-token-12345"
        encrypted = encrypt_value(test_token)
        decrypted = decrypt_value(encrypted)
        
        if decrypted == test_token:
            print("   [OK] Encryption/decryption working")
        else:
            print("   [ERROR] Encryption/decryption failed")
            return False
    except Exception as e:
        print(f"   [ERROR] Encryption test failed: {e}")
        return False
    
    # Test 4: Test public callback endpoint (without valid state)
    print("\n5. Testing public callback endpoint...")
    try:
        async with httpx.AsyncClient() as async_client:
            response = await async_client.get(
                f"{base_url}/oauth/microsoft/callback",
                params={"code": "test-code", "state": "invalid-state"},
                timeout=10.0,
            )
            
            if response.status_code == 400:
                print("   [OK] Public endpoint accessible (rejects invalid state)")
            else:
                print(f"   ⚠️  Unexpected status: {response.status_code}")
    except Exception as e:
        print(f"   ⚠️  Error: {e}")
    
    print("\n" + "=" * 60)
    print("[OK] Basic tests completed")
    print("=" * 60)
    print("\nNote: Full OAuth flow requires:")
    print("  1. User to visit authorization URL")
    print("  2. Complete Microsoft OAuth")
    print("  3. Callback with valid code")
    print("\nTo test full flow:")
    print("  1. Call POST /api/v1/connectors/sharepoint/auth")
    print("  2. Visit the returned authorization_url")
    print("  3. Complete OAuth in browser")
    print("  4. Callback will be handled automatically")
    
    return True


def test_sharepoint_e2e():
    """Run end-to-end test of SharePoint connector."""
    print("=" * 60)
    print("SharePoint Connector End-to-End Test")
    print("=" * 60)
    
    # Check environment variables
    required_vars = [
        "SHAREPOINT_CLIENT_ID",
        "SHAREPOINT_CLIENT_SECRET",
        "SHAREPOINT_REDIRECT_URI",
        "SUPABASE_URL",
        "SUPABASE_SERVICE_KEY",
        "SUPABASE_JWT_SECRET",
    ]
    
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    if missing_vars:
        print(f"\n[ERROR] Missing required environment variables: {', '.join(missing_vars)}")
        print("Please set these in your .env file.")
        return False
    
    # Create test tenant and user
    print("\n1. Setting up test tenant...")
    config = get_auth_config()
    supabase: Client = create_client(
        config.supabase_url,
        config.supabase_service_key,
    )
    
    tenant_id = str(uuid4())
    user_id = str(uuid4())
    
    try:
        tenant_result = supabase.table("tenants").insert({
            "id": tenant_id,
            "slug": f"test-tenant-{tenant_id[:8]}",
            "name": "Test Tenant",
        }).execute()
        print(f"   [OK] Created tenant: {tenant_id}")
    except Exception as e:
        print(f"   ⚠️  Tenant creation: {e}")
        print("   (May already exist)")
    
    # Run async tests
    success = asyncio.run(test_sharepoint_e2e_async())
    return success


if __name__ == "__main__":
    success = test_sharepoint_e2e()
    sys.exit(0 if success else 1)
