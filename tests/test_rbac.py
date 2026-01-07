"""Comprehensive tests for Role-Based Access Control."""
import pytest
from unittest.mock import Mock, patch
from fastapi import HTTPException, status
from fastapi.testclient import TestClient
from fastapi import FastAPI

from src.auth.roles import Role, Permission, get_role_permissions
from src.auth.permissions import has_permission, require_role, has_any_role, normalize_role, get_role_from_string
from src.auth.rbac import RequiresRole, RequiresPermission
from src.auth.decorators import requires_role, requires_any_role, requires_permission
from src.auth.jwt_validator import JWTClaims


class TestRoleDefinitions:
    """Tests for role and permission definitions."""
    
    def test_role_enum_values(self):
        """Test role enum has correct values."""
        assert Role.ADMIN.value == "admin"
        assert Role.ANALYST.value == "analyst"
        assert Role.VIEWER.value == "viewer"
    
    def test_permission_enum_values(self):
        """Test permission enum has correct values."""
        assert Permission.CREATE_USER.value == "create_user"
        assert Permission.UPLOAD_DOCUMENT.value == "upload_document"
        assert Permission.VIEW_DOCUMENT.value == "view_document"
    
    def test_admin_has_all_permissions(self):
        """Test admin role has all permissions."""
        admin_perms = get_role_permissions(Role.ADMIN)
        
        # Check key permissions
        assert Permission.CREATE_USER in admin_perms
        assert Permission.DELETE_USER in admin_perms
        assert Permission.MODIFY_TENANT_SETTINGS in admin_perms
        assert Permission.ACCESS_BILLING in admin_perms
        assert Permission.UPLOAD_DOCUMENT in admin_perms
        assert Permission.OVERRIDE_AI_DECISION in admin_perms
        assert Permission.SYSTEM_ADMIN in admin_perms
    
    def test_analyst_permissions(self):
        """Test analyst role has correct permissions."""
        analyst_perms = get_role_permissions(Role.ANALYST)
        
        # Should have document operations
        assert Permission.UPLOAD_DOCUMENT in analyst_perms
        assert Permission.EDIT_DOCUMENT in analyst_perms
        assert Permission.DELETE_DOCUMENT in analyst_perms
        assert Permission.VIEW_DOCUMENT in analyst_perms
        assert Permission.SEARCH_DOCUMENTS in analyst_perms
        assert Permission.OVERRIDE_AI_DECISION in analyst_perms
        
        # Should NOT have user management
        assert Permission.CREATE_USER not in analyst_perms
        assert Permission.DELETE_USER not in analyst_perms
        
        # Should NOT have billing access
        assert Permission.ACCESS_BILLING not in analyst_perms
    
    def test_viewer_permissions(self):
        """Test viewer role has read-only permissions."""
        viewer_perms = get_role_permissions(Role.VIEWER)
        
        # Should have read-only document operations
        assert Permission.VIEW_DOCUMENT in viewer_perms
        assert Permission.SEARCH_DOCUMENTS in viewer_perms
        
        # Should NOT have write operations
        assert Permission.UPLOAD_DOCUMENT not in viewer_perms
        assert Permission.EDIT_DOCUMENT not in viewer_perms
        assert Permission.DELETE_DOCUMENT not in viewer_perms
        
        # Should NOT have user management
        assert Permission.CREATE_USER not in viewer_perms
        assert Permission.DELETE_USER not in viewer_perms
        
        # Should NOT have billing access
        assert Permission.ACCESS_BILLING not in viewer_perms


