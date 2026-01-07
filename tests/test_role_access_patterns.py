"""Comprehensive tests for role-based access patterns."""
import pytest
from unittest.mock import Mock, patch, AsyncMock
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from fastapi import Depends

from src.auth.jwt_validator import JWTClaims
from src.auth.dependencies import get_current_user_claims
from src.auth.roles import Role, Permission
from src.api.routes import tenants, rbac_examples, example_jwt_usage, example_tenant_usage
from src.api.main import app


class TestAdminAccessPatterns:
    """Test Admin role access patterns."""
    
    @pytest.fixture
    def admin_claims(self):
        """Create admin JWT claims."""
        return JWTClaims(
            tenant_id="550e8400-e29b-41d4-a716-446655440000",
            roles=["admin"],
            user_id="auth0|admin-123",
            email="admin@example.com"
        )
    
    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)
    
    def test_admin_can_access_tenant_provisioning(self, admin_claims, client):
        """Test admin can create tenants."""
        with patch("src.auth.dependencies.get_current_user_claims") as mock_get:
            mock_get.return_value = admin_claims
            
            response = client.post(
                "/api/v1/tenants",
                json={"name": "test-tenant", "environment": "development"},
                headers={"Authorization": "Bearer fake-token"}
            )
            
            # Should not be 403 (might be 500 due to missing DB, but not 403)
            assert response.status_code != 403, "Admin should have access to tenant provisioning"
    
    def test_admin_can_access_user_management(self, admin_claims, client):
        """Test admin can manage users."""
        with patch("src.auth.dependencies.get_current_user_claims") as mock_get:
            mock_get.return_value = admin_claims
            
            # Create user
            response = client.post(
                "/api/v1/rbac-examples/users",
                headers={"Authorization": "Bearer fake-token"}
            )
            assert response.status_code == 200, "Admin should create users"
            
            # List users
            response = client.get(
                "/api/v1/rbac-examples/users",
                headers={"Authorization": "Bearer fake-token"}
            )
            assert response.status_code == 200, "Admin should list users"
            
            # Delete user
            response = client.delete(
                "/api/v1/rbac-examples/users/user-123",
                headers={"Authorization": "Bearer fake-token"}
            )
            assert response.status_code == 200, "Admin should delete users"
    
    def test_admin_can_access_billing(self, admin_claims, client):
        """Test admin can access billing."""
        with patch("src.auth.dependencies.get_current_user_claims") as mock_get:
            mock_get.return_value = admin_claims
            
            response = client.get(
                "/api/v1/rbac-examples/billing",
                headers={"Authorization": "Bearer fake-token"}
            )
            assert response.status_code == 200, "Admin should access billing"
    
    def test_admin_can_modify_tenant_settings(self, admin_claims, client):
        """Test admin can modify tenant settings."""
        with patch("src.auth.dependencies.get_current_user_claims") as mock_get:
            mock_get.return_value = admin_claims
            
            response = client.patch(
                "/api/v1/rbac-examples/tenant/settings",
                json={"setting": "value"},
                headers={"Authorization": "Bearer fake-token"}
            )
            assert response.status_code == 200, "Admin should modify tenant settings"
    
    def test_admin_can_access_all_document_operations(self, admin_claims, client):
        """Test admin can perform all document operations."""
        with patch("src.auth.dependencies.get_current_user_claims") as mock_get:
            mock_get.return_value = admin_claims
            
            # Upload
            response = client.post(
                "/api/v1/rbac-examples/documents",
                json={"content": "test"},
                headers={"Authorization": "Bearer fake-token"}
            )
            assert response.status_code == 200, "Admin should upload documents"
            
            # Edit
            response = client.put(
                "/api/v1/rbac-examples/documents/doc-123",
                json={"content": "updated"},
                headers={"Authorization": "Bearer fake-token"}
            )
            assert response.status_code == 200, "Admin should edit documents"
            
            # Delete
            response = client.delete(
                "/api/v1/rbac-examples/documents/doc-123",
                headers={"Authorization": "Bearer fake-token"}
            )
            assert response.status_code == 200, "Admin should delete documents"
            
            # View
            response = client.get(
                "/api/v1/rbac-examples/documents/doc-123",
                headers={"Authorization": "Bearer fake-token"}
            )
            assert response.status_code == 200, "Admin should view documents"
            
            # Search
            response = client.get(
                "/api/v1/rbac-examples/documents/search?query=test",
                headers={"Authorization": "Bearer fake-token"}
            )
            assert response.status_code == 200, "Admin should search documents"
    
    def test_admin_can_override_ai_decisions(self, admin_claims, client):
        """Test admin can override AI decisions."""
        with patch("src.auth.dependencies.get_current_user_claims") as mock_get:
            mock_get.return_value = admin_claims
            
            response = client.post(
                "/api/v1/rbac-examples/ai/override",
                json={"decision": "override"},
                headers={"Authorization": "Bearer fake-token"}
            )
            assert response.status_code == 200, "Admin should override AI decisions"


