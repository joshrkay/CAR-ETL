"""Test feature flags via FastAPI endpoints."""
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
from supabase import create_client
from src.auth.config import get_auth_config
from src.main import app
from src.features.models import FeatureFlagCreate, TenantFeatureFlagUpdate
import jwt
from uuid import uuid4
from datetime import datetime, timedelta


def create_test_jwt(user_id: str, email: str, tenant_id: str, roles: list[str], tenant_slug: str = None):
    """Create a test JWT token with custom claims."""
    config = get_auth_config()
    
    now = datetime.utcnow()
    exp = now + timedelta(hours=1)
    
    payload = {
        "sub": user_id,
        "email": email,
        "app_metadata": {
            "tenant_id": tenant_id,
            "roles": roles,
        },
        "exp": int(exp.timestamp()),
    }
    
    if tenant_slug:
        payload["app_metadata"]["tenant_slug"] = tenant_slug
    
    # Create HS256 token for testing
    token = jwt.encode(payload, config.supabase_jwt_secret, algorithm="HS256")
    return token


def test_feature_flags_api():
    """Test feature flags via API endpoints."""
    config = get_auth_config()
    client = TestClient(app)
    
    print("=" * 60)
    print("Testing Feature Flags API")
    print("=" * 60)
    
    # Create test user and tenant
    test_user_id = str(uuid4())
    test_tenant_id = str(uuid4())
    test_email = f"admin-{uuid4().hex[:8]}@example.com"
    
    # Create admin token
    admin_token = create_test_jwt(
        test_user_id,
        test_email,
        test_tenant_id,
        ["Admin"],
        "test-tenant"
    )
    
    headers = {"Authorization": f"Bearer {admin_token}"}
    
    # Test 1: List all flags (should be empty initially)
    print("\n1. Listing all flags (admin)...")
    response = client.get("/api/v1/admin/flags", headers=headers)
    print(f"   Status: {response.status_code}")
    if response.status_code == 200:
        flags = response.json()
        print(f"   Found {len(flags)} flags")
    
    # Test 2: Create a feature flag
    print("\n2. Creating feature flag 'experimental_search'...")
    flag_data = FeatureFlagCreate(
        name="experimental_search",
        description="New experimental search algorithm",
        enabled_default=False,
    )
    response = client.post(
        "/api/v1/admin/flags",
        json=flag_data.model_dump(),
        headers=headers,
    )
    print(f"   Status: {response.status_code}")
    if response.status_code == 201:
        flag = response.json()
        print(f"   Created: {flag['name']} (ID: {flag['id']})")
        print(f"   Default: {'Enabled' if flag['enabled_default'] else 'Disabled'}")
    
    # Test 3: Create another flag
    print("\n3. Creating feature flag 'advanced_analytics'...")
    flag_data = FeatureFlagCreate(
        name="advanced_analytics",
        description="Advanced analytics dashboard",
        enabled_default=True,
    )
    response = client.post(
        "/api/v1/admin/flags",
        json=flag_data.model_dump(),
        headers=headers,
    )
    print(f"   Status: {response.status_code}")
    if response.status_code == 201:
        flag = response.json()
        print(f"   Created: {flag['name']} (ID: {flag['id']})")
    
    # Test 4: List all flags again
    print("\n4. Listing all flags again...")
    response = client.get("/api/v1/admin/flags", headers=headers)
    if response.status_code == 200:
        flags = response.json()
        print(f"   Found {len(flags)} flags:")
        for flag in flags:
            status = "✓" if flag.get("enabled_default") else "✗"
            print(f"     {status} {flag['name']}: {flag.get('description', '')}")
    
    # Test 5: Set tenant override
    print("\n5. Setting tenant override for 'experimental_search'...")
    override_data = TenantFeatureFlagUpdate(enabled=True)
    response = client.put(
        f"/api/v1/admin/flags/experimental_search/tenants/{test_tenant_id}",
        json=override_data.model_dump(),
        headers=headers,
    )
    print(f"   Status: {response.status_code}")
    if response.status_code == 200:
        result = response.json()
        print(f"   Override set: {result['enabled']}")
    
    # Test 6: Get flag details (as regular user)
    print("\n6. Getting flag details (as regular user)...")
    user_token = create_test_jwt(
        str(uuid4()),
        "user@example.com",
        test_tenant_id,
        ["User"],
        "test-tenant"
    )
    user_headers = {"Authorization": f"Bearer {user_token}"}
    
    response = client.get(
        "/api/v1/admin/flags/experimental_search",
        headers=user_headers,
    )
    print(f"   Status: {response.status_code}")
    if response.status_code == 200:
        flag_details = response.json()
        print(f"   Flag: {flag_details['name']}")
        print(f"   Enabled: {flag_details['enabled']}")
        print(f"   Is Override: {flag_details['is_override']}")
    
    # Test 7: Try to create flag as non-admin (should fail)
    print("\n7. Attempting to create flag as non-admin (should fail)...")
    response = client.post(
        "/api/v1/admin/flags",
        json={
            "name": "unauthorized_flag",
            "description": "Should not be created",
            "enabled_default": False,
        },
        headers=user_headers,
    )
    print(f"   Status: {response.status_code}")
    if response.status_code == 403:
        print("   [OK] Correctly rejected non-admin request")
    
    print("\n" + "=" * 60)
    print("API Tests Complete!")
    print("=" * 60)


if __name__ == "__main__":
    try:
        config = get_auth_config()
    except Exception as e:
        print("ERROR: Failed to load configuration.")
        print("Please ensure you have a .env file with required variables.")
        print(f"\nError: {e}")
        exit(1)
    
    test_feature_flags_api()
