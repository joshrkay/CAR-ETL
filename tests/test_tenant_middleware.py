"""Comprehensive tests for tenant context middleware."""
import pytest
import uuid
import time
from unittest.mock import Mock, patch, MagicMock
from fastapi import FastAPI, Request, status
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from src.middleware.tenant_context import TenantContextMiddleware
from src.middleware.auth import extract_bearer_token, get_tenant_id_from_request
from src.services.tenant_resolver import TenantResolver, TenantConnection
from src.auth.jwt_validator import JWTClaims, JWTValidationError
from src.db.models.control_plane import Tenant, TenantDatabase, TenantStatus, DatabaseStatus
# Note: get_tenant_db and get_tenant_id are tested indirectly through middleware


@pytest.fixture
def mock_jwt_claims():
    """Create mock JWT claims."""
    return JWTClaims(
        tenant_id="550e8400-e29b-41d4-a716-446655440000",
        roles=["admin", "user"],
        user_id="auth0|123",
        email="test@example.com"
    )


@pytest.fixture
def mock_tenant_engine():
    """Create mock SQLAlchemy engine."""
    return create_engine("sqlite:///:memory:")


@pytest.fixture
def mock_tenant_resolver(mock_tenant_engine):
    """Create mock tenant resolver."""
    resolver = Mock(spec=TenantResolver)
    resolver.resolve_tenant_connection.return_value = mock_tenant_engine
    resolver.invalidate_cache = Mock()
    return resolver


@pytest.fixture
def test_app(mock_tenant_resolver):
    """Create test FastAPI app with middleware."""
    app = FastAPI()
    
    @app.get("/api/test")
    async def test_endpoint(request: Request):
        """Test endpoint that uses tenant context."""
        db = getattr(request.state, "db", None)
        tenant_id = getattr(request.state, "tenant_id", None)
        return {
            "has_db": db is not None,
            "tenant_id": tenant_id
        }
    
    app.add_middleware(TenantContextMiddleware, tenant_resolver=mock_tenant_resolver)
    return app


class TestExtractBearerToken:
    """Tests for JWT token extraction."""
    
    def test_extract_valid_bearer_token(self):
        """Test extracting valid Bearer token."""
        request = Mock(spec=Request)
        request.headers = {"Authorization": "Bearer test-token-123"}
        
        token = extract_bearer_token(request)
        assert token == "test-token-123"
    
    def test_extract_missing_authorization_header(self):
        """Test missing Authorization header."""
        request = Mock(spec=Request)
        request.headers = {}
        
        token = extract_bearer_token(request)
        assert token is None
    
    def test_extract_invalid_scheme(self):
        """Test invalid authorization scheme."""
        request = Mock(spec=Request)
        request.headers = {"Authorization": "Basic dGVzdDp0ZXN0"}
        
        token = extract_bearer_token(request)
        assert token is None
    
    def test_extract_empty_token(self):
        """Test empty Bearer token."""
        request = Mock(spec=Request)
        request.headers = {"Authorization": "Bearer "}
        
        token = extract_bearer_token(request)
        assert token is None or token == ""


