"""
Comprehensive test suite for CRE lease extraction across all 5 asset classes.

Tests 15 complex leases:
- Office: 3 leases (Class A, Class B, Class C)
- Retail: 3 leases (Anchor, Inline, Pad)
- Industrial: 3 leases (Warehouse, Distribution, Manufacturing)
- Multi-Family: 3 leases (Luxury, Mid-Market, Affordable)
- Mixed-Use: 3 leases (Retail+Office, Retail+Residential, Office+Residential)
"""

import pytest
import json
from unittest.mock import Mock, AsyncMock, patch
from typing import Dict, Any

from src.extraction.extractor import FieldExtractor, ExtractionResult


class TestComplexLeasesAllAssetClasses:
    """Test complex lease extraction across all CRE asset classes."""
    
    @pytest.fixture
    def mock_openai_client(self) -> Any:
        """Create mock OpenAI client."""
        client = AsyncMock()
        return client
    
    @pytest.fixture
    def extractor(self, mock_openai_client) -> Any:
        """Create FieldExtractor with mocked OpenAI client."""
        with patch('src.extraction.extractor.AsyncOpenAI', return_value=mock_openai_client):
            with patch('src.extraction.extractor.presidio_redact', return_value=lambda x: x):
                extractor = FieldExtractor(api_key="test-key")
                extractor.client = mock_openai_client
                return extractor
    
    def _create_mock_llm_response(self, fields: Dict[str, Any]) -> Mock:
        """Helper to create mock LLM response."""
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message = Mock()
        mock_response.choices[0].message.content = json.dumps({"fields": fields})
        return mock_response
    
    # ========== OFFICE LEASES (3 tests) ==========
    
    @pytest.mark.asyncio
    async def test_office_class_a_premium_lease(self, extractor, mock_openai_client) -> None:
        """Test Class A premium office lease with certifications."""
        lease_text = """
        CLASS A OFFICE LEASE AGREEMENT
        
        Tenant: Global Finance Corporation, a Delaware Corporation
        Tenant Entity Type: Corp
        Tenant Parent: International Holdings Inc.
        Landlord: Premium Office REIT, LLC
        
        Property: Tower One, 500 Financial Plaza, Suite 2000, Chicago, IL 60601
        Office Class: A
        Square Footage: 15,000 RSF
        Floor: 20th floor
        Floor Plate Size: 30,000 sq ft
        Core Factor: 1.18
        
        Term: July 1, 2024 to June 30, 2029 (5 years)
        
        RENT:
        Base Rent: $52,500/month ($42/sq ft annually)
        Full Service Gross Lease
        Rent Due: 1st of month
        Late Fee: $1,000 or 5%
        
        BUILDING FEATURES:
        Conference Room Access: Yes
        After Hours HVAC: $200/hour
        Elevator Ratio: 6 elevators
        Building Certifications: LEED Platinum, WELL Certified, EnergyStar
        Spec Suite: No, custom buildout
        Open Plan Ratio: 0.65
        
        IMPROVEMENTS:
        TI Allowance: $150,000
        Buildout Period: 120 days
        
        SECURITY:
        Security Deposit: $52,500 (1 month)
        Letter of Credit: $200,000
        Corporate Guarantee: Yes
        Personal Guarantee: No
        
        TENANT QUALITY:
        Credit Rating: A-
        Credit Score: 750
        Public Company: Yes
        Years in Business: 25
        Locations: 50+
        """
        
        mock_fields = {
            "tenant_name": {"value": "Global Finance Corporation", "confidence": 0.95, "page": 1},
            "tenant_entity_type": {"value": "Corp", "confidence": 0.95, "page": 1},
            "tenant_parent_company": {"value": "International Holdings Inc.", "confidence": 0.90, "page": 1},
            "landlord_name": {"value": "Premium Office REIT, LLC", "confidence": 0.95, "page": 1},
            "property_address": {"value": "500 Financial Plaza, Suite 2000, Chicago, IL 60601", "confidence": 0.90, "page": 1},
            "office_class": {"value": "A", "confidence": 0.95, "page": 1},
            "square_footage": {"value": "15000", "confidence": 0.90, "page": 1},
            "floor_number": {"value": "20", "confidence": 0.90, "page": 1},
            "floor_plate_size": {"value": "30000", "confidence": 0.90, "page": 1},
            "core_factor": {"value": "1.18", "confidence": 0.90, "page": 1},
            "lease_start_date": {"value": "2024-07-01", "confidence": 0.95, "page": 1},
            "lease_end_date": {"value": "2029-06-30", "confidence": 0.95, "page": 1},
            "base_rent": {"value": "$52,500", "confidence": 0.95, "page": 1},
            "lease_type": {"value": "gross", "confidence": 0.90, "page": 1},
            "rent_due_date": {"value": "1", "confidence": 0.90, "page": 1},
            "late_fee_amount": {"value": "$1,000", "confidence": 0.90, "page": 1},
            "conference_room_access": {"value": "true", "confidence": 0.90, "page": 1},
            "after_hours_hvac": {"value": "$200", "confidence": 0.90, "page": 1},
            "elevator_ratio": {"value": "6 elevators", "confidence": 0.85, "page": 1},
            "building_certifications": {"value": "LEED", "confidence": 0.90, "page": 1},
            "spec_suite": {"value": "false", "confidence": 0.90, "page": 1},
            "open_plan_ratio": {"value": "0.65", "confidence": 0.90, "page": 1},
            "tenant_improvement_allowance": {"value": "$150,000", "confidence": 0.90, "page": 1},
            "buildout_period_days": {"value": "120", "confidence": 0.90, "page": 1},
            "security_deposit": {"value": "$52,500", "confidence": 0.90, "page": 1},
            "security_deposit_months": {"value": "1.0", "confidence": 0.90, "page": 1},
            "letter_of_credit_amount": {"value": "$200,000", "confidence": 0.90, "page": 1},
            "corporate_guarantee": {"value": "true", "confidence": 0.90, "page": 1},
            "guarantee_type": {"value": "corporate", "confidence": 0.90, "page": 1},
            "tenant_credit_rating": {"value": "A-", "confidence": 0.90, "page": 1},
            "tenant_credit_score": {"value": "750", "confidence": 0.90, "page": 1},
            "tenant_is_public_company": {"value": "true", "confidence": 0.90, "page": 1},
            "tenant_years_in_business": {"value": "25", "confidence": 0.90, "page": 1},
            "tenant_locations_count": {"value": "50", "confidence": 0.85, "page": 1},
        }
        
        mock_openai_client.chat.completions.create = AsyncMock(
            return_value=self._create_mock_llm_response(mock_fields)
        )
        
        result = await extractor.extract_fields(lease_text, "cre", "lease")
        
        assert isinstance(result, ExtractionResult)
        assert result.fields["office_class"].value == "A"
        assert result.fields["building_certifications"].value == "LEED"
        assert result.fields["tenant_credit_rating"].value == "A-"
        assert len(result.fields) > 25
    
    @pytest.mark.asyncio
    async def test_office_class_b_standard_lease(self, extractor, mock_openai_client) -> None:
        """Test Class B standard office lease."""
        lease_text = """
        OFFICE LEASE AGREEMENT
        
        Tenant: Regional Services LLC
        Landlord: Standard Office Properties
        
        Property: 200 Business Park, Suite 500, Phoenix, AZ 85001
        Office Class: B
        Square Footage: 5,000 RSF
        Floor Plate: 12,000 sq ft
        
        Term: January 1, 2024 to December 31, 2026
        
        RENT:
        Base Rent: $12,500/month ($30/sq ft)
        Modified Gross Lease
        CAM: $3.50/sq ft
        Tax Reimbursement: Pro-rata share
        
        IMPROVEMENTS:
        TI Allowance: $40,000
        Buildout: 60 days
        
        SECURITY:
        Deposit: $12,500
        Personal Guarantee: Yes
        """
        
        mock_fields = {
            "tenant_name": {"value": "Regional Services LLC", "confidence": 0.95, "page": 1},
            "landlord_name": {"value": "Standard Office Properties", "confidence": 0.95, "page": 1},
            "property_address": {"value": "200 Business Park, Suite 500, Phoenix, AZ 85001", "confidence": 0.90, "page": 1},
            "office_class": {"value": "B", "confidence": 0.90, "page": 1},
            "square_footage": {"value": "5000", "confidence": 0.90, "page": 1},
            "lease_start_date": {"value": "2024-01-01", "confidence": 0.95, "page": 1},
            "lease_end_date": {"value": "2026-12-31", "confidence": 0.95, "page": 1},
            "base_rent": {"value": "$12,500", "confidence": 0.95, "page": 1},
            "lease_type": {"value": "modified_gross", "confidence": 0.90, "page": 1},
            "cam_charges": {"value": "$3.50", "confidence": 0.85, "page": 1},
            "tenant_improvement_allowance": {"value": "$40,000", "confidence": 0.90, "page": 1},
            "security_deposit": {"value": "$12,500", "confidence": 0.90, "page": 1},
            "personal_guarantee": {"value": "true", "confidence": 0.90, "page": 1},
        }
        
        mock_openai_client.chat.completions.create = AsyncMock(
            return_value=self._create_mock_llm_response(mock_fields)
        )
        
        result = await extractor.extract_fields(lease_text, "cre", "lease")
        
        assert isinstance(result, ExtractionResult)
        assert result.fields["office_class"].value == "B"
        assert result.fields["lease_type"].value == "modified_gross"
    
    @pytest.mark.asyncio
    async def test_office_class_c_value_lease(self, extractor, mock_openai_client) -> None:
        """Test Class C value office lease."""
        lease_text = """
        OFFICE LEASE
        
        Tenant: Small Business Inc.
        Landlord: Value Office LLC
        
        Property: 100 Main Street, 2nd Floor, Detroit, MI 48201
        Office Class: C
        Square Footage: 2,000 RSF
        
        Term: March 1, 2024 to February 28, 2027
        
        RENT:
        Base Rent: $3,000/month ($18/sq ft)
        Net Lease (NNN)
        CAM: $2.00/sq ft
        Taxes: Pro-rata
        Insurance: Pro-rata
        
        SECURITY:
        Deposit: $6,000 (2 months)
        """
        
        mock_fields = {
            "tenant_name": {"value": "Small Business Inc.", "confidence": 0.95, "page": 1},
            "landlord_name": {"value": "Value Office LLC", "confidence": 0.95, "page": 1},
            "property_address": {"value": "100 Main Street, 2nd Floor, Detroit, MI 48201", "confidence": 0.90, "page": 1},
            "office_class": {"value": "C", "confidence": 0.90, "page": 1},
            "square_footage": {"value": "2000", "confidence": 0.90, "page": 1},
            "lease_start_date": {"value": "2024-03-01", "confidence": 0.95, "page": 1},
            "lease_end_date": {"value": "2027-02-28", "confidence": 0.95, "page": 1},
            "base_rent": {"value": "$3,000", "confidence": 0.95, "page": 1},
            "lease_type": {"value": "nnn", "confidence": 0.90, "page": 1},
            "cam_charges": {"value": "$2.00", "confidence": 0.85, "page": 1},
            "security_deposit": {"value": "$6,000", "confidence": 0.90, "page": 1},
            "security_deposit_months": {"value": "2.0", "confidence": 0.90, "page": 1},
        }
        
        mock_openai_client.chat.completions.create = AsyncMock(
            return_value=self._create_mock_llm_response(mock_fields)
        )
        
        result = await extractor.extract_fields(lease_text, "cre", "lease")
        
        assert isinstance(result, ExtractionResult)
        assert result.fields["office_class"].value == "C"
        assert result.fields["lease_type"].value == "nnn"
    
    # ========== RETAIL LEASES (3 tests) ==========
    
    @pytest.mark.asyncio
    async def test_retail_anchor_lease(self, extractor, mock_openai_client) -> None:
        """Test anchor tenant retail lease with co-tenancy."""
        lease_text = """
        RETAIL LEASE AGREEMENT - ANCHOR TENANT
        
        Tenant: Major Department Store Corp
        Landlord: Shopping Center Partners LP
        
        Property: Regional Mall, Anchor Space A, Los Angeles, CA 90001
        Retail Type: Anchor
        Square Footage: 100,000 RSF
        
        Term: June 1, 2024 to May 31, 2034 (10 years)
        
        RENT:
        Base Rent: $50,000/month ($6/sq ft annually)
        Percentage Rent: 2% of gross sales over $30,000,000 annually
        Sales Reporting: Required monthly
        Sales Breakpoint: $30,000,000
        
        CO-TENANCY:
        Co-tenancy Clause: Yes
        Anchor Dependency: Other tenants depend on this anchor
        
        SIGNAGE:
        Signage Type: Pylon and Monument
        Exclusive Use: Department store, general merchandise
        
        MARKETING:
        Marketing Fee: $500/month
        
        SECURITY:
        Security Deposit: $100,000
        Corporate Guarantee: Yes
        """
        
        mock_fields = {
            "tenant_name": {"value": "Major Department Store Corp", "confidence": 0.95, "page": 1},
            "landlord_name": {"value": "Shopping Center Partners LP", "confidence": 0.95, "page": 1},
            "property_address": {"value": "Regional Mall, Anchor Space A, Los Angeles, CA 90001", "confidence": 0.90, "page": 1},
            "retail_type": {"value": "anchor", "confidence": 0.95, "page": 1},
            "square_footage": {"value": "100000", "confidence": 0.90, "page": 1},
            "lease_start_date": {"value": "2024-06-01", "confidence": 0.95, "page": 1},
            "lease_end_date": {"value": "2034-05-31", "confidence": 0.95, "page": 1},
            "base_rent": {"value": "$50,000", "confidence": 0.95, "page": 1},
            "percentage_rent": {"value": "2%", "confidence": 0.90, "page": 1},
            "sales_reporting_required": {"value": "true", "confidence": 0.90, "page": 1},
            "sales_breakpoint": {"value": "$30,000,000", "confidence": 0.90, "page": 1},
            "co_tenancy_clause": {"value": "true", "confidence": 0.90, "page": 1},
            "co_tenancy": {"value": "true", "confidence": 0.90, "page": 1},
            "anchor_dependency": {"value": "true", "confidence": 0.85, "page": 1},
            "signage_type": {"value": "pylon", "confidence": 0.85, "page": 1},
            "exclusive_retail_use": {"value": "Department store, general merchandise", "confidence": 0.85, "page": 1},
            "common_area_marketing_fee": {"value": "$500", "confidence": 0.85, "page": 1},
            "security_deposit": {"value": "$100,000", "confidence": 0.90, "page": 1},
            "corporate_guarantee": {"value": "true", "confidence": 0.90, "page": 1},
        }
        
        mock_openai_client.chat.completions.create = AsyncMock(
            return_value=self._create_mock_llm_response(mock_fields)
        )
        
        result = await extractor.extract_fields(lease_text, "cre", "lease")
        
        assert isinstance(result, ExtractionResult)
        assert result.fields["retail_type"].value == "anchor"
        assert result.fields["co_tenancy_clause"].value is True
        assert result.fields["percentage_rent"].value is not None
    
    @pytest.mark.asyncio
    async def test_retail_inline_lease(self, extractor, mock_openai_client) -> None:
        """Test inline retail lease with percentage rent."""
        lease_text = """
        RETAIL LEASE - INLINE STORE
        
        Tenant: Fashion Boutique LLC
        Landlord: Strip Center Management
        
        Property: 500 Shopping Center, Unit 25, Miami, FL 33101
        Retail Type: Inline
        Square Footage: 2,500 RSF
        
        Term: April 1, 2024 to March 31, 2029
        
        RENT:
        Base Rent: $6,250/month ($30/sq ft)
        Percentage Rent: 8% of gross sales over $937,500 annually
        Sales Reporting: Required monthly
        
        SIGNAGE:
        Signage Type: Façade
        Drive Thru: No
        
        SECURITY:
        Deposit: $12,500
        """
        
        mock_fields = {
            "tenant_name": {"value": "Fashion Boutique LLC", "confidence": 0.95, "page": 1},
            "landlord_name": {"value": "Strip Center Management", "confidence": 0.95, "page": 1},
            "property_address": {"value": "500 Shopping Center, Unit 25, Miami, FL 33101", "confidence": 0.90, "page": 1},
            "retail_type": {"value": "inline", "confidence": 0.95, "page": 1},
            "square_footage": {"value": "2500", "confidence": 0.90, "page": 1},
            "lease_start_date": {"value": "2024-04-01", "confidence": 0.95, "page": 1},
            "lease_end_date": {"value": "2029-03-31", "confidence": 0.95, "page": 1},
            "base_rent": {"value": "$6,250", "confidence": 0.95, "page": 1},
            "percentage_rent": {"value": "8%", "confidence": 0.90, "page": 1},
            "sales_reporting_required": {"value": "true", "confidence": 0.90, "page": 1},
            "signage_type": {"value": "façade", "confidence": 0.90, "page": 1},
            "drive_thru": {"value": "false", "confidence": 0.90, "page": 1},
            "security_deposit": {"value": "$12,500", "confidence": 0.90, "page": 1},
        }
        
        mock_openai_client.chat.completions.create = AsyncMock(
            return_value=self._create_mock_llm_response(mock_fields)
        )
        
        result = await extractor.extract_fields(lease_text, "cre", "lease")
        
        assert isinstance(result, ExtractionResult)
        assert result.fields["retail_type"].value == "inline"
        assert result.fields["percentage_rent"].value is not None
    
    @pytest.mark.asyncio
    async def test_retail_pad_lease(self, extractor, mock_openai_client) -> None:
        """Test pad site retail lease with drive-thru."""
        lease_text = """
        RETAIL PAD LEASE
        
        Tenant: Quick Service Restaurant Inc.
        Landlord: Retail Development LLC
        
        Property: 1000 Highway 101, Pad Site 3, San Diego, CA 92101
        Retail Type: Pad
        Square Footage: 3,000 RSF
        
        Term: May 1, 2024 to April 30, 2034
        
        RENT:
        Base Rent: $9,000/month ($36/sq ft)
        Triple Net Lease
        
        FEATURES:
        Drive Thru: Yes
        Signage Type: Monument
        Exclusive Use: Quick service restaurant
        
        SECURITY:
        Deposit: $18,000
        """
        
        mock_fields = {
            "tenant_name": {"value": "Quick Service Restaurant Inc.", "confidence": 0.95, "page": 1},
            "landlord_name": {"value": "Retail Development LLC", "confidence": 0.95, "page": 1},
            "property_address": {"value": "1000 Highway 101, Pad Site 3, San Diego, CA 92101", "confidence": 0.90, "page": 1},
            "retail_type": {"value": "pad", "confidence": 0.95, "page": 1},
            "square_footage": {"value": "3000", "confidence": 0.90, "page": 1},
            "lease_start_date": {"value": "2024-05-01", "confidence": 0.95, "page": 1},
            "lease_end_date": {"value": "2034-04-30", "confidence": 0.95, "page": 1},
            "base_rent": {"value": "$9,000", "confidence": 0.95, "page": 1},
            "lease_type": {"value": "nnn", "confidence": 0.90, "page": 1},
            "drive_thru": {"value": "true", "confidence": 0.90, "page": 1},
            "signage_type": {"value": "monument", "confidence": 0.90, "page": 1},
            "exclusive_retail_use": {"value": "Quick service restaurant", "confidence": 0.85, "page": 1},
            "security_deposit": {"value": "$18,000", "confidence": 0.90, "page": 1},
        }
        
        mock_openai_client.chat.completions.create = AsyncMock(
            return_value=self._create_mock_llm_response(mock_fields)
        )
        
        result = await extractor.extract_fields(lease_text, "cre", "lease")
        
        assert isinstance(result, ExtractionResult)
        assert result.fields["retail_type"].value == "pad"
        assert result.fields["drive_thru"].value is True
    
    # ========== INDUSTRIAL LEASES (3 tests) ==========
    
    @pytest.mark.asyncio
    async def test_industrial_warehouse_lease(self, extractor, mock_openai_client) -> None:
        """Test warehouse/distribution industrial lease."""
        lease_text = """
        INDUSTRIAL WAREHOUSE LEASE
        
        Tenant: Logistics Solutions Inc.
        Landlord: Industrial Properties REIT
        
        Property: 2000 Distribution Way, Building B, Dallas, TX 75201
        Building Type: Industrial
        Square Footage: 75,000 sq ft
        
        Term: June 1, 2024 to May 31, 2029
        
        RENT:
        Base Rent: $37,500/month ($6/sq ft annually)
        Triple Net Lease (NNN)
        
        SPECIFICATIONS:
        Clear Height: 32 feet
        Column Spacing: 50' x 50'
        Loading Docks: 12 dock doors
        Drive-in Doors: 3 grade-level doors
        Trailer Parking: 15 spaces
        Power Capacity: 480V, 3000A service
        Sprinkler Type: ESFR
        Floor Load: 250 psf
        Rail Access: Yes
        Cross Dock: Yes
        Truck Court Depth: 100 feet
        
        SECURITY:
        Security Deposit: $75,000
        Corporate Guarantee: Yes
        """
        
        mock_fields = {
            "tenant_name": {"value": "Logistics Solutions Inc.", "confidence": 0.95, "page": 1},
            "landlord_name": {"value": "Industrial Properties REIT", "confidence": 0.95, "page": 1},
            "property_address": {"value": "2000 Distribution Way, Building B, Dallas, TX 75201", "confidence": 0.90, "page": 1},
            "building_type": {"value": "industrial", "confidence": 0.95, "page": 1},
            "square_footage": {"value": "75000", "confidence": 0.90, "page": 1},
            "lease_start_date": {"value": "2024-06-01", "confidence": 0.95, "page": 1},
            "lease_end_date": {"value": "2029-05-31", "confidence": 0.95, "page": 1},
            "base_rent": {"value": "$37,500", "confidence": 0.95, "page": 1},
            "lease_type": {"value": "nnn", "confidence": 0.90, "page": 1},
            "clear_height": {"value": "32", "confidence": 0.90, "page": 1},
            "column_spacing": {"value": "50' x 50'", "confidence": 0.85, "page": 1},
            "loading_docks": {"value": "12", "confidence": 0.90, "page": 1},
            "drive_in_doors": {"value": "3", "confidence": 0.90, "page": 1},
            "trailer_parking_spaces": {"value": "15", "confidence": 0.90, "page": 1},
            "power_capacity": {"value": "480V, 3000A", "confidence": 0.85, "page": 1},
            "sprinkler_type": {"value": "ESFR", "confidence": 0.90, "page": 1},
            "floor_load_capacity": {"value": "250 psf", "confidence": 0.90, "page": 1},
            "rail_access": {"value": "true", "confidence": 0.90, "page": 1},
            "cross_dock": {"value": "true", "confidence": 0.90, "page": 1},
            "truck_court_depth": {"value": "100", "confidence": 0.85, "page": 1},
            "security_deposit": {"value": "$75,000", "confidence": 0.90, "page": 1},
            "corporate_guarantee": {"value": "true", "confidence": 0.90, "page": 1},
        }
        
        mock_openai_client.chat.completions.create = AsyncMock(
            return_value=self._create_mock_llm_response(mock_fields)
        )
        
        result = await extractor.extract_fields(lease_text, "cre", "lease")
        
        assert isinstance(result, ExtractionResult)
        assert result.fields["building_type"].value == "industrial"
        assert result.fields["clear_height"].value == 32
        assert result.fields["loading_docks"].value == 12
        assert result.fields["rail_access"].value is True
    
    @pytest.mark.asyncio
    async def test_industrial_manufacturing_lease(self, extractor, mock_openai_client) -> None:
        """Test manufacturing facility industrial lease."""
        lease_text = """
        MANUFACTURING FACILITY LEASE
        
        Tenant: Advanced Manufacturing Corp
        Landlord: Industrial Park LLC
        
        Property: 3000 Industrial Blvd, Building 5, Cleveland, OH 44101
        Square Footage: 50,000 sq ft
        
        Term: August 1, 2024 to July 31, 2034
        
        RENT:
        Base Rent: $25,000/month ($6/sq ft)
        Triple Net Lease
        
        SPECIFICATIONS:
        Clear Height: 28 feet
        Loading Docks: 8
        Power Capacity: 480V, 5000A (heavy power)
        Sprinkler: Wet system
        Floor Load: 300 psf
        Specialized Improvements: Heavy power, crane systems, compressed air
        
        SECURITY:
        Deposit: $50,000
        """
        
        mock_fields = {
            "tenant_name": {"value": "Advanced Manufacturing Corp", "confidence": 0.95, "page": 1},
            "landlord_name": {"value": "Industrial Park LLC", "confidence": 0.95, "page": 1},
            "property_address": {"value": "3000 Industrial Blvd, Building 5, Cleveland, OH 44101", "confidence": 0.90, "page": 1},
            "building_type": {"value": "industrial", "confidence": 0.95, "page": 1},
            "square_footage": {"value": "50000", "confidence": 0.90, "page": 1},
            "lease_start_date": {"value": "2024-08-01", "confidence": 0.95, "page": 1},
            "lease_end_date": {"value": "2034-07-31", "confidence": 0.95, "page": 1},
            "base_rent": {"value": "$25,000", "confidence": 0.95, "page": 1},
            "lease_type": {"value": "nnn", "confidence": 0.90, "page": 1},
            "clear_height": {"value": "28", "confidence": 0.90, "page": 1},
            "loading_docks": {"value": "8", "confidence": 0.90, "page": 1},
            "power_capacity": {"value": "480V, 5000A", "confidence": 0.85, "page": 1},
            "sprinkler_type": {"value": "wet", "confidence": 0.90, "page": 1},
            "floor_load_capacity": {"value": "300 psf", "confidence": 0.90, "page": 1},
            "specialized_improvements": {"value": "Heavy power, crane systems, compressed air", "confidence": 0.85, "page": 1},
            "security_deposit": {"value": "$50,000", "confidence": 0.90, "page": 1},
        }
        
        mock_openai_client.chat.completions.create = AsyncMock(
            return_value=self._create_mock_llm_response(mock_fields)
        )
        
        result = await extractor.extract_fields(lease_text, "cre", "lease")
        
        assert isinstance(result, ExtractionResult)
        assert result.fields["sprinkler_type"].value == "wet"
        assert result.fields["specialized_improvements"].value is not None
    
    @pytest.mark.asyncio
    async def test_industrial_cold_storage_lease(self, extractor, mock_openai_client) -> None:
        """Test cold storage industrial lease with specialized features."""
        lease_text = """
        COLD STORAGE FACILITY LEASE
        
        Tenant: Food Distribution LLC
        Landlord: Cold Storage Properties
        
        Property: 4000 Freezer Way, Unit A, Minneapolis, MN 55401
        Square Footage: 30,000 sq ft
        
        Term: September 1, 2024 to August 31, 2029
        
        RENT:
        Base Rent: $22,500/month ($9/sq ft)
        Triple Net Lease
        
        SPECIFICATIONS:
        Clear Height: 24 feet
        Loading Docks: 6
        Power Capacity: 480V, 2000A
        Sprinkler: Dry system
        Floor Load: 200 psf
        Specialized Improvements: Cold storage, freezer systems, temperature control
        
        SECURITY:
        Deposit: $45,000
        """
        
        mock_fields = {
            "tenant_name": {"value": "Food Distribution LLC", "confidence": 0.95, "page": 1},
            "landlord_name": {"value": "Cold Storage Properties", "confidence": 0.95, "page": 1},
            "property_address": {"value": "4000 Freezer Way, Unit A, Minneapolis, MN 55401", "confidence": 0.90, "page": 1},
            "building_type": {"value": "industrial", "confidence": 0.95, "page": 1},
            "square_footage": {"value": "30000", "confidence": 0.90, "page": 1},
            "lease_start_date": {"value": "2024-09-01", "confidence": 0.95, "page": 1},
            "lease_end_date": {"value": "2029-08-31", "confidence": 0.95, "page": 1},
            "base_rent": {"value": "$22,500", "confidence": 0.95, "page": 1},
            "lease_type": {"value": "nnn", "confidence": 0.90, "page": 1},
            "clear_height": {"value": "24", "confidence": 0.90, "page": 1},
            "loading_docks": {"value": "6", "confidence": 0.90, "page": 1},
            "power_capacity": {"value": "480V, 2000A", "confidence": 0.85, "page": 1},
            "sprinkler_type": {"value": "dry", "confidence": 0.90, "page": 1},
            "floor_load_capacity": {"value": "200 psf", "confidence": 0.90, "page": 1},
            "specialized_improvements": {"value": "Cold storage, freezer systems", "confidence": 0.85, "page": 1},
            "security_deposit": {"value": "$45,000", "confidence": 0.90, "page": 1},
        }
        
        mock_openai_client.chat.completions.create = AsyncMock(
            return_value=self._create_mock_llm_response(mock_fields)
        )
        
        result = await extractor.extract_fields(lease_text, "cre", "lease")
        
        assert isinstance(result, ExtractionResult)
        assert result.fields["sprinkler_type"].value == "dry"
        assert "cold storage" in result.fields["specialized_improvements"].value.lower()
    
    # ========== MULTI-FAMILY LEASES (3 tests) ==========
    
    @pytest.mark.asyncio
    async def test_multifamily_luxury_lease(self, extractor, mock_openai_client) -> None:
        """Test luxury multi-family apartment lease."""
        lease_text = """
        LUXURY APARTMENT LEASE AGREEMENT
        
        Tenant: John and Jane Smith
        Landlord: Luxury Residential Properties LLC
        
        Property: 1000 Luxury Tower, Unit 1205, New York, NY 10001
        Unit Type: 2BR/2BA
        Square Footage: 1,200 RSF
        
        Term: October 1, 2024 to September 30, 2025
        
        RENT:
        Monthly Rent: $5,000
        Average Rent Per Unit: $5,000
        Rent Per Square Foot: $50/sq ft annually
        
        UNIT DETAILS:
        Unit Count: 200 units
        Unit Mix: Studio, 1BR, 2BR, 3BR
        Occupancy Rate: 98%
        Concessions: 1 month free rent
        Pet Policy: Dogs and cats allowed, $100/month pet rent
        Amenities: Pool, gym, concierge, rooftop terrace, parking garage
        Lease Term Options: 6, 12, 18, 24 months
        Rent Control: No
        Parking Ratio: 1.5 spaces per unit
        
        SCREENING:
        Income Verification: Yes, 3x rent required
        Background Check: Yes, credit and criminal
        Rent to Income Ratio: 0.33 (33%)
        
        SECURITY:
        Security Deposit: $10,000 (2 months)
        """
        
        mock_fields = {
            "tenant_name": {"value": "John and Jane Smith", "confidence": 0.90, "page": 1},
            "landlord_name": {"value": "Luxury Residential Properties LLC", "confidence": 0.95, "page": 1},
            "property_address": {"value": "1000 Luxury Tower, Unit 1205, New York, NY 10001", "confidence": 0.90, "page": 1},
            "unit_type": {"value": "2BR/2BA", "confidence": 0.90, "page": 1},
            "square_footage": {"value": "1200", "confidence": 0.90, "page": 1},
            "lease_start_date": {"value": "2024-10-01", "confidence": 0.95, "page": 1},
            "lease_end_date": {"value": "2025-09-30", "confidence": 0.95, "page": 1},
            "base_rent": {"value": "$5,000", "confidence": 0.95, "page": 1},
            "average_rent_per_unit": {"value": "$5,000", "confidence": 0.90, "page": 1},
            "rent_per_square_foot": {"value": "$50", "confidence": 0.90, "page": 1},
            "unit_count": {"value": "200", "confidence": 0.90, "page": 1},
            "unit_mix": {"value": "Studio, 1BR, 2BR, 3BR", "confidence": 0.85, "page": 1},
            "occupancy_rate": {"value": "98", "confidence": 0.90, "page": 1},
            "concessions": {"value": "1 month free rent", "confidence": 0.85, "page": 1},
            "pet_policy": {"value": "Dogs and cats allowed, $100/month", "confidence": 0.85, "page": 1},
            "amenities": {"value": "Pool, gym, concierge, rooftop terrace, parking garage", "confidence": 0.85, "page": 1},
            "lease_term_options": {"value": "6, 12, 18, 24 months", "confidence": 0.85, "page": 1},
            "rent_control": {"value": "false", "confidence": 0.85, "page": 1},
            "parking_ratio": {"value": "1.5", "confidence": 0.90, "page": 1},
            "income_verification": {"value": "true", "confidence": 0.90, "page": 1},
            "background_check": {"value": "true", "confidence": 0.90, "page": 1},
            "rent_to_income_ratio": {"value": "0.33", "confidence": 0.90, "page": 1},
            "security_deposit": {"value": "$10,000", "confidence": 0.90, "page": 1},
            "security_deposit_months": {"value": "2.0", "confidence": 0.90, "page": 1},
        }
        
        mock_openai_client.chat.completions.create = AsyncMock(
            return_value=self._create_mock_llm_response(mock_fields)
        )
        
        result = await extractor.extract_fields(lease_text, "cre", "lease")
        
        assert isinstance(result, ExtractionResult)
        assert result.fields["unit_type"].value == "2BR/2BA"
        assert result.fields["occupancy_rate"].value == 98.0
        assert result.fields["income_verification"].value is True
    
    @pytest.mark.asyncio
    async def test_multifamily_mid_market_lease(self, extractor, mock_openai_client) -> None:
        """Test mid-market multi-family lease."""
        lease_text = """
        APARTMENT LEASE AGREEMENT
        
        Tenant: Family Name
        Landlord: Mid-Market Properties Inc.
        
        Property: 500 Apartment Complex, Unit 305, Denver, CO 80202
        Unit Type: 3BR/2BA
        Square Footage: 1,500 RSF
        
        Term: November 1, 2024 to October 31, 2025
        
        RENT:
        Monthly Rent: $2,500
        Occupancy Rate: 95%
        
        UNIT DETAILS:
        Unit Count: 150 units
        Concessions: $500 move-in credit
        Pet Policy: Cats only, $25/month
        Amenities: Pool, fitness center
        Lease Term: 12 months standard
        
        SCREENING:
        Income Verification: Yes
        Background Check: Yes
        Rent to Income Ratio: 0.30
        
        SECURITY:
        Deposit: $2,500 (1 month)
        """
        
        mock_fields = {
            "tenant_name": {"value": "Family Name", "confidence": 0.90, "page": 1},
            "landlord_name": {"value": "Mid-Market Properties Inc.", "confidence": 0.95, "page": 1},
            "property_address": {"value": "500 Apartment Complex, Unit 305, Denver, CO 80202", "confidence": 0.90, "page": 1},
            "unit_type": {"value": "3BR/2BA", "confidence": 0.90, "page": 1},
            "square_footage": {"value": "1500", "confidence": 0.90, "page": 1},
            "lease_start_date": {"value": "2024-11-01", "confidence": 0.95, "page": 1},
            "lease_end_date": {"value": "2025-10-31", "confidence": 0.95, "page": 1},
            "base_rent": {"value": "$2,500", "confidence": 0.95, "page": 1},
            "occupancy_rate": {"value": "95", "confidence": 0.90, "page": 1},
            "unit_count": {"value": "150", "confidence": 0.90, "page": 1},
            "concessions": {"value": "$500 move-in credit", "confidence": 0.85, "page": 1},
            "pet_policy": {"value": "Cats only, $25/month", "confidence": 0.85, "page": 1},
            "amenities": {"value": "Pool, fitness center", "confidence": 0.85, "page": 1},
            "income_verification": {"value": "true", "confidence": 0.90, "page": 1},
            "background_check": {"value": "true", "confidence": 0.90, "page": 1},
            "rent_to_income_ratio": {"value": "0.30", "confidence": 0.90, "page": 1},
            "security_deposit": {"value": "$2,500", "confidence": 0.90, "page": 1},
        }
        
        mock_openai_client.chat.completions.create = AsyncMock(
            return_value=self._create_mock_llm_response(mock_fields)
        )
        
        result = await extractor.extract_fields(lease_text, "cre", "lease")
        
        assert isinstance(result, ExtractionResult)
        assert result.fields["unit_type"].value == "3BR/2BA"
        assert result.fields["occupancy_rate"].value == 95.0
    
    @pytest.mark.asyncio
    async def test_multifamily_affordable_lease(self, extractor, mock_openai_client) -> None:
        """Test affordable housing multi-family lease."""
        lease_text = """
        AFFORDABLE HOUSING LEASE
        
        Tenant: Resident Name
        Landlord: Affordable Housing Corp
        
        Property: 200 Affordable Complex, Unit 105, Baltimore, MD 21201
        Unit Type: 2BR/1BA
        Square Footage: 900 RSF
        
        Term: December 1, 2024 to November 30, 2025
        
        RENT:
        Monthly Rent: $1,200
        Rent Control: Yes
        Occupancy Rate: 100%
        
        UNIT DETAILS:
        Unit Count: 100 units
        Concessions: None
        Pet Policy: No pets
        Amenities: Community room
        Lease Term: 12 months
        
        SCREENING:
        Income Verification: Yes, income limits apply
        Background Check: Yes
        Rent to Income Ratio: 0.30
        
        SECURITY:
        Deposit: $1,200
        """
        
        mock_fields = {
            "tenant_name": {"value": "Resident Name", "confidence": 0.90, "page": 1},
            "landlord_name": {"value": "Affordable Housing Corp", "confidence": 0.95, "page": 1},
            "property_address": {"value": "200 Affordable Complex, Unit 105, Baltimore, MD 21201", "confidence": 0.90, "page": 1},
            "unit_type": {"value": "2BR/1BA", "confidence": 0.90, "page": 1},
            "square_footage": {"value": "900", "confidence": 0.90, "page": 1},
            "lease_start_date": {"value": "2024-12-01", "confidence": 0.95, "page": 1},
            "lease_end_date": {"value": "2025-11-30", "confidence": 0.95, "page": 1},
            "base_rent": {"value": "$1,200", "confidence": 0.95, "page": 1},
            "rent_control": {"value": "true", "confidence": 0.90, "page": 1},
            "occupancy_rate": {"value": "100", "confidence": 0.90, "page": 1},
            "unit_count": {"value": "100", "confidence": 0.90, "page": 1},
            "pet_policy": {"value": "No pets", "confidence": 0.85, "page": 1},
            "amenities": {"value": "Community room", "confidence": 0.85, "page": 1},
            "income_verification": {"value": "true", "confidence": 0.90, "page": 1},
            "background_check": {"value": "true", "confidence": 0.90, "page": 1},
            "rent_to_income_ratio": {"value": "0.30", "confidence": 0.90, "page": 1},
            "security_deposit": {"value": "$1,200", "confidence": 0.90, "page": 1},
        }
        
        mock_openai_client.chat.completions.create = AsyncMock(
            return_value=self._create_mock_llm_response(mock_fields)
        )
        
        result = await extractor.extract_fields(lease_text, "cre", "lease")
        
        assert isinstance(result, ExtractionResult)
        assert result.fields["rent_control"].value is True
        assert result.fields["occupancy_rate"].value == 100.0
    
    # ========== MIXED-USE LEASES (3 tests) ==========
    
    @pytest.mark.asyncio
    async def test_mixed_use_retail_office_lease(self, extractor, mock_openai_client) -> None:
        """Test mixed-use property with retail and office components."""
        lease_text = """
        MIXED-USE PROPERTY LEASE - RETAIL/OFFICE
        
        Tenant: Business Services LLC
        Landlord: Mixed-Use Development Partners
        
        Property: 300 Main Street, Ground Floor Retail + 2nd Floor Office, Seattle, WA 98101
        Component Breakdown: Retail 40%, Office 35%, Residential 25%
        Retail Percentage: 40%
        Office Percentage: 35%
        Residential Percentage: 25%
        
        Term: January 1, 2024 to December 31, 2028
        
        RENT:
        Base Rent: $15,000/month
        Retail Component: $8,000/month
        Office Component: $7,000/month
        
        SHARED FACILITIES:
        Shared Parking: Yes, common garage
        Separate Entrances: Yes, dedicated retail and office entrances
        Operating Hours Restrictions: Retail 6 AM - 11 PM, Office 24/7 access
        Noise Restrictions: Sound limitations for residential units above
        Zoning: C-2 Commercial Mixed-Use
        Cross Default Clause: Yes, default in one component affects all
        
        SECURITY:
        Deposit: $30,000
        """
        
        mock_fields = {
            "tenant_name": {"value": "Business Services LLC", "confidence": 0.95, "page": 1},
            "landlord_name": {"value": "Mixed-Use Development Partners", "confidence": 0.95, "page": 1},
            "property_address": {"value": "300 Main Street, Ground Floor Retail + 2nd Floor Office, Seattle, WA 98101", "confidence": 0.90, "page": 1},
            "component_breakdown": {"value": "Retail 40%, Office 35%, Residential 25%", "confidence": 0.85, "page": 1},
            "retail_percentage": {"value": "40", "confidence": 0.85, "page": 1},
            "office_percentage": {"value": "35", "confidence": 0.85, "page": 1},
            "residential_percentage": {"value": "25", "confidence": 0.85, "page": 1},
            "lease_start_date": {"value": "2024-01-01", "confidence": 0.95, "page": 1},
            "lease_end_date": {"value": "2028-12-31", "confidence": 0.95, "page": 1},
            "base_rent": {"value": "$15,000", "confidence": 0.95, "page": 1},
            "shared_parking": {"value": "true", "confidence": 0.90, "page": 1},
            "separate_entrances": {"value": "true", "confidence": 0.90, "page": 1},
            "operating_hours_restrictions": {"value": "Retail 6 AM - 11 PM, Office 24/7", "confidence": 0.85, "page": 1},
            "noise_restrictions": {"value": "Sound limitations for residential", "confidence": 0.85, "page": 1},
            "zoning_classification": {"value": "C-2 Commercial Mixed-Use", "confidence": 0.90, "page": 1},
            "cross_default_clause": {"value": "true", "confidence": 0.90, "page": 1},
            "security_deposit": {"value": "$30,000", "confidence": 0.90, "page": 1},
        }
        
        mock_openai_client.chat.completions.create = AsyncMock(
            return_value=self._create_mock_llm_response(mock_fields)
        )
        
        result = await extractor.extract_fields(lease_text, "cre", "lease")
        
        assert isinstance(result, ExtractionResult)
        assert result.fields["retail_percentage"].value == 40.0
        assert result.fields["cross_default_clause"].value is True
    
    @pytest.mark.asyncio
    async def test_mixed_use_retail_residential_lease(self, extractor, mock_openai_client) -> None:
        """Test mixed-use property with retail and residential components."""
        lease_text = """
        MIXED-USE LEASE - RETAIL/RESIDENTIAL
        
        Tenant: Restaurant Group LLC
        Landlord: Urban Development LLC
        
        Property: 400 Urban Plaza, Ground Floor Restaurant, Portland, OR 97201
        Component Breakdown: Retail 50%, Residential 50%
        Retail Percentage: 50%
        Residential Percentage: 50%
        
        Term: February 1, 2024 to January 31, 2029
        
        RENT:
        Base Rent: $10,000/month
        Percentage Rent: 5% of gross sales over $2,400,000
        
        SHARED FACILITIES:
        Shared Parking: Yes
        Separate Entrances: Yes
        Operating Hours: Restaurant 11 AM - 10 PM
        Noise Restrictions: Quiet hours 10 PM - 7 AM for residential
        Zoning: Mixed-Use Commercial/Residential
        Cross Default: Yes
        
        SECURITY:
        Deposit: $20,000
        """
        
        mock_fields = {
            "tenant_name": {"value": "Restaurant Group LLC", "confidence": 0.95, "page": 1},
            "landlord_name": {"value": "Urban Development LLC", "confidence": 0.95, "page": 1},
            "property_address": {"value": "400 Urban Plaza, Ground Floor Restaurant, Portland, OR 97201", "confidence": 0.90, "page": 1},
            "component_breakdown": {"value": "Retail 50%, Residential 50%", "confidence": 0.85, "page": 1},
            "retail_percentage": {"value": "50", "confidence": 0.85, "page": 1},
            "residential_percentage": {"value": "50", "confidence": 0.85, "page": 1},
            "lease_start_date": {"value": "2024-02-01", "confidence": 0.95, "page": 1},
            "lease_end_date": {"value": "2029-01-31", "confidence": 0.95, "page": 1},
            "base_rent": {"value": "$10,000", "confidence": 0.95, "page": 1},
            "percentage_rent": {"value": "5%", "confidence": 0.90, "page": 1},
            "shared_parking": {"value": "true", "confidence": 0.90, "page": 1},
            "separate_entrances": {"value": "true", "confidence": 0.90, "page": 1},
            "operating_hours_restrictions": {"value": "Restaurant 11 AM - 10 PM", "confidence": 0.85, "page": 1},
            "noise_restrictions": {"value": "Quiet hours 10 PM - 7 AM", "confidence": 0.85, "page": 1},
            "zoning_classification": {"value": "Mixed-Use Commercial/Residential", "confidence": 0.90, "page": 1},
            "cross_default_clause": {"value": "true", "confidence": 0.90, "page": 1},
            "security_deposit": {"value": "$20,000", "confidence": 0.90, "page": 1},
        }
        
        mock_openai_client.chat.completions.create = AsyncMock(
            return_value=self._create_mock_llm_response(mock_fields)
        )
        
        result = await extractor.extract_fields(lease_text, "cre", "lease")
        
        assert isinstance(result, ExtractionResult)
        assert result.fields["retail_percentage"].value == 50.0
        assert result.fields["percentage_rent"].value is not None
    
    @pytest.mark.asyncio
    async def test_mixed_use_office_residential_lease(self, extractor, mock_openai_client) -> None:
        """Test mixed-use property with office and residential components."""
        lease_text = """
        MIXED-USE LEASE - OFFICE/RESIDENTIAL
        
        Tenant: Professional Services Corp
        Landlord: Mixed-Use Tower LLC
        
        Property: 500 Tower Plaza, 10th Floor Office, Boston, MA 02101
        Component Breakdown: Office 60%, Residential 40%
        Office Percentage: 60%
        Residential Percentage: 40%
        
        Term: March 1, 2024 to February 28, 2029
        
        RENT:
        Base Rent: $20,000/month
        Full Service Gross Lease
        
        SHARED FACILITIES:
        Shared Parking: Yes, valet parking
        Separate Entrances: Yes, dedicated office lobby
        Operating Hours: Office 8 AM - 6 PM weekdays
        Noise Restrictions: Office operations limited during residential quiet hours
        Zoning: Mixed-Use Office/Residential
        Cross Default: Yes
        
        SECURITY:
        Deposit: $40,000
        Corporate Guarantee: Yes
        """
        
        mock_fields = {
            "tenant_name": {"value": "Professional Services Corp", "confidence": 0.95, "page": 1},
            "landlord_name": {"value": "Mixed-Use Tower LLC", "confidence": 0.95, "page": 1},
            "property_address": {"value": "500 Tower Plaza, 10th Floor Office, Boston, MA 02101", "confidence": 0.90, "page": 1},
            "component_breakdown": {"value": "Office 60%, Residential 40%", "confidence": 0.85, "page": 1},
            "office_percentage": {"value": "60", "confidence": 0.85, "page": 1},
            "residential_percentage": {"value": "40", "confidence": 0.85, "page": 1},
            "lease_start_date": {"value": "2024-03-01", "confidence": 0.95, "page": 1},
            "lease_end_date": {"value": "2029-02-28", "confidence": 0.95, "page": 1},
            "base_rent": {"value": "$20,000", "confidence": 0.95, "page": 1},
            "lease_type": {"value": "gross", "confidence": 0.90, "page": 1},
            "shared_parking": {"value": "true", "confidence": 0.90, "page": 1},
            "separate_entrances": {"value": "true", "confidence": 0.90, "page": 1},
            "operating_hours_restrictions": {"value": "Office 8 AM - 6 PM weekdays", "confidence": 0.85, "page": 1},
            "noise_restrictions": {"value": "Office operations limited during residential quiet hours", "confidence": 0.85, "page": 1},
            "zoning_classification": {"value": "Mixed-Use Office/Residential", "confidence": 0.90, "page": 1},
            "cross_default_clause": {"value": "true", "confidence": 0.90, "page": 1},
            "security_deposit": {"value": "$40,000", "confidence": 0.90, "page": 1},
            "corporate_guarantee": {"value": "true", "confidence": 0.90, "page": 1},
        }
        
        mock_openai_client.chat.completions.create = AsyncMock(
            return_value=self._create_mock_llm_response(mock_fields)
        )
        
        result = await extractor.extract_fields(lease_text, "cre", "lease")
        
        assert isinstance(result, ExtractionResult)
        assert result.fields["office_percentage"].value == 60.0
        assert result.fields["cross_default_clause"].value is True
