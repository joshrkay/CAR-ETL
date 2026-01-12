"""Test login flow with real Supabase user."""
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Load environment variables from .env file if it exists
try:
    from dotenv import load_dotenv
    env_path = project_root / ".env"
    if env_path.exists():
        load_dotenv(env_path)
    else:
        # Try loading from current directory
        load_dotenv()
except ImportError:
    pass  # dotenv not installed, will use system env vars

from supabase import create_client, Client
from src.auth.config import get_auth_config
from src.auth.middleware import AuthMiddleware
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
import jwt
from uuid import uuid4
from typing import Any


def test_real_login_flow() -> bool:
    """Test the complete login flow with a real Supabase user."""
    config = get_auth_config()
    
    # Initialize Supabase client
    supabase: Client = create_client(
        config.supabase_url,
        config.supabase_service_key,
    )
    
    print("=" * 60)
    print("Testing Real Login Flow with Supabase")
    print("=" * 60)
    
    # Step 1: Create or get a test tenant
    print("\n1. Setting up test tenant...")
    tenant_slug = f"test-tenant-{uuid4().hex[:8]}"
    tenant_name = "Test Tenant"
    
    try:
        # Try using PostgREST API first
        try:
            tenant_result = (
                supabase.table("tenants")
                .select("*")
                .eq("slug", tenant_slug)
                .execute()
            )
            
            if tenant_result.data:
                tenant_id = tenant_result.data[0]["id"]
                print(f"   Using existing tenant: {tenant_id}")
            else:
                # Create new tenant
                tenant_result = (
                    supabase.table("tenants")
                    .insert({
                        "slug": tenant_slug,
                        "name": tenant_name,
                    })
                    .execute()
                )
                tenant_id = tenant_result.data[0]["id"]
                print(f"   Created new tenant: {tenant_id}")
        except Exception as api_error:
            # If PostgREST fails, try using RPC or direct SQL
            if "PGRST205" in str(api_error) or "schema cache" in str(api_error).lower():
                print(f"   WARNING: PostgREST schema cache issue: {api_error}")
                print("   Attempting to refresh schema cache via SQL...")
                try:
                    # Try to refresh schema cache using SQL
                    supabase.rpc("exec_sql", {
                        "query": "NOTIFY pgrst, 'reload schema';"
                    }).execute()
                    print("   Schema cache refresh triggered!")
                    print("   Waiting 5 seconds for cache to update...")
                    import time
                    time.sleep(5)
                    # Try again
                    tenant_result = (
                        supabase.table("tenants")
                        .select("*")
                        .eq("slug", tenant_slug)
                        .execute()
                    )
                    if tenant_result.data:
                        tenant_id = tenant_result.data[0]["id"]
                        print(f"   Using existing tenant: {tenant_id}")
                    else:
                        tenant_result = (
                            supabase.table("tenants")
                            .insert({
                                "slug": tenant_slug,
                                "name": tenant_name,
                            })
                            .execute()
                        )
                        tenant_id = tenant_result.data[0]["id"]
                        print(f"   Created new tenant: {tenant_id}")
                except Exception as refresh_error:
                    print(f"   Could not auto-refresh cache: {refresh_error}")
                    print("   Please manually refresh PostgREST schema cache:")
                    print("   1. Go to: https://supabase.com/dashboard/project/ueqzwqejpjmsspfiypgb/sql/new")
                    print("   2. Run: NOTIFY pgrst, 'reload schema';")
                    print("   3. Wait 10 seconds, then run this test again")
                    return False
            else:
                raise api_error
    except Exception as e:
        print(f"   ERROR: Failed to create/get tenant: {e}")
        print("   Make sure the 'tenants' table exists in your database.")
        print("   If tables exist, refresh PostgREST schema cache.")
        return False
    
    # Step 2: Create a test user in Supabase Auth
    print("\n2. Creating test user in Supabase Auth...")
    test_email = f"test-{uuid4().hex[:8]}@example.com"
    test_password = "TestPassword123!"
    
    try:
        auth_response = supabase.auth.admin.create_user({
            "email": test_email,
            "password": test_password,
            "email_confirm": True,
        })
        user_id = auth_response.user.id
        print(f"   Created user: {user_id}")
        print(f"   Email: {test_email}")
    except Exception as e:
        print(f"   ERROR: Failed to create user: {e}")
        return False
    
    # Step 3: Link user to tenant
    print("\n3. Linking user to tenant...")
    try:
        tenant_user_result = (
            supabase.table("tenant_users")
            .insert({
                "user_id": user_id,
                "tenant_id": tenant_id,
                "roles": ["Admin", "User"],
            })
            .execute()
        )
        print(f"   Linked user to tenant with roles: {tenant_user_result.data[0]['roles']}")
    except Exception as e:
        print(f"   ERROR: Failed to link user to tenant: {e}")
        print("   Make sure the 'tenant_users' table exists in your database.")
        # Clean up user
        try:
            supabase.auth.admin.delete_user(user_id)
        except Exception:
            pass
        return False
    
    # Step 4: Sign in to get JWT token
    print("\n4. Signing in to get JWT token...")
    try:
        sign_in_response = supabase.auth.sign_in_with_password({
            "email": test_email,
            "password": test_password,
        })
        access_token = sign_in_response.session.access_token
        print(f"   Got access token: {access_token[:50]}...")
    except Exception as e:
        print(f"   ERROR: Failed to sign in: {e}")
        return False
    
    # Step 5: Decode and verify JWT contains custom claims
    print("\n5. Verifying JWT contains custom claims...")
    try:
        decoded = jwt.decode(
            access_token,
            config.supabase_jwt_secret,
            algorithms=["HS256"],
            options={"verify_exp": False},  # Don't verify exp for testing
        )
        
        print(f"   User ID (sub): {decoded.get('sub')}")
        print(f"   Email: {decoded.get('email')}")
        
        app_metadata = decoded.get("app_metadata", {})
        jwt_tenant_id = app_metadata.get("tenant_id")
        jwt_roles = app_metadata.get("roles", [])
        jwt_tenant_slug = app_metadata.get("tenant_slug")
        
        print(f"   Tenant ID in JWT: {jwt_tenant_id}")
        print(f"   Roles in JWT: {jwt_roles}")
        print(f"   Tenant Slug in JWT: {jwt_tenant_slug}")
        
        # Verify claims
        if jwt_tenant_id != str(tenant_id):
            print(f"   ❌ FAIL: Tenant ID mismatch! Expected {tenant_id}, got {jwt_tenant_id}")
            return False
        
        if set(jwt_roles) != {"Admin", "User"}:
            print(f"   ❌ FAIL: Roles mismatch! Expected ['Admin', 'User'], got {jwt_roles}")
            return False
        
        if jwt_tenant_slug != tenant_slug:
            print(f"   ❌ FAIL: Tenant slug mismatch! Expected {tenant_slug}, got {jwt_tenant_slug}")
            return False
        
        print("   ✅ All custom claims verified!")
        
    except jwt.InvalidTokenError as e:
        print(f"   ERROR: Failed to decode JWT: {e}")
        return False
    except Exception as e:
        print(f"   ERROR: {e}")
        return False
    
    # Step 6: Test FastAPI middleware with real token
    print("\n6. Testing FastAPI middleware with real token...")
    try:
        app = FastAPI()
        app.add_middleware(AuthMiddleware, config=config)  # type: ignore[arg-type]
        
        @app.get("/test")
        async def test_endpoint(request: Request) -> Any:
            auth = request.state.auth
            return {
                "user_id": str(auth.user_id),
                "email": auth.email,
                "tenant_id": str(auth.tenant_id),
                "roles": auth.roles,
                "tenant_slug": auth.tenant_slug,
            }
        
        client = TestClient(app)
        response = client.get(
            "/test",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        
        if response.status_code == 200:
            data = response.json()
            print("   ✅ Middleware extracted auth context:")
            print(f"      User ID: {data['user_id']}")
            print(f"      Email: {data['email']}")
            print(f"      Tenant ID: {data['tenant_id']}")
            print(f"      Roles: {data['roles']}")
            print(f"      Tenant Slug: {data['tenant_slug']}")
        else:
            print(f"   ❌ FAIL: Middleware returned {response.status_code}")
            print(f"   Response: {response.json()}")
            return False
            
    except Exception as e:
        print(f"   ERROR: Failed to test middleware: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # Step 7: Cleanup (optional - comment out to keep test data)
    print("\n7. Cleaning up test data...")
    try:
        # Delete tenant_user relationship
        supabase.table("tenant_users").delete().eq("user_id", user_id).execute()
        print("   Deleted tenant_user relationship")
        
        # Delete tenant
        supabase.table("tenants").delete().eq("id", tenant_id).execute()
        print("   Deleted tenant")
        
        # Delete user
        supabase.auth.admin.delete_user(user_id)
        print("   Deleted user")
    except Exception as e:
        print(f"   WARNING: Cleanup failed (this is okay): {e}")
    
    print("\n" + "=" * 60)
    print("✅ All tests passed! Login flow is working correctly.")
    print("=" * 60)
    return True


if __name__ == "__main__":
    # Check if environment variables are set
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
        config.supabase_service_key,
        config.supabase_jwt_secret,
    ]):
        print("ERROR: Missing required environment variables.")
        print("Please set SUPABASE_URL, SUPABASE_SERVICE_KEY, and SUPABASE_JWT_SECRET")
        exit(1)
    
    success = test_real_login_flow()
    exit(0 if success else 1)
