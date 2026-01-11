"""
Integration Tests for Entity Merge Endpoint

Tests cover:
- Successful entity merge
- Validation errors (same entity merge)
- NotFoundError handling for source entity
- NotFoundError handling for target entity
- Permission enforcement
- General exception handling
"""

from typing import Any, Generator
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, patch, AsyncMock
from uuid import uuid4

import pytest
import jwt
from fastapi import status
from fastapi.testclient import TestClient

from src.main import app
from src.auth.models import AuthContext
from src.auth.config import AuthConfig
from src.exceptions import NotFoundError


@pytest.fixture
def mock_auth_context() -> AuthContext:
    """Create a mock authenticated user context."""
    auth = Mock(spec=AuthContext)
    auth.user_id = uuid4()
    auth.tenant_id = uuid4()
    auth.email = "test@example.com"
    auth.roles = ["Admin"]
    auth.tenant_slug = "test-tenant"
    auth.has_permission = Mock(return_value=True)
    return auth


@pytest.fixture
def mock_supabase_client() -> Any:
    """Create a mock Supabase client."""
    client = Mock()
    
    # Mock rate limit table (for auth rate limiter)
    rate_limit_response = Mock()
    rate_limit_response.data = []
    rate_limit_response.execute = Mock(return_value=rate_limit_response)
    
    rate_limit_query = Mock()
    rate_limit_query.limit = Mock(return_value=rate_limit_query)
    rate_limit_query.order = Mock(return_value=rate_limit_query)
    rate_limit_query.gte = Mock(return_value=rate_limit_query)
    rate_limit_query.eq = Mock(return_value=rate_limit_query)
    rate_limit_query.select = Mock(return_value=rate_limit_query)
    rate_limit_query.execute = Mock(return_value=rate_limit_response)
    
    client.table = Mock(return_value=rate_limit_query)
    
    return client


@pytest.fixture
def mock_auth_config() -> Any:
    """Create mock auth config for testing."""
    return AuthConfig(
        supabase_url="https://test.supabase.co",
        supabase_anon_key="test-anon-key",
        supabase_service_key="test-service-key",
        supabase_jwt_secret="test-jwt-secret-for-testing-only-do-not-use-in-production",
        app_env="test",
    )


@pytest.fixture
def valid_jwt_token(mock_auth_context, mock_auth_config) -> Any:
    """Create a valid JWT token for testing."""
    exp = datetime.now(timezone.utc) + timedelta(hours=1)
    payload = {
        "sub": str(mock_auth_context.user_id),
        "email": mock_auth_context.email,
        "app_metadata": {
            "tenant_id": str(mock_auth_context.tenant_id),
            "roles": mock_auth_context.roles,
            "tenant_slug": mock_auth_context.tenant_slug,
        },
        "exp": int(exp.timestamp()),
    }
    
    return jwt.encode(payload, mock_auth_config.supabase_jwt_secret, algorithm="HS256")


@pytest.fixture
def mock_audit_logger() -> Generator:
    """Create a mock audit logger."""
    logger = Mock()
    logger.log_entity_merge = AsyncMock()
    return logger


@pytest.fixture
def client_with_auth(mock_auth_context, mock_supabase_client, valid_jwt_token, mock_auth_config, mock_audit_logger) -> Generator:
    """Create test client with mocked auth and dependencies."""
    from src.dependencies import get_current_user, get_supabase_client, get_audit_logger
    
    def override_get_current_user():
        return mock_auth_context
    
    def override_get_supabase_client():
        return mock_supabase_client
    
    def override_get_audit_logger():
        return mock_audit_logger
    
    # Patch rate limiter
    rate_limiter_patcher = patch("src.auth.rate_limit.create_client", return_value=mock_supabase_client)
    rate_limiter_patcher.start()
    
    # Patch auth config at multiple points where it's used
    config_patcher1 = patch("src.auth.middleware.get_auth_config", return_value=mock_auth_config)
    config_patcher2 = patch("src.auth.config.get_auth_config", return_value=mock_auth_config)
    config_patcher1.start()
    config_patcher2.start()
    
    # Patch the middleware's _validate_token to bypass validation
    async def mock_validate_token(self, request):
        # Set auth context directly
        request.state.auth = mock_auth_context
        request.state.supabase = mock_supabase_client
        return None
    
    middleware_patcher = patch("src.auth.middleware.AuthMiddleware._validate_token", mock_validate_token)
    middleware_patcher.start()
    
    try:
        app.dependency_overrides[get_current_user] = override_get_current_user
        app.dependency_overrides[get_supabase_client] = override_get_supabase_client
        app.dependency_overrides[get_audit_logger] = override_get_audit_logger
        
        client = TestClient(app)
        
        yield client, valid_jwt_token, mock_auth_context
        
        # Cleanup
        app.dependency_overrides.clear()
        middleware_patcher.stop()
        config_patcher2.stop()
        config_patcher1.stop()
    finally:
        rate_limiter_patcher.stop()


