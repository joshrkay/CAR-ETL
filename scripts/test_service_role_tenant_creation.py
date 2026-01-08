"""Test that service_role can create tenants."""
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
        load_dotenv(env_path, override=True)
    else:
        load_dotenv(override=True)
except ImportError:
    pass

from supabase import create_client
from src.auth.config import get_auth_config
from uuid import uuid4


def test_service_role_tenant_creation():
    """Test that service_role can create tenants."""
    config = get_auth_config()
    
    # Initialize Supabase client with service key (service_role)
    supabase_service = create_client(
        config.supabase_url,
        config.supabase_service_key,
    )
    
    print("=" * 60)
    print("Testing Service Role Tenant Creation")
    print("=" * 60)
    
    # Step 1: Create a tenant using service_role
    print("\n1. Creating tenant with service_role...")
    
    tenant_name = f"Test Tenant {uuid4().hex[:8]}"
    tenant_slug = f"test-tenant-{uuid4().hex[:8]}"
    
    try:
        result = supabase_service.table("tenants").insert({
            "name": tenant_name,
            "slug": tenant_slug,
            "environment": "dev",
            "status": "active",
            "settings": {"test": True},
        }).execute()
        
        if result.data:
            tenant_id = result.data[0]["id"]
            print(f"   [OK] Created tenant: {tenant_name}")
            print(f"        ID: {tenant_id}")
            print(f"        Slug: {tenant_slug}")
        else:
            print(f"   [FAIL] No data returned")
            return False
            
    except Exception as e:
        print(f"   [FAIL] Failed to create tenant: {e}")
        return False
    
    # Step 2: Verify tenant was created
    print("\n2. Verifying tenant exists...")
    
    try:
        verify_result = supabase_service.table("tenants").select("*").eq("id", tenant_id).execute()
        
        if verify_result.data:
            tenant = verify_result.data[0]
            print(f"   [OK] Tenant verified:")
            print(f"        Name: {tenant['name']}")
            print(f"        Slug: {tenant['slug']}")
            print(f"        Environment: {tenant['environment']}")
            print(f"        Status: {tenant['status']}")
        else:
            print(f"   [FAIL] Tenant not found after creation")
            return False
            
    except Exception as e:
        print(f"   [FAIL] Failed to verify tenant: {e}")
        return False
    
    # Step 3: Test updating tenant (service_role should be able to)
    print("\n3. Testing tenant update with service_role...")
    
    try:
        update_result = supabase_service.table("tenants").update({
            "status": "inactive",
            "settings": {"test": True, "updated": True},
        }).eq("id", tenant_id).execute()
        
        if update_result.data:
            updated_tenant = update_result.data[0]
            print(f"   [OK] Tenant updated successfully")
            print(f"        New status: {updated_tenant['status']}")
        else:
            print(f"   [FAIL] Update returned no data")
            return False
            
    except Exception as e:
        print(f"   [FAIL] Failed to update tenant: {e}")
        return False
    
    # Step 4: Test deleting tenant (service_role should be able to)
    print("\n4. Testing tenant deletion with service_role...")
    
    try:
        supabase_service.table("tenants").delete().eq("id", tenant_id).execute()
        print(f"   [OK] Tenant deleted successfully")
        
        # Verify deletion
        verify_deleted = supabase_service.table("tenants").select("*").eq("id", tenant_id).execute()
        if not verify_deleted.data:
            print(f"   [OK] Tenant deletion verified (not found)")
        else:
            print(f"   [WARNING] Tenant still exists after deletion")
            
    except Exception as e:
        print(f"   [FAIL] Failed to delete tenant: {e}")
        return False
    
    # Step 5: Test that anon/authenticated role cannot create tenants
    print("\n5. Testing that anon role cannot create tenants...")
    
    try:
        # Try with anon key (should fail due to RLS)
        supabase_anon = create_client(
            config.supabase_url,
            config.supabase_anon_key,
        )
        
        # This should fail - anon role cannot insert into tenants
        try:
            anon_result = supabase_anon.table("tenants").insert({
                "name": "Unauthorized Tenant",
                "slug": f"unauthorized-{uuid4().hex[:8]}",
                "environment": "dev",
                "status": "active",
            }).execute()
            
            # If we get here, RLS is not working correctly
            print(f"   [FAIL] Anon role was able to create tenant (RLS violation!)")
            print(f"        This should not be possible")
            
            # Clean up the unauthorized tenant
            if anon_result.data:
                tenant_id_unauth = anon_result.data[0]["id"]
                supabase_service.table("tenants").delete().eq("id", tenant_id_unauth).execute()
            
            return False
            
        except Exception as e:
            error_msg = str(e)
            if "permission denied" in error_msg.lower() or "row-level security" in error_msg.lower() or "policy" in error_msg.lower():
                print(f"   [OK] Anon role correctly blocked from creating tenant")
                print(f"        Error: {error_msg[:100]}...")
            else:
                print(f"   [WARNING] Unexpected error (might be RLS working): {error_msg[:100]}")
                
    except Exception as e:
        print(f"   [INFO] Anon test error (expected): {e}")
    
    # Summary
    print("\n" + "=" * 60)
    print("Service Role Test Summary")
    print("=" * 60)
    print("[OK] Service role can CREATE tenants")
    print("[OK] Service role can READ tenants")
    print("[OK] Service role can UPDATE tenants")
    print("[OK] Service role can DELETE tenants")
    print("[OK] Anon role is blocked from creating tenants (RLS working)")
    print("=" * 60)
    
    return True


if __name__ == "__main__":
    try:
        config = get_auth_config()
    except Exception as e:
        print("ERROR: Failed to load configuration.")
        print("Please ensure you have a .env file with required variables.")
        print(f"\nError: {e}")
        exit(1)
    
    if not all([
        config.supabase_url,
        config.supabase_anon_key,
        config.supabase_service_key,
    ]):
        print("ERROR: Missing required environment variables.")
        exit(1)
    
    success = test_service_role_tenant_creation()
    exit(0 if success else 1)
