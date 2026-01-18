"""Unit tests for RBAC permission system."""
import pytest
import logging
from datetime import datetime, timedelta
from uuid import uuid4, UUID
from fastapi import FastAPI, Request, Depends
from fastapi.testclient import TestClient
import jwt

from src.auth.config import AuthConfig
from src.auth.middleware import AuthMiddleware
from src.auth.models import AuthContext
from src.auth.rbac import PERMISSIONS, has_permission
from src.auth.decorators import require_permission, RequireAdmin, RequireAnalyst, RequireViewer


from typing import Any, Generator
@pytest.fixture
def mock_config() -> Any:
    """Create mock auth config for testing."""
    return AuthConfig(
        supabase_url="https://test.supabase.co",
        supabase_anon_key="test-anon-key",
        supabase_service_key="test-service-key",
        supabase_jwt_secret="test-jwt-secret-key-for-testing-only",
        app_env="test",
    )


@pytest.fixture
def create_jwt_token(mock_config: Any) -> Any:
    """Factory to create JWT tokens with specified roles."""
    def _create_token(roles: list[str]) -> Any:
        user_id = uuid4()
        tenant_id = uuid4()
        exp = datetime.utcnow() + timedelta(hours=1)
        
        payload = {
            "sub": str(user_id),
            "email": "test@example.com",
            "app_metadata": {
                "tenant_id": str(tenant_id),
                "roles": roles,
                "tenant_slug": "test-tenant",
            },
            "exp": int(exp.timestamp()),
        }
        
        return jwt.encode(payload, mock_config.supabase_jwt_secret, algorithm="HS256")
    
    return _create_token


@pytest.fixture
def app_with_auth(mock_config: Any) -> Any:
    """Create FastAPI app with auth middleware."""
    app = FastAPI()
    app.add_middleware(AuthMiddleware, config=mock_config)  # type: ignore[arg-type]
    return app


class TestPermissionMatrix:
    """Test permission matrix structure."""
    
    def test_permissions_defined(self) -> None:
        """Test that all expected roles are defined."""
        assert "Admin" in PERMISSIONS
        assert "Analyst" in PERMISSIONS
        assert "Viewer" in PERMISSIONS
    
    def test_admin_has_wildcard(self) -> None:
        """Test that Admin role has wildcard permission."""
        assert "*" in PERMISSIONS["Admin"]
    
    def test_analyst_permissions(self) -> None:
        """Test Analyst role permissions."""
        analyst_perms = PERMISSIONS["Analyst"]
        assert "documents:read" in analyst_perms
        assert "documents:write" in analyst_perms
        assert "documents:delete" in analyst_perms
        assert "search:read" in analyst_perms
        assert "ask:read" in analyst_perms
        assert "extractions:read" in analyst_perms
        assert "extractions:override" in analyst_perms
        assert "exports:read" in analyst_perms
        assert "exports:write" in analyst_perms
    
    def test_viewer_permissions(self) -> None:
        """Test Viewer role permissions."""
        viewer_perms = PERMISSIONS["Viewer"]
        assert "documents:read" in viewer_perms
        assert "search:read" in viewer_perms
        assert "ask:read" in viewer_perms
        assert "extractions:read" in viewer_perms
        assert "exports:read" in viewer_perms
        # Viewer should NOT have write permissions
        assert "documents:write" not in viewer_perms
        assert "documents:delete" not in viewer_perms
        assert "extractions:override" not in viewer_perms


