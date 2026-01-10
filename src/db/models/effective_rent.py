"""Pydantic models for effective rent calculations."""
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


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
    document_type: str | None = Field(None, description="Document type (lease, rent_roll, etc.)")
    extraction_id: UUID = Field(..., description="Extraction UUID")

    rent_components: RentComponents = Field(..., description="Breakdown of rent components")

    effective_monthly_rent: float = Field(..., ge=0.0, description="Total effective monthly rent")
    effective_annual_rent: float = Field(..., ge=0.0, description="Total effective annual rent (monthly × 12)")

    confidence: float | None = Field(None, ge=0.0, le=1.0, description="Average extraction confidence")
    extracted_at: datetime | None = Field(None, description="When extraction completed")


class EffectiveRentListResponse(BaseModel):
    """Response listing tenants by effective rent."""
    tenants: list[TenantEffectiveRent] = Field(
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
    highest_effective_rent: TenantEffectiveRent | None = Field(
        None, description="Tenant with highest effective rent"
    )
    lowest_effective_rent: TenantEffectiveRent | None = Field(
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


class PropertyRentSummary(BaseModel):
    """Rent summary for a single property."""
    property_name: str = Field(..., description="Property/building name")
    property_address: str | None = Field(None, description="Property address")
    tenant_count: int = Field(..., ge=0, description="Number of tenants in property")
    total_monthly_rent: float = Field(..., ge=0.0, description="Total monthly rent for property")
    total_annual_rent: float = Field(..., ge=0.0, description="Total annual rent for property")
    average_rent_per_tenant: float = Field(..., ge=0.0, description="Average rent per tenant")
    tenants: list[TenantEffectiveRent] = Field(
        default_factory=list, description="Tenants in this property"
    )


class RentByPropertyResponse(BaseModel):
    """Response for rent grouped by property."""
    properties: list[PropertyRentSummary] = Field(
        default_factory=list, description="Properties with rent summaries"
    )
    total_properties: int = Field(..., ge=0, description="Total number of properties")
    total_portfolio_monthly: float = Field(..., ge=0.0, description="Total portfolio monthly rent")


class TenantConcentration(BaseModel):
    """Tenant rent concentration analysis."""
    tenant_name: str = Field(..., description="Tenant name")
    effective_monthly_rent: float = Field(..., ge=0.0, description="Effective monthly rent")
    effective_annual_rent: float = Field(..., ge=0.0, description="Effective annual rent")
    percentage_of_portfolio: float = Field(
        ..., ge=0.0, le=100.0, description="Percentage of total portfolio rent"
    )
    cumulative_percentage: float = Field(
        ..., ge=0.0, le=100.0, description="Cumulative percentage (for top-N analysis)"
    )
    document_name: str = Field(..., description="Source document")


class RentConcentrationResponse(BaseModel):
    """Response for rent concentration analysis."""
    top_tenants: list[TenantConcentration] = Field(
        default_factory=list, description="Top tenants by rent concentration"
    )
    top_10_concentration: float = Field(
        ..., ge=0.0, le=100.0, description="% of rent from top 10 tenants"
    )
    total_portfolio_monthly: float = Field(..., ge=0.0, description="Total portfolio monthly rent")


class RentPerSFAnalysis(BaseModel):
    """Rent per square foot analysis for a tenant."""
    tenant_name: str = Field(..., description="Tenant name")
    effective_monthly_rent: float = Field(..., ge=0.0, description="Effective monthly rent")
    square_footage: float = Field(..., gt=0.0, description="Square footage")
    rent_per_sf_monthly: float = Field(..., ge=0.0, description="Monthly rent per SF")
    rent_per_sf_annual: float = Field(..., ge=0.0, description="Annual rent per SF")
    property_name: str | None = Field(None, description="Property name")
    document_name: str = Field(..., description="Source document")


class RentPerSFResponse(BaseModel):
    """Response for rent per SF analysis."""
    tenants: list[RentPerSFAnalysis] = Field(
        default_factory=list, description="Tenants with rent per SF data"
    )
    average_rent_per_sf_monthly: float = Field(
        ..., ge=0.0, description="Portfolio average monthly rent per SF"
    )
    average_rent_per_sf_annual: float = Field(
        ..., ge=0.0, description="Portfolio average annual rent per SF"
    )
    total_square_footage: float = Field(..., ge=0.0, description="Total portfolio square footage")


class PortfolioMetrics(BaseModel):
    """Comprehensive portfolio health metrics."""
    # Tenant metrics
    total_tenants: int = Field(..., ge=0, description="Total tenants")
    total_properties: int = Field(..., ge=0, description="Total properties")

    # Rent metrics
    total_monthly_rent: float = Field(..., ge=0.0, description="Total monthly rent")
    total_annual_rent: float = Field(..., ge=0.0, description="Total annual rent")
    average_rent_per_tenant: float = Field(..., ge=0.0, description="Average rent per tenant")

    # Space metrics
    total_square_footage: float = Field(..., ge=0.0, description="Total leased square footage")
    average_sf_per_tenant: float = Field(..., ge=0.0, description="Average SF per tenant")
    average_rent_per_sf_annual: float = Field(..., ge=0.0, description="Average annual rent per SF")

    # Concentration metrics
    top_tenant_concentration: float = Field(
        ..., ge=0.0, le=100.0, description="% of rent from top tenant"
    )
    top_5_concentration: float = Field(
        ..., ge=0.0, le=100.0, description="% of rent from top 5 tenants"
    )
    top_10_concentration: float = Field(
        ..., ge=0.0, le=100.0, description="% of rent from top 10 tenants"
    )

    # Quality metrics
    average_extraction_confidence: float = Field(
        ..., ge=0.0, le=1.0, description="Average confidence of extractions"
    )