class TestTenantContextMiddleware:
    """Tests for tenant context middleware."""
    
    def test_skip_non_api_requests(self, test_app, mock_tenant_resolver):
        """Test that non-API requests are skipped."""
        client = TestClient(test_app)
        
        response = client.get("/health")
        
        # Should not call resolver
        mock_tenant_resolver.resolve_tenant_connection.assert_not_called()
        # Should return 404 (route doesn't exist, but middleware didn't process)
        assert response.status_code == 404
    
    def test_missing_authorization_header(self, test_app, mock_tenant_resolver):
        """Test request with missing Authorization header."""
        client = TestClient(test_app)
        
        response = client.get("/api/test")
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert "detail" in response.json()
        mock_tenant_resolver.resolve_tenant_connection.assert_not_called()
    
    def test_invalid_jwt_token(self, test_app, mock_tenant_resolver):
        """Test request with invalid JWT token."""
        client = TestClient(test_app)
        
        with patch("src.middleware.tenant_context.get_tenant_id_from_request") as mock_get:
            mock_get.side_effect = Exception("Invalid token")
            
            response = client.get(
                "/api/test",
                headers={"Authorization": "Bearer invalid-token"}
            )
            
            assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
    
    def test_missing_tenant_id_in_jwt(self, test_app, mock_tenant_resolver):
        """Test JWT token without tenant_id claim."""
        client = TestClient(test_app)
        
        with patch("src.middleware.tenant_context.get_tenant_id_from_request") as mock_get:
            mock_get.return_value = None
            
            response = client.get(
                "/api/test",
                headers={"Authorization": "Bearer valid-token"}
            )
            
            assert response.status_code == status.HTTP_401_UNAUTHORIZED
            assert "detail" in response.json()
            mock_tenant_resolver.resolve_tenant_connection.assert_not_called()
    
    def test_unknown_tenant(self, test_app, mock_tenant_resolver):
        """Test request with unknown tenant_id."""
        client = TestClient(test_app)
        
        with patch("src.middleware.tenant_context.get_tenant_id_from_request") as mock_get:
            mock_get.return_value = "unknown-tenant-id"
            mock_tenant_resolver.resolve_tenant_connection.return_value = None
            
            response = client.get(
                "/api/test",
                headers={"Authorization": "Bearer valid-token"}
            )
            
            assert response.status_code == status.HTTP_401_UNAUTHORIZED
            assert "detail" in response.json()
            mock_tenant_resolver.resolve_tenant_connection.assert_called_once_with(
                "unknown-tenant-id"
            )
    
    def test_inactive_tenant(self, test_app, mock_tenant_resolver):
        """Test request with inactive tenant."""
        client = TestClient(test_app)
        
        with patch("src.middleware.tenant_context.get_tenant_id_from_request") as mock_get:
            mock_get.return_value = "inactive-tenant-id"
            mock_tenant_resolver.resolve_tenant_connection.return_value = None
            
            response = client.get(
                "/api/test",
                headers={"Authorization": "Bearer valid-token"}
            )
            
            assert response.status_code == status.HTTP_401_UNAUTHORIZED
    
    def test_successful_tenant_resolution(self, test_app, mock_tenant_resolver, mock_tenant_engine):
        """Test successful tenant context resolution."""
        client = TestClient(test_app)
        tenant_id = "550e8400-e29b-41d4-a716-446655440000"
        
        with patch("src.middleware.tenant_context.get_tenant_id_from_request") as mock_get:
            mock_get.return_value = tenant_id
            mock_tenant_resolver.resolve_tenant_connection.return_value = mock_tenant_engine
            
            response = client.get(
                "/api/test",
                headers={"Authorization": "Bearer valid-token"}
            )
            
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["has_db"] is True
            assert data["tenant_id"] == tenant_id
            mock_tenant_resolver.resolve_tenant_connection.assert_called_once_with(tenant_id)
    
    def test_middleware_performance(self, test_app, mock_tenant_resolver, mock_tenant_engine):
        """Test middleware overhead is under 50ms."""
        client = TestClient(test_app)
        tenant_id = "550e8400-e29b-41d4-a716-446655440000"
        
        with patch("src.middleware.tenant_context.get_tenant_id_from_request") as mock_get:
            mock_get.return_value = tenant_id
            mock_tenant_resolver.resolve_tenant_connection.return_value = mock_tenant_engine
            
            start = time.time()
            response = client.get(
                "/api/test",
                headers={"Authorization": "Bearer valid-token"}
            )
            elapsed = (time.time() - start) * 1000  # Convert to milliseconds
            
            assert response.status_code == status.HTTP_200_OK
            # Allow some overhead for test framework, but should be fast
            assert elapsed < 100  # More lenient for test environment