class TestAnalystAccessPatterns:
    """Test Analyst role access patterns."""
    
    @pytest.fixture
    def analyst_claims(self):
        """Create analyst JWT claims."""
        return JWTClaims(
            tenant_id="550e8400-e29b-41d4-a716-446655440000",
            roles=["analyst"],
            user_id="auth0|analyst-456",
            email="analyst@example.com"
        )
    
    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)
    
    def test_analyst_cannot_access_tenant_provisioning(self, analyst_claims, client):
        """Test analyst cannot create tenants."""
        with patch("src.auth.dependencies.get_current_user_claims") as mock_get:
            mock_get.return_value = analyst_claims
            
            response = client.post(
                "/api/v1/tenants",
                json={"name": "test-tenant", "environment": "development"},
                headers={"Authorization": "Bearer fake-token"}
            )
            
            assert response.status_code == 403, "Analyst should NOT have access to tenant provisioning"
            assert "Required role" in response.json()["detail"] or "Required permission" in response.json()["detail"]
    
    def test_analyst_cannot_manage_users(self, analyst_claims, client):
        """Test analyst cannot manage users."""
        with patch("src.auth.dependencies.get_current_user_claims") as mock_get:
            mock_get.return_value = analyst_claims
            
            # Create user - should fail
            response = client.post(
                "/api/v1/rbac-examples/users",
                headers={"Authorization": "Bearer fake-token"}
            )
            assert response.status_code == 403, "Analyst should NOT create users"
            
            # List users - should fail
            response = client.get(
                "/api/v1/rbac-examples/users",
                headers={"Authorization": "Bearer fake-token"}
            )
            assert response.status_code == 403, "Analyst should NOT list users"
            
            # Delete user - should fail
            response = client.delete(
                "/api/v1/rbac-examples/users/user-123",
                headers={"Authorization": "Bearer fake-token"}
            )
            assert response.status_code == 403, "Analyst should NOT delete users"
    
    def test_analyst_cannot_access_billing(self, analyst_claims, client):
        """Test analyst cannot access billing."""
        with patch("src.auth.dependencies.get_current_user_claims") as mock_get:
            mock_get.return_value = analyst_claims
            
            response = client.get(
                "/api/v1/rbac-examples/billing",
                headers={"Authorization": "Bearer fake-token"}
            )
            assert response.status_code == 403, "Analyst should NOT access billing"
    
    def test_analyst_cannot_modify_tenant_settings(self, analyst_claims, client):
        """Test analyst cannot modify tenant settings."""
        with patch("src.auth.dependencies.get_current_user_claims") as mock_get:
            mock_get.return_value = analyst_claims
            
            response = client.patch(
                "/api/v1/rbac-examples/tenant/settings",
                json={"setting": "value"},
                headers={"Authorization": "Bearer fake-token"}
            )
            assert response.status_code == 403, "Analyst should NOT modify tenant settings"
    
    def test_analyst_can_access_document_operations(self, analyst_claims, client):
        """Test analyst can perform document operations."""
        with patch("src.auth.dependencies.get_current_user_claims") as mock_get:
            mock_get.return_value = analyst_claims
            
            # Upload
            response = client.post(
                "/api/v1/rbac-examples/documents",
                json={"content": "test"},
                headers={"Authorization": "Bearer fake-token"}
            )
            assert response.status_code == 200, "Analyst should upload documents"
            
            # Edit
            response = client.put(
                "/api/v1/rbac-examples/documents/doc-123",
                json={"content": "updated"},
                headers={"Authorization": "Bearer fake-token"}
            )
            assert response.status_code == 200, "Analyst should edit documents"
            
            # Delete
            response = client.delete(
                "/api/v1/rbac-examples/documents/doc-123",
                headers={"Authorization": "Bearer fake-token"}
            )
            assert response.status_code == 200, "Analyst should delete documents"
            
            # View
            response = client.get(
                "/api/v1/rbac-examples/documents/doc-123",
                headers={"Authorization": "Bearer fake-token"}
            )
            assert response.status_code == 200, "Analyst should view documents"
            
            # Search
            response = client.get(
                "/api/v1/rbac-examples/documents/search?query=test",
                headers={"Authorization": "Bearer fake-token"}
            )
            assert response.status_code == 200, "Analyst should search documents"
    
    def test_analyst_can_override_ai_decisions(self, analyst_claims, client):
        """Test analyst can override AI decisions."""
        with patch("src.auth.dependencies.get_current_user_claims") as mock_get:
            mock_get.return_value = analyst_claims
            
            response = client.post(
                "/api/v1/rbac-examples/ai/override",
                json={"decision": "override"},
                headers={"Authorization": "Bearer fake-token"}
            )
            assert response.status_code == 200, "Analyst should override AI decisions"
    
    def test_analyst_can_view_tenant_settings(self, analyst_claims, client):
        """Test analyst can view tenant settings (read-only)."""
        with patch("src.auth.dependencies.get_current_user_claims") as mock_get:
            mock_get.return_value = analyst_claims
            
            response = client.get(
                "/api/v1/rbac-examples/tenant/settings",
                headers={"Authorization": "Bearer fake-token"}
            )
            assert response.status_code == 200, "Analyst should view tenant settings"


