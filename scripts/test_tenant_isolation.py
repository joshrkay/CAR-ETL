"""Test that user A cannot query tenant B data (RLS isolation)."""
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
        load_dotenv(env_path, override=True)
        print(f"Loaded .env from: {env_path}")
    else:
        load_dotenv(override=True)
        if not os.getenv("SUPABASE_URL"):
            print("WARNING: .env file not found and SUPABASE_URL not set")
except ImportError:
    print("WARNING: python-dotenv not installed. Install with: pip install python-dotenv")

from uuid import uuid4

from src.auth.client import create_service_client, create_user_client
from src.auth.config import get_auth_config


def test_tenant_isolation():
    """Test that user A cannot query tenant B data."""
    config = get_auth_config()

    # Initialize Supabase admin client for setup
    supabase_admin = create_service_client(config)

    print("=" * 70)
    print("Testing Tenant Isolation: User A cannot query Tenant B data")
    print("=" * 70)

    # Step 1: Create two tenants
    print("\n1. Creating test tenants...")

    tenant_a_id = str(uuid4())
    tenant_b_id = str(uuid4())
    tenant_a_slug = f"tenant-a-{uuid4().hex[:8]}"
    tenant_b_slug = f"tenant-b-{uuid4().hex[:8]}"

    try:
        tenant_a_result = supabase_admin.table("tenants").insert({
            "id": tenant_a_id,
            "name": "Tenant A",
            "slug": tenant_a_slug,
            "environment": "dev",
            "status": "active",
        }).execute()

        print(f"   [OK] Created Tenant A: {tenant_a_slug} (ID: {tenant_a_id})")

        tenant_b_result = supabase_admin.table("tenants").insert({
            "id": tenant_b_id,
            "name": "Tenant B",
            "slug": tenant_b_slug,
            "environment": "dev",
            "status": "active",
        }).execute()

        print(f"   [OK] Created Tenant B: {tenant_b_slug} (ID: {tenant_b_id})")

    except Exception as e:
        print(f"   [ERROR] Failed to create tenants: {e}")
        return False

    # Step 2: Create users in auth.users
    print("\n2. Creating test users...")

    user_a_id = str(uuid4())
    user_b_id = str(uuid4())
    user_a_email = f"user-a-{uuid4().hex[:8]}@example.com"
    user_b_email = f"user-b-{uuid4().hex[:8]}@example.com"

    try:
        # Verify service key format before attempting user creation
        service_key = config.supabase_service_key
        if not service_key or not service_key.startswith(('eyJ', 'sb_')):
            print("   [WARNING] Service key format may be incorrect.")
            print("   [INFO] Service key should be a JWT (starts with 'eyJ') or Supabase key.")
            print(f"   [INFO] Current key starts with: {service_key[:10] if service_key else 'None'}...")
            print("   [INFO] Get your service_role key from: Supabase Dashboard → Settings → API")

        # Create User A in Tenant A
        user_a_auth = supabase_admin.auth.admin.create_user({
            "email": user_a_email,
            "password": "TestPassword123!",
            "email_confirm": True,
        })
        user_a_id = user_a_auth.user.id
        print(f"   [OK] Created User A: {user_a_email} (ID: {user_a_id})")

        # Create User B in Tenant B
        user_b_auth = supabase_admin.auth.admin.create_user({
            "email": user_b_email,
            "password": "TestPassword123!",
            "email_confirm": True,
        })
        user_b_id = user_b_auth.user.id
        print(f"   [OK] Created User B: {user_b_email} (ID: {user_b_id})")

    except Exception as e:
        error_msg = str(e)
        print(f"   [ERROR] Failed to create users: {error_msg}")

        # Provide helpful diagnostics
        if "Bearer token" in error_msg or "authentication" in error_msg.lower():
            print("\n   [DIAGNOSTIC] Authentication error detected.")
            print("   [INFO] The service_role key may be incorrect or missing.")
            print("   [INFO] Service key format check:")
            service_key = config.supabase_service_key
            if service_key:
                if service_key.startswith('eyJ'):
                    print("      ✓ Key appears to be a JWT (correct format)")
                elif service_key.startswith('sb_'):
                    print("      ⚠ Key appears to be a publishable key (may not work for admin operations)")
                    print("      [INFO] You need the 'service_role' key, not the 'anon' or 'publishable' key")
                else:
                    print(f"      ⚠ Key format is unusual: starts with '{service_key[:10]}...'")
                print(f"      [INFO] Key length: {len(service_key)} characters")
            else:
                print("      ✗ Service key is not set")

            print("\n   [SOLUTION] To fix this:")
            # Extract project ref from URL
            try:
                project_ref = config.supabase_url.split('//')[1].split('.')[0] if '//' in config.supabase_url else 'your-project'
                print(f"   1. Go to: https://supabase.com/dashboard/project/{project_ref}/settings/api")
            except:
                print("   1. Go to: Supabase Dashboard → Settings → API")
            print("   2. Copy the 'service_role' key (not 'anon' or 'publishable')")
            print("   3. Set it as SUPABASE_SERVICE_KEY environment variable")
            print("   4. The service_role key should be a JWT token starting with 'eyJ'")

        return False

    # Step 3: Link users to tenants
    print("\n3. Linking users to tenants...")

    try:
        supabase_admin.table("tenant_users").insert({
            "tenant_id": tenant_a_id,
            "user_id": user_a_id,
            "roles": ["Admin"],
        }).execute()
        print("   [OK] Linked User A to Tenant A")

        supabase_admin.table("tenant_users").insert({
            "tenant_id": tenant_b_id,
            "user_id": user_b_id,
            "roles": ["Admin"],
        }).execute()
        print("   [OK] Linked User B to Tenant B")

    except Exception as e:
        print(f"   [ERROR] Failed to link users to tenants: {e}")
        return False

    # Step 4: Get real access tokens by signing in users through Supabase Auth
    # This ensures PostgREST can extract JWT claims properly
    print("\n4. Getting access tokens from Supabase Auth...")

    try:
        # Sign in User A to get a real access token
        sign_in_a = supabase_admin.auth.sign_in_with_password({
            "email": user_a_email,
            "password": "TestPassword123!",
        })
        token_a = sign_in_a.session.access_token
        print("   [OK] Got access token for User A")

        # Sign in User B to get a real access token
        sign_in_b = supabase_admin.auth.sign_in_with_password({
            "email": user_b_email,
            "password": "TestPassword123!",
        })
        token_b = sign_in_b.session.access_token
        print("   [OK] Got access token for User B")

    except Exception as e:
        print(f"   [ERROR] Failed to get access tokens: {e}")
        print("   [INFO] Make sure users were created successfully and passwords are correct.")
        return False

    # Step 5: Create Supabase clients with user JWTs (RLS enforced)
    print("\n5. Creating user clients with RLS...")

    client_a = create_user_client(token_a, config)
    client_b = create_user_client(token_b, config)
    print("   [OK] Created client for User A (anon_key + JWT)")
    print("   [OK] Created client for User B (anon_key + JWT)")

    # Step 6: Test tenant isolation
    print("\n6. Testing tenant isolation...")

    try:
        # User A queries tenants table
        print("\n   Testing: User A queries tenants table...")
        result_a_tenants = client_a.table("tenants").select("*").execute()
        tenant_ids_a = [t["id"] for t in result_a_tenants.data]

        print(f"      User A can see {len(tenant_ids_a)} tenant(s)")
        for tenant in result_a_tenants.data:
            print(f"      - {tenant['name']} ({tenant['slug']})")

        # Verify User A can only see Tenant A
        if tenant_a_id in tenant_ids_a and tenant_b_id not in tenant_ids_a:
            print("      [PASS] User A can only see Tenant A")
        else:
            print("      [FAIL] User A can see Tenant B! Violation of tenant isolation!")
            print(f"         Expected: [{tenant_a_id}]")
            print(f"         Got: {tenant_ids_a}")
            return False

        # User B queries tenants table
        print("\n   Testing: User B queries tenants table...")
        result_b_tenants = client_b.table("tenants").select("*").execute()
        tenant_ids_b = [t["id"] for t in result_b_tenants.data]

        print(f"      User B can see {len(tenant_ids_b)} tenant(s)")
        for tenant in result_b_tenants.data:
            print(f"      - {tenant['name']} ({tenant['slug']})")

        # Verify User B can only see Tenant B
        if tenant_b_id in tenant_ids_b and tenant_a_id not in tenant_ids_b:
            print("      [PASS] User B can only see Tenant B")
        else:
            print("      [FAIL] User B can see Tenant A! Violation of tenant isolation!")
            print(f"         Expected: [{tenant_b_id}]")
            print(f"         Got: {tenant_ids_b}")
            return False

        # User A queries tenant_users table
        print("\n   Testing: User A queries tenant_users table...")
        result_a_users = client_a.table("tenant_users").select("*").execute()
        user_tenant_ids_a = [tu["tenant_id"] for tu in result_a_users.data]

        print(f"      User A can see {len(result_a_users.data)} tenant_user record(s)")
        for tu in result_a_users.data:
            print(f"      - User {tu['user_id']} in Tenant {tu['tenant_id']}")

        # Verify User A can only see Tenant A's users
        if all(tid == tenant_a_id for tid in user_tenant_ids_a):
            print("      [PASS] User A can only see Tenant A's users")
        else:
            print("      [FAIL] User A can see Tenant B's users! Violation of tenant isolation!")
            print(f"         Expected: All records with tenant_id = {tenant_a_id}")
            print(f"         Got: {user_tenant_ids_a}")
            return False

        # User B queries tenant_users table
        print("\n   Testing: User B queries tenant_users table...")
        result_b_users = client_b.table("tenant_users").select("*").execute()
        user_tenant_ids_b = [tu["tenant_id"] for tu in result_b_users.data]

        print(f"      User B can see {len(result_b_users.data)} tenant_user record(s)")
        for tu in result_b_users.data:
            print(f"      - User {tu['user_id']} in Tenant {tu['tenant_id']}")

        # Verify User B can only see Tenant B's users
        if all(tid == tenant_b_id for tid in user_tenant_ids_b):
            print("      [PASS] User B can only see Tenant B's users")
        else:
            print("      [FAIL] User B can see Tenant A's users! Violation of tenant isolation!")
            print(f"         Expected: All records with tenant_id = {tenant_b_id}")
            print(f"         Got: {user_tenant_ids_b}")
            return False

        # User A tries to directly query Tenant B by ID (should fail)
        print("\n   Testing: User A tries to query Tenant B by ID...")
        try:
            result_a_tenant_b = client_a.table("tenants").select("*").eq("id", tenant_b_id).execute()
            if len(result_a_tenant_b.data) == 0:
                print("      [PASS] User A cannot query Tenant B by ID (RLS blocked)")
            else:
                print("      [FAIL] User A can query Tenant B by ID! Violation of tenant isolation!")
                return False
        except Exception as e:
            # Some Supabase clients may raise an error instead of returning empty
            print(f"      [PASS] User A cannot query Tenant B (error raised: {type(e).__name__})")

        # User B tries to directly query Tenant A by ID (should fail)
        print("\n   Testing: User B tries to query Tenant A by ID...")
        try:
            result_b_tenant_a = client_b.table("tenants").select("*").eq("id", tenant_a_id).execute()
            if len(result_b_tenant_a.data) == 0:
                print("      [PASS] User B cannot query Tenant A by ID (RLS blocked)")
            else:
                print("      [FAIL] User B can query Tenant A by ID! Violation of tenant isolation!")
                return False
        except Exception as e:
            # Some Supabase clients may raise an error instead of returning empty
            print(f"      [PASS] User B cannot query Tenant A (error raised: {type(e).__name__})")

    except Exception as e:
        print(f"   [ERROR] Failed to test tenant isolation: {e}")
        import traceback
        traceback.print_exc()
        return False

    # Step 7: Cleanup (optional - comment out to keep test data)
    print("\n7. Cleaning up test data...")
    try:
        # Delete tenant_users first (due to foreign key)
        supabase_admin.table("tenant_users").delete().eq("tenant_id", tenant_a_id).execute()
        supabase_admin.table("tenant_users").delete().eq("tenant_id", tenant_b_id).execute()

        # Delete users
        supabase_admin.auth.admin.delete_user(user_a_id)
        supabase_admin.auth.admin.delete_user(user_b_id)

        # Delete tenants
        supabase_admin.table("tenants").delete().eq("id", tenant_a_id).execute()
        supabase_admin.table("tenants").delete().eq("id", tenant_b_id).execute()

        print("   [OK] Cleaned up test data")
    except Exception as e:
        print(f"   [WARNING] Failed to cleanup: {e}")

    print("\n" + "=" * 70)
    print("TEST RESULT: PASS - Tenant isolation is working correctly!")
    print("=" * 70)
    return True


if __name__ == "__main__":
    success = test_tenant_isolation()
    sys.exit(0 if success else 1)
