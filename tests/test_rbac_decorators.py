"""Tests for RBAC decorators."""
import pytest
from unittest.mock import Mock, AsyncMock, patch
from fastapi import HTTPException, status

from src.auth.decorators import requires_role, requires_any_role, requires_permission
from src.auth.jwt_validator import JWTClaims
from src.auth.roles import Role, Permission


class TestDecorators:
    """Tests for RBAC decorators."""
    
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
        """Test @requires_role allows admin access."""
        @requires_role("Admin")
        async def admin_endpoint(claims: JWTClaims = None):
            return {"message": "success"}
        
        # Pass claims as keyword argument
        result = await admin_endpoint(claims=mock_claims_admin)
        assert result["message"] == "success"
    
    @pytest.mark.asyncio
    async def test_requires_role_case_insensitive(self, mock_claims_admin):
        """Test @requires_role is case-insensitive."""
        @requires_role("ADMIN")
        async def admin_endpoint(claims: JWTClaims = None):
            return {"message": "success"}
        
        result = await admin_endpoint(claims=mock_claims_admin)
        assert result["message"] == "success"
    
    @pytest.mark.asyncio
    async def test_requires_role_admin_denied(self, mock_claims_analyst):
        """Test @requires_role denies non-admin access."""
        @requires_role("Admin")
        async def admin_endpoint(claims: JWTClaims = None):
            return {"message": "success"}
        
        with pytest.raises(HTTPException) as exc_info:
            await admin_endpoint(claims=mock_claims_analyst)
        
        assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN
        assert "Required role(s)" in exc_info.value.detail
    
    @pytest.mark.asyncio
    async def test_requires_any_role_success(self, mock_claims_analyst):
        """Test @requires_any_role allows access with one of the roles."""
        @requires_any_role(["Admin", "Analyst"])
        async def documents_endpoint(claims: JWTClaims = None):
            return {"message": "success"}
        
        result = await documents_endpoint(claims=mock_claims_analyst)
        assert result["message"] == "success"
    
    @pytest.mark.asyncio
    async def test_requires_any_role_denied(self, mock_claims_viewer):
        """Test @requires_any_role denies access without required roles."""
        @requires_any_role(["Admin", "Analyst"])
        async def documents_endpoint(claims: JWTClaims = None):
            return {"message": "success"}
        
        with pytest.raises(HTTPException) as exc_info:
            await documents_endpoint(claims=mock_claims_viewer)
        
        assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN
    
    @pytest.mark.asyncio
    async def test_requires_permission_success(self, mock_claims_analyst):
        """Test @requires_permission allows access with permission."""
        @requires_permission("upload_document")
        async def upload_endpoint(claims: JWTClaims = None):
            return {"message": "success"}
        
        result = await upload_endpoint(claims=mock_claims_analyst)
        assert result["message"] == "success"
    
    @pytest.mark.asyncio
    async def test_requires_permission_denied(self, mock_claims_viewer):
        """Test @requires_permission denies access without permission."""
        @requires_permission("upload_document")
        async def upload_endpoint(claims: JWTClaims = None):
            return {"message": "success"}
        
        with pytest.raises(HTTPException) as exc_info:
            await upload_endpoint(claims=mock_claims_viewer)
        
        assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN
    
    @pytest.mark.asyncio
    async def test_requires_permission_with_enum(self, mock_claims_admin):
        """Test @requires_permission works with Permission enum."""
        @requires_permission(Permission.CREATE_USER)
        async def create_user_endpoint(claims: JWTClaims = None):
            return {"message": "success"}
        
        result = await create_user_endpoint(claims=mock_claims_admin)
        assert result["message"] == "success"
    
    @pytest.mark.asyncio
    async def test_requires_role_with_enum(self, mock_claims_admin):
        """Test @requires_role works with Role enum."""
        @requires_role(Role.ADMIN)
        async def admin_endpoint(claims: JWTClaims = None):
            return {"message": "success"}
        
        result = await admin_endpoint(claims=mock_claims_admin)
        assert result["message"] == "success"
