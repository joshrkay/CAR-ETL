"""Tests for extended analytics endpoints."""
import pytest
import jwt
from uuid import uuid4
from datetime import datetime, timedelta
from unittest.mock import Mock
from fastapi.testclient import TestClient

from src.main import app
from src.dependencies import get_supabase_client, get_current_user
from src.auth.models import AuthContext
from src.auth.config import get_auth_config
from typing import Any, Generator


class TestExtendedAnalyticsAPI:
    """Integration tests for new analytics endpoints."""

    @pytest.fixture(autouse=True)
    def setup_dependencies(self) -> Generator[None, None, None]:
        """Set up dependency overrides for all tests."""
        # Create mock auth context
        mock_auth_context = Mock(spec=AuthContext)
        self.user_id = uuid4()
        self.tenant_id = uuid4()
        mock_auth_context.user_id = self.user_id
        mock_auth_context.tenant_id = self.tenant_id
        mock_auth_context.email = "test@example.com"
        mock_auth_context.roles = ["Admin"]

        # Create mock user dependency
        def mock_user_dependency() -> AuthContext:
            return mock_auth_context

        # Create mock Supabase client
        mock_supabase = Mock()

        def mock_supabase_dependency() -> Mock:
            return mock_supabase

        # Override dependencies
        app.dependency_overrides[get_current_user] = mock_user_dependency
        app.dependency_overrides[get_supabase_client] = mock_supabase_dependency

        # Store for test access
        self.mock_supabase = mock_supabase
        self.mock_auth_context = mock_auth_context

        yield

        # Clean up
        app.dependency_overrides.clear()

    @pytest.fixture
    def auth_token(self) -> str:
        """Generate a valid JWT token for testing."""
        config = get_auth_config()
        exp = datetime.utcnow() + timedelta(hours=1)
        payload = {
            "sub": str(self.user_id),
            "email": "test@example.com",
            "app_metadata": {
                "tenant_id": str(self.tenant_id),
                "roles": ["Admin"],
                "tenant_slug": "test-tenant",
            },
            "exp": int(exp.timestamp()),
        }
        return jwt.encode(payload, config.supabase_jwt_secret, algorithm="HS256")

    @pytest.fixture
    def client(self, auth_token: str) -> TestClient:
        """Create test client with auth headers."""
        client = TestClient(app)
        client.headers = {"Authorization": f"Bearer {auth_token}"}
        return client

    def test_rent_by_property_success(self, client: Any) -> None:
        """Test rent grouped by property."""
        extraction_id = str(uuid4())
        document_id = str(uuid4())

        # Mock extraction and field data
        def mock_table(table_name: str) -> Any:
            mock_chain = Mock()
            mock_result = Mock()

            if table_name == "extractions":
                # Handle: .select(...).eq('is_current', True).execute()
                mock_result.data = [
                    {"id": extraction_id, "document_id": document_id, "document_type": "lease", "extracted_at": None}
                ]
                mock_chain.select.return_value.eq.return_value.execute.return_value = mock_result
            elif table_name == "extraction_fields":
                # Handle: .select(...).eq('extraction_id', ...).execute()
                mock_result.data = [
                    {"field_name": "tenant_name", "field_value": {"value": "Test Tenant"}, "confidence": 0.95},
                    {"field_name": "base_rent", "field_value": {"value": "$10,000"}, "confidence": 0.95},
                    {"field_name": "property_name", "field_value": {"value": "Test Building"}, "confidence": 0.90},
                ]
                mock_chain.select.return_value.eq.return_value.execute.return_value = mock_result
            elif table_name == "documents":
                # Handle: .select(...).eq('id', ...).limit(1).execute()
                mock_result.data = [{"original_filename": "Lease.pdf"}]
                mock_chain.select.return_value.eq.return_value.limit.return_value.execute.return_value = mock_result

            return mock_chain

        self.mock_supabase.table.side_effect = mock_table

        response = client.get("/api/v1/analytics/rent-by-property")

        if response.status_code != 200:
            print(f"\n=== RESPONSE DEBUG ===")
            print(f"Status: {response.status_code}")
            print(f"Body: {response.text}")
            print(f"======================\n")

        assert response.status_code == 200
        data = response.json()
        assert "properties" in data
        assert "total_properties" in data

    def test_rent_concentration_success(self, client: Any) -> None:
        """Test rent concentration analysis."""
        extraction_id = str(uuid4())
        document_id = str(uuid4())

        def mock_table(table_name: str) -> Any:
            mock_chain = Mock()
            mock_result = Mock()

            if table_name == "extractions":
                mock_result.data = [
                    {"id": extraction_id, "document_id": document_id, "document_type": "lease", "extracted_at": None}
                ]
                mock_chain.select.return_value.eq.return_value.execute.return_value = mock_result
            elif table_name == "extraction_fields":
                mock_result.data = [
                    {"field_name": "tenant_name", "field_value": {"value": "Top Tenant"}, "confidence": 0.95},
                    {"field_name": "base_rent", "field_value": {"value": "$50,000"}, "confidence": 0.95},
                ]
                mock_chain.select.return_value.eq.return_value.execute.return_value = mock_result
            elif table_name == "documents":
                mock_result.data = [{"original_filename": "Lease.pdf"}]
                mock_chain.select.return_value.eq.return_value.limit.return_value.execute.return_value = mock_result

            return mock_chain

        self.mock_supabase.table.side_effect = mock_table

        response = client.get("/api/v1/analytics/rent-concentration?top_n=10")

        assert response.status_code == 200
        data = response.json()
        assert "top_tenants" in data
        assert "top_10_concentration" in data

    def test_rent_per_sf_success(self, client: Any) -> None:
        """Test rent per SF analysis."""
        extraction_id = str(uuid4())
        document_id = str(uuid4())

        def mock_table(table_name: str) -> Any:
            mock_chain = Mock()
            mock_result = Mock()

            if table_name == "extractions":
                mock_result.data = [
                    {"id": extraction_id, "document_id": document_id, "document_type": "lease", "extracted_at": None}
                ]
                mock_chain.select.return_value.eq.return_value.execute.return_value = mock_result
            elif table_name == "extraction_fields":
                mock_result.data = [
                    {"field_name": "tenant_name", "field_value": {"value": "Test Tenant"}, "confidence": 0.95},
                    {"field_name": "base_rent", "field_value": {"value": "$10,000"}, "confidence": 0.95},
                    {"field_name": "square_footage", "field_value": {"value": "5000"}, "confidence": 0.90},
                ]
                mock_chain.select.return_value.eq.return_value.execute.return_value = mock_result
            elif table_name == "documents":
                mock_result.data = [{"original_filename": "Lease.pdf"}]
                mock_chain.select.return_value.eq.return_value.limit.return_value.execute.return_value = mock_result

            return mock_chain

        self.mock_supabase.table.side_effect = mock_table

        response = client.get("/api/v1/analytics/rent-per-sf")

        assert response.status_code == 200
        data = response.json()
        assert "tenants" in data
        assert "average_rent_per_sf_monthly" in data
        assert "average_rent_per_sf_annual" in data

    def test_portfolio_metrics_success(self, client: Any) -> None:
        """Test portfolio metrics dashboard."""
        extraction_id = str(uuid4())
        document_id = str(uuid4())

        def mock_table(table_name: str) -> Any:
            mock_chain = Mock()
            mock_result = Mock()

            if table_name == "extractions":
                mock_result.data = [
                    {"id": extraction_id, "document_id": document_id, "document_type": "lease", "extracted_at": None}
                ]
                mock_chain.select.return_value.eq.return_value.execute.return_value = mock_result
            elif table_name == "extraction_fields":
                mock_result.data = [
                    {"field_name": "tenant_name", "field_value": {"value": "Tenant"}, "confidence": 0.95},
                    {"field_name": "base_rent", "field_value": {"value": "$10,000"}, "confidence": 0.95},
                    {"field_name": "property_name", "field_value": {"value": "Building A"}, "confidence": 0.90},
                    {"field_name": "square_footage", "field_value": {"value": "5000"}, "confidence": 0.90},
                ]
                mock_chain.select.return_value.eq.return_value.execute.return_value = mock_result
            elif table_name == "documents":
                mock_result.data = [{"original_filename": "Lease.pdf"}]
                mock_chain.select.return_value.eq.return_value.limit.return_value.execute.return_value = mock_result

            return mock_chain

        self.mock_supabase.table.side_effect = mock_table

        response = client.get("/api/v1/analytics/portfolio-metrics")

        assert response.status_code == 200
        data = response.json()
        assert "total_tenants" in data
        assert "total_properties" in data
        assert "total_monthly_rent" in data
        assert "average_rent_per_tenant" in data
        assert "top_tenant_concentration" in data
        assert "top_5_concentration" in data
        assert "top_10_concentration" in data
