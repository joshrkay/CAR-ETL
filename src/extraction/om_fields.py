"""
Offering Memorandum Field Definitions - Understanding Plane

Defines OM-specific fields, types, weights, and metadata for extraction.
"""

from enum import Enum
from typing import Dict, List, Optional, Any

from pydantic import BaseModel, Field


class OMFieldType(str, Enum):
    STRING = "string"
    ADDRESS = "address"
    DATE = "date"
    CURRENCY = "currency"
    INTEGER = "integer"
    FLOAT = "float"
    BOOLEAN = "boolean"
    ENUM = "enum"
    PERCENT = "percent"
    LIST_STRING = "list[string]"


class OMFieldDefinition(BaseModel):
    """Definition for a single OM field."""

    type: OMFieldType = Field(..., description="Field data type")
    required: bool = Field(default=False, description="Whether field is required")
    weight: float = Field(..., ge=0.0, description="Weight for confidence and document scoring")
    values: Optional[List[str]] = Field(default=None, description="Allowed enum values")
    applies_to: Optional[List[str]] = Field(default=None, description="Optional property type applicability")
    skepticism: float = Field(default=1.0, description="Marketing skepticism factor (<=1.0)")
    description: Optional[str] = Field(default=None, description="Human readable description")
    validation: Optional[Dict[str, Any]] = Field(default=None, description="Optional validation constraints")
    max_items: Optional[int] = Field(default=None, description="Max items for list fields")