class TestViewerAccessPatterns:
    """Test Viewer role access patterns."""
    
    @pytest.fixture
    def viewer_claims(self):
        """Create viewer JWT claims."""
        return JWTClaims(
            tenant_id="550e8400-e29b-41d4-a716-446655440000",
            roles=["viewer"],
            user_id="auth0|viewer-789",
            email="viewer@example.com"
        )
    
    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)
    
    def test_viewer_cannot_access_tenant_provisioning(self, viewer_claims, client):
        """Test viewer cannot create tenants."""
        with patch("src.auth.dependencies.get_current_user_claims") as mock_get:
            mock_get.return_value = viewer_claims
            
            response = client.post(
                "/api/v1/tenants",
                json={"name": "test-tenant", "environment": "development"},
                headers={"Authorization": "Bearer fake-token"}
            )
            
            assert response.status_code == 403, "Viewer should NOT have access to tenant provisioning"
    
    def test_viewer_cannot_manage_users(self, viewer_claims, client):
        """Test viewer cannot manage users."""
        with patch("src.auth.dependencies.get_current_user_claims") as mock_get:
            mock_get.return_value = viewer_claims
            
            # Create user - should fail
            response = client.post(
                "/api/v1/rbac-examples/users",
                headers={"Authorization": "Bearer fake-token"}
            )
            assert response.status_code == 403, "Viewer should NOT create users"
    
    def test_viewer_cannot_access_billing(self, viewer_claims, client):
        """Test viewer cannot access billing."""
        with patch("src.auth.dependencies.get_current_user_claims") as mock_get:
            mock_get.return_value = viewer_claims
            
            response = client.get(
                "/api/v1/rbac-examples/billing",
                headers={"Authorization": "Bearer fake-token"}
            )
            assert response.status_code == 403, "Viewer should NOT access billing"
    
    def test_viewer_cannot_modify_documents(self, viewer_claims, client):
        """Test viewer cannot modify documents."""
        with patch("src.auth.dependencies.get_current_user_claims") as mock_get:
            mock_get.return_value = viewer_claims
            
            # Upload - should fail
            response = client.post(
                "/api/v1/rbac-examples/documents",
                json={"content": "test"},
                headers={"Authorization": "Bearer fake-token"}
            )
            assert response.status_code == 403, "Viewer should NOT upload documents"
            
            # Edit - should fail
            response = client.put(
                "/api/v1/rbac-examples/documents/doc-123",
                json={"content": "updated"},
                headers={"Authorization": "Bearer fake-token"}
            )
            assert response.status_code == 403, "Viewer should NOT edit documents"
            
            # Delete - should fail
            response = client.delete(
                "/api/v1/rbac-examples/documents/doc-123",
                headers={"Authorization": "Bearer fake-token"}
            )
            assert response.status_code == 403, "Viewer should NOT delete documents"
    
    def test_viewer_can_view_documents(self, viewer_claims, client):
        """Test viewer can view documents (read-only)."""
        with patch("src.auth.dependencies.get_current_user_claims") as mock_get:
            mock_get.return_value = viewer_claims
            
            # View
            response = client.get(
                "/api/v1/rbac-examples/documents/doc-123",
                headers={"Authorization": "Bearer fake-token"}
            )
            assert response.status_code == 200, "Viewer should view documents"
            
            # Search
            response = client.get(
                "/api/v1/rbac-examples/documents/search?query=test",
                headers={"Authorization": "Bearer fake-token"}
            )
            assert response.status_code == 200, "Viewer should search documents"
    
    def test_viewer_cannot_override_ai_decisions(self, viewer_claims, client):
        """Test viewer cannot override AI decisions."""
        with patch("src.auth.dependencies.get_current_user_claims") as mock_get:
            mock_get.return_value = viewer_claims
            
            response = client.post(
                "/api/v1/rbac-examples/ai/override",
                json={"decision": "override"},
                headers={"Authorization": "Bearer fake-token"}
            )
            assert response.status_code == 403, "Viewer should NOT override AI decisions"
    
    def test_viewer_can_view_tenant_settings(self, viewer_claims, client):
        """Test viewer can view tenant settings (read-only)."""
        with patch("src.auth.dependencies.get_current_user_claims") as mock_get:
            mock_get.return_value = viewer_claims
            
            response = client.get(
                "/api/v1/rbac-examples/tenant/settings",
                headers={"Authorization": "Bearer fake-token"}
            )
            assert response.status_code == 200, "Viewer should view tenant settings"


