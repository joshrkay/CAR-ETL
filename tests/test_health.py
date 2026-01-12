"""Unit tests for health check endpoints."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient
from fastapi import FastAPI

from src.api.routes import health as health_routes
from src.services.health_checker import HealthChecker, HealthCheckResult
from typing import Any, Generator


@pytest.fixture
def app() -> FastAPI:
    """Create FastAPI app with health routes."""
    app = FastAPI()
    app.include_router(health_routes.router)
    return app


@pytest.fixture
def client(app: Any) -> TestClient:
    """Create test client."""
    return TestClient(app)


class TestHealthLiveness:
    """Test liveness endpoint."""
    
    def test_health_liveness_returns_200(self, client: Any) -> None:
        """Test that /health returns 200 OK."""
        response = client.get("/health")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"


class TestHealthReadiness:
    """Test readiness endpoint."""
    
    @pytest.mark.asyncio
    async def test_readiness_all_healthy(self, client: Any) -> None:
        """Test readiness check when all services are healthy."""
        with patch("src.api.routes.health.HealthChecker") as mock_checker_class:
            mock_checker = MagicMock()
            mock_checker_class.return_value = mock_checker
            
            # Mock all checks returning healthy
            mock_checker.check_all = AsyncMock(return_value={
                "database": HealthCheckResult(status="up", latency_ms=5),
                "storage": HealthCheckResult(status="up", latency_ms=12),
                "auth": HealthCheckResult(status="up", latency_ms=8),
            })
            mock_checker.get_overall_status.return_value = "healthy"
            
            response = client.get("/health/ready")
            
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "healthy"
            assert "checks" in data
            assert data["checks"]["database"]["status"] == "up"
            assert data["checks"]["storage"]["status"] == "up"
            assert data["checks"]["auth"]["status"] == "up"
            assert data["version"] == "1.0.0"
    
    @pytest.mark.asyncio
    async def test_readiness_unhealthy_returns_503(self, client: Any) -> None:
        """Test readiness check returns 503 when services are unhealthy."""
        with patch("src.api.routes.health.HealthChecker") as mock_checker_class:
            mock_checker = MagicMock()
            mock_checker_class.return_value = mock_checker
            
            # Mock checks returning unhealthy
            mock_checker.check_all = AsyncMock(return_value={
                "database": HealthCheckResult(status="down", latency_ms=5000, error="Connection timeout"),
                "storage": HealthCheckResult(status="up", latency_ms=12),
                "auth": HealthCheckResult(status="up", latency_ms=8),
            })
            mock_checker.get_overall_status.return_value = "unhealthy"
            
            response = client.get("/health/ready")
            
            assert response.status_code == 503
            data = response.json()
            assert data["status"] == "unhealthy"
            assert data["checks"]["database"]["status"] == "down"
            assert "error" in data["checks"]["database"]
    
    @pytest.mark.asyncio
    async def test_readiness_includes_latency(self, client: Any) -> None:
        """Test that readiness check includes latency for each service."""
        with patch("src.api.routes.health.HealthChecker") as mock_checker_class:
            mock_checker = MagicMock()
            mock_checker_class.return_value = mock_checker
            
            mock_checker.check_all = AsyncMock(return_value={
                "database": HealthCheckResult(status="up", latency_ms=5),
                "storage": HealthCheckResult(status="up", latency_ms=12),
                "auth": HealthCheckResult(status="up", latency_ms=8),
            })
            mock_checker.get_overall_status.return_value = "healthy"
            
            response = client.get("/health/ready")
            
            assert response.status_code == 200
            data = response.json()
            assert data["checks"]["database"]["latency_ms"] == 5
            assert data["checks"]["storage"]["latency_ms"] == 12
            assert data["checks"]["auth"]["latency_ms"] == 8


class TestHealthChecker:
    """Test HealthChecker service."""
    
    @pytest.fixture
    def health_checker(self) -> Any:
        """Create HealthChecker instance."""
        with patch("src.services.health_checker.get_auth_config"):
            with patch("src.services.health_checker.create_service_client"):
                return HealthChecker()
    
    @pytest.mark.asyncio
    async def test_check_database_success(self, health_checker: Any) -> None:
        """Test database check succeeds."""
        mock_client = MagicMock()
        mock_client.table.return_value.select.return_value.limit.return_value.execute.return_value = MagicMock()
        health_checker.service_client = mock_client
        
        result = await health_checker.check_database()
        
        assert result.status == "up"
        assert result.latency_ms >= 0
        assert result.error is None
    
    @pytest.mark.asyncio
    async def test_check_database_failure(self, health_checker: Any) -> None:
        """Test database check fails on error."""
        mock_client = MagicMock()
        mock_client.table.return_value.select.return_value.limit.return_value.execute.side_effect = Exception("Connection failed")
        health_checker.service_client = mock_client
        
        result = await health_checker.check_database()
        
        assert result.status == "down"
        assert result.error is not None
        assert "Connection failed" in result.error
    
    @pytest.mark.asyncio
    async def test_check_storage_success(self, health_checker: Any) -> None:
        """Test storage check succeeds."""
        mock_client = MagicMock()
        mock_client.storage.list_buckets.return_value = []
        health_checker.service_client = mock_client
        
        result = await health_checker.check_storage()
        
        assert result.status == "up"
        assert result.latency_ms >= 0
        assert result.error is None
    
    @pytest.mark.asyncio
    async def test_check_storage_failure(self, health_checker: Any) -> None:
        """Test storage check fails on error."""
        mock_client = MagicMock()
        mock_client.storage.list_buckets.side_effect = Exception("Storage unavailable")
        health_checker.service_client = mock_client
        
        result = await health_checker.check_storage()
        
        assert result.status == "down"
        assert result.error is not None
        assert "Storage unavailable" in result.error
    
    @pytest.mark.asyncio
    async def test_check_auth_success(self, health_checker: Any) -> None:
        """Test auth check succeeds."""
        
        health_checker.config = MagicMock()
        health_checker.config.supabase_url = "https://test.supabase.co"
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client.get.return_value = mock_response
            
            result = await health_checker.check_auth()
            
            assert result.status == "up"
            assert result.latency_ms >= 0
            assert result.error is None
    
    @pytest.mark.asyncio
    async def test_check_auth_timeout(self, health_checker: Any) -> None:
        """Test auth check handles timeout."""
        import httpx
        
        health_checker.config = MagicMock()
        health_checker.config.supabase_url = "https://test.supabase.co"
        
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client.get.side_effect = httpx.TimeoutException("Request timed out")
            
            result = await health_checker.check_auth()
            
            assert result.status == "down"
            assert result.error == "Timeout"
    
    @pytest.mark.asyncio
    async def test_check_all_runs_all_checks(self, health_checker: Any) -> None:
        """Test that check_all runs all component checks."""
        mock_client = MagicMock()
        mock_client.table.return_value.select.return_value.limit.return_value.execute.return_value = MagicMock()
        mock_client.storage.list_buckets.return_value = []
        health_checker.service_client = mock_client
        
        health_checker.config = MagicMock()
        health_checker.config.supabase_url = "https://test.supabase.co"
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        
        with patch("httpx.AsyncClient") as mock_httpx:
            mock_http_client = AsyncMock()
            mock_httpx.return_value.__aenter__.return_value = mock_http_client
            mock_http_client.get.return_value = mock_response
            
            results = await health_checker.check_all()
            
            assert "database" in results
            assert "storage" in results
            assert "auth" in results
            assert len(results) == 3
    
    def test_get_overall_status_healthy(self, health_checker: Any) -> None:
        """Test overall status when all checks pass."""
        checks = {
            "database": HealthCheckResult(status="up", latency_ms=5),
            "storage": HealthCheckResult(status="up", latency_ms=12),
            "auth": HealthCheckResult(status="up", latency_ms=8),
        }
        
        status = health_checker.get_overall_status(checks)
        assert status == "healthy"
    
    def test_get_overall_status_unhealthy(self, health_checker: Any) -> None:
        """Test overall status when any check fails."""
        checks = {
            "database": HealthCheckResult(status="down", latency_ms=5000, error="Timeout"),
            "storage": HealthCheckResult(status="up", latency_ms=12),
            "auth": HealthCheckResult(status="up", latency_ms=8),
        }
        
        status = health_checker.get_overall_status(checks)
        assert status == "unhealthy"


class TestHealthCheckResult:
    """Test HealthCheckResult model."""
    
    def test_to_dict_without_error(self) -> None:
        """Test converting result to dict without error."""
        result = HealthCheckResult(status="up", latency_ms=5)
        data = result.to_dict()
        
        assert data["status"] == "up"
        assert data["latency_ms"] == 5
        assert "error" not in data
    
    def test_to_dict_with_error(self) -> None:
        """Test converting result to dict with error."""
        result = HealthCheckResult(status="down", latency_ms=5000, error="Connection failed")
        data = result.to_dict()
        
        assert data["status"] == "down"
        assert data["latency_ms"] == 5000
        assert data["error"] == "Connection failed"
