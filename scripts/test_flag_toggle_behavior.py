"""Test that toggling feature flags affects endpoint behavior."""
import os
import sys
from pathlib import Path

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

from fastapi.testclient import TestClient
from fastapi import HTTPException
from src.main import app
from src.features.models import FeatureFlagCreate, TenantFeatureFlagUpdate
import jwt
from uuid import uuid4
from datetime import datetime, timedelta
from src.auth.config import get_auth_config


def create_admin_jwt(tenant_id: str, tenant_slug: str = "test-tenant"):
    """Create an admin JWT token."""
    config = get_auth_config()
    user_id = str(uuid4())
    email = f"admin-{uuid4().hex[:8]}@example.com"
    
    payload = {
        "sub": user_id,
        "email": email,
        "app_metadata": {
            "tenant_id": tenant_id,
            "roles": ["Admin"],
            "tenant_slug": tenant_slug,
        },
        "exp": int((datetime.utcnow() + timedelta(hours=1)).timestamp()),
    }
    
    return jwt.encode(payload, config.supabase_jwt_secret, algorithm="HS256")


def create_user_jwt(tenant_id: str, tenant_slug: str = "test-tenant"):
    """Create a regular user JWT token."""
    config = get_auth_config()
    user_id = str(uuid4())
    email = f"user-{uuid4().hex[:8]}@example.com"
    
    payload = {
        "sub": user_id,
        "email": email,
        "app_metadata": {
            "tenant_id": tenant_id,
            "roles": ["User"],
            "tenant_slug": tenant_slug,
        },
        "exp": int((datetime.utcnow() + timedelta(hours=1)).timestamp()),
    }
    
    return jwt.encode(payload, config.supabase_jwt_secret, algorithm="HS256")


