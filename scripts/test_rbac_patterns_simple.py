"""Simple script to test RBAC access patterns without middleware dependencies."""
import sys
import os
import base64
import secrets

# Set dummy environment variables for testing
os.environ["ENCRYPTION_KEY"] = base64.urlsafe_b64encode(secrets.token_bytes(32)).decode('utf-8')
os.environ["AUTH0_DOMAIN"] = "test.auth0.com"
os.environ["AUTH0_MANAGEMENT_CLIENT_ID"] = "test-client-id"
os.environ["AUTH0_MANAGEMENT_CLIENT_SECRET"] = "test-client-secret"
os.environ["AUTH0_DATABASE_CONNECTION_NAME"] = "test-connection"

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI, Depends
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
from src.auth.jwt_validator import JWTClaims
from src.auth.decorators import requires_role, requires_permission
from src.auth.dependencies import get_current_user_claims

# Create a simple test app without middleware
test_app = FastAPI()

# Test endpoints with RBAC decorators
@test_app.post("/admin-only")
@requires_role("Admin")
async def admin_endpoint(claims: JWTClaims = Depends(get_current_user_claims)):
    return {"message": "Admin access granted", "role": "admin"}

@test_app.post("/analyst-only")
@requires_role("Analyst")
async def analyst_endpoint(claims: JWTClaims = Depends(get_current_user_claims)):
    return {"message": "Analyst access granted", "role": "analyst"}

@test_app.post("/viewer-only")
@requires_role("Viewer")
async def viewer_endpoint(claims: JWTClaims = Depends(get_current_user_claims)):
    return {"message": "Viewer access granted", "role": "viewer"}

@test_app.post("/admin-or-analyst")
@requires_role("Admin", "Analyst")
async def admin_or_analyst_endpoint(claims: JWTClaims = Depends(get_current_user_claims)):
    return {"message": "Admin or Analyst access granted"}

@test_app.post("/upload-document")
@requires_permission("upload_document")
async def upload_document_endpoint(claims: JWTClaims = Depends(get_current_user_claims)):
    return {"message": "Document upload granted"}

@test_app.get("/view-document")
@requires_permission("view_document")
async def view_document_endpoint(claims: JWTClaims = Depends(get_current_user_claims)):
    return {"message": "Document view granted"}

@test_app.post("/create-user")
@requires_permission("create_user")
async def create_user_endpoint(claims: JWTClaims = Depends(get_current_user_claims)):
    return {"message": "User creation granted"}