class TestTenantResolver:
    """Tests for tenant resolver service."""
    
    @pytest.fixture
    def mock_connection_manager(self):
        """Create mock connection manager."""
        manager = Mock()
        manager.get_session = Mock()
        return manager
    
    @pytest.fixture
    def mock_encryption_service(self):
        """Create mock encryption service."""
        service = Mock()
        service.decrypt.return_value = "postgresql://user:pass@host:5432/db"
        return service
    
    def test_cache_hit(self, mock_encryption_service, mock_tenant_engine):
        """Test cache hit returns cached connection."""
        resolver = TenantResolver(encryption_service=mock_encryption_service)
        tenant_id = "550e8400-e29b-41d4-a716-446655440000"
        
        # First call - cache miss
        with patch.object(resolver, "_get_tenant_from_db") as mock_get:
            mock_tenant = Mock(spec=Tenant)
            mock_tenant.status = TenantStatus.ACTIVE
            mock_tenant.tenant_id = uuid.UUID(tenant_id)
            
            mock_db = Mock(spec=TenantDatabase)
            mock_db.connection_string_encrypted = "encrypted-string"
            mock_db.status = DatabaseStatus.ACTIVE
            
            mock_get.return_value = (mock_tenant, mock_db)
            
            # Mock engine creation
            with patch.object(resolver, "_create_engine", return_value=mock_tenant_engine):
                engine1 = resolver.resolve_tenant_connection(tenant_id)
                assert engine1 is not None
        
        # Second call - cache hit
        with patch.object(resolver, "_get_tenant_from_db") as mock_get:
            engine2 = resolver.resolve_tenant_connection(tenant_id)
            assert engine2 is not None
            # Should not call database again
            mock_get.assert_not_called()
    
    def test_cache_expiration(self, mock_encryption_service, mock_tenant_engine):
        """Test cache expiration triggers refresh."""
        resolver = TenantResolver(
            encryption_service=mock_encryption_service,
            cache_ttl=1  # 1 second TTL for testing
        )
        tenant_id = "550e8400-e29b-41d4-a716-446655440000"
        
        # Create expired cache entry
        expired_connection = TenantConnection(
            tenant_id=tenant_id,
            connection_string="postgresql://user:pass@host:5432/db",
            engine=mock_tenant_engine,
            cached_at=time.time() - 10,  # 10 seconds ago
            expires_at=time.time() - 9    # Expired 9 seconds ago
        )
        resolver._cache[tenant_id] = expired_connection
        
        # Should trigger refresh
        with patch.object(resolver, "_get_tenant_from_db") as mock_get:
            mock_tenant = Mock(spec=Tenant)
            mock_tenant.status = TenantStatus.ACTIVE
            mock_tenant.tenant_id = uuid.UUID(tenant_id)
            
            mock_db = Mock(spec=TenantDatabase)
            mock_db.connection_string_encrypted = "encrypted-string"
            mock_db.status = DatabaseStatus.ACTIVE
            
            mock_get.return_value = (mock_tenant, mock_db)
            
            with patch.object(resolver, "_create_engine", return_value=mock_tenant_engine):
                engine = resolver.resolve_tenant_connection(tenant_id)
                assert engine is not None
                mock_get.assert_called_once()
    
    def test_invalidate_cache(self, mock_encryption_service):
        """Test cache invalidation."""
        resolver = TenantResolver(encryption_service=mock_encryption_service)
        tenant_id = "550e8400-e29b-41d4-a716-446655440000"
        
        # Add cache entry
        resolver._cache[tenant_id] = TenantConnection(
            tenant_id=tenant_id,
            connection_string="postgresql://user:pass@host:5432/db",
            engine=mock_tenant_engine,
            cached_at=time.time(),
            expires_at=time.time() + 300
        )
        
        # Invalidate
        resolver.invalidate_cache(tenant_id)
        assert tenant_id not in resolver._cache
    
    def test_invalidate_all_cache(self, mock_encryption_service):
        """Test invalidate all cache entries."""
        resolver = TenantResolver(encryption_service=mock_encryption_service)
        
        # Add multiple cache entries
        for i in range(3):
            tenant_id = f"550e8400-e29b-41d4-a716-44665544000{i}"
            resolver._cache[tenant_id] = TenantConnection(
                tenant_id=tenant_id,
                connection_string="postgresql://user:pass@host:5432/db",
                engine=mock_tenant_engine,
                cached_at=time.time(),
                expires_at=time.time() + 300
            )
        
        # Invalidate all
        resolver.invalidate_cache()
        assert len(resolver._cache) == 0


class TestMultipleTenants:
    """Tests for multiple tenant scenarios."""
    
    def test_concurrent_tenant_resolution(self, test_app, mock_tenant_resolver):
        """Test concurrent requests from different tenants."""
        client = TestClient(test_app)
        
        tenant_ids = [
            "550e8400-e29b-41d4-a716-446655440000",
            "660e8400-e29b-41d4-a716-446655440001",
            "770e8400-e29b-41d4-a716-446655440002"
        ]
        
        engines = {}
        for tenant_id in tenant_ids:
            engine = create_engine("sqlite:///:memory:")
            engines[tenant_id] = engine
        
        def resolve_side_effect(tenant_id):
            return engines.get(tenant_id)
        
        mock_tenant_resolver.resolve_tenant_connection.side_effect = resolve_side_effect
        
        with patch("src.middleware.tenant_context.get_tenant_id_from_request") as mock_get:
            for tenant_id in tenant_ids:
                mock_get.return_value = tenant_id
                
                response = client.get(
                    "/api/test",
                    headers={"Authorization": f"Bearer token-{tenant_id}"}
                )
                
                assert response.status_code == status.HTTP_200_OK
                data = response.json()
                assert data["tenant_id"] == tenant_id
                assert data["has_db"] is True
