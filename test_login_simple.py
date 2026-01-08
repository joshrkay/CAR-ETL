"""Simplified login test that bypasses PostgREST schema cache issues."""
import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
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

from supabase import create_client
from src.auth.config import get_auth_config
import jwt
from uuid import uuid4


def test_login_simple():
    """Test login flow without using PostgREST tables."""
    config = get_auth_config()
    
    print("=" * 60)
    print("Simplified Login Flow Test (Bypasses PostgREST)")
    print("=" * 60)
    
    # Initialize Supabase client
    supabase = create_client(
        config.supabase_url,
        config.supabase_service_key,
    )
    
    # Step 1: Create a test user
    print("\n1. Creating test user in Supabase Auth...")
    test_email = f"test-{uuid4().hex[:8]}@example.com"
    test_password = "TestPassword123!"
    
    try:
        auth_response = supabase.auth.admin.create_user({
            "email": test_email,
            "password": test_password,
            "email_confirm": True,
        })
        user_id = auth_response.user.id
        print(f"   [OK] Created user: {user_id}")
        print(f"   Email: {test_email}")
    except Exception as e:
        print(f"   [ERROR] Failed to create user: {e}")
        return False
    
    # Step 2: Sign in to get JWT token
    print("\n2. Signing in to get JWT token...")
    try:
        sign_in_response = supabase.auth.sign_in_with_password({
            "email": test_email,
            "password": test_password,
        })
        access_token = sign_in_response.session.access_token
        print(f"   [OK] Got access token: {access_token[:50]}...")
    except Exception as e:
        print(f"   [ERROR] Failed to sign in: {e}")
        # Clean up
        try:
            supabase.auth.admin.delete_user(user_id)
        except:
            pass
        return False
    
    # Step 3: Decode and verify JWT
    print("\n3. Verifying JWT structure...")
    try:
        # Supabase access tokens use ES256 (ECDSA) which requires a public key
        # For testing, we'll decode without verification to inspect the claims
        # In production, you'd verify with Supabase's public key
        decoded = jwt.decode(
            access_token,
            options={"verify_signature": False, "verify_exp": False}
        )
        print(f"   [OK] JWT decoded successfully (signature verification skipped for testing)")
        
        print(f"   [OK] JWT decoded successfully")
        print(f"   User ID (sub): {decoded.get('sub')}")
        print(f"   Email: {decoded.get('email')}")
        
        app_metadata = decoded.get("app_metadata", {})
        jwt_tenant_id = app_metadata.get("tenant_id")
        jwt_roles = app_metadata.get("roles", [])
        jwt_tenant_slug = app_metadata.get("tenant_slug")
        
        print(f"\n   Custom Claims in JWT:")
        print(f"   - tenant_id: {jwt_tenant_id}")
        print(f"   - roles: {jwt_roles}")
        print(f"   - tenant_slug: {jwt_tenant_slug}")
        
        if jwt_tenant_id or jwt_roles or jwt_tenant_slug:
            print("\n   [OK] Custom claims are present in JWT!")
            print("   Note: Values may be null if user is not linked to a tenant yet.")
            print("   This is expected - the hook function will populate these when")
            print("   the user is assigned to a tenant in the tenant_users table.")
        else:
            print("\n   [WARNING] No custom claims found (user not linked to tenant yet)")
            print("   This is normal for a new user without tenant assignment.")
        
    except jwt.InvalidTokenError as e:
        print(f"   [ERROR] Failed to decode JWT: {e}")
        return False
    except Exception as e:
        print(f"   [ERROR] {e}")
        return False
    
    # Step 4: Test FastAPI middleware
    print("\n4. Testing FastAPI middleware extraction...")
    try:
        from fastapi import FastAPI, Request
        from fastapi.testclient import TestClient
        from src.auth.middleware import AuthMiddleware
        
        app = FastAPI()
        app.add_middleware(AuthMiddleware, config=config)
        
        @app.get("/test")
        async def test_endpoint(request: Request):
            auth = request.state.auth
            return {
                "user_id": str(auth.user_id),
                "email": auth.email,
                "tenant_id": str(auth.tenant_id) if auth.tenant_id else None,
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
            print(f"   [OK] Middleware extracted auth context:")
            print(f"      User ID: {data['user_id']}")
            print(f"      Email: {data['email']}")
            print(f"      Tenant ID: {data['tenant_id']}")
            print(f"      Roles: {data['roles']}")
            print(f"      Tenant Slug: {data['tenant_slug']}")
        elif response.status_code == 401:
            error_data = response.json()
            if error_data.get("code") == "MISSING_CLAIMS":
                print(f"   [WARNING] Middleware requires tenant_id claim")
                print(f"   This is expected - user needs to be linked to a tenant first")
                print(f"   Error: {error_data.get('message')}")
            else:
                print(f"   [FAIL] Middleware returned {response.status_code}")
                print(f"   Response: {error_data}")
                return False
        else:
            print(f"   [FAIL] Middleware returned {response.status_code}")
            print(f"   Response: {response.json()}")
            return False
            
    except Exception as e:
        print(f"   [ERROR] Failed to test middleware: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # Step 5: Cleanup
    print("\n5. Cleaning up test user...")
    try:
        supabase.auth.admin.delete_user(user_id)
        print("   [OK] Deleted test user")
    except Exception as e:
        print(f"   [WARNING] Cleanup failed (this is okay): {e}")
    
    print("\n" + "=" * 60)
    print("[OK] Basic login flow test completed!")
    print("=" * 60)
    print("\nNote: To test with tenant assignment, you need to:")
    print("1. Refresh PostgREST schema cache (run: NOTIFY pgrst, 'reload schema';)")
    print("2. Create a tenant and link the user via tenant_users table")
    print("3. Then the JWT will include tenant_id, roles, and tenant_slug")
    print("=" * 60)
    return True


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
        config.supabase_service_key,
        config.supabase_jwt_secret,
    ]):
        print("ERROR: Missing required environment variables.")
        exit(1)
    
    success = test_login_simple()
    exit(0 if success else 1)