def get_om_fields() -> Dict[str, OMFieldDefinition]:
    """Return OM field configuration."""

    return {
        # PROPERTY IDENTIFICATION
        "property_name": OMFieldDefinition(
            type=OMFieldType.STRING, required=True, weight=1.0, description="Marketing name of property"
        ),
        "property_address": OMFieldDefinition(
            type=OMFieldType.ADDRESS, required=True, weight=1.2, description="Full street address"
        ),
        "city": OMFieldDefinition(type=OMFieldType.STRING, required=True, weight=1.0),
        "state": OMFieldDefinition(type=OMFieldType.STRING, required=True, weight=1.0),
        "zip_code": OMFieldDefinition(type=OMFieldType.STRING, required=True, weight=0.8),
        "county": OMFieldDefinition(type=OMFieldType.STRING, required=False, weight=0.6),
        "submarket": OMFieldDefinition(
            type=OMFieldType.STRING, required=False, weight=0.8, description="Broker-defined submarket area"
        ),
        # PROPERTY CHARACTERISTICS
        "property_type": OMFieldDefinition(
            type=OMFieldType.ENUM,
            values=[
                "office",
                "retail",
                "multifamily",
                "industrial",
                "hospitality",
                "mixed_use",
                "land",
                "self_storage",
                "medical_office",
                "data_center",
            ],
            required=True,
            weight=1.3,
        ),
        "property_subtype": OMFieldDefinition(
            type=OMFieldType.STRING,
            required=False,
            weight=0.7,
            description="E.g., 'Class A Office', 'Garden-Style Apartments', 'Last-Mile Industrial'",
        ),
        "year_built": OMFieldDefinition(
            type=OMFieldType.INTEGER, required=True, weight=1.1, validation={"min": 1800, "max": 2030}
        ),
        "year_renovated": OMFieldDefinition(type=OMFieldType.INTEGER, required=False, weight=0.8),
        "total_sf": OMFieldDefinition(
            type=OMFieldType.INTEGER, required=True, weight=1.4, description="Total rentable/sellable square footage"
        ),
        "land_area_sf": OMFieldDefinition(
            type=OMFieldType.INTEGER, required=False, weight=0.9, description="Land area in SF (or convert from acres)"
        ),
        "land_area_acres": OMFieldDefinition(type=OMFieldType.FLOAT, required=False, weight=0.9),
        "num_buildings": OMFieldDefinition(type=OMFieldType.INTEGER, required=False, weight=0.7),
        "num_floors": OMFieldDefinition(type=OMFieldType.INTEGER, required=False, weight=0.7),
        "num_units": OMFieldDefinition(
            type=OMFieldType.INTEGER,
            required=True,
            weight=1.3,
            applies_to=["multifamily", "self_storage", "hospitality"],
            description="Number of units/rooms/keys",
        ),
        "parking_spaces": OMFieldDefinition(type=OMFieldType.INTEGER, required=False, weight=0.6),
        "parking_ratio": OMFieldDefinition(
            type=OMFieldType.FLOAT, required=False, weight=0.6, description="Spaces per 1,000 SF"
        ),
        "zoning": OMFieldDefinition(type=OMFieldType.STRING, required=False, weight=0.7),
        "construction_type": OMFieldDefinition(
            type=OMFieldType.STRING,
            required=False,
            weight=0.5,
            description="E.g., 'Steel Frame', 'Wood Frame', 'Concrete Tilt-Up'",
        ),
        # PRICING
        "asking_price": OMFieldDefinition(
            type=OMFieldType.CURRENCY, required=True, weight=1.5, description="Listed asking price (may be 'Call for Offers')"
        ),
        "price_psf": OMFieldDefinition(
            type=OMFieldType.CURRENCY, required=False, weight=1.2, description="Price per square foot"
        ),
        "price_per_unit": OMFieldDefinition(
            type=OMFieldType.CURRENCY, required=False, weight=1.2, applies_to=["multifamily", "self_storage", "hospitality"]
        ),
        "guidance_price_low": OMFieldDefinition(
            type=OMFieldType.CURRENCY, required=False, weight=1.3, description="If range given, low end"
        ),
        "guidance_price_high": OMFieldDefinition(
            type=OMFieldType.CURRENCY, required=False, weight=1.3, description="If range given, high end"
        ),
        # FINANCIAL METRICS - IN PLACE (ACTUAL)
        "noi_in_place": OMFieldDefinition(
            type=OMFieldType.CURRENCY,
            required=True,
            weight=1.5,
            description="Current/Trailing Net Operating Income",
        ),
        "cap_rate_in_place": OMFieldDefinition(
            type=OMFieldType.PERCENT,
            required=True,
            weight=1.5,
            description="Current cap rate based on in-place NOI",
        ),
        "occupancy_current": OMFieldDefinition(
            type=OMFieldType.PERCENT,
            required=True,
            weight=1.4,
            description="Current physical or economic occupancy",
        ),
        "occupancy_type": OMFieldDefinition(
            type=OMFieldType.ENUM, values=["physical", "economic"], required=False, weight=0.8
        ),
        "egr_in_place": OMFieldDefinition(
            type=OMFieldType.CURRENCY, required=False, weight=1.2, description="Effective Gross Revenue - current"
        ),
        "operating_expenses": OMFieldDefinition(type=OMFieldType.CURRENCY, required=False, weight=1.1),
        "expense_ratio": OMFieldDefinition(type=OMFieldType.PERCENT, required=False, weight=0.9),
        # FINANCIAL METRICS - PRO FORMA (PROJECTED)
        "noi_pro_forma": OMFieldDefinition(
            type=OMFieldType.CURRENCY,
            required=False,
            weight=1.3,
            skepticism=0.85,
            description="Projected NOI after stabilization/improvements",
        ),
        "cap_rate_pro_forma": OMFieldDefinition(
            type=OMFieldType.PERCENT, required=False, weight=1.3, skepticism=0.85
        ),
        "occupancy_pro_forma": OMFieldDefinition(
            type=OMFieldType.PERCENT,
            required=False,
            weight=1.1,
            skepticism=0.85,
            description="Stabilized occupancy assumption",
        ),
        "egr_pro_forma": OMFieldDefinition(type=OMFieldType.CURRENCY, required=False, weight=1.1, skepticism=0.85),
        "rent_growth_assumption": OMFieldDefinition(
            type=OMFieldType.PERCENT, required=False, weight=0.8, skepticism=0.80
        ),
        # RENT ROLL SUMMARY
        "avg_rent_psf": OMFieldDefinition(
            type=OMFieldType.CURRENCY,
            required=False,
            weight=1.2,
            description="Average rent per SF (annual or monthly - note which)",
        ),
        "avg_rent_per_unit": OMFieldDefinition(
            type=OMFieldType.CURRENCY, required=False, weight=1.2, applies_to=["multifamily"]
        ),
        "market_rent_psf": OMFieldDefinition(
            type=OMFieldType.CURRENCY, required=False, weight=1.0, skepticism=0.90, description="Broker's claimed market rent"
        ),
        "rent_to_market_ratio": OMFieldDefinition(
            type=OMFieldType.PERCENT, required=False, weight=1.1, description="In-place rent vs market (loss-to-lease indicator)"
        ),
        "walt_years": OMFieldDefinition(
            type=OMFieldType.FLOAT, required=False, weight=1.3, description="Weighted Average Lease Term in years"
        ),
        "largest_tenant": OMFieldDefinition(type=OMFieldType.STRING, required=False, weight=0.9),
        "largest_tenant_sf": OMFieldDefinition(type=OMFieldType.INTEGER, required=False, weight=0.8),
        "largest_tenant_pct": OMFieldDefinition(type=OMFieldType.PERCENT, required=False, weight=0.9),
        "num_tenants": OMFieldDefinition(type=OMFieldType.INTEGER, required=False, weight=0.7),
        # DEBT INFORMATION
        "assumable_debt": OMFieldDefinition(type=OMFieldType.BOOLEAN, required=False, weight=1.2),
        "loan_amount": OMFieldDefinition(type=OMFieldType.CURRENCY, required=False, weight=1.1),
        "loan_rate": OMFieldDefinition(type=OMFieldType.PERCENT, required=False, weight=1.0),
        "loan_maturity_date": OMFieldDefinition(type=OMFieldType.DATE, required=False, weight=1.0),
        "loan_type": OMFieldDefinition(
            type=OMFieldType.STRING,
            required=False,
            weight=0.7,
            description="E.g., 'Agency', 'CMBS', 'Bank', 'Life Co'",
        ),
        "ltv": OMFieldDefinition(type=OMFieldType.PERCENT, required=False, weight=0.9, description="Loan to value ratio"),
        # INVESTMENT NARRATIVE
        "investment_highlights": OMFieldDefinition(
            type=OMFieldType.LIST_STRING,
            required=False,
            weight=0.6,
            max_items=10,
            description="Key selling points (bullet points)",
        ),
        "value_add_opportunities": OMFieldDefinition(
            type=OMFieldType.LIST_STRING,
            required=False,
            weight=0.7,
            skepticism=0.80,
            description="Upside potential claims",
        ),
        # TRANSACTION INFO
        "listing_broker_company": OMFieldDefinition(type=OMFieldType.STRING, required=True, weight=0.8),
        "listing_broker_name": OMFieldDefinition(type=OMFieldType.STRING, required=False, weight=0.6),
        "listing_broker_contact": OMFieldDefinition(type=OMFieldType.STRING, required=False, weight=0.5),
        "offer_deadline": OMFieldDefinition(
            type=OMFieldType.DATE, required=False, weight=1.0, description="Call for offers / best and final date"
        ),
        "sale_type": OMFieldDefinition(
            type=OMFieldType.ENUM,
            values=["fee_simple", "ground_lease", "leasehold", "portfolio", "note_sale"],
            required=False,
            weight=0.9,
        ),
        "marketing_start_date": OMFieldDefinition(type=OMFieldType.DATE, required=False, weight=0.5),
    }


def format_om_field_definitions_for_prompt(field_defs: Dict[str, OMFieldDefinition]) -> str:
    """
    Format OM field definitions for prompt inclusion.
    """
    lines: List[str] = []
    for name, definition in field_defs.items():
        line = f"- {name}: type={definition.type.value}, required={definition.required}, weight={definition.weight}"
        if definition.values:
            line += f", values={definition.values}"
        if definition.skepticism != 1.0:
            line += f", skepticism={definition.skepticism}"
        if definition.description:
            line += f" ({definition.description})"
        lines.append(line)
    return "\n".join(lines)


# Export singleton mapping for convenience
OM_FIELDS: Dict[str, OMFieldDefinition] = get_om_fields()