class TestPermissionChecks:
    """Tests for permission checking functions."""
    
    def test_has_permission_admin(self):
        """Test admin has all permissions."""
        assert has_permission(["admin"], Permission.CREATE_USER)
        assert has_permission(["admin"], Permission.DELETE_USER)
        assert has_permission(["admin"], Permission.ACCESS_BILLING)
        assert has_permission(["admin"], Permission.UPLOAD_DOCUMENT)
    
    def test_has_permission_analyst(self):
        """Test analyst has document permissions but not user management."""
        assert has_permission(["analyst"], Permission.UPLOAD_DOCUMENT)
        assert has_permission(["analyst"], Permission.EDIT_DOCUMENT)
        assert has_permission(["analyst"], Permission.OVERRIDE_AI_DECISION)
        assert not has_permission(["analyst"], Permission.CREATE_USER)
        assert not has_permission(["analyst"], Permission.ACCESS_BILLING)
    
    def test_has_permission_viewer(self):
        """Test viewer has read-only permissions."""
        assert has_permission(["viewer"], Permission.VIEW_DOCUMENT)
        assert has_permission(["viewer"], Permission.SEARCH_DOCUMENTS)
        assert not has_permission(["viewer"], Permission.UPLOAD_DOCUMENT)
        assert not has_permission(["viewer"], Permission.EDIT_DOCUMENT)
        assert not has_permission(["viewer"], Permission.CREATE_USER)
    
    def test_has_permission_multiple_roles(self):
        """Test permission check with multiple roles."""
        assert has_permission(["viewer", "analyst"], Permission.UPLOAD_DOCUMENT)
        assert has_permission(["viewer", "admin"], Permission.CREATE_USER)
    
    def test_has_permission_invalid_role(self):
        """Test permission check with invalid role."""
        assert not has_permission(["invalid_role"], Permission.VIEW_DOCUMENT)
        assert not has_permission([], Permission.VIEW_DOCUMENT)
    
    def test_require_role(self):
        """Test require_role function."""
        assert require_role(["admin"], Role.ADMIN)
        assert require_role(["analyst"], Role.ANALYST)
        assert require_role(["viewer"], Role.VIEWER)
        assert not require_role(["analyst"], Role.ADMIN)
        assert not require_role([], Role.ADMIN)
    
    def test_has_any_role(self):
        """Test has_any_role function."""
        assert has_any_role(["admin"], [Role.ADMIN])
        assert has_any_role(["analyst", "viewer"], [Role.ANALYST])
        assert has_any_role(["viewer"], [Role.ADMIN, Role.VIEWER])
        assert not has_any_role(["viewer"], [Role.ADMIN, Role.ANALYST])
    
    def test_case_insensitive_roles(self):
        """Test case-insensitive role comparison."""
        assert has_permission(["Admin"], Permission.CREATE_USER)
        assert has_permission(["ADMIN"], Permission.CREATE_USER)
        assert has_permission(["admin"], Permission.CREATE_USER)
        assert require_role(["Admin"], Role.ADMIN)
        assert require_role(["ADMIN"], Role.ADMIN)
        assert has_any_role(["Analyst", "Viewer"], [Role.ANALYST])
    
    def test_normalize_role(self):
        """Test role normalization."""
        assert normalize_role("Admin") == "admin"
        assert normalize_role("ADMIN") == "admin"
        assert normalize_role("  admin  ") == "admin"
        assert normalize_role("") == ""
    
    def test_get_role_from_string(self):
        """Test get_role_from_string with caching."""
        assert get_role_from_string("admin") == Role.ADMIN
        assert get_role_from_string("Admin") == Role.ADMIN
        assert get_role_from_string("ADMIN") == Role.ADMIN
        assert get_role_from_string("invalid") is None