class TestHasPermission:
    """Test has_permission function."""
    
    def test_admin_has_all_permissions(self) -> None:
        """Test that Admin role grants all permissions."""
        assert has_permission(["Admin"], "documents:read") is True
        assert has_permission(["Admin"], "documents:write") is True
        assert has_permission(["Admin"], "documents:delete") is True
        assert has_permission(["Admin"], "search:read") is True
        assert has_permission(["Admin"], "ask:read") is True
        assert has_permission(["Admin"], "extractions:read") is True
        assert has_permission(["Admin"], "extractions:override") is True
        assert has_permission(["Admin"], "exports:read") is True
        assert has_permission(["Admin"], "exports:write") is True
        assert has_permission(["Admin"], "nonexistent:permission") is True
    
    def test_analyst_permissions(self) -> None:
        """Test Analyst role permissions."""
        assert has_permission(["Analyst"], "documents:read") is True
        assert has_permission(["Analyst"], "documents:write") is True
        assert has_permission(["Analyst"], "documents:delete") is True
        assert has_permission(["Analyst"], "search:read") is True
        assert has_permission(["Analyst"], "ask:read") is True
        assert has_permission(["Analyst"], "extractions:read") is True
        assert has_permission(["Analyst"], "extractions:override") is True
        assert has_permission(["Analyst"], "exports:read") is True
        assert has_permission(["Analyst"], "exports:write") is True
        # Analyst should NOT have admin-only permissions
        assert has_permission(["Analyst"], "admin:manage") is False
    
    def test_viewer_permissions(self) -> None:
        """Test Viewer role permissions."""
        assert has_permission(["Viewer"], "documents:read") is True
        assert has_permission(["Viewer"], "search:read") is True
        assert has_permission(["Viewer"], "ask:read") is True
        assert has_permission(["Viewer"], "extractions:read") is True
        assert has_permission(["Viewer"], "exports:read") is True
        # Viewer should NOT have write permissions
        assert has_permission(["Viewer"], "documents:write") is False
        assert has_permission(["Viewer"], "documents:delete") is False
        assert has_permission(["Viewer"], "extractions:override") is False
        assert has_permission(["Viewer"], "exports:write") is False
    
    def test_case_insensitive_roles(self) -> None:
        """Test that role comparison is case-insensitive."""
        assert has_permission(["admin"], "documents:read") is True
        assert has_permission(["ADMIN"], "documents:read") is True
        assert has_permission(["Admin"], "documents:read") is True
        assert has_permission(["analyst"], "documents:write") is True
        assert has_permission(["ANALYST"], "documents:write") is True
        assert has_permission(["viewer"], "documents:read") is True
        assert has_permission(["VIEWER"], "documents:read") is True
    
    def test_multiple_roles(self) -> None:
        """Test permission check with multiple roles."""
        # User with both Viewer and Analyst roles
        assert has_permission(["Viewer", "Analyst"], "documents:read") is True
        assert has_permission(["Viewer", "Analyst"], "documents:write") is True
        # User with Viewer role only
        assert has_permission(["Viewer"], "documents:write") is False
    
    def test_empty_roles(self) -> None:
        """Test permission check with empty roles list."""
        assert has_permission([], "documents:read") is False
        assert has_permission([], "documents:write") is False
    
    def test_unknown_role(self) -> None:
        """Test permission check with unknown role."""
        assert has_permission(["UnknownRole"], "documents:read") is False
        assert has_permission(["UnknownRole"], "documents:write") is False
    
    def test_role_with_whitespace(self) -> None:
        """Test permission check with role containing whitespace."""
        assert has_permission(["  Admin  "], "documents:read") is True
        assert has_permission(["  Analyst  "], "documents:write") is True


