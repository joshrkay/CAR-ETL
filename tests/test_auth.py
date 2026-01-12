"""Unit tests for authentication middleware and dependencies."""
import pytest
from datetime import datetime, timedelta
from typing import Any
from uuid import uuid4, UUID
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
import jwt

from src.auth.config import AuthConfig
from src.auth.middleware import AuthMiddleware
from src.auth.models import AuthContext
from src.dependencies import get_current_user, require_role, require_any_role


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
def valid_jwt_payload(mock_config) -> Any:
    """Create a valid JWT payload for testing."""
    user_id = uuid4()
    tenant_id = uuid4()
    exp = datetime.utcnow() + timedelta(hours=1)
    
    return {
        "sub": str(user_id),
        "email": "test@example.com",
        "app_metadata": {
            "tenant_id": str(tenant_id),
            "roles": ["Admin", "User"],
            "tenant_slug": "test-tenant",
        },
        "exp": int(exp.timestamp()),
    }


@pytest.fixture
def valid_token(mock_config, valid_jwt_payload) -> Any:
    """Create a valid JWT token for testing."""
    return jwt.encode(valid_jwt_payload, mock_config.supabase_jwt_secret, algorithm="HS256")


@pytest.fixture
def expired_token(mock_config, valid_jwt_payload) -> Any:
    """Create an expired JWT token for testing."""
    valid_jwt_payload["exp"] = int((datetime.utcnow() - timedelta(hours=1)).timestamp())
    return jwt.encode(valid_jwt_payload, mock_config.supabase_jwt_secret, algorithm="HS256")


@pytest.fixture
def app_with_auth(mock_config) -> Any:
    """Create FastAPI app with auth middleware."""
    app = FastAPI()
    app.add_middleware(AuthMiddleware, config=mock_config)
    
    @app.get("/protected")
    async def protected_endpoint(request: Request):
        auth: AuthContext = request.state.auth
        return {"user_id": str(auth.user_id), "tenant_id": str(auth.tenant_id)}
    
    @app.get("/public")
    async def public_endpoint():
        return {"message": "public"}
    
    return app


class TestAuthMiddleware:
    """Test authentication middleware."""

    def test_missing_token(self, app_with_auth) -> None:
        """Test request without Authorization header."""
        client = TestClient(app_with_auth)
        response = client.get("/protected")
        
        assert response.status_code == 401
        data = response.json()
        assert data["code"] == "MISSING_TOKEN"

    def test_valid_token(self, app_with_auth, valid_token) -> None:
        """Test request with valid token."""
        client = TestClient(app_with_auth)
        response = client.get(
            "/protected",
            headers={"Authorization": f"Bearer {valid_token}"},
        )
        
        assert response.status_code == 200
        assert "user_id" in response.json()
        assert "tenant_id" in response.json()

    def test_expired_token(self, app_with_auth, expired_token) -> None:
        """Test request with expired token."""
        client = TestClient(app_with_auth)
        response = client.get(
            "/protected",
            headers={"Authorization": f"Bearer {expired_token}"},
        )
        
        assert response.status_code == 401
        data = response.json()
        assert data["code"] == "EXPIRED_TOKEN"

    def test_invalid_token_signature(self, app_with_auth) -> None:
        """Test request with invalid token signature."""
        invalid_token = jwt.encode(
            {"sub": "test"},
            "wrong-secret",
            algorithm="HS256",
        )
        
        client = TestClient(app_with_auth)
        response = client.get(
            "/protected",
            headers={"Authorization": f"Bearer {invalid_token}"},
        )
        
        assert response.status_code == 401
        data = response.json()
        assert data["code"] == "INVALID_TOKEN"

    def test_missing_tenant_id(self, app_with_auth, mock_config) -> None:
        """Test token missing tenant_id claim."""
        payload = {
            "sub": str(uuid4()),
            "email": "test@example.com",
            "app_metadata": {"roles": ["User"]},
            "exp": int((datetime.utcnow() + timedelta(hours=1)).timestamp()),
        }
        token = jwt.encode(payload, mock_config.supabase_jwt_secret, algorithm="HS256")
        
        client = TestClient(app_with_auth)
        response = client.get(
            "/protected",
            headers={"Authorization": f"Bearer {token}"},
        )
        
        assert response.status_code == 401
        data = response.json()
        assert data["code"] == "MISSING_CLAIMS"
        assert "tenant_id" in data["message"]

    def test_public_endpoint_no_auth(self, app_with_auth) -> None:
        """Test public endpoint doesn't require auth."""
        client = TestClient(app_with_auth)
        response = client.get("/public")
        
        assert response.status_code == 200
        assert response.json()["message"] == "public"