def test_role_access():
    """Test role-based access patterns."""
    print("\n" + "="*60)
    print("  Role-Based Access Pattern Testing")
    print("="*60)
    
    client = TestClient(test_app)
    
    # Test data
    admin_claims = JWTClaims(
        tenant_id="550e8400-e29b-41d4-a716-446655440000",
        roles=["admin"],
        user_id="auth0|admin-123",
        email="admin@example.com"
    )
    
    analyst_claims = JWTClaims(
        tenant_id="550e8400-e29b-41d4-a716-446655440000",
        roles=["analyst"],
        user_id="auth0|analyst-456",
        email="analyst@example.com"
    )
    
    viewer_claims = JWTClaims(
        tenant_id="550e8400-e29b-41d4-a716-446655440000",
        roles=["viewer"],
        user_id="auth0|viewer-789",
        email="viewer@example.com"
    )
    
    total_passed = 0
    total_failed = 0
    
    # Test Admin Access
    print("\n=== Testing Admin Role ===")
    with patch("src.auth.decorators.get_current_user_claims") as mock_get:
        mock_get.return_value = admin_claims
        
        tests = [
            ("POST /admin-only", "post", "/admin-only", True),
            ("POST /analyst-only", "post", "/analyst-only", False),  # Should fail
            ("POST /viewer-only", "post", "/viewer-only", False),  # Should fail
            ("POST /admin-or-analyst", "post", "/admin-or-analyst", True),
            ("POST /upload-document", "post", "/upload-document", True),
            ("GET /view-document", "get", "/view-document", True),
            ("POST /create-user", "post", "/create-user", True),
        ]
        
        for test_name, method, path, should_pass in tests:
            response = getattr(client, method)(path, headers={"Authorization": "Bearer fake-token"})
            if should_pass:
                if response.status_code == 200:
                    print(f"  [PASS] {test_name}")
                    total_passed += 1
                else:
                    print(f"  [FAIL] {test_name} - Expected 200, got {response.status_code}")
                    total_failed += 1
            else:
                if response.status_code == 403:
                    print(f"  [PASS] {test_name} - Correctly denied")
                    total_passed += 1
                else:
                    print(f"  [FAIL] {test_name} - Expected 403, got {response.status_code}")
                    total_failed += 1
    
    # Test Analyst Access
    print("\n=== Testing Analyst Role ===")
    with patch("src.auth.decorators.get_current_user_claims") as mock_get:
        mock_get.return_value = analyst_claims
        
        tests = [
            ("POST /admin-only", "post", "/admin-only", False),  # Should fail
            ("POST /analyst-only", "post", "/analyst-only", True),
            ("POST /viewer-only", "post", "/viewer-only", False),  # Should fail
            ("POST /admin-or-analyst", "post", "/admin-or-analyst", True),
            ("POST /upload-document", "post", "/upload-document", True),
            ("GET /view-document", "get", "/view-document", True),
            ("POST /create-user", "post", "/create-user", False),  # Should fail
        ]
        
        for test_name, method, path, should_pass in tests:
            response = getattr(client, method)(path, headers={"Authorization": "Bearer fake-token"})
            if should_pass:
                if response.status_code == 200:
                    print(f"  [PASS] {test_name}")
                    total_passed += 1
                else:
                    print(f"  [FAIL] {test_name} - Expected 200, got {response.status_code}")
                    total_failed += 1
            else:
                if response.status_code == 403:
                    print(f"  [PASS] {test_name} - Correctly denied")
                    total_passed += 1
                else:
                    print(f"  [FAIL] {test_name} - Expected 403, got {response.status_code}")
                    total_failed += 1
    
    # Test Viewer Access
    print("\n=== Testing Viewer Role ===")
    with patch("src.auth.decorators.get_current_user_claims") as mock_get:
        mock_get.return_value = viewer_claims
        
        tests = [
            ("POST /admin-only", "post", "/admin-only", False),  # Should fail
            ("POST /analyst-only", "post", "/analyst-only", False),  # Should fail
            ("POST /viewer-only", "post", "/viewer-only", True),
            ("POST /admin-or-analyst", "post", "/admin-or-analyst", False),  # Should fail
            ("POST /upload-document", "post", "/upload-document", False),  # Should fail
            ("GET /view-document", "get", "/view-document", True),
            ("POST /create-user", "post", "/create-user", False),  # Should fail
        ]
        
        for test_name, method, path, should_pass in tests:
            response = getattr(client, method)(path, headers={"Authorization": "Bearer fake-token"})
            if should_pass:
                if response.status_code == 200:
                    print(f"  [PASS] {test_name}")
                    total_passed += 1
                else:
                    print(f"  [FAIL] {test_name} - Expected 200, got {response.status_code}")
                    total_failed += 1
            else:
                if response.status_code == 403:
                    print(f"  [PASS] {test_name} - Correctly denied")
                    total_passed += 1
                else:
                    print(f"  [FAIL] {test_name} - Expected 403, got {response.status_code}")
                    total_failed += 1
    
    # Summary
    print("\n" + "="*60)
    print("  Test Summary")
    print("="*60)
    print(f"  Total Passed: {total_passed}")
    print(f"  Total Failed: {total_failed}")
    print(f"  Total Tests: {total_passed + total_failed}")
    
    if total_failed == 0:
        print("\n  [SUCCESS] All role access patterns verified!")
        return 0
    else:
        print("\n  [FAILURE] Some tests failed. Please review.")
        return 1


if __name__ == "__main__":
    exit(test_role_access())