class TestRBACDependencies:
    """Tests for RBAC FastAPI dependencies."""
    
    @pytest.fixture
    def mock_claims_admin(self):
        """Create mock JWT claims with admin role."""
        return JWTClaims(
            tenant_id="550e8400-e29b-41d4-a716-446655440000",
            roles=["admin"],
            user_id="auth0|123",
            email="admin@example.com"
        )
    
    @pytest.fixture
    def mock_claims_analyst(self):
        """Create mock JWT claims with analyst role."""
        return JWTClaims(
            tenant_id="550e8400-e29b-41d4-a716-446655440000",
            roles=["analyst"],
            user_id="auth0|456",
            email="analyst@example.com"
        )
    
    @pytest.fixture
    def mock_claims_viewer(self):
        """Create mock JWT claims with viewer role."""
        return JWTClaims(
            tenant_id="550e8400-e29b-41d4-a716-446655440000",
            roles=["viewer"],
            user_id="auth0|789",
            email="viewer@example.com"
        )
    
    @pytest.mark.asyncio
    async def test_requires_role_admin_success(self, mock_claims_admin):
        """Test RequiresRole allows admin access."""
        from fastapi import Request
        from unittest.mock import Mock
        
        mock_request = Mock(spec=Request)
        mock_request.state = type('State', (), {'rbac_cache': {}})()
        mock_request.url.path = "/test"
        
        dependency = RequiresRole(Role.ADMIN)
        
        # Should not raise exception - pass request first, then claims
        result = await dependency(mock_request, mock_claims_admin)
        assert result == mock_claims_admin
    
    @pytest.mark.asyncio
    async def test_requires_role_admin_denied(self, mock_claims_analyst):
        """Test RequiresRole denies non-admin access."""
        from fastapi import Request
        from unittest.mock import Mock
        
        mock_request = Mock(spec=Request)
        mock_request.state = type('State', (), {'rbac_cache': {}})()
        mock_request.url.path = "/test"
        
        dependency = RequiresRole(Role.ADMIN)
        
        with pytest.raises(HTTPException) as exc_info:
            await dependency(mock_request, mock_claims_analyst)
        
        assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN
        assert "Required role(s)" in exc_info.value.detail
    
    @pytest.mark.asyncio
    async def test_requires_role_analyst_success(self, mock_claims_analyst):
        """Test RequiresRole allows analyst access."""
        from fastapi import Request
        from unittest.mock import Mock
        
        mock_request = Mock(spec=Request)
        mock_request.state = type('State', (), {'rbac_cache': {}})()
        mock_request.url.path = "/test"
        
        dependency = RequiresRole(Role.ANALYST)
        result = await dependency(mock_request, mock_claims_analyst)
        assert result == mock_claims_analyst
    
    @pytest.mark.asyncio
    async def test_requires_role_viewer_success(self, mock_claims_viewer):
        """Test RequiresRole allows viewer access."""
        from fastapi import Request
        from unittest.mock import Mock
        
        mock_request = Mock(spec=Request)
        mock_request.state = type('State', (), {'rbac_cache': {}})()
        mock_request.url.path = "/test"
        
        dependency = RequiresRole(Role.VIEWER)
        result = await dependency(mock_request, mock_claims_viewer)
        assert result == mock_claims_viewer
    
    @pytest.mark.asyncio
    async def test_requires_role_multiple_roles(self, mock_claims_analyst):
        """Test RequiresRole with multiple allowed roles."""
        from fastapi import Request
        from unittest.mock import Mock
        
        mock_request = Mock(spec=Request)
        mock_request.state = type('State', (), {'rbac_cache': {}})()
        mock_request.url.path = "/test"
        
        dependency = RequiresRole(Role.ANALYST, Role.ADMIN)
        result = await dependency(mock_request, mock_claims_analyst)
        assert result == mock_claims_analyst
    
    @pytest.mark.asyncio
    async def test_requires_permission_admin_success(self, mock_claims_admin):
        """Test RequiresPermission allows admin with permission."""
        from fastapi import Request
        from unittest.mock import Mock
        
        mock_request = Mock(spec=Request)
        mock_request.state = type('State', (), {'rbac_cache': {}})()
        mock_request.url.path = "/test"
        
        dependency = RequiresPermission(Permission.CREATE_USER)
        result = await dependency(mock_request, mock_claims_admin)
        assert result == mock_claims_admin
    
    @pytest.mark.asyncio
    async def test_requires_permission_analyst_denied(self, mock_claims_analyst):
        """Test RequiresPermission denies analyst without permission."""
        from fastapi import Request
        from unittest.mock import Mock
        
        mock_request = Mock(spec=Request)
        mock_request.state = type('State', (), {'rbac_cache': {}})()
        mock_request.url.path = "/test"
        
        dependency = RequiresPermission(Permission.CREATE_USER)
        
        with pytest.raises(HTTPException) as exc_info:
            await dependency(mock_request, mock_claims_analyst)
        
        assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN
        assert "Required permission" in exc_info.value.detail
    
    @pytest.mark.asyncio
    async def test_requires_permission_analyst_success(self, mock_claims_analyst):
        """Test RequiresPermission allows analyst with permission."""
        from fastapi import Request
        from unittest.mock import Mock
        
        mock_request = Mock(spec=Request)
        mock_request.state = type('State', (), {'rbac_cache': {}})()
        mock_request.url.path = "/test"
        
        dependency = RequiresPermission(Permission.UPLOAD_DOCUMENT)
        result = await dependency(mock_request, mock_claims_analyst)
        assert result == mock_claims_analyst
    
    @pytest.mark.asyncio
    async def test_requires_permission_viewer_denied(self, mock_claims_viewer):
        """Test RequiresPermission denies viewer without permission."""
        from fastapi import Request
        from unittest.mock import Mock
        
        mock_request = Mock(spec=Request)
        mock_request.state = type('State', (), {'rbac_cache': {}})()
        mock_request.url.path = "/test"
        
        dependency = RequiresPermission(Permission.UPLOAD_DOCUMENT)
        
        with pytest.raises(HTTPException) as exc_info:
            await dependency(mock_request, mock_claims_viewer)
        
        assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN
    
    @pytest.mark.asyncio
    async def test_requires_permission_viewer_success(self, mock_claims_viewer):
        """Test RequiresPermission allows viewer with permission."""
        from fastapi import Request
        from unittest.mock import Mock
        
        mock_request = Mock(spec=Request)
        mock_request.state = type('State', (), {'rbac_cache': {}})()
        mock_request.url.path = "/test"
        
        dependency = RequiresPermission(Permission.VIEW_DOCUMENT)
        result = await dependency(mock_request, mock_claims_viewer)
        assert result == mock_claims_viewer


