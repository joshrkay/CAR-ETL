"""Pydantic models for effective rent calculations."""
from pydantic import BaseModel, Field
from typing import Optional, List
from uuid import UUID
from datetime import datetime


class RentComponents(BaseModel):
    """Breakdown of rent components."""
    base_rent: float = Field(default=0.0, description="Base monthly rent")
    cam_charges: float = Field(default=0.0, description="Common area maintenance charges")
    tax_reimbursement: float = Field(default=0.0, description="Property tax reimbursement")
    insurance_reimbursement: float = Field(default=0.0, description="Insurance reimbursement")
    parking_fee: float = Field(default=0.0, description="Parking charges")
    storage_rent: float = Field(default=0.0, description="Storage rental fees")


class TenantEffectiveRent(BaseModel):
    """Effective rent calculation for a single tenant."""
    tenant_name: str = Field(..., description="Tenant name")
    document_id: UUID = Field(..., description="Source document UUID")
    document_name: str = Field(..., description="Source document filename")
    document_type: Optional[str] = Field(None, description="Document type (lease, rent_roll, etc.)")
    extraction_id: UUID = Field(..., description="Extraction UUID")

    rent_components: RentComponents = Field(..., description="Breakdown of rent components")

    effective_monthly_rent: float = Field(..., ge=0.0, description="Total effective monthly rent")
    effective_annual_rent: float = Field(..., ge=0.0, description="Total effective annual rent (monthly × 12)")

    confidence: Optional[float] = Field(None, ge=0.0, le=1.0, description="Average extraction confidence")
    extracted_at: Optional[datetime] = Field(None, description="When extraction completed")


class EffectiveRentListResponse(BaseModel):
    """Response listing tenants by effective rent."""
    tenants: List[TenantEffectiveRent] = Field(
        default_factory=list, description="Tenants sorted by effective rent"
    )
    total_count: int = Field(..., ge=0, description="Total number of tenants with rent data")
    total_effective_monthly_rent: float = Field(
        ..., ge=0.0, description="Sum of all effective monthly rents"
    )
    total_effective_annual_rent: float = Field(
        ..., ge=0.0, description="Sum of all effective annual rents"
    )


class EffectiveRentSummary(BaseModel):
    """Summary statistics for effective rent across portfolio."""
    total_tenants: int = Field(..., ge=0, description="Total tenants with rent data")
    highest_effective_rent: Optional[TenantEffectiveRent] = Field(
        None, description="Tenant with highest effective rent"
    )
    lowest_effective_rent: Optional[TenantEffectiveRent] = Field(
        None, description="Tenant with lowest effective rent"
    )
    average_effective_monthly_rent: float = Field(
        ..., ge=0.0, description="Average effective monthly rent across all tenants"
    )
    total_portfolio_monthly_rent: float = Field(
        ..., ge=0.0, description="Total portfolio monthly rent"
    )
    total_portfolio_annual_rent: float = Field(
        ..., ge=0.0, description="Total portfolio annual rent"
    )