class TestMultiRoleAccessPatterns:
    """Test multi-role access patterns."""
    
    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)
    
    def test_all_roles_can_access_list_documents(self, client):
        """Test all roles can list documents."""
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
                assert response.status_code == 200, f"{role.capitalize()} should list documents"
    
    def test_admin_and_analyst_can_access_moderator_endpoint(self, client):
        """Test admin and analyst can access moderator endpoint."""
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
                assert response.status_code == 200, f"{role.capitalize()} should access moderator endpoint"
        
        # Viewer should NOT access
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
            assert response.status_code == 403, "Viewer should NOT access moderator endpoint"


class TestPermissionBasedAccess:
    """Test permission-based access patterns."""
    
    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)
    
    def test_permission_based_document_access(self, client):
        """Test permission-based document access."""
        # Admin has all permissions
        admin_claims = JWTClaims(
            tenant_id="550e8400-e29b-41d4-a716-446655440000",
            roles=["admin"],
            user_id="auth0|admin-test",
            email="admin@example.com"
        )
        
        with patch("src.auth.dependencies.get_current_user_claims") as mock_get:
            mock_get.return_value = admin_claims
            
            response = client.post(
                "/api/v1/rbac-examples/documents",
                json={"content": "test"},
                headers={"Authorization": "Bearer fake-token"}
            )
            assert response.status_code == 200, "Admin should have upload_document permission"
        
        # Analyst has upload permission
        analyst_claims = JWTClaims(
            tenant_id="550e8400-e29b-41d4-a716-446655440000",
            roles=["analyst"],
            user_id="auth0|analyst-test",
            email="analyst@example.com"
        )
        
        with patch("src.auth.dependencies.get_current_user_claims") as mock_get:
            mock_get.return_value = analyst_claims
            
            response = client.post(
                "/api/v1/rbac-examples/documents",
                json={"content": "test"},
                headers={"Authorization": "Bearer fake-token"}
            )
            assert response.status_code == 200, "Analyst should have upload_document permission"
        
        # Viewer does NOT have upload permission
        viewer_claims = JWTClaims(
            tenant_id="550e8400-e29b-41d4-a716-446655440000",
            roles=["viewer"],
            user_id="auth0|viewer-test",
            email="viewer@example.com"
        )
        
        with patch("src.auth.dependencies.get_current_user_claims") as mock_get:
            mock_get.return_value = viewer_claims
            
            response = client.post(
                "/api/v1/rbac-examples/documents",
                json={"content": "test"},
                headers={"Authorization": "Bearer fake-token"}
            )
            assert response.status_code == 403, "Viewer should NOT have upload_document permission"