class TestRequirePermission:
    """Test require_permission FastAPI dependency."""
    
    def test_admin_can_access_any_permission(self, app_with_auth: Any, create_jwt_token: Any) -> None:
        """Test that Admin can access any permission-protected endpoint."""
        token = create_jwt_token(["Admin"])
        
        @app_with_auth.delete("/documents/{id}")
        async def delete_document(
            id: UUID,
            request: Request,
            auth: AuthContext = Depends(require_permission("documents:delete")),
        ) -> Any:
            return {"message": "deleted", "id": str(id)}
        
        client = TestClient(app_with_auth)
        response = client.delete(
            f"/documents/{uuid4()}",
            headers={"Authorization": f"Bearer {token}"},
        )
        
        assert response.status_code == 200
    
    def test_analyst_can_delete_document(self, app_with_auth: Any, create_jwt_token: Any) -> None:
        """Test that Analyst can delete documents."""
        token = create_jwt_token(["Analyst"])
        
        @app_with_auth.delete("/documents/{id}")
        async def delete_document(
            id: UUID,
            request: Request,
            auth: AuthContext = Depends(require_permission("documents:delete")),
        ) -> Any:
            return {"message": "deleted", "id": str(id)}
        
        client = TestClient(app_with_auth)
        response = client.delete(
            f"/documents/{uuid4()}",
            headers={"Authorization": f"Bearer {token}"},
        )
        
        assert response.status_code == 200
    
    def test_viewer_cannot_delete_document(self, app_with_auth: Any, create_jwt_token: Any) -> None:
        """Test that Viewer cannot delete documents."""
        token = create_jwt_token(["Viewer"])
        
        @app_with_auth.delete("/documents/{id}")
        async def delete_document(
            id: UUID,
            request: Request,
            auth: AuthContext = Depends(require_permission("documents:delete")),
        ) -> Any:
            return {"message": "deleted", "id": str(id)}
        
        client = TestClient(app_with_auth)
        response = client.delete(
            f"/documents/{uuid4()}",
            headers={"Authorization": f"Bearer {token}"},
        )
        
        assert response.status_code == 403
        data = response.json()
        assert data["detail"]["code"] == "PERMISSION_DENIED"
        assert "documents:delete" in data["detail"]["message"]
        assert data["detail"]["your_roles"] == ["Viewer"]
    
    def test_viewer_can_read_documents(self, app_with_auth: Any, create_jwt_token: Any) -> None:
        """Test that Viewer can read documents."""
        token = create_jwt_token(["Viewer"])
        
        @app_with_auth.get("/documents")
        async def list_documents(
            request: Request,
            auth: AuthContext = Depends(require_permission("documents:read")),
        ) -> Any:
            return {"documents": []}
        
        client = TestClient(app_with_auth)
        response = client.get(
            "/documents",
            headers={"Authorization": f"Bearer {token}"},
        )
        
        assert response.status_code == 200
    
    def test_analyst_can_override_extractions(self, app_with_auth: Any, create_jwt_token: Any) -> None:
        """Test that Analyst can override extractions."""
        token = create_jwt_token(["Analyst"])
        
        @app_with_auth.post("/extractions/{id}/override")
        async def override_extraction(
            id: UUID,
            request: Request,
            auth: AuthContext = Depends(require_permission("extractions:override")),
        ) -> Any:
            return {"message": "overridden", "id": str(id)}
        
        client = TestClient(app_with_auth)
        response = client.post(
            f"/extractions/{uuid4()}/override",
            headers={"Authorization": f"Bearer {token}"},
        )
        
        assert response.status_code == 200
    
    def test_viewer_cannot_override_extractions(self, app_with_auth: Any, create_jwt_token: Any) -> None:
        """Test that Viewer cannot override extractions."""
        token = create_jwt_token(["Viewer"])
        
        @app_with_auth.post("/extractions/{id}/override")
        async def override_extraction(
            id: UUID,
            request: Request,
            auth: AuthContext = Depends(require_permission("extractions:override")),
        ) -> Any:
            return {"message": "overridden", "id": str(id)}
        
        client = TestClient(app_with_auth)
        response = client.post(
            f"/extractions/{uuid4()}/override",
            headers={"Authorization": f"Bearer {token}"},
        )
        
        assert response.status_code == 403
    
    def test_permission_denial_logging(self, app_with_auth: Any, create_jwt_token: Any, caplog: Any) -> None:
        """Test that permission denials are logged."""
        token = create_jwt_token(["Viewer"])
        
        @app_with_auth.delete("/documents/{id}")
        async def delete_document(
            id: UUID,
            request: Request,
            auth: AuthContext = Depends(require_permission("documents:delete")),
        ) -> Any:
            return {"message": "deleted"}
        
        with caplog.at_level(logging.WARNING):
            client = TestClient(app_with_auth)
            response = client.delete(
                f"/documents/{uuid4()}",
                headers={"Authorization": f"Bearer {token}"},
            )
            
            assert response.status_code == 403
            # Check that permission denial was logged
            assert any(
                "Permission denied" in record.message
                and record.levelname == "WARNING"
                for record in caplog.records
            )
            
            # Check log extra fields
            log_record = next(
                (r for r in caplog.records if "Permission denied" in r.message),
                None,
            )
            assert log_record is not None
            assert log_record.event_type == "PERMISSION_DENIED"
            assert "permission" in log_record.__dict__
            assert log_record.permission == "documents:delete"
            assert "endpoint" in log_record.__dict__


