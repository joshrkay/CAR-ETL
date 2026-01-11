"""
Integration tests for effective rent API endpoints.

Tests the complete flow from HTTP request to effective rent calculation.
"""

from unittest.mock import Mock, patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from src.main import app


class TestEffectiveRentAPIIntegration:
    """Integration tests for effective rent API endpoints."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)

    def test_list_effective_rents_success(self, client) -> None:
        """Test listing all effective rents."""
        tenant_id = uuid4()
        doc_id = uuid4()
        extraction_id = uuid4()

        with patch("src.api.routes.effective_rent.get_supabase_client") as mock_get_supabase:
            with patch("src.api.routes.effective_rent.require_permission") as mock_auth_dep:
                # Mock auth
                mock_auth_context = Mock()
                mock_auth_context.user_id = uuid4()
                mock_auth_context.tenant_id = tenant_id
                mock_auth_dep.return_value = lambda: mock_auth_context

                # Mock Supabase
                mock_supabase = Mock()
                mock_get_supabase.return_value = mock_supabase

                def mock_table(table_name):
                    mock_chain = Mock()
                    if table_name == "extractions":
                        mock_chain.select.return_value.eq.return_value.execute.return_value.data = [
                            {
                                "id": str(extraction_id),
                                "document_id": str(doc_id),
                                "document_type": "lease",
                                "extracted_at": "2024-01-01T00:00:00",
                            }
                        ]
                    elif table_name == "extraction_fields":
                        mock_chain.select.return_value.eq.return_value.execute.return_value.data = [
                            {"field_name": "tenant_name", "field_value": {"value": "Test Tenant"}, "confidence": 0.95},
                            {"field_name": "base_rent", "field_value": {"value": "$10,000"}, "confidence": 0.95},
                            {"field_name": "cam_charges", "field_value": {"value": "$1,000"}, "confidence": 0.90},
                        ]
                    elif table_name == "documents":
                        mock_chain.select.return_value.eq.return_value.single.return_value.execute.return_value.data = {
                            "original_filename": "Test_Lease.pdf"
                        }
                    return mock_chain

                mock_supabase.table.side_effect = mock_table

                # Make request
                response = client.get("/api/v1/analytics/effective-rent")

                # Verify response
                assert response.status_code == 200
                data = response.json()

                assert "tenants" in data
                assert "total_count" in data
                assert "total_effective_monthly_rent" in data
                assert "total_effective_annual_rent" in data

                assert data["total_count"] == 1
                assert len(data["tenants"]) == 1

                tenant = data["tenants"][0]
                assert tenant["tenant_name"] == "Test Tenant"
                assert tenant["effective_monthly_rent"] == 11000.0  # 10000 + 1000
                assert tenant["effective_annual_rent"] == 132000.0  # 11000 * 12

    def test_list_effective_rents_with_limit(self, client) -> None:
        """Test listing with limit parameter."""
        with patch("src.api.routes.effective_rent.get_supabase_client") as mock_get_supabase:
            with patch("src.api.routes.effective_rent.require_permission") as mock_auth_dep:
                mock_auth_context = Mock()
                mock_auth_context.user_id = uuid4()
                mock_auth_context.tenant_id = uuid4()
                mock_auth_dep.return_value = lambda: mock_auth_context

                mock_supabase = Mock()
                mock_get_supabase.return_value = mock_supabase

                # Return multiple extractions
                extractions = [
                    {
                        "id": str(uuid4()),
                        "document_id": str(uuid4()),
                        "document_type": "lease",
                        "extracted_at": None,
                    }
                    for _ in range(10)
                ]

                call_count = [0]

                def mock_table(table_name):
                    mock_chain = Mock()
                    if table_name == "extractions":
                        mock_chain.select.return_value.eq.return_value.execute.return_value.data = extractions
                    elif table_name == "extraction_fields":
                        idx = call_count[0]
                        call_count[0] += 1
                        mock_chain.select.return_value.eq.return_value.execute.return_value.data = [
                            {"field_name": "tenant_name", "field_value": {"value": f"Tenant {idx}"}, "confidence": 0.95},
                            {"field_name": "base_rent", "field_value": {"value": "$5000"}, "confidence": 0.95},
                        ]
                    elif table_name == "documents":
                        mock_chain.select.return_value.eq.return_value.single.return_value.execute.return_value.data = {
                            "original_filename": "Lease.pdf"
                        }
                    return mock_chain

                mock_supabase.table.side_effect = mock_table

                # Make request with limit
                response = client.get("/api/v1/analytics/effective-rent?limit=5")

                assert response.status_code == 200
                data = response.json()
                assert len(data["tenants"]) == 5

    def test_list_effective_rents_with_sort(self, client) -> None:
        """Test listing with different sort orders."""
        with patch("src.api.routes.effective_rent.get_supabase_client") as mock_get_supabase:
            with patch("src.api.routes.effective_rent.require_permission") as mock_auth_dep:
                mock_auth_context = Mock()
                mock_auth_context.user_id = uuid4()
                mock_auth_context.tenant_id = uuid4()
                mock_auth_dep.return_value = lambda: mock_auth_context

                mock_supabase = Mock()
                mock_get_supabase.return_value = mock_supabase

                extractions = [
                    {"id": str(uuid4()), "document_id": str(uuid4()), "document_type": "lease", "extracted_at": None}
                    for _ in range(3)
                ]

                rents = [5000, 10000, 7500]
                call_count = [0]

                def mock_table(table_name):
                    mock_chain = Mock()
                    if table_name == "extractions":
                        mock_chain.select.return_value.eq.return_value.execute.return_value.data = extractions
                    elif table_name == "extraction_fields":
                        idx = call_count[0] % 3
                        call_count[0] += 1
                        mock_chain.select.return_value.eq.return_value.execute.return_value.data = [
                            {"field_name": "tenant_name", "field_value": {"value": f"Tenant {idx}"}, "confidence": 0.95},
                            {"field_name": "base_rent", "field_value": {"value": f"${rents[idx]}"}, "confidence": 0.95},
                        ]
                    elif table_name == "documents":
                        mock_chain.select.return_value.eq.return_value.single.return_value.execute.return_value.data = {
                            "original_filename": "Lease.pdf"
                        }
                    return mock_chain

                mock_supabase.table.side_effect = mock_table

                # Test ascending sort
                response = client.get("/api/v1/analytics/effective-rent?sort=asc")
                assert response.status_code == 200
                data = response.json()

                # Verify ascending order
                rents_list = [t["effective_monthly_rent"] for t in data["tenants"]]
                assert rents_list == sorted(rents_list)

    def test_get_highest_effective_rent_success(self, client) -> None:
        """Test getting tenant with highest rent."""
        doc_id = uuid4()
        extraction_id = uuid4()

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
                            {
                                "id": str(extraction_id),
                                "document_id": str(doc_id),
                                "document_type": "lease",
                                "extracted_at": None,
                            }
                        ]
                    elif table_name == "extraction_fields":
                        mock_chain.select.return_value.eq.return_value.execute.return_value.data = [
                            {"field_name": "tenant_name", "field_value": {"value": "Highest Rent Tenant"}, "confidence": 0.95},
                            {"field_name": "base_rent", "field_value": {"value": "$25,000"}, "confidence": 0.95},
                            {"field_name": "cam_charges", "field_value": {"value": "$2,000"}, "confidence": 0.90},
                        ]
                    elif table_name == "documents":
                        mock_chain.select.return_value.eq.return_value.single.return_value.execute.return_value.data = {
                            "original_filename": "Premium_Lease.pdf"
                        }
                    return mock_chain

                mock_supabase.table.side_effect = mock_table

                # Make request
                response = client.get("/api/v1/analytics/effective-rent/highest")

                # Verify response
                assert response.status_code == 200
                data = response.json()

                assert data["tenant_name"] == "Highest Rent Tenant"
                assert data["effective_monthly_rent"] == 27000.0
                assert data["document_name"] == "Premium_Lease.pdf"

    def test_get_highest_effective_rent_no_data(self, client) -> None:
        """Test getting highest rent when no data exists."""
        with patch("src.api.routes.effective_rent.get_supabase_client") as mock_get_supabase:
            with patch("src.api.routes.effective_rent.require_permission") as mock_auth_dep:
                mock_auth_context = Mock()
                mock_auth_context.user_id = uuid4()
                mock_auth_context.tenant_id = uuid4()
                mock_auth_dep.return_value = lambda: mock_auth_context

                mock_supabase = Mock()
                mock_get_supabase.return_value = mock_supabase

                # Return no extractions
                mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value.data = []

                # Make request
                response = client.get("/api/v1/analytics/effective-rent/highest")

                # Should return 404
                assert response.status_code == 404
                assert "No rent data found" in response.json()["detail"]

    def test_get_summary_success(self, client) -> None:
        """Test getting portfolio summary."""
        with patch("src.api.routes.effective_rent.get_supabase_client") as mock_get_supabase:
            with patch("src.api.routes.effective_rent.require_permission") as mock_auth_dep:
                mock_auth_context = Mock()
                mock_auth_context.user_id = uuid4()
                mock_auth_context.tenant_id = uuid4()
                mock_auth_dep.return_value = lambda: mock_auth_context

                mock_supabase = Mock()
                mock_get_supabase.return_value = mock_supabase

                # Create multiple tenants with different rents
                extractions = [
                    {"id": str(uuid4()), "document_id": str(uuid4()), "document_type": "lease", "extracted_at": None}
                    for _ in range(5)
                ]

                rents = [5000, 7500, 10000, 6000, 8000]
                call_count = [0]

                def mock_table(table_name):
                    mock_chain = Mock()
                    if table_name == "extractions":
                        mock_chain.select.return_value.eq.return_value.execute.return_value.data = extractions
                    elif table_name == "extraction_fields":
                        idx = call_count[0] % 5
                        call_count[0] += 1
                        mock_chain.select.return_value.eq.return_value.execute.return_value.data = [
                            {"field_name": "tenant_name", "field_value": {"value": f"Tenant {idx}"}, "confidence": 0.95},
                            {"field_name": "base_rent", "field_value": {"value": f"${rents[idx]}"}, "confidence": 0.95},
                        ]
                    elif table_name == "documents":
                        mock_chain.select.return_value.eq.return_value.single.return_value.execute.return_value.data = {
                            "original_filename": "Lease.pdf"
                        }
                    return mock_chain

                mock_supabase.table.side_effect = mock_table

                # Make request
                response = client.get("/api/v1/analytics/effective-rent/summary")

                # Verify response
                assert response.status_code == 200
                data = response.json()

                assert data["total_tenants"] == 5
                assert "highest_effective_rent" in data
                assert "lowest_effective_rent" in data
                assert "average_effective_monthly_rent" in data
                assert "total_portfolio_monthly_rent" in data
                assert "total_portfolio_annual_rent" in data

                # Verify highest and lowest
                assert data["highest_effective_rent"]["effective_monthly_rent"] == 10000.0
                assert data["lowest_effective_rent"]["effective_monthly_rent"] == 5000.0

    def test_validation_error_invalid_limit(self, client) -> None:
        """Test validation error for invalid limit."""
        with patch("src.api.routes.effective_rent.get_supabase_client"):
            with patch("src.api.routes.effective_rent.require_permission"):
                # Request with invalid limit (exceeds max)
                response = client.get("/api/v1/analytics/effective-rent?limit=2000")

                # Should return validation error
                assert response.status_code == 422

    def test_validation_error_invalid_sort(self, client) -> None:
        """Test validation error for invalid sort parameter."""
        with patch("src.api.routes.effective_rent.get_supabase_client"):
            with patch("src.api.routes.effective_rent.require_permission"):
                # Request with invalid sort value
                response = client.get("/api/v1/analytics/effective-rent?sort=invalid")

                # Should return validation error
                assert response.status_code == 422
