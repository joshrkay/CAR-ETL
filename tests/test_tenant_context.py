"""Unit tests for tenant context middleware."""
import pytest
from unittest.mock import Mock, patch, AsyncMock
from fastapi import Request, HTTPException, status
from fastapi.testclient import TestClient
from uuid import uuid4
from datetime import datetime, timedelta
import jwt

from src.auth.middleware import AuthMiddleware
from src.auth.models import AuthContext, AuthError
from src.auth.config import AuthConfig
from src.auth.client import create_user_client, create_service_client
from src.main import app


@pytest.fixture
def mock_config():
    """Create a mock AuthConfig."""
    return AuthConfig(
        supabase_url="https://test.supabase.co",
        supabase_anon_key="test-anon-key",
        supabase_service_key="test-service-key",
        supabase_jwt_secret="test-secret",
        app_env="test",
    )


@pytest.fixture
def sample_token(mock_config):
    """Create a sample JWT token."""
    tenant_id = uuid4()
    user_id = uuid4()
    
    payload = {
        "sub": str(user_id),
        "email": "test@example.com",
        "app_metadata": {
            "tenant_id": str(tenant_id),
            "roles": ["Admin"],
            "tenant_slug": "test-tenant",
        },
        "exp": int((datetime.utcnow() + timedelta(hours=1)).timestamp()),
    }
    
    return jwt.encode(payload, mock_config.supabase_jwt_secret, algorithm="HS256")


def test_create_user_client_uses_anon_key(mock_config) -> None:
    """Test that create_user_client uses anon_key, not service_key."""
    token = "test-token"
    
    with patch("src.auth.client.create_client") as mock_create:
        mock_client = Mock()
        mock_client.postgrest = Mock()
        mock_client.postgrest.session = Mock()
        mock_client.postgrest.session.headers = {}
        mock_create.return_value = mock_client
        
        client = create_user_client(token, mock_config)
        
        # Verify anon_key is used, not service_key
        mock_create.assert_called_once()
        call_args = mock_create.call_args
        assert call_args[0][0] == mock_config.supabase_url
        assert call_args[0][1] == mock_config.supabase_anon_key
        assert call_args[0][1] != mock_config.supabase_service_key
        
        # Verify Authorization header is set on session
        assert mock_client.postgrest.session.headers["Authorization"] == f"Bearer {token}"


def test_create_service_client_uses_service_key(mock_config) -> None:
    """Test that create_service_client uses service_key."""
    with patch("src.auth.client.create_client") as mock_create:
        create_service_client(mock_config)
        
        # Verify service_key is used
        mock_create.assert_called_once()
        call_args = mock_create.call_args
        assert call_args[0][0] == mock_config.supabase_url
        assert call_args[0][1] == mock_config.supabase_service_key


def test_middleware_creates_user_client(mock_config, sample_token) -> None:
    """Test that middleware creates user client with JWT token."""
    middleware = AuthMiddleware(app, mock_config)
    
    # Mock request
    request = Mock(spec=Request)
    request.url.path = "/api/test"
    request.headers = {"Authorization": f"Bearer {sample_token}"}
    request.client = Mock(host="127.0.0.1")
    request.state = Mock()
    
    # Mock rate limiter
    middleware.rate_limiter = Mock()
    middleware.rate_limiter.check_rate_limit = Mock()
    middleware.rate_limiter.reset_rate_limit = Mock()
    
    # Mock call_next
    call_next = AsyncMock(return_value=Mock(status_code=200))
    
    with patch("src.auth.middleware.create_user_client") as mock_create_client:
        mock_client = Mock()
        mock_create_client.return_value = mock_client
        
        # Run middleware
        import asyncio
        asyncio.run(middleware.dispatch(request, call_next))
        
        # Verify user client was created with token
        mock_create_client.assert_called_once()
        assert mock_create_client.call_args[0][0] == sample_token
        
        # Verify client was attached to request.state
        assert request.state.supabase == mock_client
        assert request.state.auth is not None
        assert isinstance(request.state.auth, AuthContext)


def test_middleware_skips_auth_for_public_paths(mock_config) -> None:
    """Test that middleware skips auth for public paths."""
    middleware = AuthMiddleware(app, mock_config)
    
    public_paths = ["/health", "/docs", "/openapi.json", "/redoc", "/public"]
    
    for path in public_paths:
        request = Mock(spec=Request)
        request.url.path = path
        request.state = Mock()
        
        call_next = AsyncMock(return_value=Mock(status_code=200))
        
        # Should not raise error for public paths
        import asyncio
        result = asyncio.run(middleware.dispatch(request, call_next))
        assert result.status_code == 200


def test_get_supabase_client_requires_auth() -> None:
    """Test that get_supabase_client requires authenticated user."""
    from src.dependencies import get_supabase_client
    
    # Request without supabase client in state
    request = Mock(spec=Request)
    request.state = Mock()
    delattr(request.state, "supabase")
    
    # Should raise 401
    with pytest.raises(HTTPException) as exc_info:
        get_supabase_client(request)
    
    assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED


def test_get_supabase_client_returns_user_client() -> None:
    """Test that get_supabase_client returns user client from request state."""
    from src.dependencies import get_supabase_client
    
    # Request with supabase client in state
    mock_client = Mock()
    request = Mock(spec=Request)
    request.state = Mock()
    request.state.supabase = mock_client
    
    # Should return the client
    client = get_supabase_client(request)
    assert client == mock_client


def test_user_client_respects_rls(mock_config, sample_token) -> None:
    """Test that user client uses anon_key which respects RLS."""
    with patch("src.auth.client.create_client") as mock_create:
        mock_client = Mock()
        mock_client.postgrest = Mock()
        mock_client.postgrest.session = Mock()
        mock_client.postgrest.session.headers = {}
        mock_create.return_value = mock_client
        
        client = create_user_client(sample_token, mock_config)
        
        # Verify anon_key was used (not service_key)
        call_args = mock_create.call_args
        assert call_args[0][1] == mock_config.supabase_anon_key
        assert call_args[0][1] != mock_config.supabase_service_key
        
        # Verify Authorization header contains user's token
        assert mock_client.postgrest.session.headers["Authorization"] == f"Bearer {sample_token}"


def test_service_client_bypasses_rls(mock_config) -> None:
    """Test that service client uses service_key which bypasses RLS."""
    with patch("src.auth.client.create_client") as mock_create:
        mock_client = Mock()
        mock_create.return_value = mock_client
        
        client = create_service_client(mock_config)
        
        # Verify service_key was used
        call_args = mock_create.call_args
        assert call_args[0][1] == mock_config.supabase_service_key
        assert call_args[0][1] != mock_config.supabase_anon_key