class TestRoleShortcuts:
    """Test role shortcut dependencies."""
    
    def test_require_admin_allows_admin(self, app_with_auth: Any, create_jwt_token: Any) -> None:
        """Test RequireAdmin shortcut allows Admin role."""
        token = create_jwt_token(["Admin"])
        
        @app_with_auth.get("/admin-only")
        async def admin_endpoint(
            request: Request,
            auth: AuthContext = Depends(RequireAdmin),
        ) -> Any:
            return {"message": "admin access"}
        
        client = TestClient(app_with_auth)
        response = client.get(
            "/admin-only",
            headers={"Authorization": f"Bearer {token}"},
        )
        
        assert response.status_code == 200
    
    def test_require_admin_denies_viewer(self, app_with_auth: Any, create_jwt_token: Any) -> None:
        """Test RequireAdmin shortcut denies Viewer role."""
        token = create_jwt_token(["Viewer"])
        
        @app_with_auth.get("/admin-only")
        async def admin_endpoint(
            request: Request,
            auth: AuthContext = Depends(RequireAdmin),
        ) -> Any:
            return {"message": "admin access"}
        
        client = TestClient(app_with_auth)
        response = client.get(
            "/admin-only",
            headers={"Authorization": f"Bearer {token}"},
        )
        
        assert response.status_code == 403
    
    def test_require_analyst_allows_analyst(self, app_with_auth: Any, create_jwt_token: Any) -> None:
        """Test RequireAnalyst shortcut allows Analyst role."""
        token = create_jwt_token(["Analyst"])
        
        @app_with_auth.post("/documents")
        async def create_document(
            request: Request,
            auth: AuthContext = Depends(RequireAnalyst),
        ) -> Any:
            return {"message": "created"}
        
        client = TestClient(app_with_auth)
        response = client.post(
            "/documents",
            headers={"Authorization": f"Bearer {token}"},
        )
        
        assert response.status_code == 200
    
    def test_require_analyst_allows_admin(self, app_with_auth: Any, create_jwt_token: Any) -> None:
        """Test RequireAnalyst shortcut allows Admin role (hierarchical)."""
        token = create_jwt_token(["Admin"])
        
        @app_with_auth.post("/documents")
        async def create_document(
            request: Request,
            auth: AuthContext = Depends(RequireAnalyst),
        ) -> Any:
            return {"message": "created"}
        
        client = TestClient(app_with_auth)
        response = client.post(
            "/documents",
            headers={"Authorization": f"Bearer {token}"},
        )
        
        assert response.status_code == 200
    
    def test_require_analyst_denies_viewer(self, app_with_auth: Any, create_jwt_token: Any) -> None:
        """Test RequireAnalyst shortcut denies Viewer role."""
        token = create_jwt_token(["Viewer"])
        
        @app_with_auth.post("/documents")
        async def create_document(
            request: Request,
            auth: AuthContext = Depends(RequireAnalyst),
        ) -> Any:
            return {"message": "created"}
        
        client = TestClient(app_with_auth)
        response = client.post(
            "/documents",
            headers={"Authorization": f"Bearer {token}"},
        )
        
        assert response.status_code == 403
    
    def test_require_viewer_allows_all_roles(self, app_with_auth: Any, create_jwt_token: Any) -> None:
        """Test RequireViewer shortcut allows all roles."""
        for role in ["Admin", "Analyst", "Viewer"]:
            token = create_jwt_token([role])
            
            @app_with_auth.get("/documents")
            async def list_documents(
                request: Request,
                auth: AuthContext = Depends(RequireViewer),
            ) -> Any:
                return {"documents": []}
            
            client = TestClient(app_with_auth)
            response = client.get(
                "/documents",
                headers={"Authorization": f"Bearer {token}"},
            )
            
            assert response.status_code == 200, f"Role {role} should have read access"
