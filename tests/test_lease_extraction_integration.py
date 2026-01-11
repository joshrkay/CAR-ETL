"""
Integration tests for CRE lease extraction with real-world scenarios.

Tests extraction on leases of varying complexity and length.
Uses synthetic and publicly available sample leases.
"""

import json
from typing import Any
from unittest.mock import AsyncMock, Mock, patch

import pytest

from src.extraction.extractor import ExtractionResult, FieldExtractor


class TestLeaseExtractionIntegration:
    """Integration tests for lease extraction with various document complexities."""

    @pytest.fixture
    def mock_openai_client(self):
        """Create mock OpenAI client."""
        client = AsyncMock()
        return client

    @pytest.fixture
    def extractor(self, mock_openai_client):
        """Create FieldExtractor with mocked OpenAI client."""
        with patch('src.extraction.extractor.AsyncOpenAI', return_value=mock_openai_client):
            with patch('src.extraction.extractor.presidio_redact', return_value=lambda x: x):
                extractor = FieldExtractor(api_key="test-key")
                extractor.client = mock_openai_client
                return extractor

    def _create_mock_llm_response(self, fields: dict[str, Any]) -> Mock:
        """Helper to create mock LLM response."""
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message = Mock()
        mock_response.choices[0].message.content = json.dumps({"fields": fields})
        return mock_response

    @pytest.mark.asyncio
    async def test_simple_short_lease(self, extractor, mock_openai_client) -> None:
        """Test extraction from a simple, short lease (1-2 pages)."""
        lease_text = """
        COMMERCIAL LEASE AGREEMENT

        Tenant: ABC Corporation
        Landlord: XYZ Properties LLC
        Property: 123 Main Street, Suite 100, New York, NY 10001

        Lease Term: January 1, 2024 to December 31, 2024
        Base Rent: $5,000 per month
        Square Footage: 2,000 sq ft
        Security Deposit: $5,000
        """

        mock_fields = {
            "tenant_name": {"value": "ABC Corporation", "confidence": 0.95, "page": 1, "quote": "Tenant: ABC Corporation"},
            "landlord_name": {"value": "XYZ Properties LLC", "confidence": 0.95, "page": 1, "quote": "Landlord: XYZ Properties LLC"},
            "property_address": {"value": "123 Main Street, Suite 100, New York, NY 10001", "confidence": 0.90, "page": 1},
            "lease_start_date": {"value": "2024-01-01", "confidence": 0.95, "page": 1},
            "lease_end_date": {"value": "2024-12-31", "confidence": 0.95, "page": 1},
            "base_rent": {"value": "$5,000", "confidence": 0.95, "page": 1},
            "rent_frequency": {"value": "monthly", "confidence": 0.90, "page": 1},
            "square_footage": {"value": "2000", "confidence": 0.90, "page": 1},
            "security_deposit": {"value": "$5,000", "confidence": 0.90, "page": 1},
        }

        mock_openai_client.chat.completions.create = AsyncMock(
            return_value=self._create_mock_llm_response(mock_fields)
        )

        result = await extractor.extract_fields(lease_text, "cre", "lease")

        assert isinstance(result, ExtractionResult)
        assert "tenant_name" in result.fields
        assert result.fields["tenant_name"].value == "ABC Corporation"
        assert result.overall_confidence > 0.0

    @pytest.mark.asyncio
    async def test_medium_complexity_lease(self, extractor, mock_openai_client) -> None:
        """Test extraction from medium complexity lease (5-10 pages)."""
        lease_text = """
        COMMERCIAL OFFICE LEASE AGREEMENT

        PARTIES:
        Tenant: TechStart Inc., a Delaware Corporation
        Landlord: Metro Office Holdings LLC, a Delaware Limited Liability Company

        PROPERTY:
        Building: Metro Office Tower
        Address: 456 Business Park Drive, Suite 500, San Francisco, CA 94105
        Square Footage: 5,000 rentable square feet
        Suite: 500

        LEASE TERM:
        Commencement Date: March 1, 2024
        Expiration Date: February 28, 2027
        Initial Term: 36 months

        RENT:
        Base Rent: $15,000 per month ($18.00 per square foot annually)
        Rent Frequency: Monthly
        Rent Due Date: 1st of each month
        Late Fee: $500 or 5% of rent, whichever is greater

        ESCALATIONS:
        Annual escalation: 3% per year
        CPI adjustments: Yes, based on Consumer Price Index

        LEASE TYPE:
        Modified Gross Lease
        CAM Charges: Estimated $2.50 per square foot annually
        Tax Reimbursement: Tenant's pro-rata share
        Insurance Reimbursement: Tenant's pro-rata share

        SECURITY:
        Security Deposit: $15,000
        Personal Guarantee: Yes

        OPTIONS:
        Renewal Option: One 3-year renewal option at market rate
        Right of First Refusal: Yes, for adjacent space

        IMPROVEMENTS:
        Tenant Improvement Allowance: $50,000
        Buildout Period: 60 days

        USE:
        Permitted Use: General office use, software development
        Prohibited Use: Retail, manufacturing, food service
        """

        mock_fields = {
            "tenant_name": {"value": "TechStart Inc.", "confidence": 0.95, "page": 1},
            "landlord_name": {"value": "Metro Office Holdings LLC", "confidence": 0.95, "page": 1},
            "property_address": {"value": "456 Business Park Drive, Suite 500, San Francisco, CA 94105", "confidence": 0.90, "page": 1},
            "city": {"value": "San Francisco", "confidence": 0.90, "page": 1},
            "state": {"value": "CA", "confidence": 0.90, "page": 1},
            "zip_code": {"value": "94105", "confidence": 0.90, "page": 1},
            "square_footage": {"value": "5000", "confidence": 0.90, "page": 1},
            "lease_start_date": {"value": "2024-03-01", "confidence": 0.95, "page": 1},
            "lease_end_date": {"value": "2027-02-28", "confidence": 0.95, "page": 1},
            "initial_term_months": {"value": "36", "confidence": 0.90, "page": 1},
            "base_rent": {"value": "$15,000", "confidence": 0.95, "page": 1},
            "rent_frequency": {"value": "monthly", "confidence": 0.95, "page": 1},
            "rent_due_date": {"value": "1", "confidence": 0.90, "page": 1},
            "late_fee_amount": {"value": "$500", "confidence": 0.85, "page": 1},
            "escalation_rate_percent": {"value": "3", "confidence": 0.90, "page": 1},
            "lease_type": {"value": "modified_gross", "confidence": 0.90, "page": 1},
            "cam_charges": {"value": "$2.50", "confidence": 0.85, "page": 1},
            "security_deposit": {"value": "$15,000", "confidence": 0.90, "page": 1},
            "personal_guarantee": {"value": "true", "confidence": 0.90, "page": 1},
            "renewal_options": {"value": "One 3-year renewal option", "confidence": 0.85, "page": 1},
            "right_of_first_refusal": {"value": "true", "confidence": 0.85, "page": 1},
            "tenant_improvement_allowance": {"value": "$50,000", "confidence": 0.90, "page": 1},
            "buildout_period_days": {"value": "60", "confidence": 0.90, "page": 1},
            "permitted_use": {"value": "General office use, software development", "confidence": 0.85, "page": 1},
        }

        mock_openai_client.chat.completions.create = AsyncMock(
            return_value=self._create_mock_llm_response(mock_fields)
        )

        result = await extractor.extract_fields(lease_text, "cre", "lease")

        assert isinstance(result, ExtractionResult)
        assert len(result.fields) > 15  # Should extract many fields
        assert result.overall_confidence > 0.0

    @pytest.mark.asyncio
    async def test_complex_retail_lease(self, extractor, mock_openai_client) -> None:
        """Test extraction from complex retail lease with percentage rent."""
        lease_text = """
        RETAIL LEASE AGREEMENT

        Tenant: Fashion Retail Co., LLC
        Landlord: Shopping Center Partners, LP

        Premises: 789 Shopping Mall, Unit 25, Los Angeles, CA 90001
        Property Type: Retail, Inline Store
        Square Footage: 3,500 rentable square feet

        Term: April 1, 2024 to March 31, 2029 (5 years)

        BASE RENT:
        Year 1-2: $8,750/month ($30/sq ft annually)
        Year 3-4: $9,625/month ($33/sq ft annually)
        Year 5: $10,500/month ($36/sq ft annually)

        PERCENTAGE RENT:
        Percentage: 6% of gross sales over $1,750,000 annually
        Sales Reporting: Required monthly
        Breakpoint: $1,750,000 per year

        COMMON AREA CHARGES:
        CAM: Estimated $4.50/sq ft annually
        Marketing Fee: $200/month
        Insurance: Tenant's pro-rata share

        CO-TENANCY:
        Co-tenancy clause: Yes, rent reduction if anchor tenant leaves

        SIGNAGE:
        Signage Type: Façade signage allowed
        Exclusive Use: Women's fashion apparel

        PARKING:
        Parking Spaces: 2 spaces
        Parking Fee: $50/month per space

        SECURITY:
        Security Deposit: $17,500
        Letter of Credit: $50,000
        """

        mock_fields = {
            "tenant_name": {"value": "Fashion Retail Co., LLC", "confidence": 0.95, "page": 1},
            "landlord_name": {"value": "Shopping Center Partners, LP", "confidence": 0.95, "page": 1},
            "property_address": {"value": "789 Shopping Mall, Unit 25, Los Angeles, CA 90001", "confidence": 0.90, "page": 1},
            "retail_type": {"value": "inline", "confidence": 0.90, "page": 1},
            "square_footage": {"value": "3500", "confidence": 0.90, "page": 1},
            "lease_start_date": {"value": "2024-04-01", "confidence": 0.95, "page": 1},
            "lease_end_date": {"value": "2029-03-31", "confidence": 0.95, "page": 1},
            "base_rent": {"value": "$8,750", "confidence": 0.90, "page": 1},
            "percentage_rent": {"value": "6%", "confidence": 0.90, "page": 1},
            "sales_reporting_required": {"value": "true", "confidence": 0.90, "page": 1},
            "cam_charges": {"value": "$4.50", "confidence": 0.85, "page": 1},
            "common_area_marketing_fee": {"value": "$200", "confidence": 0.85, "page": 1},
            "co_tenancy_clause": {"value": "true", "confidence": 0.85, "page": 1},
            "signage_type": {"value": "façade", "confidence": 0.85, "page": 1},
            "exclusive_retail_use": {"value": "Women's fashion apparel", "confidence": 0.85, "page": 1},
            "parking_spaces": {"value": "2", "confidence": 0.90, "page": 1},
            "parking_fee": {"value": "$50", "confidence": 0.85, "page": 1},
            "security_deposit": {"value": "$17,500", "confidence": 0.90, "page": 1},
            "letter_of_credit_amount": {"value": "$50,000", "confidence": 0.90, "page": 1},
        }

        mock_openai_client.chat.completions.create = AsyncMock(
            return_value=self._create_mock_llm_response(mock_fields)
        )

        result = await extractor.extract_fields(lease_text, "cre", "lease")

        assert isinstance(result, ExtractionResult)
        assert "retail_type" in result.fields
        assert "percentage_rent" in result.fields
        assert result.fields["retail_type"].value == "inline"

    @pytest.mark.asyncio
    async def test_industrial_warehouse_lease(self, extractor, mock_openai_client) -> None:
        """Test extraction from industrial/warehouse lease."""
        lease_text = """
        INDUSTRIAL WAREHOUSE LEASE

        Tenant: Logistics Solutions Inc.
        Landlord: Industrial Properties REIT

        Facility: 1000 Distribution Way, Building B, Dallas, TX 75201
        Square Footage: 50,000 sq ft
        Building Type: Industrial

        Term: June 1, 2024 to May 31, 2029

        RENT:
        Base Rent: $25,000/month ($6.00/sq ft annually)
        Triple Net Lease (NNN)

        PROPERTY SPECIFICATIONS:
        Clear Height: 32 feet
        Column Spacing: 50' x 50'
        Loading Docks: 8 dock doors
        Drive-in Doors: 2 grade-level doors
        Trailer Parking: 10 spaces
        Power Capacity: 480V, 2000A service
        Sprinkler Type: ESFR
        Floor Load: 250 psf
        Rail Access: Yes
        Cross Dock: Yes

        SECURITY:
        Security Deposit: $50,000
        Corporate Guarantee: Yes
        """

        mock_fields = {
            "tenant_name": {"value": "Logistics Solutions Inc.", "confidence": 0.95, "page": 1},
            "landlord_name": {"value": "Industrial Properties REIT", "confidence": 0.95, "page": 1},
            "property_address": {"value": "1000 Distribution Way, Building B, Dallas, TX 75201", "confidence": 0.90, "page": 1},
            "building_type": {"value": "industrial", "confidence": 0.90, "page": 1},
            "square_footage": {"value": "50000", "confidence": 0.90, "page": 1},
            "lease_start_date": {"value": "2024-06-01", "confidence": 0.95, "page": 1},
            "lease_end_date": {"value": "2029-05-31", "confidence": 0.95, "page": 1},
            "base_rent": {"value": "$25,000", "confidence": 0.95, "page": 1},
            "lease_type": {"value": "nnn", "confidence": 0.90, "page": 1},
            "clear_height": {"value": "32", "confidence": 0.90, "page": 1},
            "column_spacing": {"value": "50' x 50'", "confidence": 0.85, "page": 1},
            "loading_docks": {"value": "8", "confidence": 0.90, "page": 1},
            "drive_in_doors": {"value": "2", "confidence": 0.90, "page": 1},
            "trailer_parking_spaces": {"value": "10", "confidence": 0.90, "page": 1},
            "power_capacity": {"value": "480V, 2000A", "confidence": 0.85, "page": 1},
            "sprinkler_type": {"value": "ESFR", "confidence": 0.90, "page": 1},
            "floor_load_capacity": {"value": "250 psf", "confidence": 0.90, "page": 1},
            "rail_access": {"value": "true", "confidence": 0.90, "page": 1},
            "cross_dock": {"value": "true", "confidence": 0.90, "page": 1},
            "security_deposit": {"value": "$50,000", "confidence": 0.90, "page": 1},
            "corporate_guarantee": {"value": "true", "confidence": 0.90, "page": 1},
        }

        mock_openai_client.chat.completions.create = AsyncMock(
            return_value=self._create_mock_llm_response(mock_fields)
        )

        result = await extractor.extract_fields(lease_text, "cre", "lease")

        assert isinstance(result, ExtractionResult)
        assert "clear_height" in result.fields
        assert "loading_docks" in result.fields
        assert result.fields["lease_type"].value == "nnn"

    @pytest.mark.asyncio
    async def test_office_class_a_lease(self, extractor, mock_openai_client) -> None:
        """Test extraction from Class A office lease with certifications."""
        lease_text = """
        CLASS A OFFICE LEASE AGREEMENT

        Tenant: Global Finance Corp
        Landlord: Premium Office REIT

        Building: Tower One, 500 Financial Plaza, Suite 2000, Chicago, IL 60601
        Office Class: A
        Square Footage: 10,000 RSF
        Floor: 20th floor

        Term: July 1, 2024 to June 30, 2027

        RENT:
        Base Rent: $35,000/month ($42/sq ft annually)
        Full Service Gross Lease

        BUILDING FEATURES:
        Floor Plate Size: 25,000 sq ft
        Core Factor: 1.15
        Conference Room Access: Yes
        After Hours HVAC: $150/hour
        Elevator Ratio: 4 elevators, 1 per 6,250 sq ft
        Building Certifications: LEED Gold, EnergyStar
        Spec Suite: No, custom buildout
        Open Plan Ratio: 0.60

        IMPROVEMENTS:
        TI Allowance: $100,000
        Buildout Period: 90 days
        """

        mock_fields = {
            "tenant_name": {"value": "Global Finance Corp", "confidence": 0.95, "page": 1},
            "landlord_name": {"value": "Premium Office REIT", "confidence": 0.95, "page": 1},
            "property_address": {"value": "500 Financial Plaza, Suite 2000, Chicago, IL 60601", "confidence": 0.90, "page": 1},
            "office_class": {"value": "A", "confidence": 0.95, "page": 1},
            "square_footage": {"value": "10000", "confidence": 0.90, "page": 1},
            "floor_number": {"value": "20", "confidence": 0.90, "page": 1},
            "lease_start_date": {"value": "2024-07-01", "confidence": 0.95, "page": 1},
            "lease_end_date": {"value": "2027-06-30", "confidence": 0.95, "page": 1},
            "base_rent": {"value": "$35,000", "confidence": 0.95, "page": 1},
            "lease_type": {"value": "gross", "confidence": 0.90, "page": 1},
            "floor_plate_size": {"value": "25000", "confidence": 0.90, "page": 1},
            "core_factor": {"value": "1.15", "confidence": 0.90, "page": 1},
            "conference_room_access": {"value": "true", "confidence": 0.90, "page": 1},
            "after_hours_hvac": {"value": "$150", "confidence": 0.90, "page": 1},
            "elevator_ratio": {"value": "4 elevators", "confidence": 0.85, "page": 1},
            "building_certifications": {"value": "LEED", "confidence": 0.90, "page": 1},
            "spec_suite": {"value": "false", "confidence": 0.90, "page": 1},
            "open_plan_ratio": {"value": "0.60", "confidence": 0.90, "page": 1},
            "tenant_improvement_allowance": {"value": "$100,000", "confidence": 0.90, "page": 1},
            "buildout_period_days": {"value": "90", "confidence": 0.90, "page": 1},
        }

        mock_openai_client.chat.completions.create = AsyncMock(
            return_value=self._create_mock_llm_response(mock_fields)
        )

        result = await extractor.extract_fields(lease_text, "cre", "lease")

        assert isinstance(result, ExtractionResult)
        assert "office_class" in result.fields
        assert result.fields["office_class"].value == "A"
        assert "building_certifications" in result.fields

    @pytest.mark.asyncio
    async def test_mixed_use_lease(self, extractor, mock_openai_client) -> None:
        """Test extraction from mixed-use property lease."""
        lease_text = """
        MIXED-USE PROPERTY LEASE

        Tenant: Restaurant Group LLC
        Landlord: Urban Development Partners

        Property: 200 Main Street, Ground Floor, Seattle, WA 98101
        Component: Retail (Ground Floor)

        Term: August 1, 2024 to July 31, 2029

        RENT:
        Base Rent: $12,000/month
        Percentage Rent: 5% of gross sales over $2,400,000 annually

        PROPERTY BREAKDOWN:
        Retail Percentage: 40% of building
        Office Percentage: 35% of building
        Residential Percentage: 25% of building

        SHARED FACILITIES:
        Shared Parking: Yes, common garage
        Separate Entrances: Yes, dedicated retail entrance
        Operating Hours Restrictions: Retail limited to 6 AM - 11 PM
        Noise Restrictions: Sound limitations for residential units above
        Zoning: C-2 Commercial Mixed-Use
        """

        mock_fields = {
            "tenant_name": {"value": "Restaurant Group LLC", "confidence": 0.95, "page": 1},
            "landlord_name": {"value": "Urban Development Partners", "confidence": 0.95, "page": 1},
            "property_address": {"value": "200 Main Street, Ground Floor, Seattle, WA 98101", "confidence": 0.90, "page": 1},
            "lease_start_date": {"value": "2024-08-01", "confidence": 0.95, "page": 1},
            "lease_end_date": {"value": "2029-07-31", "confidence": 0.95, "page": 1},
            "base_rent": {"value": "$12,000", "confidence": 0.95, "page": 1},
            "percentage_rent": {"value": "5%", "confidence": 0.90, "page": 1},
            "component_breakdown": {"value": "Retail 40%, Office 35%, Residential 25%", "confidence": 0.85, "page": 1},
            "retail_percentage": {"value": "40", "confidence": 0.85, "page": 1},
            "office_percentage": {"value": "35", "confidence": 0.85, "page": 1},
            "residential_percentage": {"value": "25", "confidence": 0.85, "page": 1},
            "shared_parking": {"value": "true", "confidence": 0.90, "page": 1},
            "separate_entrances": {"value": "true", "confidence": 0.90, "page": 1},
            "operating_hours_restrictions": {"value": "6 AM - 11 PM", "confidence": 0.85, "page": 1},
            "noise_restrictions": {"value": "Sound limitations for residential", "confidence": 0.85, "page": 1},
            "zoning_classification": {"value": "C-2 Commercial Mixed-Use", "confidence": 0.90, "page": 1},
        }

        mock_openai_client.chat.completions.create = AsyncMock(
            return_value=self._create_mock_llm_response(mock_fields)
        )

        result = await extractor.extract_fields(lease_text, "cre", "lease")

        assert isinstance(result, ExtractionResult)
        assert "retail_percentage" in result.fields
        assert "shared_parking" in result.fields

    @pytest.mark.asyncio
    async def test_long_complex_lease(self, extractor, mock_openai_client) -> None:
        """Test extraction from long, complex lease (20+ pages equivalent)."""
        # Simulate a very long lease with many sections
        lease_text = """
        COMPREHENSIVE COMMERCIAL LEASE AGREEMENT

        This is a detailed lease agreement containing extensive terms and conditions...

        PARTIES:
        Tenant: MegaCorp International, Inc., a Delaware Corporation
        Tenant Entity Type: Corp
        Tenant Contact: John Smith, jsmith@megacorp.com, (555) 123-4567
        Landlord: Prime Real Estate Holdings, LLC, a Delaware Limited Liability Company
        Landlord Entity Type: LLC
        Landlord Contact: Jane Doe

        PROPERTY:
        Property Name: Prime Business Center
        Address: 1000 Corporate Boulevard, Suite 1500, Atlanta, GA 30309
        City: Atlanta
        State: Georgia
        Zip Code: 30309
        Suite: 1500
        Floor: 15th floor
        Building Type: Office

        LEASE TERM:
        Commencement Date: September 1, 2024
        Expiration Date: August 31, 2034
        Execution Date: June 15, 2024
        Possession Date: August 15, 2024
        Initial Term: 120 months (10 years)
        Holdover: Month-to-month at 150% of base rent

        RENT & PAYMENTS:
        Base Rent Year 1-2: $50,000/month ($60/sq ft)
        Base Rent Year 3-5: $55,000/month ($66/sq ft)
        Base Rent Year 6-10: $60,000/month ($72/sq ft)
        Rent Frequency: Monthly
        Rent Due Date: 1st of month
        Late Fee: $1,000 or 5%, whichever greater
        Late Fee Grace Period: 5 days

        ESCALATIONS:
        Escalation Type: Fixed annual increase of 3%
        Escalation Rate: 3% per year
        Escalation Frequency: Annual
        Free Rent: 3 months free rent (months 1-3)
        Rent Abatement: 50% abatement months 4-6

        LEASE STRUCTURE:
        Lease Type: Modified Gross
        Expense Reimbursement: CAM, Tax, Insurance
        Expense Stop: $8.50/sq ft
        CAM Charges: Estimated $5.00/sq ft annually
        Tax Reimbursement: Pro-rata share
        Insurance Reimbursement: Pro-rata share

        SPACE DETAILS:
        Square Footage: 10,000 RSF
        Rentable Square Feet: 10,000
        Usable Square Feet: 8,500
        Load Factor: 1.176
        Common Area Factor: 0.176
        Parking Spaces: 4 spaces
        Parking Fee: $100/month per space

        SECURITY:
        Security Deposit: $50,000
        Letter of Credit: $100,000
        Personal Guarantee: Yes
        Corporate Guarantee: Yes

        OPTIONS:
        Renewal Options: Two 5-year renewal options
        Renewal Term: 5 years each
        Expansion Rights: Right to expand into adjacent 2,500 sq ft
        Right of First Refusal: Yes
        Right of First Offer: Yes
        Termination Clause: Early termination after 5 years with 6 months notice
        Early Termination Fee: 6 months base rent

        USE & RESTRICTIONS:
        Permitted Use: General office, corporate headquarters
        Exclusive Use: Financial services, corporate headquarters
        Prohibited Use: Retail, manufacturing, food service
        Sublease Rights: Allowed with landlord consent
        Assignment Rights: Allowed with landlord consent

        IMPROVEMENTS:
        TI Allowance: $150,000
        Buildout Period: 120 days
        Landlord Repairs: Structural, roof, HVAC
        Tenant Repairs: Interior, non-structural
        HVAC Responsibility: Shared
        Roof Responsibility: Landlord

        INSURANCE:
        Tenant Insurance Required: Yes
        Insurance Minimum: $2,000,000
        Indemnification: Mutual indemnification
        ADA Compliance: Yes

        LEGAL:
        Default Events: Non-payment, breach of use, assignment without consent
        Remedies: Landlord may terminate, accelerate rent, re-enter
        Governing Law: State of Georgia
        Attorney Fees: Prevailing party
        Confidentiality: Yes

        MISC:
        Force Majeure: Yes
        Signage Rights: Building directory and suite signage
        Operating Hours: 24/7 access
        Broker: Commercial Realty Group
        Broker Commission: $75,000

        PROPERTY METRICS:
        Cap Rate: 5.5%
        NOI: $600,000
        GRM: 12.5
        Expense Ratio: 35%
        Year Built: 2010
        Renovation Year: 2020
        Flood Zone: Zone X
        """

        # Create comprehensive mock response
        mock_fields = {
            "tenant_name": {"value": "MegaCorp International, Inc.", "confidence": 0.95, "page": 1},
            "tenant_entity_type": {"value": "Corp", "confidence": 0.90, "page": 1},
            "tenant_contact_name": {"value": "John Smith", "confidence": 0.85, "page": 1},
            "tenant_email": {"value": "jsmith@megacorp.com", "confidence": 0.85, "page": 1},
            "tenant_phone": {"value": "(555) 123-4567", "confidence": 0.85, "page": 1},
            "landlord_name": {"value": "Prime Real Estate Holdings, LLC", "confidence": 0.95, "page": 1},
            "landlord_entity_type": {"value": "LLC", "confidence": 0.90, "page": 1},
            "property_name": {"value": "Prime Business Center", "confidence": 0.90, "page": 1},
            "property_address": {"value": "1000 Corporate Boulevard, Suite 1500, Atlanta, GA 30309", "confidence": 0.90, "page": 1},
            "city": {"value": "Atlanta", "confidence": 0.90, "page": 1},
            "state": {"value": "Georgia", "confidence": 0.90, "page": 1},
            "zip_code": {"value": "30309", "confidence": 0.90, "page": 1},
            "lease_start_date": {"value": "2024-09-01", "confidence": 0.95, "page": 1},
            "lease_end_date": {"value": "2034-08-31", "confidence": 0.95, "page": 1},
            "lease_execution_date": {"value": "2024-06-15", "confidence": 0.90, "page": 1},
            "possession_date": {"value": "2024-08-15", "confidence": 0.90, "page": 1},
            "initial_term_months": {"value": "120", "confidence": 0.90, "page": 1},
            "base_rent": {"value": "$50,000", "confidence": 0.95, "page": 1},
            "rent_frequency": {"value": "monthly", "confidence": 0.95, "page": 1},
            "rent_due_date": {"value": "1", "confidence": 0.90, "page": 1},
            "late_fee_amount": {"value": "$1,000", "confidence": 0.90, "page": 1},
            "late_fee_grace_period_days": {"value": "5", "confidence": 0.90, "page": 1},
            "escalation_rate_percent": {"value": "3", "confidence": 0.90, "page": 1},
            "escalation_frequency": {"value": "annual", "confidence": 0.90, "page": 1},
            "free_rent_period": {"value": "3 months", "confidence": 0.85, "page": 1},
            "rent_abatement": {"value": "50% months 4-6", "confidence": 0.85, "page": 1},
            "lease_type": {"value": "modified_gross", "confidence": 0.90, "page": 1},
            "expense_reimbursement_type": {"value": "all", "confidence": 0.85, "page": 1},
            "expense_stop": {"value": "$8.50", "confidence": 0.85, "page": 1},
            "cam_charges": {"value": "$5.00", "confidence": 0.85, "page": 1},
            "square_footage": {"value": "10000", "confidence": 0.90, "page": 1},
            "rentable_square_feet": {"value": "10000", "confidence": 0.90, "page": 1},
            "usable_square_feet": {"value": "8500", "confidence": 0.90, "page": 1},
            "load_factor": {"value": "1.176", "confidence": 0.90, "page": 1},
            "common_area_factor": {"value": "0.176", "confidence": 0.90, "page": 1},
            "parking_spaces": {"value": "4", "confidence": 0.90, "page": 1},
            "parking_fee": {"value": "$100", "confidence": 0.90, "page": 1},
            "security_deposit": {"value": "$50,000", "confidence": 0.90, "page": 1},
            "letter_of_credit_amount": {"value": "$100,000", "confidence": 0.90, "page": 1},
            "personal_guarantee": {"value": "true", "confidence": 0.90, "page": 1},
            "corporate_guarantee": {"value": "true", "confidence": 0.90, "page": 1},
            "renewal_options": {"value": "Two 5-year renewal options", "confidence": 0.85, "page": 1},
            "renewal_term_length": {"value": "5 years", "confidence": 0.85, "page": 1},
            "expansion_rights": {"value": "Right to expand into adjacent 2,500 sq ft", "confidence": 0.85, "page": 1},
            "right_of_first_refusal": {"value": "true", "confidence": 0.85, "page": 1},
            "right_of_first_offer": {"value": "true", "confidence": 0.85, "page": 1},
            "termination_clause": {"value": "Early termination after 5 years", "confidence": 0.85, "page": 1},
            "early_termination_fee": {"value": "$300,000", "confidence": 0.85, "page": 1},
            "permitted_use": {"value": "General office, corporate headquarters", "confidence": 0.85, "page": 1},
            "exclusive_use": {"value": "Financial services, corporate headquarters", "confidence": 0.85, "page": 1},
            "prohibited_use": {"value": "Retail, manufacturing, food service", "confidence": 0.85, "page": 1},
            "sublease_rights": {"value": "allowed", "confidence": 0.90, "page": 1},
            "assignment_rights": {"value": "allowed", "confidence": 0.90, "page": 1},
            "tenant_improvement_allowance": {"value": "$150,000", "confidence": 0.90, "page": 1},
            "buildout_period_days": {"value": "120", "confidence": 0.90, "page": 1},
            "hvac_responsibility": {"value": "shared", "confidence": 0.85, "page": 1},
            "roof_responsibility": {"value": "landlord", "confidence": 0.90, "page": 1},
            "tenant_insurance_required": {"value": "true", "confidence": 0.90, "page": 1},
            "insurance_minimum_amount": {"value": "$2,000,000", "confidence": 0.90, "page": 1},
            "ada_compliance": {"value": "true", "confidence": 0.90, "page": 1},
            "default_events": {"value": "Non-payment, breach of use", "confidence": 0.85, "page": 1},
            "governing_law": {"value": "State of Georgia", "confidence": 0.90, "page": 1},
            "attorney_fees_clause": {"value": "true", "confidence": 0.85, "page": 1},
            "confidentiality_clause": {"value": "true", "confidence": 0.85, "page": 1},
            "force_majeure": {"value": "true", "confidence": 0.85, "page": 1},
            "signage_rights": {"value": "Building directory and suite signage", "confidence": 0.85, "page": 1},
            "operating_hours": {"value": "24/7 access", "confidence": 0.85, "page": 1},
            "broker_name": {"value": "Commercial Realty Group", "confidence": 0.85, "page": 1},
            "broker_commission": {"value": "$75,000", "confidence": 0.85, "page": 1},
            "cap_rate": {"value": "5.5", "confidence": 0.85, "page": 1},
            "net_operating_income": {"value": "$600,000", "confidence": 0.85, "page": 1},
            "gross_rent_multiplier": {"value": "12.5", "confidence": 0.85, "page": 1},
            "expense_ratio": {"value": "35", "confidence": 0.85, "page": 1},
            "year_built": {"value": "2010", "confidence": 0.90, "page": 1},
            "renovation_year": {"value": "2020", "confidence": 0.90, "page": 1},
            "flood_zone": {"value": "Zone X", "confidence": 0.90, "page": 1},
        }

        mock_openai_client.chat.completions.create = AsyncMock(
            return_value=self._create_mock_llm_response(mock_fields)
        )

        result = await extractor.extract_fields(lease_text, "cre", "lease")

        assert isinstance(result, ExtractionResult)
        assert len(result.fields) > 50  # Should extract many fields from complex lease
        assert result.overall_confidence > 0.0
        # Verify key fields are extracted
        assert "cap_rate" in result.fields
        assert "net_operating_income" in result.fields
        assert "year_built" in result.fields

    @pytest.mark.asyncio
    async def test_minimal_lease_missing_fields(self, extractor, mock_openai_client) -> None:
        """Test extraction from minimal lease with many missing optional fields."""
        lease_text = """
        LEASE AGREEMENT

        Tenant: Small Business LLC
        Landlord: Property Owner Inc.
        Address: 50 Main St, Boston, MA 02101

        Start: 01/01/2024
        End: 12/31/2024
        Rent: $2,000/month
        """

        mock_fields = {
            "tenant_name": {"value": "Small Business LLC", "confidence": 0.90, "page": 1},
            "landlord_name": {"value": "Property Owner Inc.", "confidence": 0.90, "page": 1},
            "property_address": {"value": "50 Main St, Boston, MA 02101", "confidence": 0.85, "page": 1},
            "lease_start_date": {"value": "2024-01-01", "confidence": 0.90, "page": 1},
            "lease_end_date": {"value": "2024-12-31", "confidence": 0.90, "page": 1},
            "base_rent": {"value": "$2,000", "confidence": 0.90, "page": 1},
            "rent_frequency": {"value": "monthly", "confidence": 0.85, "page": 1},
        }

        mock_openai_client.chat.completions.create = AsyncMock(
            return_value=self._create_mock_llm_response(mock_fields)
        )

        result = await extractor.extract_fields(lease_text, "cre", "lease")

        assert isinstance(result, ExtractionResult)
        # Should extract only required and available fields
        assert len(result.fields) >= 7
        assert "tenant_name" in result.fields
        assert "base_rent" in result.fields

    @pytest.mark.asyncio
    async def test_lease_with_abbreviations(self, extractor, mock_openai_client) -> None:
        """Test extraction handling abbreviations and industry jargon."""
        lease_text = """
        LEASE

        T: Tech Co LLC
        L: Landlord Corp
        Prem: 100 Tech Way, Ste 200, Austin, TX 78701

        Term: 3/1/24 - 2/28/27
        Rent: $10K/mo
        SF: 3,000 RSF
        Deposit: $10K
        TI: $30K
        NNN lease
        """

        mock_fields = {
            "tenant_name": {"value": "Tech Co LLC", "confidence": 0.85, "page": 1},
            "landlord_name": {"value": "Landlord Corp", "confidence": 0.85, "page": 1},
            "property_address": {"value": "100 Tech Way, Ste 200, Austin, TX 78701", "confidence": 0.80, "page": 1},
            "lease_start_date": {"value": "2024-03-01", "confidence": 0.85, "page": 1},
            "lease_end_date": {"value": "2027-02-28", "confidence": 0.85, "page": 1},
            "base_rent": {"value": "$10,000", "confidence": 0.85, "page": 1},
            "square_footage": {"value": "3000", "confidence": 0.85, "page": 1},
            "security_deposit": {"value": "$10,000", "confidence": 0.85, "page": 1},
            "tenant_improvement_allowance": {"value": "$30,000", "confidence": 0.85, "page": 1},
            "lease_type": {"value": "nnn", "confidence": 0.90, "page": 1},
        }

        mock_openai_client.chat.completions.create = AsyncMock(
            return_value=self._create_mock_llm_response(mock_fields)
        )

        result = await extractor.extract_fields(lease_text, "cre", "lease")

        assert isinstance(result, ExtractionResult)
        # Should handle abbreviations
        assert "tenant_name" in result.fields
        assert result.fields["lease_type"].value == "nnn"

    @pytest.mark.asyncio
    async def test_multi_family_lease(self, extractor, mock_openai_client) -> None:
        """Test extraction from multi-family property lease."""
        lease_text = """
        APARTMENT LEASE AGREEMENT

        Tenant: John and Jane Doe
        Landlord: Residential Properties LLC

        Property: 500 Apartment Complex, Unit 205, Denver, CO 80202

        Term: October 1, 2024 to September 30, 2025

        RENT:
        Monthly Rent: $2,500
        Average Rent Per Unit: $2,500
        Occupancy Rate: 95%

        UNIT DETAILS:
        Unit Count: 200 units
        Unit Mix: 1BR/1BA, 2BR/2BA, 3BR/2BA
        Concessions: 1 month free rent
        Pet Policy: Dogs and cats allowed, $50/month pet rent
        Amenities: Pool, gym, clubhouse, parking garage
        Lease Term Options: 6, 12, 18, 24 months
        Rent Control: No
        Parking Ratio: 1.2 spaces per unit
        """

        mock_fields = {
            "tenant_name": {"value": "John and Jane Doe", "confidence": 0.90, "page": 1},
            "landlord_name": {"value": "Residential Properties LLC", "confidence": 0.90, "page": 1},
            "property_address": {"value": "500 Apartment Complex, Unit 205, Denver, CO 80202", "confidence": 0.85, "page": 1},
            "lease_start_date": {"value": "2024-10-01", "confidence": 0.90, "page": 1},
            "lease_end_date": {"value": "2025-09-30", "confidence": 0.90, "page": 1},
            "base_rent": {"value": "$2,500", "confidence": 0.90, "page": 1},
            "average_rent_per_unit": {"value": "$2,500", "confidence": 0.90, "page": 1},
            "occupancy_rate": {"value": "95", "confidence": 0.90, "page": 1},
            "unit_count": {"value": "200", "confidence": 0.90, "page": 1},
            "unit_mix": {"value": "1BR/1BA, 2BR/2BA, 3BR/2BA", "confidence": 0.85, "page": 1},
            "concessions": {"value": "1 month free rent", "confidence": 0.85, "page": 1},
            "pet_policy": {"value": "Dogs and cats allowed, $50/month", "confidence": 0.85, "page": 1},
            "amenities": {"value": "Pool, gym, clubhouse, parking garage", "confidence": 0.85, "page": 1},
            "lease_term_options": {"value": "6, 12, 18, 24 months", "confidence": 0.85, "page": 1},
            "rent_control": {"value": "false", "confidence": 0.85, "page": 1},
            "parking_ratio": {"value": "1.2", "confidence": 0.90, "page": 1},
        }

        mock_openai_client.chat.completions.create = AsyncMock(
            return_value=self._create_mock_llm_response(mock_fields)
        )

        result = await extractor.extract_fields(lease_text, "cre", "lease")

        assert isinstance(result, ExtractionResult)
        assert "unit_count" in result.fields
        assert "occupancy_rate" in result.fields
        assert "amenities" in result.fields