class TestRBACIntegration:
    """Integration tests for RBAC with FastAPI."""
    
    @pytest.fixture
    def test_app(self):
        """Create test FastAPI app."""
        from fastapi import Depends
        
        app = FastAPI()
        
        @app.get("/admin-only")
        async def admin_endpoint(
            claims: JWTClaims = Depends(RequiresRole(Role.ADMIN))
        ):
            return {"message": "Admin access", "user_id": claims.user_id}
        
        @app.get("/analyst-only")
        async def analyst_endpoint(
            claims: JWTClaims = Depends(RequiresRole(Role.ANALYST))
        ):
            return {"message": "Analyst access", "user_id": claims.user_id}
        
        @app.get("/viewer-only")
        async def viewer_endpoint(
            claims: JWTClaims = Depends(RequiresRole(Role.VIEWER))
        ):
            return {"message": "Viewer access", "user_id": claims.user_id}
        
        @app.post("/upload")
        async def upload_endpoint(
            claims: JWTClaims = Depends(RequiresPermission(Permission.UPLOAD_DOCUMENT))
        ):
            return {"message": "Upload successful", "user_id": claims.user_id}
        
        return app
    
    def test_admin_access_admin_endpoint(self, test_app):
        """Test admin can access admin-only endpoint."""
        from unittest.mock import patch
        
        with patch("src.auth.rbac.get_current_user_claims") as mock_get:
            mock_get.return_value = JWTClaims(
                tenant_id="test-tenant",
                roles=["admin"],
                user_id="admin-user"
            )
            
            client = TestClient(test_app)
            response = client.get(
                "/admin-only",
                headers={"Authorization": "Bearer fake-token"}
            )
            
            assert response.status_code == status.HTTP_200_OK
            assert response.json()["message"] == "Admin access"
    
    def test_analyst_denied_admin_endpoint(self, test_app):
        """Test analyst cannot access admin-only endpoint."""
        from unittest.mock import patch
        
        with patch("src.auth.rbac.get_current_user_claims") as mock_get:
            mock_get.return_value = JWTClaims(
                tenant_id="test-tenant",
                roles=["analyst"],
                user_id="analyst-user"
            )
            
            client = TestClient(test_app)
            response = client.get(
                "/admin-only",
                headers={"Authorization": "Bearer fake-token"}
            )
            
            assert response.status_code == status.HTTP_403_FORBIDDEN
    
    def test_viewer_denied_upload_endpoint(self, test_app):
        """Test viewer cannot access upload endpoint."""
        from unittest.mock import patch
        
        with patch("src.auth.rbac.get_current_user_claims") as mock_get:
            mock_get.return_value = JWTClaims(
                tenant_id="test-tenant",
                roles=["viewer"],
                user_id="viewer-user"
            )
            
            client = TestClient(test_app)
            response = client.post(
                "/upload",
                headers={"Authorization": "Bearer fake-token"}
            )
            
            assert response.status_code == status.HTTP_403_FORBIDDEN
    
    def test_analyst_allowed_upload_endpoint(self, test_app):
        """Test analyst can access upload endpoint."""
        from unittest.mock import patch
        
        with patch("src.auth.rbac.get_current_user_claims") as mock_get:
            mock_get.return_value = JWTClaims(
                tenant_id="test-tenant",
                roles=["analyst"],
                user_id="analyst-user"
            )
            
            client = TestClient(test_app)
            response = client.post(
                "/upload",
                headers={"Authorization": "Bearer fake-token"}
            )
            
            assert response.status_code == status.HTTP_200_OK


