"""Script to test role-based access patterns for all endpoints."""
import sys
import os
import base64
import secrets

# Set dummy ENCRYPTION_KEY for testing
os.environ["ENCRYPTION_KEY"] = base64.urlsafe_b64encode(secrets.token_bytes(32)).decode('utf-8')

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
from src.auth.jwt_validator import JWTClaims
from src.api.main import app

# Color codes for terminal output
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
RESET = "\033[0m"


def print_test_result(test_name: str, passed: bool, message: str = ""):
    """Print test result with color coding."""
    status = f"{GREEN}PASS{RESET}" if passed else f"{RED}FAIL{RESET}"
    print(f"  {status} {test_name}")
    if message:
        print(f"      {message}")


def test_admin_access(client: TestClient):
    """Test Admin role access patterns."""
    print(f"\n{BLUE}=== Testing Admin Role Access ==={RESET}")
    
    admin_claims = JWTClaims(
        tenant_id="550e8400-e29b-41d4-a716-446655440000",
        roles=["admin"],
        user_id="auth0|admin-123",
        email="admin@example.com"
    )
    
    with patch("src.auth.dependencies.get_current_user_claims") as mock_get:
        mock_get.return_value = admin_claims
        
        # Test admin-only endpoints
        tests = [
            ("POST /api/v1/rbac-examples/users", "post", "/api/v1/rbac-examples/users", {}),
            ("GET /api/v1/rbac-examples/users", "get", "/api/v1/rbac-examples/users", {}),
            ("DELETE /api/v1/rbac-examples/users/user-123", "delete", "/api/v1/rbac-examples/users/user-123", {}),
            ("GET /api/v1/rbac-examples/billing", "get", "/api/v1/rbac-examples/billing", {}),
            ("PATCH /api/v1/rbac-examples/tenant/settings", "patch", "/api/v1/rbac-examples/tenant/settings", {"json": {"setting": "value"}}),
            ("POST /api/v1/rbac-examples/documents", "post", "/api/v1/rbac-examples/documents", {"json": {"content": "test"}}),
            ("PUT /api/v1/rbac-examples/documents/doc-123", "put", "/api/v1/rbac-examples/documents/doc-123", {"json": {"content": "updated"}}),
            ("DELETE /api/v1/rbac-examples/documents/doc-123", "delete", "/api/v1/rbac-examples/documents/doc-123", {}),
            ("GET /api/v1/rbac-examples/documents/doc-123", "get", "/api/v1/rbac-examples/documents/doc-123", {}),
            ("GET /api/v1/rbac-examples/documents/search", "get", "/api/v1/rbac-examples/documents/search?query=test", {}),
            ("POST /api/v1/rbac-examples/ai/override", "post", "/api/v1/rbac-examples/ai/override", {"json": {"decision": "override"}}),
        ]
        
        passed = 0
        failed = 0
        
        for test_name, method, path, kwargs in tests:
            headers = {"Authorization": "Bearer fake-token"}
            kwargs["headers"] = headers
            
            try:
                response = getattr(client, method)(path, **kwargs)
                if response.status_code == 200:
                    print_test_result(test_name, True)
                    passed += 1
                else:
                    print_test_result(test_name, False, f"Status: {response.status_code}")
                    failed += 1
            except Exception as e:
                print_test_result(test_name, False, f"Error: {str(e)}")
                failed += 1
        
        print(f"\n  {GREEN}Passed: {passed}{RESET} | {RED}Failed: {failed}{RESET}")
        return passed, failed