class TestAuthContext:
    """Test AuthContext model."""

    def test_has_role(self, valid_jwt_payload) -> None:
        """Test role checking."""
        user_id = UUID(valid_jwt_payload["sub"])
        tenant_id = UUID(valid_jwt_payload["app_metadata"]["tenant_id"])
        exp = datetime.fromtimestamp(valid_jwt_payload["exp"])
        
        auth = AuthContext(
            user_id=user_id,
            email=valid_jwt_payload["email"],
            tenant_id=tenant_id,
            roles=valid_jwt_payload["app_metadata"]["roles"],
            token_exp=exp,
        )
        
        assert auth.has_role("Admin") is True
        assert auth.has_role("User") is True
        assert auth.has_role("Manager") is False

    def test_has_any_role(self, valid_jwt_payload) -> None:
        """Test any role checking."""
        user_id = UUID(valid_jwt_payload["sub"])
        tenant_id = UUID(valid_jwt_payload["app_metadata"]["tenant_id"])
        exp = datetime.fromtimestamp(valid_jwt_payload["exp"])
        
        auth = AuthContext(
            user_id=user_id,
            email=valid_jwt_payload["email"],
            tenant_id=tenant_id,
            roles=valid_jwt_payload["app_metadata"]["roles"],
            token_exp=exp,
        )
        
        assert auth.has_any_role(["Admin", "Manager"]) is True
        assert auth.has_any_role(["Manager", "Guest"]) is False


class TestDependencies:
    """Test FastAPI dependencies."""

    def test_get_current_user_success(self, app_with_auth, valid_token) -> None:
        """Test get_current_user dependency with valid auth."""
        from fastapi import Depends
        from typing import Annotated
        
        app = app_with_auth
        
        @app.get("/user")
        async def get_user(user: Annotated[AuthContext, Depends(get_current_user)]):
            return {"user_id": str(user.user_id)}
        
        client = TestClient(app)
        response = client.get(
            "/user",
            headers={"Authorization": f"Bearer {valid_token}"},
        )
        
        assert response.status_code == 200
        assert "user_id" in response.json()

    def test_get_current_user_no_auth(self, app_with_auth) -> None:
        """Test get_current_user dependency without auth."""
        from fastapi import Depends
        from typing import Annotated
        
        app = app_with_auth
        
        @app.get("/user")
        async def get_user(user: Annotated[AuthContext, Depends(get_current_user)]):
            return {"user_id": str(user.user_id)}
        
        client = TestClient(app)
        response = client.get("/user")
        
        assert response.status_code == 401

    def test_require_role_success(self, app_with_auth, valid_token) -> None:
        """Test require_role dependency with correct role."""
        from fastapi import Depends
        from typing import Annotated
        
        app = app_with_auth
        
        @app.get("/admin")
        async def admin_endpoint(user: Annotated[AuthContext, Depends(require_role("Admin"))]):
            return {"message": "admin access"}
        
        client = TestClient(app)
        response = client.get(
            "/admin",
            headers={"Authorization": f"Bearer {valid_token}"},
        )
        
        assert response.status_code == 200

    def test_require_role_failure(self, app_with_auth, mock_config) -> None:
        """Test require_role dependency with incorrect role."""
        from fastapi import Depends
        from typing import Annotated
        
        payload = {
            "sub": str(uuid4()),
            "email": "test@example.com",
            "app_metadata": {
                "tenant_id": str(uuid4()),
                "roles": ["User"],
            },
            "exp": int((datetime.utcnow() + timedelta(hours=1)).timestamp()),
        }
        token = jwt.encode(payload, mock_config.supabase_jwt_secret, algorithm="HS256")
        
        app = app_with_auth
        
        @app.get("/admin")
        async def admin_endpoint(user: Annotated[AuthContext, Depends(require_role("Admin"))]):
            return {"message": "admin access"}
        
        client = TestClient(app)
        response = client.get(
            "/admin",
            headers={"Authorization": f"Bearer {token}"},
        )
        
        assert response.status_code == 403

    def test_require_any_role_success(self, app_with_auth, valid_token) -> None:
        """Test require_any_role dependency with matching role."""
        from fastapi import Depends
        from typing import Annotated
        
        app = app_with_auth
        
        @app.get("/manager")
        async def manager_endpoint(user: Annotated[AuthContext, Depends(require_any_role(["Admin", "Manager"]))]):
            return {"message": "manager access"}
        
        client = TestClient(app)
        response = client.get(
            "/manager",
            headers={"Authorization": f"Bearer {valid_token}"},
        )
        
        assert response.status_code == 200

    def test_require_any_role_failure(self, app_with_auth, mock_config) -> None:
        """Test require_any_role dependency with no matching roles."""
        from fastapi import Depends
        from typing import Annotated
        
        payload = {
            "sub": str(uuid4()),
            "email": "test@example.com",
            "app_metadata": {
                "tenant_id": str(uuid4()),
                "roles": ["Guest"],
            },
            "exp": int((datetime.utcnow() + timedelta(hours=1)).timestamp()),
        }
        token = jwt.encode(payload, mock_config.supabase_jwt_secret, algorithm="HS256")
        
        app = app_with_auth
        
        @app.get("/manager")
        async def manager_endpoint(user: Annotated[AuthContext, Depends(require_any_role(["Admin", "Manager"]))]):
            return {"message": "manager access"}
        
        client = TestClient(app)
        response = client.get(
            "/manager",
            headers={"Authorization": f"Bearer {token}"},
        )
        
        assert response.status_code == 403