class TestRolePermissionsMatrix:
    """Test role-permission matrix to verify acceptance criteria."""
    
    def test_admin_permissions_matrix(self):
        """Verify admin has all required permissions per acceptance criteria."""
        admin_perms = get_role_permissions(Role.ADMIN)
        
        # Admin can: create/delete users
        assert Permission.CREATE_USER in admin_perms
        assert Permission.DELETE_USER in admin_perms
        assert Permission.UPDATE_USER in admin_perms
        assert Permission.LIST_USERS in admin_perms
        
        # Admin can: modify tenant settings
        assert Permission.MODIFY_TENANT_SETTINGS in admin_perms
        
        # Admin can: access billing
        assert Permission.ACCESS_BILLING in admin_perms
        
        # Admin can: all document operations
        assert Permission.UPLOAD_DOCUMENT in admin_perms
        assert Permission.EDIT_DOCUMENT in admin_perms
        assert Permission.DELETE_DOCUMENT in admin_perms
        assert Permission.VIEW_DOCUMENT in admin_perms
        assert Permission.SEARCH_DOCUMENTS in admin_perms
    
    def test_analyst_permissions_matrix(self):
        """Verify analyst has correct permissions per acceptance criteria."""
        analyst_perms = get_role_permissions(Role.ANALYST)
        
        # Analyst can: upload/edit documents
        assert Permission.UPLOAD_DOCUMENT in analyst_perms
        assert Permission.EDIT_DOCUMENT in analyst_perms
        assert Permission.DELETE_DOCUMENT in analyst_perms
        
        # Analyst can: override AI decisions
        assert Permission.OVERRIDE_AI_DECISION in analyst_perms
        
        # Analyst can: search
        assert Permission.SEARCH_DOCUMENTS in analyst_perms
        
        # Analyst cannot: manage users
        assert Permission.CREATE_USER not in analyst_perms
        assert Permission.DELETE_USER not in analyst_perms
        assert Permission.UPDATE_USER not in analyst_perms
    
    def test_viewer_permissions_matrix(self):
        """Verify viewer has correct permissions per acceptance criteria."""
        viewer_perms = get_role_permissions(Role.VIEWER)
        
        # Viewer can: search and view documents
        assert Permission.SEARCH_DOCUMENTS in viewer_perms
        assert Permission.VIEW_DOCUMENT in viewer_perms
        
        # Viewer cannot: edit documents
        assert Permission.UPLOAD_DOCUMENT not in viewer_perms
        assert Permission.EDIT_DOCUMENT not in viewer_perms
        assert Permission.DELETE_DOCUMENT not in viewer_perms
        
        # Viewer cannot: manage users
        assert Permission.CREATE_USER not in viewer_perms
        assert Permission.DELETE_USER not in viewer_perms