def test_analyst_access(client: TestClient):
    """Test Analyst role access patterns."""
    print(f"\n{BLUE}=== Testing Analyst Role Access ==={RESET}")
    
    analyst_claims = JWTClaims(
        tenant_id="550e8400-e29b-41d4-a716-446655440000",
        roles=["analyst"],
        user_id="auth0|analyst-456",
        email="analyst@example.com"
    )
    
    with patch("src.auth.dependencies.get_current_user_claims") as mock_get:
        mock_get.return_value = analyst_claims
        
        # Test analyst should NOT access (should be 403)
        denied_tests = [
            ("POST /api/v1/rbac-examples/users", "post", "/api/v1/rbac-examples/users", {}),
            ("GET /api/v1/rbac-examples/users", "get", "/api/v1/rbac-examples/users", {}),
            ("GET /api/v1/rbac-examples/billing", "get", "/api/v1/rbac-examples/billing", {}),
            ("PATCH /api/v1/rbac-examples/tenant/settings", "patch", "/api/v1/rbac-examples/tenant/settings", {"json": {"setting": "value"}}),
        ]
        
        # Test analyst SHOULD access (should be 200)
        allowed_tests = [
            ("POST /api/v1/rbac-examples/documents", "post", "/api/v1/rbac-examples/documents", {"json": {"content": "test"}}),
            ("PUT /api/v1/rbac-examples/documents/doc-123", "put", "/api/v1/rbac-examples/documents/doc-123", {"json": {"content": "updated"}}),
            ("DELETE /api/v1/rbac-examples/documents/doc-123", "delete", "/api/v1/rbac-examples/documents/doc-123", {}),
            ("GET /api/v1/rbac-examples/documents/doc-123", "get", "/api/v1/rbac-examples/documents/doc-123", {}),
            ("GET /api/v1/rbac-examples/documents/search", "get", "/api/v1/rbac-examples/documents/search?query=test", {}),
            ("POST /api/v1/rbac-examples/ai/override", "post", "/api/v1/rbac-examples/ai/override", {"json": {"decision": "override"}}),
            ("GET /api/v1/rbac-examples/tenant/settings", "get", "/api/v1/rbac-examples/tenant/settings", {}),
        ]
        
        passed = 0
        failed = 0
        
        # Test denied access
        print(f"\n  {YELLOW}Testing Denied Access:{RESET}")
        for test_name, method, path, kwargs in denied_tests:
            headers = {"Authorization": "Bearer fake-token"}
            kwargs["headers"] = headers
            
            try:
                response = getattr(client, method)(path, **kwargs)
                if response.status_code == 403:
                    print_test_result(test_name, True, "Correctly denied")
                    passed += 1
                else:
                    print_test_result(test_name, False, f"Should be 403, got {response.status_code}")
                    failed += 1
            except Exception as e:
                print_test_result(test_name, False, f"Error: {str(e)}")
                failed += 1
        
        # Test allowed access
        print(f"\n  {YELLOW}Testing Allowed Access:{RESET}")
        for test_name, method, path, kwargs in allowed_tests:
            headers = {"Authorization": "Bearer fake-token"}
            kwargs["headers"] = headers
            
            try:
                response = getattr(client, method)(path, **kwargs)
                if response.status_code == 200:
                    print_test_result(test_name, True)
                    passed += 1
                else:
                    print_test_result(test_name, False, f"Status: {response.status_code}")
                    failed += 1
            except Exception as e:
                print_test_result(test_name, False, f"Error: {str(e)}")
                failed += 1
        
        print(f"\n  {GREEN}Passed: {passed}{RESET} | {RED}Failed: {failed}{RESET}")
        return passed, failed


def test_viewer_access(client: TestClient):
    """Test Viewer role access patterns."""
    print(f"\n{BLUE}=== Testing Viewer Role Access ==={RESET}")
    
    viewer_claims = JWTClaims(
        tenant_id="550e8400-e29b-41d4-a716-446655440000",
        roles=["viewer"],
        user_id="auth0|viewer-789",
        email="viewer@example.com"
    )
    
    with patch("src.auth.dependencies.get_current_user_claims") as mock_get:
        mock_get.return_value = viewer_claims
        
        # Test viewer should NOT access (should be 403)
        denied_tests = [
            ("POST /api/v1/rbac-examples/users", "post", "/api/v1/rbac-examples/users", {}),
            ("GET /api/v1/rbac-examples/billing", "get", "/api/v1/rbac-examples/billing", {}),
            ("POST /api/v1/rbac-examples/documents", "post", "/api/v1/rbac-examples/documents", {"json": {"content": "test"}}),
            ("PUT /api/v1/rbac-examples/documents/doc-123", "put", "/api/v1/rbac-examples/documents/doc-123", {"json": {"content": "updated"}}),
            ("DELETE /api/v1/rbac-examples/documents/doc-123", "delete", "/api/v1/rbac-examples/documents/doc-123", {}),
            ("POST /api/v1/rbac-examples/ai/override", "post", "/api/v1/rbac-examples/ai/override", {"json": {"decision": "override"}}),
        ]
        
        # Test viewer SHOULD access (should be 200)
        allowed_tests = [
            ("GET /api/v1/rbac-examples/documents/doc-123", "get", "/api/v1/rbac-examples/documents/doc-123", {}),
            ("GET /api/v1/rbac-examples/documents/search", "get", "/api/v1/rbac-examples/documents/search?query=test", {}),
            ("GET /api/v1/rbac-examples/tenant/settings", "get", "/api/v1/rbac-examples/tenant/settings", {}),
        ]
        
        passed = 0
        failed = 0
        
        # Test denied access
        print(f"\n  {YELLOW}Testing Denied Access:{RESET}")
        for test_name, method, path, kwargs in denied_tests:
            headers = {"Authorization": "Bearer fake-token"}
            kwargs["headers"] = headers
            
            try:
                response = getattr(client, method)(path, **kwargs)
                if response.status_code == 403:
                    print_test_result(test_name, True, "Correctly denied")
                    passed += 1
                else:
                    print_test_result(test_name, False, f"Should be 403, got {response.status_code}")
                    failed += 1
            except Exception as e:
                print_test_result(test_name, False, f"Error: {str(e)}")
                failed += 1
        
        # Test allowed access
        print(f"\n  {YELLOW}Testing Allowed Access:{RESET}")
        for test_name, method, path, kwargs in allowed_tests:
            headers = {"Authorization": "Bearer fake-token"}
            kwargs["headers"] = headers
            
            try:
                response = getattr(client, method)(path, **kwargs)
                if response.status_code == 200:
                    print_test_result(test_name, True)
                    passed += 1
                else:
                    print_test_result(test_name, False, f"Status: {response.status_code}")
                    failed += 1
            except Exception as e:
                print_test_result(test_name, False, f"Error: {str(e)}")
                failed += 1
        
        print(f"\n  {GREEN}Passed: {passed}{RESET} | {RED}Failed: {failed}{RESET}")
        return passed, failed


