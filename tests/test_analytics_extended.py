"""Tests for extended analytics endpoints."""
from unittest.mock import Mock, patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from src.main import app


class TestExtendedAnalyticsAPI:
    """Integration tests for new analytics endpoints."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)

    def test_rent_by_property_success(self, client) -> None:
        """Test rent grouped by property."""
        with patch("src.api.routes.effective_rent.get_supabase_client") as mock_get_supabase:
            with patch("src.api.routes.effective_rent.require_permission") as mock_auth_dep:
                mock_auth_context = Mock()
                mock_auth_context.user_id = uuid4()
                mock_auth_context.tenant_id = uuid4()
                mock_auth_dep.return_value = lambda: mock_auth_context

                mock_supabase = Mock()
                mock_get_supabase.return_value = mock_supabase

                # Mock extraction and field data
                def mock_table(table_name):
                    mock_chain = Mock()
                    if table_name == "extractions":
                        mock_chain.select.return_value.eq.return_value.execute.return_value.data = [
                            {"id": str(uuid4()), "document_id": str(uuid4()), "document_type": "lease", "extracted_at": None}
                        ]
                    elif table_name == "extraction_fields":
                        mock_chain.select.return_value.eq.return_value.execute.return_value.data = [
                            {"field_name": "tenant_name", "field_value": {"value": "Test Tenant"}, "confidence": 0.95},
                            {"field_name": "base_rent", "field_value": {"value": "$10,000"}, "confidence": 0.95},
                            {"field_name": "property_name", "field_value": {"value": "Test Building"}, "confidence": 0.90},
                        ]
                    elif table_name == "documents":
                        mock_chain.select.return_value.eq.return_value.single.return_value.execute.return_value.data = {
                            "original_filename": "Lease.pdf"
                        }
                    return mock_chain

                mock_supabase.table.side_effect = mock_table

                response = client.get("/api/v1/analytics/rent-by-property")

                assert response.status_code == 200
                data = response.json()
                assert "properties" in data
                assert "total_properties" in data

    def test_rent_concentration_success(self, client) -> None:
        """Test rent concentration analysis."""
        with patch("src.api.routes.effective_rent.get_supabase_client") as mock_get_supabase:
            with patch("src.api.routes.effective_rent.require_permission") as mock_auth_dep:
                mock_auth_context = Mock()
                mock_auth_context.user_id = uuid4()
                mock_auth_context.tenant_id = uuid4()
                mock_auth_dep.return_value = lambda: mock_auth_context

                mock_supabase = Mock()
                mock_get_supabase.return_value = mock_supabase

                def mock_table(table_name):
                    mock_chain = Mock()
                    if table_name == "extractions":
                        mock_chain.select.return_value.eq.return_value.execute.return_value.data = [
                            {"id": str(uuid4()), "document_id": str(uuid4()), "document_type": "lease", "extracted_at": None}
                        ]
                    elif table_name == "extraction_fields":
                        mock_chain.select.return_value.eq.return_value.execute.return_value.data = [
                            {"field_name": "tenant_name", "field_value": {"value": "Top Tenant"}, "confidence": 0.95},
                            {"field_name": "base_rent", "field_value": {"value": "$50,000"}, "confidence": 0.95},
                        ]
                    elif table_name == "documents":
                        mock_chain.select.return_value.eq.return_value.single.return_value.execute.return_value.data = {
                            "original_filename": "Lease.pdf"
                        }
                    return mock_chain

                mock_supabase.table.side_effect = mock_table

                response = client.get("/api/v1/analytics/rent-concentration?top_n=10")

                assert response.status_code == 200
                data = response.json()
                assert "top_tenants" in data
                assert "top_10_concentration" in data

    def test_rent_per_sf_success(self, client) -> None:
        """Test rent per SF analysis."""
        with patch("src.api.routes.effective_rent.get_supabase_client") as mock_get_supabase:
            with patch("src.api.routes.effective_rent.require_permission") as mock_auth_dep:
                mock_auth_context = Mock()
                mock_auth_context.user_id = uuid4()
                mock_auth_context.tenant_id = uuid4()
                mock_auth_dep.return_value = lambda: mock_auth_context

                mock_supabase = Mock()
                mock_get_supabase.return_value = mock_supabase

                def mock_table(table_name):
                    mock_chain = Mock()
                    if table_name == "extractions":
                        mock_chain.select.return_value.eq.return_value.execute.return_value.data = [
                            {"id": str(uuid4()), "document_id": str(uuid4()), "document_type": "lease", "extracted_at": None}
                        ]
                    elif table_name == "extraction_fields":
                        mock_chain.select.return_value.eq.return_value.execute.return_value.data = [
                            {"field_name": "tenant_name", "field_value": {"value": "Test Tenant"}, "confidence": 0.95},
                            {"field_name": "base_rent", "field_value": {"value": "$10,000"}, "confidence": 0.95},
                            {"field_name": "square_footage", "field_value": {"value": "5000"}, "confidence": 0.90},
                        ]
                    elif table_name == "documents":
                        mock_chain.select.return_value.eq.return_value.single.return_value.execute.return_value.data = {
                            "original_filename": "Lease.pdf"
                        }
                    return mock_chain

                mock_supabase.table.side_effect = mock_table

                response = client.get("/api/v1/analytics/rent-per-sf")

                assert response.status_code == 200
                data = response.json()
                assert "tenants" in data
                assert "average_rent_per_sf_monthly" in data
                assert "average_rent_per_sf_annual" in data

    def test_portfolio_metrics_success(self, client) -> None:
        """Test portfolio metrics dashboard."""
        with patch("src.api.routes.effective_rent.get_supabase_client") as mock_get_supabase:
            with patch("src.api.routes.effective_rent.require_permission") as mock_auth_dep:
                mock_auth_context = Mock()
                mock_auth_context.user_id = uuid4()
                mock_auth_context.tenant_id = uuid4()
                mock_auth_dep.return_value = lambda: mock_auth_context

                mock_supabase = Mock()
                mock_get_supabase.return_value = mock_supabase

                def mock_table(table_name):
                    mock_chain = Mock()
                    if table_name == "extractions":
                        mock_chain.select.return_value.eq.return_value.execute.return_value.data = [
                            {"id": str(uuid4()), "document_id": str(uuid4()), "document_type": "lease", "extracted_at": None}
                            for _ in range(5)
                        ]
                    elif table_name == "extraction_fields":
                        mock_chain.select.return_value.eq.return_value.execute.return_value.data = [
                            {"field_name": "tenant_name", "field_value": {"value": "Tenant"}, "confidence": 0.95},
                            {"field_name": "base_rent", "field_value": {"value": "$10,000"}, "confidence": 0.95},
                            {"field_name": "property_name", "field_value": {"value": "Building A"}, "confidence": 0.90},
                            {"field_name": "square_footage", "field_value": {"value": "5000"}, "confidence": 0.90},
                        ]
                    elif table_name == "documents":
                        mock_chain.select.return_value.eq.return_value.single.return_value.execute.return_value.data = {
                            "original_filename": "Lease.pdf"
                        }
                    return mock_chain

                mock_supabase.table.side_effect = mock_table

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
