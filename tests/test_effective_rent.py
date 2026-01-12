"""Tests for effective rent calculation service and API."""
import pytest
from typing import Any, Generator
from uuid import uuid4
from unittest.mock import Mock

from src.services.effective_rent import EffectiveRentService
from src.db.models.effective_rent import (
    EffectiveRentListResponse,
    EffectiveRentSummary,
)


class TestEffectiveRentService:
    """Unit tests for EffectiveRentService."""

    @pytest.fixture
    def mock_supabase(self) -> Mock:
        """Create mock Supabase client."""
        return Mock()

    @pytest.fixture
    def service(self, mock_supabase) -> Any:
        """Create EffectiveRentService instance."""
        return EffectiveRentService(mock_supabase)

    def test_extract_numeric_currency(self, service) -> None:
        """Test extracting numeric values from currency strings."""
        assert service._extract_numeric("$5,000.00") == 5000.0
        assert service._extract_numeric("$10,500") == 10500.0
        assert service._extract_numeric("2500.50") == 2500.50
        assert service._extract_numeric("$1,234,567.89") == 1234567.89

    def test_extract_numeric_invalid(self, service) -> None:
        """Test extracting numeric values from invalid strings."""
        assert service._extract_numeric("") == 0.0
        assert service._extract_numeric(None) == 0.0
        assert service._extract_numeric("N/A") == 0.0
        assert service._extract_numeric("TBD") == 0.0

    def test_get_field_value(self, service) -> None:
        """Test getting field values from extraction fields."""
        fields = [
            {
                "field_name": "base_rent",
                "field_value": {"value": "$5,000"},
                "confidence": 0.95,
            },
            {
                "field_name": "cam_charges",
                "field_value": {"value": "$500"},
                "confidence": 0.90,
            },
        ]

        assert service._get_field_value(fields, "base_rent") == 5000.0
        assert service._get_field_value(fields, "cam_charges") == 500.0
        assert service._get_field_value(fields, "nonexistent") == 0.0

    def test_get_field_confidence(self, service) -> None:
        """Test getting confidence scores for fields."""
        fields = [
            {
                "field_name": "base_rent",
                "field_value": {"value": "$5,000"},
                "confidence": 0.95,
            },
        ]

        assert service._get_field_confidence(fields, "base_rent") == 0.95
        assert service._get_field_confidence(fields, "nonexistent") is None

    @pytest.mark.asyncio
    async def test_calculate_all_effective_rents_no_data(self, service, mock_supabase) -> None:
        """Test calculation when no extractions exist."""
        mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value.data = []

        result = await service.calculate_all_effective_rents()

        assert isinstance(result, EffectiveRentListResponse)
        assert result.total_count == 0
        assert len(result.tenants) == 0
        assert result.total_effective_monthly_rent == 0.0

    @pytest.mark.asyncio
    async def test_calculate_all_effective_rents_single_tenant(self, service, mock_supabase) -> None:
        """Test calculation with single tenant."""
        extraction_id = str(uuid4())
        doc_id = str(uuid4())

        # Mock extractions query
        mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value.data = [
            {
                "id": extraction_id,
                "document_id": doc_id,
                "document_type": "lease",
                "extracted_at": "2024-01-01T00:00:00",
            }
        ]

        # Mock extraction_fields query
        fields_data = [
            {"field_name": "tenant_name", "field_value": {"value": "Acme Corp"}, "confidence": 0.95},
            {"field_name": "base_rent", "field_value": {"value": "$10,000"}, "confidence": 0.95},
            {"field_name": "cam_charges", "field_value": {"value": "$1,500"}, "confidence": 0.90},
            {"field_name": "tax_reimbursement", "field_value": {"value": "$800"}, "confidence": 0.85},
            {"field_name": "insurance_reimbursement", "field_value": {"value": "$200"}, "confidence": 0.85},
            {"field_name": "parking_fee", "field_value": {"value": "$500"}, "confidence": 0.90},
        ]

        # Mock documents query
        def mock_table(table_name: str) -> Any:
            mock_chain = Mock()
            if table_name == "extractions":
                mock_chain.select.return_value.eq.return_value.execute.return_value.data = [
                    {
                        "id": extraction_id,
                        "document_id": doc_id,
                        "document_type": "lease",
                        "extracted_at": "2024-01-01T00:00:00",
                    }
                ]
            elif table_name == "extraction_fields":
                mock_chain.select.return_value.eq.return_value.execute.return_value.data = fields_data
            elif table_name == "documents":
                mock_chain.select.return_value.eq.return_value.single.return_value.execute.return_value.data = {
                    "original_filename": "Acme_Lease.pdf"
                }
            return mock_chain

        mock_supabase.table.side_effect = mock_table

        result = await service.calculate_all_effective_rents()

        assert result.total_count == 1
        assert len(result.tenants) == 1

        tenant = result.tenants[0]
        assert tenant.tenant_name == "Acme Corp"
        assert tenant.rent_components.base_rent == 10000.0
        assert tenant.rent_components.cam_charges == 1500.0
        assert tenant.rent_components.tax_reimbursement == 800.0
        assert tenant.rent_components.insurance_reimbursement == 200.0
        assert tenant.rent_components.parking_fee == 500.0
        assert tenant.effective_monthly_rent == 13000.0  # 10000 + 1500 + 800 + 200 + 500
        assert tenant.effective_annual_rent == 156000.0  # 13000 * 12

    @pytest.mark.asyncio
    async def test_calculate_all_effective_rents_sorting(self, service, mock_supabase) -> None:
        """Test that results are sorted correctly."""
        # Create mock data for 3 tenants with different rents
        extractions = [
            {"id": str(uuid4()), "document_id": str(uuid4()), "document_type": "lease", "extracted_at": None},
            {"id": str(uuid4()), "document_id": str(uuid4()), "document_type": "lease", "extracted_at": None},
            {"id": str(uuid4()), "document_id": str(uuid4()), "document_type": "lease", "extracted_at": None},
        ]

        rents = [5000, 10000, 7500]  # Different base rents

        call_count = [0]

        def mock_table(table_name: str) -> Any:
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
                    "original_filename": f"Lease_{call_count[0]}.pdf"
                }
            return mock_chain

        mock_supabase.table.side_effect = mock_table

        # Test descending sort (default)
        result_desc = await service.calculate_all_effective_rents(sort_desc=True)
        assert len(result_desc.tenants) == 3
        assert result_desc.tenants[0].effective_monthly_rent >= result_desc.tenants[1].effective_monthly_rent
        assert result_desc.tenants[1].effective_monthly_rent >= result_desc.tenants[2].effective_monthly_rent

        # Reset call count
        call_count[0] = 0

        # Test ascending sort
        result_asc = await service.calculate_all_effective_rents(sort_desc=False)
        assert len(result_asc.tenants) == 3
        assert result_asc.tenants[0].effective_monthly_rent <= result_asc.tenants[1].effective_monthly_rent
        assert result_asc.tenants[1].effective_monthly_rent <= result_asc.tenants[2].effective_monthly_rent

    @pytest.mark.asyncio
    async def test_calculate_all_effective_rents_limit(self, service, mock_supabase) -> None:
        """Test limit parameter."""
        extractions = [
            {"id": str(uuid4()), "document_id": str(uuid4()), "document_type": "lease", "extracted_at": None}
            for _ in range(10)
        ]

        call_count = [0]

        def mock_table(table_name: str) -> Any:
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

        result = await service.calculate_all_effective_rents(limit=5)

        assert len(result.tenants) == 5

    @pytest.mark.asyncio
    async def test_get_highest_effective_rent(self, service, mock_supabase) -> None:
        """Test getting tenant with highest rent."""
        extraction_id = str(uuid4())
        doc_id = str(uuid4())

        def mock_table(table_name: str) -> Any:
            mock_chain = Mock()
            if table_name == "extractions":
                mock_chain.select.return_value.eq.return_value.execute.return_value.data = [
                    {"id": extraction_id, "document_id": doc_id, "document_type": "lease", "extracted_at": None}
                ]
            elif table_name == "extraction_fields":
                mock_chain.select.return_value.eq.return_value.execute.return_value.data = [
                    {"field_name": "tenant_name", "field_value": {"value": "Top Tenant"}, "confidence": 0.95},
                    {"field_name": "base_rent", "field_value": {"value": "$20,000"}, "confidence": 0.95},
                ]
            elif table_name == "documents":
                mock_chain.select.return_value.eq.return_value.single.return_value.execute.return_value.data = {
                    "original_filename": "HighRent_Lease.pdf"
                }
            return mock_chain

        mock_supabase.table.side_effect = mock_table

        result = await service.get_highest_effective_rent()

        assert result is not None
        assert result.tenant_name == "Top Tenant"
        assert result.effective_monthly_rent == 20000.0

    @pytest.mark.asyncio
    async def test_get_highest_effective_rent_no_data(self, service, mock_supabase) -> None:
        """Test getting highest rent when no data exists."""
        mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value.data = []

        result = await service.get_highest_effective_rent()

        assert result is None

    @pytest.mark.asyncio
    async def test_get_summary_no_data(self, service, mock_supabase) -> None:
        """Test summary when no data exists."""
        mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value.data = []

        summary = await service.get_summary()

        assert isinstance(summary, EffectiveRentSummary)
        assert summary.total_tenants == 0
        assert summary.highest_effective_rent is None
        assert summary.lowest_effective_rent is None
        assert summary.average_effective_monthly_rent == 0.0
        assert summary.total_portfolio_monthly_rent == 0.0

    @pytest.mark.asyncio
    async def test_skip_zero_rent_tenants(self, service, mock_supabase) -> None:
        """Test that tenants with zero rent are skipped."""
        extraction_id = str(uuid4())
        doc_id = str(uuid4())

        def mock_table(table_name: str) -> Any:
            mock_chain = Mock()
            if table_name == "extractions":
                mock_chain.select.return_value.eq.return_value.execute.return_value.data = [
                    {"id": extraction_id, "document_id": doc_id, "document_type": "lease", "extracted_at": None}
                ]
            elif table_name == "extraction_fields":
                # Tenant with no rent data
                mock_chain.select.return_value.eq.return_value.execute.return_value.data = [
                    {"field_name": "tenant_name", "field_value": {"value": "Zero Rent"}, "confidence": 0.95},
                ]
            elif table_name == "documents":
                mock_chain.select.return_value.eq.return_value.single.return_value.execute.return_value.data = {
                    "original_filename": "Lease.pdf"
                }
            return mock_chain

        mock_supabase.table.side_effect = mock_table

        result = await service.calculate_all_effective_rents()

        assert result.total_count == 0
        assert len(result.tenants) == 0

    @pytest.mark.asyncio
    async def test_skip_tenants_without_name(self, service, mock_supabase) -> None:
        """Test that extractions without tenant name are skipped."""
        extraction_id = str(uuid4())
        doc_id = str(uuid4())

        def mock_table(table_name: str) -> Any:
            mock_chain = Mock()
            if table_name == "extractions":
                mock_chain.select.return_value.eq.return_value.execute.return_value.data = [
                    {"id": extraction_id, "document_id": doc_id, "document_type": "lease", "extracted_at": None}
                ]
            elif table_name == "extraction_fields":
                # No tenant_name field
                mock_chain.select.return_value.eq.return_value.execute.return_value.data = [
                    {"field_name": "base_rent", "field_value": {"value": "$5000"}, "confidence": 0.95},
                ]
            elif table_name == "documents":
                mock_chain.select.return_value.eq.return_value.single.return_value.execute.return_value.data = {
                    "original_filename": "Lease.pdf"
                }
            return mock_chain

        mock_supabase.table.side_effect = mock_table

        result = await service.calculate_all_effective_rents()

        assert result.total_count == 0
        assert len(result.tenants) == 0