def test_multi_role_access(client: TestClient):
    """Test multi-role access patterns."""
    print(f"\n{BLUE}=== Testing Multi-Role Access ==={RESET}")
    
    passed = 0
    failed = 0
    
    # Test all roles can access list documents
    roles = ["admin", "analyst", "viewer"]
    for role in roles:
        claims = JWTClaims(
            tenant_id="550e8400-e29b-41d4-a716-446655440000",
            roles=[role],
            user_id=f"auth0|{role}-test",
            email=f"{role}@example.com"
        )
        
        with patch("src.auth.dependencies.get_current_user_claims") as mock_get:
            mock_get.return_value = claims
            
            response = client.get(
                "/api/v1/rbac-examples/documents",
                headers={"Authorization": "Bearer fake-token"}
            )
            
            if response.status_code == 200:
                print_test_result(f"GET /api/v1/rbac-examples/documents ({role})", True)
                passed += 1
            else:
                print_test_result(f"GET /api/v1/rbac-examples/documents ({role})", False, f"Status: {response.status_code}")
                failed += 1
    
    # Test admin and analyst can access moderator endpoint
    for role in ["admin", "analyst"]:
        claims = JWTClaims(
            tenant_id="550e8400-e29b-41d4-a716-446655440000",
            roles=[role],
            user_id=f"auth0|{role}-test",
            email=f"{role}@example.com"
        )
        
        with patch("src.auth.dependencies.get_current_user_claims") as mock_get:
            mock_get.return_value = claims
            
            response = client.get(
                "/api/v1/example/moderator-or-admin",
                headers={"Authorization": "Bearer fake-token"}
            )
            
            if response.status_code == 200:
                print_test_result(f"GET /api/v1/example/moderator-or-admin ({role})", True)
                passed += 1
            else:
                print_test_result(f"GET /api/v1/example/moderator-or-admin ({role})", False, f"Status: {response.status_code}")
                failed += 1
    
    # Test viewer cannot access moderator endpoint
    viewer_claims = JWTClaims(
        tenant_id="550e8400-e29b-41d4-a716-446655440000",
        roles=["viewer"],
        user_id="auth0|viewer-test",
        email="viewer@example.com"
    )
    
    with patch("src.auth.dependencies.get_current_user_claims") as mock_get:
        mock_get.return_value = viewer_claims
        
        response = client.get(
            "/api/v1/example/moderator-or-admin",
            headers={"Authorization": "Bearer fake-token"}
        )
        
        if response.status_code == 403:
            print_test_result("GET /api/v1/example/moderator-or-admin (viewer)", True, "Correctly denied")
            passed += 1
        else:
            print_test_result("GET /api/v1/example/moderator-or-admin (viewer)", False, f"Should be 403, got {response.status_code}")
            failed += 1
    
    print(f"\n  {GREEN}Passed: {passed}{RESET} | {RED}Failed: {failed}{RESET}")
    return passed, failed


def main():
    """Run all role access pattern tests."""
    print(f"\n{BLUE}{'='*60}{RESET}")
    print(f"{BLUE}  Role-Based Access Pattern Testing{RESET}")
    print(f"{BLUE}{'='*60}{RESET}")
    
    client = TestClient(app)
    
    total_passed = 0
    total_failed = 0
    
    # Test Admin access
    passed, failed = test_admin_access(client)
    total_passed += passed
    total_failed += failed
    
    # Test Analyst access
    passed, failed = test_analyst_access(client)
    total_passed += passed
    total_failed += failed
    
    # Test Viewer access
    passed, failed = test_viewer_access(client)
    total_passed += passed
    total_failed += failed
    
    # Test multi-role access
    passed, failed = test_multi_role_access(client)
    total_passed += passed
    total_failed += failed
    
    # Summary
    print(f"\n{BLUE}{'='*60}{RESET}")
    print(f"{BLUE}  Test Summary{RESET}")
    print(f"{BLUE}{'='*60}{RESET}")
    print(f"  {GREEN}Total Passed: {total_passed}{RESET}")
    print(f"  {RED}Total Failed: {total_failed}{RESET}")
    print(f"  Total Tests: {total_passed + total_failed}")
    
    if total_failed == 0:
        print(f"\n  {GREEN}✓ All role access patterns verified!{RESET}\n")
        return 0
    else:
        print(f"\n  {RED}✗ Some tests failed. Please review.{RESET}\n")
        return 1


if __name__ == "__main__":
    exit(main())