class TestEntityMergeEndpoint:
    """Test entity merge endpoint."""

    def test_successful_merge(self, client_with_auth) -> None:
        """Test successful entity merge."""
        client, token, auth_context = client_with_auth
        
        entity_id = uuid4()
        merge_into_id = uuid4()
        
        # Mock the merge_entities function to return success
        mock_result = Mock()
        mock_result.merged_entity_id = merge_into_id
        mock_result.documents_updated = 5
        
        with patch("src.api.routes.entities.merge_entities", new_callable=AsyncMock) as mock_merge:
            mock_merge.return_value = mock_result
            
            response = client.post(
                f"/api/v1/entities/{entity_id}/merge",
                json={"merge_into_id": str(merge_into_id)},
                headers={"Authorization": f"Bearer {token}"},
            )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["merged_entity_id"] == str(merge_into_id)
        assert data["documents_updated"] == 5
        
        # Verify merge_entities was called with correct parameters
        mock_merge.assert_called_once()
        call_kwargs = mock_merge.call_args.kwargs
        assert call_kwargs["tenant_id"] == auth_context.tenant_id
        assert call_kwargs["source_entity_id"] == entity_id
        assert call_kwargs["target_entity_id"] == merge_into_id
        assert call_kwargs["reviewed_by"] == auth_context.user_id

    def test_merge_same_entity_returns_400(self, client_with_auth) -> None:
        """Test merging entity with itself returns validation error."""
        client, token, _ = client_with_auth
        
        entity_id = uuid4()
        
        response = client.post(
            f"/api/v1/entities/{entity_id}/merge",
            json={"merge_into_id": str(entity_id)},
            headers={"Authorization": f"Bearer {token}"},
        )
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        data = response.json()
        assert data["detail"]["code"] == "INVALID_MERGE"
        assert "merge_into_id must be different from entity_id" in data["detail"]["message"]

    def test_source_entity_not_found(self, client_with_auth) -> None:
        """Test merge with non-existent source entity returns 404."""
        client, token, _ = client_with_auth
        
        entity_id = uuid4()
        merge_into_id = uuid4()
        
        # Mock merge_entities to raise NotFoundError for source entity
        with patch("src.api.routes.entities.merge_entities", new_callable=AsyncMock) as mock_merge:
            mock_merge.side_effect = NotFoundError(
                resource_type="Entity",
                resource_id=str(entity_id)
            )
            
            response = client.post(
                f"/api/v1/entities/{entity_id}/merge",
                json={"merge_into_id": str(merge_into_id)},
                headers={"Authorization": f"Bearer {token}"},
            )
        
        assert response.status_code == status.HTTP_404_NOT_FOUND
        data = response.json()
        assert data["detail"]["code"] == "NOT_FOUND"
        assert str(entity_id) in data["detail"]["message"]

    def test_target_entity_not_found(self, client_with_auth) -> None:
        """Test merge with non-existent target entity returns 404."""
        client, token, _ = client_with_auth
        
        entity_id = uuid4()
        merge_into_id = uuid4()
        
        # Mock merge_entities to raise NotFoundError for target entity
        with patch("src.api.routes.entities.merge_entities", new_callable=AsyncMock) as mock_merge:
            mock_merge.side_effect = NotFoundError(
                resource_type="Entity",
                resource_id=str(merge_into_id)
            )
            
            response = client.post(
                f"/api/v1/entities/{entity_id}/merge",
                json={"merge_into_id": str(merge_into_id)},
                headers={"Authorization": f"Bearer {token}"},
            )
        
        assert response.status_code == status.HTTP_404_NOT_FOUND
        data = response.json()
        assert data["detail"]["code"] == "NOT_FOUND"
        assert str(merge_into_id) in data["detail"]["message"]

    def test_permission_required(self, mock_supabase_client, valid_jwt_token, mock_auth_config, mock_audit_logger) -> None:
        """Test that entities:merge permission is required."""
        from src.dependencies import get_current_user, get_supabase_client, get_audit_logger
        
        # Create auth context without permission
        auth_without_permission = Mock(spec=AuthContext)
        auth_without_permission.user_id = uuid4()
        auth_without_permission.tenant_id = uuid4()
        auth_without_permission.email = "test@example.com"
        auth_without_permission.roles = ["Viewer"]
        auth_without_permission.tenant_slug = "test-tenant"
        auth_without_permission.has_permission = Mock(return_value=False)
        
        def override_get_current_user():
            return auth_without_permission
        
        def override_get_supabase_client():
            return mock_supabase_client
        
        def override_get_audit_logger():
            return mock_audit_logger
        
        # Patch rate limiter
        rate_limiter_patcher = patch("src.auth.rate_limit.create_client", return_value=mock_supabase_client)
        rate_limiter_patcher.start()
        
        # Patch auth config at multiple points where it's used
        config_patcher1 = patch("src.auth.middleware.get_auth_config", return_value=mock_auth_config)
        config_patcher2 = patch("src.auth.config.get_auth_config", return_value=mock_auth_config)
        config_patcher1.start()
        config_patcher2.start()
        
        # Patch the middleware's _validate_token to bypass validation
        async def mock_validate_token(self, request):
            # Set auth context directly
            request.state.auth = auth_without_permission
            request.state.supabase = mock_supabase_client
            return None
        
        middleware_patcher = patch("src.auth.middleware.AuthMiddleware._validate_token", mock_validate_token)
        middleware_patcher.start()
        
        try:
            app.dependency_overrides[get_current_user] = override_get_current_user
            app.dependency_overrides[get_supabase_client] = override_get_supabase_client
            app.dependency_overrides[get_audit_logger] = override_get_audit_logger
            
            client = TestClient(app)
            
            entity_id = uuid4()
            merge_into_id = uuid4()
            
            response = client.post(
                f"/api/v1/entities/{entity_id}/merge",
                json={"merge_into_id": str(merge_into_id)},
                headers={"Authorization": f"Bearer {valid_jwt_token}"},
            )
            
            # Permission check should prevent access
            assert response.status_code == status.HTTP_403_FORBIDDEN
            
        finally:
            app.dependency_overrides.clear()
            middleware_patcher.stop()
            config_patcher2.stop()
            config_patcher1.stop()
            rate_limiter_patcher.stop()

    def test_general_exception_handling(self, client_with_auth) -> None:
        """Test that general exceptions are handled and return 500."""
        client, token, _ = client_with_auth
        
        entity_id = uuid4()
        merge_into_id = uuid4()
        
        # Mock merge_entities to raise a general exception
        with patch("src.api.routes.entities.merge_entities", new_callable=AsyncMock) as mock_merge:
            mock_merge.side_effect = Exception("Database connection error")
            
            response = client.post(
                f"/api/v1/entities/{entity_id}/merge",
                json={"merge_into_id": str(merge_into_id)},
                headers={"Authorization": f"Bearer {token}"},
            )
        
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        data = response.json()
        assert data["detail"]["code"] == "MERGE_FAILED"
        assert data["detail"]["message"] == "Failed to merge entities"

    def test_missing_authorization_header(self, mock_supabase_client, mock_auth_config) -> None:
        """Test request without Authorization header returns 401."""
        from src.dependencies import get_supabase_client
        
        def override_get_supabase_client():
            return mock_supabase_client
        
        # Patch rate limiter
        rate_limiter_patcher = patch("src.auth.rate_limit.create_client", return_value=mock_supabase_client)
        rate_limiter_patcher.start()
        
        # Patch auth config at multiple points where it's used
        config_patcher1 = patch("src.auth.middleware.get_auth_config", return_value=mock_auth_config)
        config_patcher2 = patch("src.auth.config.get_auth_config", return_value=mock_auth_config)
        config_patcher1.start()
        config_patcher2.start()
        
        try:
            app.dependency_overrides[get_supabase_client] = override_get_supabase_client
            
            client = TestClient(app)
            
            entity_id = uuid4()
            merge_into_id = uuid4()
            
            response = client.post(
                f"/api/v1/entities/{entity_id}/merge",
                json={"merge_into_id": str(merge_into_id)},
            )
            
            assert response.status_code == status.HTTP_401_UNAUTHORIZED
            
        finally:
            app.dependency_overrides.clear()
            config_patcher2.stop()
            config_patcher1.stop()
            rate_limiter_patcher.stop()

    def test_invalid_uuid_format(self, client_with_auth) -> None:
        """Test that invalid UUID format in request returns 400 or 422."""
        client, token, _ = client_with_auth
        
        entity_id = uuid4()
        
        response = client.post(
            f"/api/v1/entities/{entity_id}/merge",
            json={"merge_into_id": "not-a-valid-uuid"},
            headers={"Authorization": f"Bearer {token}"},
        )
        
        # Both 400 and 422 are valid responses for invalid input
        assert response.status_code in [status.HTTP_400_BAD_REQUEST, 422]
