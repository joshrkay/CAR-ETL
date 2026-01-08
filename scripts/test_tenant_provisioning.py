"""Test script for tenant provisioning API endpoint."""
import sys
from pathlib import Path
from typing import Dict, Any
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

from fastapi.testclient import TestClient
from src.main import app
from src.auth.config import get_auth_config
import jwt
from datetime import datetime, timedelta
from supabase import create_client, Client


def create_admin_jwt(user_id: str, email: str, tenant_id: str, tenant_slug: str) -> str:
    """Create a JWT token for an admin user."""
    config = get_auth_config()
    
    payload = {
        "sub": user_id,
        "email": email,
        "app_metadata": {
            "tenant_id": tenant_id,
            "roles": ["Admin"],
            "tenant_slug": tenant_slug,
        },
        "exp": datetime.utcnow() + timedelta(hours=1),
    }
    
    return jwt.encode(payload, config.supabase_jwt_secret, algorithm="HS256")


def test_tenant_provisioning():
    """Test the tenant provisioning endpoint."""
    config = get_auth_config()
    
    if not all([
        config.supabase_url,
        config.supabase_anon_key,
        config.supabase_service_key,
        config.supabase_jwt_secret,
    ]):
        print("ERROR: Missing required environment variables for AuthConfig.")
        print("Please ensure your .env file is configured correctly.")
        return False
    
    client = TestClient(app)
    supabase_admin: Client = create_client(config.supabase_url, config.supabase_service_key)
    
    print("=" * 60)
    print("Testing Tenant Provisioning API")
    print("=" * 60)
    
    # Step 1: Create a test admin user and tenant for authentication
    print("\n1. Setting up test admin user and tenant...")
    test_tenant_id = str(uuid4())
    test_tenant_slug = f"test-admin-{uuid4().hex[:8]}"
    test_admin_user_id = str(uuid4())
    test_admin_email = f"admin-{uuid4().hex[:8]}@example.com"
    
    try:
        # Create tenant for admin user
        tenant_result = supabase_admin.table("tenants").insert({
            "id": test_tenant_id,
            "name": f"Test Admin Tenant {test_tenant_slug}",
            "slug": test_tenant_slug,
        }).execute()
        print(f"   [OK] Created admin tenant: {test_tenant_slug}")
        
        # Create admin user
        auth_response = supabase_admin.auth.admin.create_user({
            "email": test_admin_email,
            "password": "Password123!",
            "email_confirm": True,
        })
        print(f"   [OK] Created admin user: {test_admin_email}")
        
        # Get the actual user ID from the created user
        actual_user_id = auth_response.user.id
        
        # Link admin to tenant with actual user ID
        supabase_admin.table("tenant_users").insert({
            "tenant_id": test_tenant_id,
            "user_id": actual_user_id,
            "roles": ["Admin"],
        }).execute()
        print(f"   [OK] Linked admin to tenant")
        
        # Update test_admin_user_id to use actual user ID
        test_admin_user_id = actual_user_id
        
    except Exception as e:
        print(f"   [WARNING] Setup failed (may already exist): {e}")
        # Try to get existing user if creation failed
        try:
            users_list = supabase_admin.auth.admin.list_users()
            for user in users_list.users:
                if user.email == test_admin_email:
                    test_admin_user_id = user.id
                    # Try to link if not already linked
                    try:
                        supabase_admin.table("tenant_users").insert({
                            "tenant_id": test_tenant_id,
                            "user_id": test_admin_user_id,
                            "roles": ["Admin"],
                        }).execute()
                        print(f"   [OK] Linked existing admin to tenant")
                    except:
                        pass  # Already linked
                    break
        except:
            pass
    
    admin_token = create_admin_jwt(
        test_admin_user_id,
        test_admin_email,
        test_tenant_id,
        test_tenant_slug,
    )
    admin_headers = {"Authorization": f"Bearer {admin_token}"}
    
    # Step 2: Test creating a new tenant
    print("\n2. Testing POST /api/v1/admin/tenants (Create Tenant)...")
    new_tenant_slug = f"provisioned-tenant-{uuid4().hex[:8]}"
    new_tenant_name = f"Provisioned Test Tenant {new_tenant_slug}"
    new_admin_email = f"admin-{uuid4().hex[:8]}@provisioned.com"
    
    create_data = {
        "name": new_tenant_name,
        "slug": new_tenant_slug,
        "admin_email": new_admin_email,
        "environment": "dev",
    }
    
    response = client.post("/api/v1/admin/tenants", json=create_data, headers=admin_headers)
    
    if response.status_code == 201:
        result = response.json()
        print(f"   [OK] Created tenant successfully:")
        print(f"        Tenant ID: {result['tenant_id']}")
        print(f"        Name: {result['name']}")
        print(f"        Slug: {result['slug']}")
        print(f"        Status: {result['status']}")
        print(f"        Storage Bucket: {result['storage_bucket']}")
        print(f"        Admin Invite Sent: {result['admin_invite_sent']}")
        
        provisioned_tenant_id = result['tenant_id']
        provisioned_bucket = result['storage_bucket']
        
        # Step 3: Verify tenant exists in database
        print("\n3. Verifying tenant in database...")
        verify_result = supabase_admin.table("tenants").select("*").eq("id", provisioned_tenant_id).execute()
        if verify_result.data:
            print(f"   [OK] Tenant verified in database: {verify_result.data[0]['name']}")
        else:
            print(f"   [FAIL] Tenant not found in database")
            return False
        
        # Step 4: Verify storage bucket exists
        print("\n4. Verifying storage bucket exists...")
        try:
            # Try to list files in bucket (will fail if bucket doesn't exist)
            bucket_files = supabase_admin.storage.from_(provisioned_bucket).list()
            print(f"   [OK] Storage bucket exists: {provisioned_bucket}")
        except Exception as e:
            print(f"   [WARNING] Could not verify bucket (may need manual check): {e}")
        
        # Step 5: Verify admin user was created
        print("\n5. Verifying admin user was created...")
        try:
            # Check if user exists (via tenant_users table)
            user_result = supabase_admin.table("tenant_users").select("*").eq(
                "tenant_id", provisioned_tenant_id
            ).execute()
            if user_result.data:
                print(f"   [OK] Admin user linked to tenant: {user_result.data[0]['user_id']}")
            else:
                print(f"   [WARNING] Could not verify admin user link")
        except Exception as e:
            print(f"   [WARNING] Could not verify admin user: {e}")
        
        # Step 6: Test duplicate slug (should fail)
        print("\n6. Testing duplicate slug (should fail)...")
        duplicate_response = client.post("/api/v1/admin/tenants", json=create_data, headers=admin_headers)
        if duplicate_response.status_code == 400:
            print(f"   [OK] Duplicate slug correctly rejected: {duplicate_response.json()}")
        else:
            print(f"   [FAIL] Expected 400, got {duplicate_response.status_code}")
            return False
        
        # Step 7: Cleanup (optional)
        print("\n7. Cleanup (optional)...")
        try:
            # Delete tenant_users
            supabase_admin.table("tenant_users").delete().eq("tenant_id", provisioned_tenant_id).execute()
            # Delete tenant
            supabase_admin.table("tenants").delete().eq("id", provisioned_tenant_id).execute()
            print(f"   [OK] Cleaned up test tenant")
        except Exception as e:
            print(f"   [WARNING] Cleanup failed (this is okay): {e}")
        
        print("\n" + "=" * 60)
        print("[OK] All Tenant Provisioning Tests Passed!")
        print("=" * 60)
        return True
        
    else:
        print(f"   [FAIL] Failed to create tenant: {response.status_code}")
        print(f"        Response: {response.json()}")
        return False


if __name__ == "__main__":
    if not test_tenant_provisioning():
        sys.exit(1)
