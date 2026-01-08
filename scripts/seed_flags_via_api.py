"""Seed feature flags via admin API endpoints."""
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
from src.main import app
from src.features.models import FeatureFlagCreate, TenantFeatureFlagUpdate
import jwt
from uuid import uuid4
from datetime import datetime, timedelta
from src.auth.config import get_auth_config


def create_admin_jwt(tenant_id: str, tenant_slug: str = "seed-tenant"):
    """Create an admin JWT token for API requests."""
    config = get_auth_config()
    
    user_id = str(uuid4())
    email = f"admin-seed-{uuid4().hex[:8]}@example.com"
    
    now = datetime.utcnow()
    exp = now + timedelta(hours=1)
    
    payload = {
        "sub": user_id,
        "email": email,
        "app_metadata": {
            "tenant_id": tenant_id,
            "roles": ["Admin"],
            "tenant_slug": tenant_slug,
        },
        "exp": int(exp.timestamp()),
    }
    
    # Create HS256 token for testing
    token = jwt.encode(payload, config.supabase_jwt_secret, algorithm="HS256")
    return token


def seed_flags_via_api():
    """Seed feature flags via admin API endpoints."""
    config = get_auth_config()
    client = TestClient(app)
    
    # Create admin token
    tenant_id = str(uuid4())
    admin_token = create_admin_jwt(tenant_id)
    headers = {"Authorization": f"Bearer {admin_token}"}
    
    print("=" * 60)
    print("Seeding Feature Flags via Admin API")
    print("=" * 60)
    
    # Define seed flags
    seed_flags = [
        {
            "name": "experimental_search",
            "description": "New experimental search algorithm with improved relevance",
            "enabled_default": False,
        },
        {
            "name": "advanced_analytics",
            "description": "Advanced analytics dashboard with real-time metrics",
            "enabled_default": True,
        },
        {
            "name": "ai_summarization",
            "description": "AI-powered document summarization feature",
            "enabled_default": False,
        },
        {
            "name": "bulk_export",
            "description": "Bulk export functionality for large datasets",
            "enabled_default": True,
        },
        {
            "name": "dark_mode",
            "description": "Dark mode UI theme",
            "enabled_default": False,
        },
        {
            "name": "api_v2",
            "description": "New API v2 endpoints with improved performance",
            "enabled_default": False,
        },
    ]
    
    created_count = 0
    skipped_count = 0
    error_count = 0
    
    # First, list existing flags
    print("\n1. Checking existing flags...")
    response = client.get("/api/v1/admin/flags", headers=headers)
    existing_flags = set()
    
    if response.status_code == 200:
        flags = response.json()
        existing_flags = {flag["name"] for flag in flags}
        print(f"   Found {len(existing_flags)} existing flags")
    elif response.status_code == 401:
        print("   [ERROR] Authentication failed - check JWT secret")
        return
    else:
        print(f"   [WARNING] Unexpected status: {response.status_code}")
    
    # Create flags
    print("\n2. Creating feature flags...")
    for flag_data in seed_flags:
        flag_name = flag_data["name"]
        
        if flag_name in existing_flags:
            print(f"   [SKIP] Flag '{flag_name}' already exists")
            skipped_count += 1
            continue
        
        print(f"   Creating '{flag_name}'...")
        
        try:
            response = client.post(
                "/api/v1/admin/flags",
                json=flag_data,
                headers=headers,
            )
            
            if response.status_code == 201:
                flag = response.json()
                status = "Enabled" if flag.get("enabled_default") else "Disabled"
                print(f"     [OK] Created (ID: {flag['id'][:8]}..., Default: {status})")
                created_count += 1
            elif response.status_code == 409:
                print(f"     [SKIP] Flag already exists")
                skipped_count += 1
            elif response.status_code == 403:
                print(f"     [ERROR] Permission denied - not an admin")
                error_count += 1
            else:
                error_detail = response.json() if response.content else {}
                print(f"     [ERROR] Status {response.status_code}: {error_detail.get('detail', 'Unknown error')}")
                error_count += 1
                
        except Exception as e:
            print(f"     [ERROR] Exception: {e}")
            error_count += 1
    
    # List all flags
    print("\n3. Listing all flags...")
    response = client.get("/api/v1/admin/flags", headers=headers)
    
    if response.status_code == 200:
        flags = response.json()
        print(f"   Total flags: {len(flags)}")
        print("\n   Flags:")
        for flag in sorted(flags, key=lambda x: x["name"]):
            status = "✓ Enabled" if flag.get("enabled_default") else "✗ Disabled"
            print(f"     {status} {flag['name']}")
            if flag.get("description"):
                print(f"              {flag['description']}")
    else:
        print(f"   [ERROR] Failed to list flags: {response.status_code}")
    
    # Summary
    print("\n" + "=" * 60)
    print("Seed Summary")
    print("=" * 60)
    print(f"  Created:  {created_count}")
    print(f"  Skipped:  {skipped_count}")
    print(f"  Errors:   {error_count}")
    print("=" * 60)
    
    if created_count > 0 or skipped_count > 0:
        print("\n✅ Flags seeded successfully!")
        print("\nNext steps:")
        print("  1. Test flag evaluation in your endpoints")
        print("  2. Set tenant overrides: PUT /api/v1/admin/flags/{name}/tenants/{tenant_id}")
        print("  3. Check flag details: GET /api/v1/admin/flags/{name}")
    else:
        print("\n⚠️  No flags were created. Check errors above.")
    
    print("=" * 60)
    
    return {
        "created": created_count,
        "skipped": skipped_count,
        "errors": error_count,
    }


if __name__ == "__main__":
    try:
        config = get_auth_config()
    except Exception as e:
        print("ERROR: Failed to load configuration.")
        print("Please ensure you have a .env file with:")
        print("  SUPABASE_URL=...")
        print("  SUPABASE_ANON_KEY=...")
        print("  SUPABASE_SERVICE_KEY=...")
        print("  SUPABASE_JWT_SECRET=...")
        print(f"\nError: {e}")
        exit(1)
    
    if not all([
        config.supabase_url,
        config.supabase_anon_key,
        config.supabase_service_key,
        config.supabase_jwt_secret,
    ]):
        print("ERROR: Missing required environment variables.")
        exit(1)
    
    seed_flags_via_api()
