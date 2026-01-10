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
