"""
Effective Rent Calculation Service - Data Plane

Calculates effective rent (base rent + additional fees) from extraction data.
Provides portfolio-level analytics on tenant rent obligations.
"""

import logging
import re
from typing import List, Optional, Dict, Any
from uuid import UUID
from supabase import Client

from src.db.models.effective_rent import (
    TenantEffectiveRent,
    RentComponents,
    EffectiveRentListResponse,
    EffectiveRentSummary,
    PropertyRentSummary,
    RentByPropertyResponse,
    TenantConcentration,
    RentConcentrationResponse,
    RentPerSFAnalysis,
    RentPerSFResponse,
    PortfolioMetrics,
)

logger = logging.getLogger(__name__)


class EffectiveRentService:
    """
    Service for calculating effective rent from extraction data.

    Effective Rent = Base Rent + CAM + Tax + Insurance + Parking + Storage

    Enforces tenant isolation via RLS.
    """

    def __init__(self, supabase_client: Client):
        """
        Initialize effective rent service.

        Args:
            supabase_client: Supabase client with user JWT (for tenant isolation)
        """
        self.client = supabase_client

    def _extract_numeric(self, value_str: Optional[str]) -> float:
        """
        Extract numeric value from currency string.

        Args:
            value_str: String like "$5,000.00" or "5000"

        Returns:
            Numeric value as float
        """
        if not value_str:
            return 0.0

        # Remove currency symbols, commas, spaces
        cleaned = re.sub(r'[^\d.]', '', str(value_str))
        try:
            return float(cleaned) if cleaned else 0.0
        except ValueError:
            return 0.0

    def _get_field_value(self, fields: List[Dict[str, Any]], field_name: str) -> float:
        """
        Get numeric value for a specific field from extraction fields.

        Args:
            fields: List of extraction field dictionaries
            field_name: Field name to search for

        Returns:
            Numeric value as float
        """
        for field in fields:
            if field.get('field_name') == field_name:
                value_str = field.get('field_value', {}).get('value', '')
                return self._extract_numeric(value_str)
        return 0.0

    def _get_field_confidence(self, fields: List[Dict[str, Any]], field_name: str) -> Optional[float]:
        """Get confidence score for a specific field."""
        for field in fields:
            if field.get('field_name') == field_name:
                return field.get('confidence')
        return None

    async def calculate_all_effective_rents(
        self,
        limit: Optional[int] = None,
        sort_desc: bool = True,
    ) -> EffectiveRentListResponse:
        """
        Calculate effective rent for all tenants in current tenant's portfolio.

        Args:
            limit: Optional limit on number of results
            sort_desc: Sort by effective rent descending (highest first)

        Returns:
            EffectiveRentListResponse with all tenants and totals
        """
        logger.info("Calculating effective rents for all tenants")

        # Get all current extractions (RLS enforces tenant isolation)
        extractions_result = self.client.table('extractions').select(
            'id, document_id, document_type, extracted_at'
        ).eq('is_current', True).execute()

        if not extractions_result.data:
            logger.info("No current extractions found")
            return EffectiveRentListResponse(
                tenants=[],
                total_count=0,
                total_effective_monthly_rent=0.0,
                total_effective_annual_rent=0.0,
            )

        tenant_rents: List[TenantEffectiveRent] = []

        for extraction in extractions_result.data:
            extraction_id = extraction['id']
            doc_id = extraction['document_id']

            # Get all fields for this extraction
            fields_result = self.client.table('extraction_fields').select(
                'field_name, field_value, confidence'
            ).eq('extraction_id', extraction_id).execute()

            if not fields_result.data:
                continue

            fields = fields_result.data

            # Get tenant name
            tenant_name = None
            for field in fields:
                if field.get('field_name') == 'tenant_name':
                    tenant_name = field.get('field_value', {}).get('value')
                    break

            if not tenant_name:
                continue

            # Extract rent components
            base_rent = self._get_field_value(fields, 'base_rent') or self._get_field_value(fields, 'monthly_rent')
            cam_charges = self._get_field_value(fields, 'cam_charges')
            tax_reimbursement = self._get_field_value(fields, 'tax_reimbursement')
            insurance_reimbursement = self._get_field_value(fields, 'insurance_reimbursement')
            parking_fee = (
                self._get_field_value(fields, 'parking_fee') or
                self._get_field_value(fields, 'parking_rent')
            )
            storage_rent = self._get_field_value(fields, 'storage_rent')

            # Calculate effective rent
            effective_monthly = (
                base_rent +
                cam_charges +
                tax_reimbursement +
                insurance_reimbursement +
                parking_fee +
                storage_rent
            )

            # Skip if no rent data
            if effective_monthly == 0.0:
                continue

            # Get document details
            doc_result = self.client.table('documents').select(
                'original_filename'
            ).eq('id', doc_id).single().execute()

            doc_name = doc_result.data['original_filename'] if doc_result.data else 'Unknown'

            # Calculate average confidence
            confidences = [
                c for c in [
                    self._get_field_confidence(fields, 'base_rent'),
                    self._get_field_confidence(fields, 'tenant_name'),
                ] if c is not None
            ]
            avg_confidence = sum(confidences) / len(confidences) if confidences else None

            # Build response object
            tenant_rent = TenantEffectiveRent(
                tenant_name=tenant_name,
                document_id=UUID(doc_id),
                document_name=doc_name,
                document_type=extraction['document_type'],
                extraction_id=UUID(extraction_id),
                rent_components=RentComponents(
                    base_rent=base_rent,
                    cam_charges=cam_charges,
                    tax_reimbursement=tax_reimbursement,
                    insurance_reimbursement=insurance_reimbursement,
                    parking_fee=parking_fee,
                    storage_rent=storage_rent,
                ),
                effective_monthly_rent=effective_monthly,
                effective_annual_rent=effective_monthly * 12,
                confidence=avg_confidence,
                extracted_at=extraction.get('extracted_at'),
            )

            tenant_rents.append(tenant_rent)

        # Sort by effective rent
        tenant_rents.sort(
            key=lambda t: t.effective_monthly_rent,
            reverse=sort_desc,
        )

        # Apply limit if specified
        if limit:
            tenant_rents = tenant_rents[:limit]

        # Calculate totals
        total_monthly = sum(t.effective_monthly_rent for t in tenant_rents)
        total_annual = sum(t.effective_annual_rent for t in tenant_rents)

        logger.info(
            "Calculated effective rents",
            extra={
                "tenant_count": len(tenant_rents),
                "total_monthly": total_monthly,
                "total_annual": total_annual,
            },
        )

        return EffectiveRentListResponse(
            tenants=tenant_rents,
            total_count=len(tenant_rents),
            total_effective_monthly_rent=total_monthly,
            total_effective_annual_rent=total_annual,
        )

    async def get_highest_effective_rent(self) -> Optional[TenantEffectiveRent]:
        """
        Get tenant with highest effective rent.

        Returns:
            TenantEffectiveRent for highest rent tenant, or None if no data
        """
        result = await self.calculate_all_effective_rents(limit=1, sort_desc=True)
        return result.tenants[0] if result.tenants else None

    async def get_summary(self) -> EffectiveRentSummary:
        """
        Get portfolio summary statistics for effective rent.

        Returns:
            EffectiveRentSummary with portfolio-level metrics
        """
        logger.info("Generating effective rent summary")

        all_rents = await self.calculate_all_effective_rents(limit=None, sort_desc=True)

        if not all_rents.tenants:
            return EffectiveRentSummary(
                total_tenants=0,
                highest_effective_rent=None,
                lowest_effective_rent=None,
                average_effective_monthly_rent=0.0,
                total_portfolio_monthly_rent=0.0,
                total_portfolio_annual_rent=0.0,
            )

        highest = all_rents.tenants[0]
        lowest = all_rents.tenants[-1]
        average_monthly = (
            all_rents.total_effective_monthly_rent / len(all_rents.tenants)
            if all_rents.tenants else 0.0
        )

        return EffectiveRentSummary(
            total_tenants=len(all_rents.tenants),
            highest_effective_rent=highest,
            lowest_effective_rent=lowest,
            average_effective_monthly_rent=average_monthly,
            total_portfolio_monthly_rent=all_rents.total_effective_monthly_rent,
            total_portfolio_annual_rent=all_rents.total_effective_annual_rent,
        )

    async def calculate_rent_by_property(self) -> RentByPropertyResponse:
        """
        Calculate rent grouped by property.

        Returns:
            RentByPropertyResponse with rent totals per property
        """
        logger.info("Calculating rent by property")

        # Get all tenants with rent data
        all_rents = await self.calculate_all_effective_rents(limit=None, sort_desc=False)

        if not all_rents.tenants:
            return RentByPropertyResponse(
                properties=[],
                total_properties=0,
                total_portfolio_monthly=0.0,
            )

        # Group tenants by property
        properties_map: Dict[str, List[TenantEffectiveRent]] = {}
        property_addresses: Dict[str, Optional[str]] = {}

        for tenant in all_rents.tenants:
            # Get property name from extraction fields
            fields_result = self.client.table('extraction_fields').select(
                'field_name, field_value'
            ).eq('extraction_id', str(tenant.extraction_id)).execute()

            property_name = "Unknown Property"
            property_address = None

            if fields_result.data:
                for field in fields_result.data:
                    if field.get('field_name') == 'property_name':
                        property_name = field.get('field_value', {}).get('value', 'Unknown Property')
                    elif field.get('field_name') == 'property_address':
                        property_address = field.get('field_value', {}).get('value')

            if property_name not in properties_map:
                properties_map[property_name] = []
                property_addresses[property_name] = property_address

            properties_map[property_name].append(tenant)

        # Build property summaries
        property_summaries: List[PropertyRentSummary] = []

        for prop_name, tenants in properties_map.items():
            total_monthly = sum(t.effective_monthly_rent for t in tenants)
            total_annual = sum(t.effective_annual_rent for t in tenants)
            avg_per_tenant = total_monthly / len(tenants) if tenants else 0.0

            property_summaries.append(PropertyRentSummary(
                property_name=prop_name,
                property_address=property_addresses.get(prop_name),
                tenant_count=len(tenants),
                total_monthly_rent=total_monthly,
                total_annual_rent=total_annual,
                average_rent_per_tenant=avg_per_tenant,
                tenants=tenants,
            ))

        # Sort by total rent descending
        property_summaries.sort(key=lambda p: p.total_monthly_rent, reverse=True)

        logger.info(
            "Calculated rent by property",
            extra={
                "property_count": len(property_summaries),
                "total_monthly": all_rents.total_effective_monthly_rent,
            },
        )

        return RentByPropertyResponse(
            properties=property_summaries,
            total_properties=len(property_summaries),
            total_portfolio_monthly=all_rents.total_effective_monthly_rent,
        )

    async def calculate_rent_concentration(self, top_n: int = 20) -> RentConcentrationResponse:
        """
        Calculate rent concentration (top tenants by % of portfolio).

        Args:
            top_n: Number of top tenants to return

        Returns:
            RentConcentrationResponse with concentration analysis
        """
        logger.info("Calculating rent concentration", extra={"top_n": top_n})

        # Get all tenants sorted by rent (highest first)
        all_rents = await self.calculate_all_effective_rents(limit=None, sort_desc=True)

        if not all_rents.tenants:
            return RentConcentrationResponse(
                top_tenants=[],
                top_10_concentration=0.0,
                total_portfolio_monthly=0.0,
            )

        total_portfolio = all_rents.total_effective_monthly_rent

        # Calculate concentration for each tenant
        concentrations: List[TenantConcentration] = []
        cumulative_pct = 0.0

        for tenant in all_rents.tenants[:top_n]:
            pct_of_portfolio = (tenant.effective_monthly_rent / total_portfolio * 100) if total_portfolio > 0 else 0.0
            cumulative_pct += pct_of_portfolio

            concentrations.append(TenantConcentration(
                tenant_name=tenant.tenant_name,
                effective_monthly_rent=tenant.effective_monthly_rent,
                effective_annual_rent=tenant.effective_annual_rent,
                percentage_of_portfolio=pct_of_portfolio,
                cumulative_percentage=cumulative_pct,
                document_name=tenant.document_name,
            ))

        # Calculate top 10 concentration
        top_10_monthly = sum(t.effective_monthly_rent for t in all_rents.tenants[:10])
        top_10_pct = (top_10_monthly / total_portfolio * 100) if total_portfolio > 0 else 0.0

        logger.info(
            "Calculated rent concentration",
            extra={
                "top_n": len(concentrations),
                "top_10_concentration": top_10_pct,
            },
        )

        return RentConcentrationResponse(
            top_tenants=concentrations,
            top_10_concentration=top_10_pct,
            total_portfolio_monthly=total_portfolio,
        )

    async def calculate_rent_per_sf(self) -> RentPerSFResponse:
        """
        Calculate rent per square foot for all tenants with SF data.

        Returns:
            RentPerSFResponse with rent per SF analysis
        """
        logger.info("Calculating rent per square foot")

        # Get all tenants with rent data
        all_rents = await self.calculate_all_effective_rents(limit=None, sort_desc=False)

        if not all_rents.tenants:
            return RentPerSFResponse(
                tenants=[],
                average_rent_per_sf_monthly=0.0,
                average_rent_per_sf_annual=0.0,
                total_square_footage=0.0,
            )

        # Build rent per SF analysis for tenants with SF data
        analyses: List[RentPerSFAnalysis] = []
        total_sf = 0.0
        total_monthly_rent = 0.0

        for tenant in all_rents.tenants:
            # Get square footage from extraction fields
            fields_result = self.client.table('extraction_fields').select(
                'field_name, field_value'
            ).eq('extraction_id', str(tenant.extraction_id)).execute()

            square_footage = None
            property_name = None

            if fields_result.data:
                for field in fields_result.data:
                    field_name = field.get('field_name')
                    if field_name in ('square_footage', 'rentable_square_feet', 'usable_square_feet'):
                        sf_value = field.get('field_value', {}).get('value', '')
                        square_footage = self._extract_numeric(sf_value)
                        if square_footage > 0:
                            break
                    elif field_name == 'property_name':
                        property_name = field.get('field_value', {}).get('value')

            # Skip tenants without SF data
            if not square_footage or square_footage == 0:
                continue

            rent_per_sf_monthly = tenant.effective_monthly_rent / square_footage
            rent_per_sf_annual = tenant.effective_annual_rent / square_footage

            analyses.append(RentPerSFAnalysis(
                tenant_name=tenant.tenant_name,
                effective_monthly_rent=tenant.effective_monthly_rent,
                square_footage=square_footage,
                rent_per_sf_monthly=rent_per_sf_monthly,
                rent_per_sf_annual=rent_per_sf_annual,
                property_name=property_name,
                document_name=tenant.document_name,
            ))

            total_sf += square_footage
            total_monthly_rent += tenant.effective_monthly_rent

        # Calculate averages
        avg_monthly_per_sf = (total_monthly_rent / total_sf) if total_sf > 0 else 0.0
        avg_annual_per_sf = avg_monthly_per_sf * 12

        logger.info(
            "Calculated rent per SF",
            extra={
                "tenant_count": len(analyses),
                "total_sf": total_sf,
                "avg_annual_per_sf": avg_annual_per_sf,
            },
        )

        return RentPerSFResponse(
            tenants=analyses,
            average_rent_per_sf_monthly=avg_monthly_per_sf,
            average_rent_per_sf_annual=avg_annual_per_sf,
            total_square_footage=total_sf,
        )

    async def calculate_portfolio_metrics(self) -> PortfolioMetrics:
        """
        Calculate comprehensive portfolio health metrics.

        Returns:
            PortfolioMetrics with portfolio-level analytics
        """
        logger.info("Calculating portfolio metrics")

        # Get all tenant rent data
        all_rents = await self.calculate_all_effective_rents(limit=None, sort_desc=True)

        if not all_rents.tenants:
            return PortfolioMetrics(
                total_tenants=0,
                total_properties=0,
                total_monthly_rent=0.0,
                total_annual_rent=0.0,
                average_rent_per_tenant=0.0,
                total_square_footage=0.0,
                average_sf_per_tenant=0.0,
                average_rent_per_sf_annual=0.0,
                top_tenant_concentration=0.0,
                top_5_concentration=0.0,
                top_10_concentration=0.0,
                average_extraction_confidence=0.0,
            )

        # Get property count (unique properties)
        properties_set = set()
        total_sf = 0.0
        confidences: List[float] = []

        for tenant in all_rents.tenants:
            # Get property name and SF
            fields_result = self.client.table('extraction_fields').select(
                'field_name, field_value, confidence'
            ).eq('extraction_id', str(tenant.extraction_id)).execute()

            if fields_result.data:
                for field in fields_result.data:
                    field_name = field.get('field_name')

                    if field_name == 'property_name':
                        prop_name = field.get('field_value', {}).get('value')
                        if prop_name:
                            properties_set.add(prop_name)

                    elif field_name in ('square_footage', 'rentable_square_feet'):
                        sf_value = field.get('field_value', {}).get('value', '')
                        sf = self._extract_numeric(sf_value)
                        if sf > 0:
                            total_sf += sf

                    # Collect confidences
                    conf = field.get('confidence')
                    if conf is not None:
                        confidences.append(conf)

        # Calculate concentration percentages
        total_monthly = all_rents.total_effective_monthly_rent

        top_1_monthly = all_rents.tenants[0].effective_monthly_rent if all_rents.tenants else 0.0
        top_1_pct = (top_1_monthly / total_monthly * 100) if total_monthly > 0 else 0.0

        top_5_monthly = sum(t.effective_monthly_rent for t in all_rents.tenants[:5])
        top_5_pct = (top_5_monthly / total_monthly * 100) if total_monthly > 0 else 0.0

        top_10_monthly = sum(t.effective_monthly_rent for t in all_rents.tenants[:10])
        top_10_pct = (top_10_monthly / total_monthly * 100) if total_monthly > 0 else 0.0

        # Calculate averages
        avg_rent = total_monthly / len(all_rents.tenants) if all_rents.tenants else 0.0
        avg_sf = total_sf / len(all_rents.tenants) if all_rents.tenants else 0.0
        avg_rent_per_sf_annual = ((total_monthly * 12) / total_sf) if total_sf > 0 else 0.0
        avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0

        metrics = PortfolioMetrics(
            total_tenants=len(all_rents.tenants),
            total_properties=len(properties_set),
            total_monthly_rent=total_monthly,
            total_annual_rent=all_rents.total_effective_annual_rent,
            average_rent_per_tenant=avg_rent,
            total_square_footage=total_sf,
            average_sf_per_tenant=avg_sf,
            average_rent_per_sf_annual=avg_rent_per_sf_annual,
            top_tenant_concentration=top_1_pct,
            top_5_concentration=top_5_pct,
            top_10_concentration=top_10_pct,
            average_extraction_confidence=avg_confidence,
        )

        logger.info(
            "Calculated portfolio metrics",
            extra={
                "total_tenants": metrics.total_tenants,
                "total_properties": metrics.total_properties,
                "total_monthly": metrics.total_monthly_rent,
            },
        )

        return metrics