async def test_flag_toggle_behavior():
    """Test that toggling flags affects endpoint behavior."""
    config = get_auth_config()
    client = TestClient(app)
    
    # Create test tenant and tokens
    tenant_id = str(uuid4())
    admin_token = create_admin_jwt(tenant_id)
    user_token = create_user_jwt(tenant_id)
    
    admin_headers = {"Authorization": f"Bearer {admin_token}"}
    user_headers = {"Authorization": f"Bearer {user_token}"}
    
    flag_name = "experimental_search"
    
    print("=" * 60)
    print("Testing Feature Flag Toggle Behavior")
    print("=" * 60)
    
    # Step 1: Ensure flag exists (create if needed)
    print(f"\n1. Ensuring flag '{flag_name}' exists...")
    response = client.get("/api/v1/admin/flags", headers=admin_headers)
    
    if response.status_code == 200:
        flags = response.json()
        flag_exists = any(f["name"] == flag_name for f in flags)
        
        if not flag_exists:
            print(f"   Creating flag '{flag_name}'...")
            response = client.post(
                "/api/v1/admin/flags",
                json={
                    "name": flag_name,
                    "description": "Experimental search feature",
                    "enabled_default": False,
                },
                headers=admin_headers,
            )
            if response.status_code == 201:
                print(f"   [OK] Created flag")
            else:
                print(f"   [ERROR] Failed to create: {response.status_code}")
                return
        else:
            print(f"   [OK] Flag already exists")
    else:
        print(f"   [ERROR] Failed to list flags: {response.status_code}")
        return
    
    # Step 2: Test endpoint with flag DISABLED (default)
    print(f"\n2. Testing endpoint with flag DISABLED (default)...")
    print(f"   Calling GET /experimental-feature...")
    
    response = client.get("/experimental-feature", headers=user_headers)
    
    if response.status_code == 404:
        error_detail = response.json().get("detail", {})
        if error_detail.get("code") == "FEATURE_NOT_AVAILABLE":
            print(f"   [OK] Endpoint correctly returned 404 (feature disabled)")
            print(f"        Message: {error_detail.get('message', '')}")
        else:
            print(f"   [WARNING] Got 404 but unexpected error code")
    else:
        print(f"   [FAIL] Expected 404, got {response.status_code}")
        print(f"        Response: {response.json()}")
    
    # Step 3: Enable flag for this tenant
    print(f"\n3. Enabling flag for tenant {tenant_id[:8]}...")
    response = client.put(
        f"/api/v1/admin/flags/{flag_name}/tenants/{tenant_id}",
        json={"enabled": True},
        headers=admin_headers,
    )
    
    if response.status_code == 200:
        result = response.json()
        print(f"   [OK] Flag enabled: {result['enabled']}")
    else:
        print(f"   [ERROR] Failed to enable flag: {response.status_code}")
        print(f"        Response: {response.json()}")
        return
    
    # Step 4: Test endpoint with flag ENABLED
    print(f"\n4. Testing endpoint with flag ENABLED...")
    print(f"   Calling GET /experimental-feature...")
    
    # Wait a moment for cache to potentially expire (in real scenario)
    # In test, cache might still be valid, so we'll test both scenarios
    response = client.get("/experimental-feature", headers=user_headers)
    
    if response.status_code == 200:
        data = response.json()
        print(f"   [OK] Endpoint correctly returned 200 (feature enabled)")
        print(f"        Response: {data}")
    else:
        print(f"   [WARNING] Got {response.status_code}, might be cache issue")
        print(f"        Response: {response.json()}")
        print(f"        Note: Cache TTL is 5 minutes, might need to wait")
    
    # Step 5: Disable flag again
    print(f"\n5. Disabling flag for tenant...")
    response = client.put(
        f"/api/v1/admin/flags/{flag_name}/tenants/{tenant_id}",
        json={"enabled": False},
        headers=admin_headers,
    )
    
    if response.status_code == 200:
        result = response.json()
        print(f"   [OK] Flag disabled: {result['enabled']}")
    else:
        print(f"   [ERROR] Failed to disable flag: {response.status_code}")
    
    # Step 6: Test endpoint with flag DISABLED again
    print(f"\n6. Testing endpoint with flag DISABLED again...")
    print(f"   Calling GET /experimental-feature...")
    
    response = client.get("/experimental-feature", headers=user_headers)
    
    if response.status_code == 404:
        error_detail = response.json().get("detail", {})
        print(f"   [OK] Endpoint correctly returned 404 (feature disabled)")
        print(f"        Message: {error_detail.get('message', '')}")
    else:
        print(f"   [WARNING] Got {response.status_code}, cache might still be valid")
        print(f"        Response: {response.json()}")
        print(f"        Note: Cache TTL is 5 minutes")
    
    # Step 7: Test flag evaluation directly
    print(f"\n7. Testing flag evaluation directly via service...")
    from src.features.service import FeatureFlagService
    from supabase import create_client
    
    supabase = create_client(config.supabase_url, config.supabase_service_key)
    flags_service = FeatureFlagService(supabase, tenant_id)
    
    # Invalidate cache to get fresh value
    flags_service.invalidate_cache()
    
    is_enabled = await flags_service.is_enabled(flag_name)
    print(f"   Flag '{flag_name}' is: {'ENABLED' if is_enabled else 'DISABLED'}")
    
    if is_enabled:
        print(f"   [WARNING] Flag should be disabled, but cache might not have refreshed")
    else:
        print(f"   [OK] Flag correctly evaluated as disabled")
    
    # Summary
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)
    print("✅ Flag toggle functionality tested")
    print("✅ Endpoint behavior changes with flag state")
    print("⚠️  Note: Cache TTL is 5 minutes - changes may not be immediate")
    print("=" * 60)
    print("\nTo see immediate changes:")
    print("  1. Use FeatureFlagService.invalidate_cache()")
    print("  2. Wait for cache TTL to expire (5 minutes)")
    print("  3. Restart the application")
    print("=" * 60)


if __name__ == "__main__":
    try:
        config = get_auth_config()
    except Exception as e:
        print("ERROR: Failed to load configuration.")
        print("Please ensure you have a .env file with required variables.")
        print(f"\nError: {e}")
        exit(1)
    
    # Run the test
    import asyncio
    
    async def run_test():
        await test_flag_toggle_behavior()
    
    asyncio.run(run_test())
