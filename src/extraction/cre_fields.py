"""
CRE Field Definitions - Understanding Plane

Industry-configurable field definitions for Commercial Real Estate document extraction.
Fields are organized by document type and can be configured per industry.
"""

from typing import Dict, Any, List, Optional
from enum import Enum
from pydantic import BaseModel, Field


class FieldType(str, Enum):
    """Field data type."""
    STRING = "string"
    DATE = "date"
    CURRENCY = "currency"
    INTEGER = "integer"
    ENUM = "enum"
    FLOAT = "float"
    BOOLEAN = "boolean"


class FieldDefinition(BaseModel):
    """Definition for a single extraction field."""
    type: FieldType = Field(..., description="Field data type")
    required: bool = Field(default=False, description="Whether field is required")
    weight: float = Field(..., ge=0.0, description="Weight for confidence calculation")
    values: Optional[List[str]] = Field(None, description="Allowed enum values")
    aliases: Optional[List[str]] = Field(None, description="Alternative names/synonyms for this field")


class IndustryFieldConfig(BaseModel):
    """Field configuration for a specific industry and document type."""
    industry: str = Field(..., min_length=1, description="Industry identifier (e.g., 'cre')")
    document_type: str = Field(..., min_length=1, description="Document type (e.g., 'lease')")
    fields: Dict[str, FieldDefinition] = Field(..., description="Field definitions")


def get_cre_lease_fields() -> Dict[str, FieldDefinition]:
    """
    Get CRE lease field definitions with aliases for NLP extraction.
    
    Returns:
        Dictionary mapping field names to field definitions
    """
    return {
        # PARTIES & PROPERTY
        "tenant_name": FieldDefinition(
            type=FieldType.STRING,
            required=True,
            weight=1.3,
            aliases=["tenant", "lessee", "occupant", "tenant entity", "tenant legal name", "tenant company", "renter"]
        ),
        "tenant_entity_type": FieldDefinition(
            type=FieldType.ENUM,
            required=False,
            weight=0.6,
            values=["LLC", "Corp", "Partnership", "Individual"]
        ),
        "tenant_contact_name": FieldDefinition(
            type=FieldType.STRING,
            required=False,
            weight=0.7
        ),
        "tenant_email": FieldDefinition(
            type=FieldType.STRING,
            required=False,
            weight=0.6
        ),
        "tenant_phone": FieldDefinition(
            type=FieldType.STRING,
            required=False,
            weight=0.6
        ),
        "landlord_name": FieldDefinition(
            type=FieldType.STRING,
            required=True,
            weight=1.3,
            aliases=["landlord", "lessor", "owner", "property owner", "property manager", "building owner"]
        ),
        "landlord_entity_type": FieldDefinition(
            type=FieldType.ENUM,
            required=False,
            weight=0.6,
            values=["LLC", "REIT", "Corp", "Individual"]
        ),
        "landlord_contact_name": FieldDefinition(
            type=FieldType.STRING,
            required=False,
            weight=0.7
        ),
        "property_name": FieldDefinition(
            type=FieldType.STRING,
            required=False,
            weight=0.8,
            aliases=["building name", "center name", "shopping center", "office park", "complex name"]
        ),
        "property_address": FieldDefinition(
            type=FieldType.STRING,
            required=True,
            weight=1.2,  # Increased: appears in all tests, critical for location
            aliases=["premises address", "leased premises", "property location", "building address", "site address", "physical address"]
        ),
        "city": FieldDefinition(
            type=FieldType.STRING,
            required=True,
            weight=0.9  # Increased: appears in 10+ tests
        ),
        "state": FieldDefinition(
            type=FieldType.STRING,
            required=True,
            weight=0.9  # Increased: appears in 10+ tests
        ),
        "zip_code": FieldDefinition(
            type=FieldType.STRING,
            required=True,
            weight=0.9  # Increased: appears in 10+ tests
        ),
        "suite_number": FieldDefinition(
            type=FieldType.STRING,
            required=False,
            weight=0.8,
            aliases=["suite", "unit", "space", "office", "storefront", "bay", "lot", "room number"]
        ),
        "floor_number": FieldDefinition(
            type=FieldType.STRING,
            required=False,
            weight=0.6
        ),
        "building_type": FieldDefinition(
            type=FieldType.ENUM,
            required=False,
            weight=0.7,
            values=["office", "retail", "industrial", "medical", "mixed_use"]
        ),
        
        # LEASE TERM
        "lease_start_date": FieldDefinition(
            type=FieldType.DATE,
            required=True,
            weight=1.5,
            aliases=["commencement date", "start of term", "effective date", "inception date", "beginning date"]
        ),
        "lease_end_date": FieldDefinition(
            type=FieldType.DATE,
            required=True,
            weight=1.5,
            aliases=["expiration date", "termination date", "end of term", "lease expiry", "maturity date"]
        ),
        "lease_execution_date": FieldDefinition(
            type=FieldType.DATE,
            required=False,
            weight=0.9,
            aliases=["date of execution", "signed date", "contract date", "agreement date"]
        ),
        "possession_date": FieldDefinition(
            type=FieldType.DATE,
            required=False,
            weight=0.9,
            aliases=["delivery date", "occupancy date", "turnover date"]
        ),
        "initial_term_months": FieldDefinition(
            type=FieldType.INTEGER,
            required=False,
            weight=0.8
        ),
        "holdover_clause": FieldDefinition(
            type=FieldType.STRING,
            required=False,
            weight=0.7
        ),
        
        # RENT & PAYMENTS
        "base_rent": FieldDefinition(
            type=FieldType.CURRENCY,
            required=True,
            weight=1.5,
            aliases=["minimum rent", "fixed rent", "monthly rent", "annual rent", "scheduled rent", "stated rent", "contract rent"]
        ),
        "rent_frequency": FieldDefinition(
            type=FieldType.ENUM,
            required=False,
            weight=1.1,  # Increased: appears in 11/15 tests, important for rent calculation
            values=["monthly", "annual", "quarterly"],
            aliases=["payment frequency", "billing cycle", "rent schedule"]
        ),
        "rent_due_date": FieldDefinition(
            type=FieldType.INTEGER,
            required=False,
            weight=0.8,
            aliases=["payment due", "due day", "rent due", "billing date"]
        ),
        "late_fee_amount": FieldDefinition(
            type=FieldType.CURRENCY,
            required=False,
            weight=0.9,
            aliases=["late charge", "penalty fee", "delinquency fee"]
        ),
        "late_fee_grace_period_days": FieldDefinition(
            type=FieldType.INTEGER,
            required=False,
            weight=0.8
        ),
        "rent_escalation": FieldDefinition(
            type=FieldType.STRING,
            required=False,
            weight=1.1,
            aliases=["rent increase", "annual bump", "step rent", "rate adjustment", "CPI adjustment", "indexed rent"]
        ),
        "escalation_rate_percent": FieldDefinition(
            type=FieldType.FLOAT,
            required=False,
            weight=1.0
        ),
        "escalation_frequency": FieldDefinition(
            type=FieldType.ENUM,
            required=False,
            weight=0.9,
            values=["annual", "biennial", "fixed"]
        ),
        "free_rent_period": FieldDefinition(
            type=FieldType.STRING,
            required=False,
            weight=0.8,
            aliases=["abatement period", "rent holiday", "free rent", "concession period"]
        ),
        "rent_abatement": FieldDefinition(
            type=FieldType.STRING,
            required=False,
            weight=0.7
        ),
        
        # LEASE STRUCTURE
        "lease_type": FieldDefinition(
            type=FieldType.ENUM,
            required=False,
            weight=1.2,  # Increased: appears in 12/15 tests, critical for lease structure
            values=["gross", "net", "nn", "nnn", "modified_gross"],
            aliases=["full service", "triple net", "double net", "absolute net", "industrial net"]
        ),
        "expense_reimbursement_type": FieldDefinition(
            type=FieldType.ENUM,
            required=False,
            weight=0.8,
            values=["cam", "tax", "insurance", "all"]
        ),
        "expense_stop": FieldDefinition(
            type=FieldType.CURRENCY,
            required=False,
            weight=0.7
        ),
        "cam_charges": FieldDefinition(
            type=FieldType.CURRENCY,
            required=False,
            weight=1.1,  # Increased: appears in 8+ tests (net/modified gross leases), critical for rent calculation
            aliases=["common area maintenance", "operating expenses", "opex", "property expenses", "shared expenses"]
        ),
        "tax_reimbursement": FieldDefinition(
            type=FieldType.CURRENCY,
            required=False,
            weight=0.9,
            aliases=["real estate tax", "property tax pass-through", "tax share"]
        ),
        "insurance_reimbursement": FieldDefinition(
            type=FieldType.CURRENCY,
            required=False,
            weight=0.9,
            aliases=["insurance pass-through", "policy reimbursement"]
        ),
        
        # SPACE DETAILS
        "square_footage": FieldDefinition(
            type=FieldType.INTEGER,
            required=False,
            weight=1.2,  # Increased: appears in 14/15 tests, critical for valuation
            aliases=["sq ft", "square feet", "rentable area", "leased area", "RSF"]
        ),
        "rentable_square_feet": FieldDefinition(
            type=FieldType.INTEGER,
            required=False,
            weight=0.9,
            aliases=["RSF", "gross square feet", "billable square feet"]
        ),
        "usable_square_feet": FieldDefinition(
            type=FieldType.INTEGER,
            required=False,
            weight=0.9,
            aliases=["USF", "net rentable", "usable area"]
        ),
        "load_factor": FieldDefinition(
            type=FieldType.FLOAT,
            required=False,
            weight=0.6,
            aliases=["add-on factor", "efficiency factor", "core factor"]
        ),
        "common_area_factor": FieldDefinition(
            type=FieldType.FLOAT,
            required=False,
            weight=0.6
        ),
        "parking_spaces": FieldDefinition(
            type=FieldType.INTEGER,
            required=False,
            weight=0.7
        ),
        "parking_fee": FieldDefinition(
            type=FieldType.CURRENCY,
            required=False,
            weight=0.6
        ),
        
        # DEPOSITS & FINANCIAL SECURITY
        "security_deposit": FieldDefinition(
            type=FieldType.CURRENCY,
            required=False,
            weight=1.2,
            aliases=["deposit", "cash security", "damage deposit", "security funds"]
        ),
        "letter_of_credit_amount": FieldDefinition(
            type=FieldType.CURRENCY,
            required=False,
            weight=0.8,
            aliases=["LC", "bank guarantee", "standby letter"]
        ),
        "personal_guarantee": FieldDefinition(
            type=FieldType.BOOLEAN,
            required=False,
            weight=0.9,  # Increased: appears in 2+ tests, important for tenant quality
            aliases=["PG", "individual guarantee", "guarantor"]
        ),
        "corporate_guarantee": FieldDefinition(
            type=FieldType.BOOLEAN,
            required=False,
            weight=0.9  # Increased: appears in 3+ tests, important for tenant quality
        ),
        
        # OPTIONS & RIGHTS
        "renewal_options": FieldDefinition(
            type=FieldType.STRING,
            required=False,
            weight=0.9,
            aliases=["extension option", "option to renew", "option term", "renewal right"]
        ),
        "renewal_term_length": FieldDefinition(
            type=FieldType.STRING,
            required=False,
            weight=0.8
        ),
        "expansion_rights": FieldDefinition(
            type=FieldType.STRING,
            required=False,
            weight=0.7,
            aliases=["right to expand", "growth option", "first right"]
        ),
        "right_of_first_refusal": FieldDefinition(
            type=FieldType.BOOLEAN,
            required=False,
            weight=0.7
        ),
        "right_of_first_offer": FieldDefinition(
            type=FieldType.BOOLEAN,
            required=False,
            weight=0.7
        ),
        "termination_clause": FieldDefinition(
            type=FieldType.STRING,
            required=False,
            weight=0.9,
            aliases=["break clause", "early termination", "kick-out clause", "exit option"]
        ),
        "early_termination_fee": FieldDefinition(
            type=FieldType.CURRENCY,
            required=False,
            weight=0.8
        ),
        
        # USE & RESTRICTIONS
        "permitted_use": FieldDefinition(
            type=FieldType.STRING,
            required=False,
            weight=1.0,
            aliases=["use clause", "allowed use", "intended use"]
        ),
        "exclusive_use": FieldDefinition(
            type=FieldType.STRING,
            required=False,
            weight=0.7,
            aliases=["exclusivity", "no competition clause"]
        ),
        "prohibited_use": FieldDefinition(
            type=FieldType.STRING,
            required=False,
            weight=0.6
        ),
        "sublease_rights": FieldDefinition(
            type=FieldType.ENUM,
            required=False,
            weight=0.8,
            values=["allowed", "restricted", "prohibited"],
            aliases=["subletting", "right to sublet", "subtenancy"]
        ),
        "assignment_rights": FieldDefinition(
            type=FieldType.ENUM,
            required=False,
            weight=0.8,
            values=["allowed", "restricted", "prohibited"]
        ),
        
        # IMPROVEMENTS & MAINTENANCE
        "tenant_improvement_allowance": FieldDefinition(
            type=FieldType.CURRENCY,
            required=False,
            weight=1.1,  # Increased: appears in 10+ tests, critical for lease economics
            aliases=["TI allowance", "build-out allowance", "construction allowance"]
        ),
        "buildout_period_days": FieldDefinition(
            type=FieldType.INTEGER,
            required=False,
            weight=0.8,
            aliases=["construction period", "fixturization", "fit-out period"]
        ),
        "landlord_repairs": FieldDefinition(
            type=FieldType.STRING,
            required=False,
            weight=0.7
        ),
        "tenant_repairs": FieldDefinition(
            type=FieldType.STRING,
            required=False,
            weight=0.7
        ),
        "hvac_responsibility": FieldDefinition(
            type=FieldType.ENUM,
            required=False,
            weight=0.7,
            values=["landlord", "tenant", "shared"]
        ),
        "roof_responsibility": FieldDefinition(
            type=FieldType.ENUM,
            required=False,
            weight=0.7,
            values=["landlord", "tenant"]
        ),
        
        # INSURANCE & COMPLIANCE
        "tenant_insurance_required": FieldDefinition(
            type=FieldType.BOOLEAN,
            required=False,
            weight=0.8
        ),
        "insurance_minimum_amount": FieldDefinition(
            type=FieldType.CURRENCY,
            required=False,
            weight=0.7
        ),
        "indemnification_clause": FieldDefinition(
            type=FieldType.STRING,
            required=False,
            weight=0.7
        ),
        "ada_compliance": FieldDefinition(
            type=FieldType.BOOLEAN,
            required=False,
            weight=0.6
        ),
        
        # DEFAULTS & LEGAL
        "default_events": FieldDefinition(
            type=FieldType.STRING,
            required=False,
            weight=0.8,
            aliases=["events of default", "breach", "non-performance"]
        ),
        "remedies_clause": FieldDefinition(
            type=FieldType.STRING,
            required=False,
            weight=0.8
        ),
        "governing_law": FieldDefinition(
            type=FieldType.STRING,
            required=False,
            weight=0.7,
            aliases=["choice of law", "jurisdiction"]
        ),
        "attorney_fees_clause": FieldDefinition(
            type=FieldType.BOOLEAN,
            required=False,
            weight=0.6
        ),
        "confidentiality_clause": FieldDefinition(
            type=FieldType.BOOLEAN,
            required=False,
            weight=0.6
        ),
        
        # MISC
        "force_majeure": FieldDefinition(
            type=FieldType.BOOLEAN,
            required=False,
            weight=0.6
        ),
        "signage_rights": FieldDefinition(
            type=FieldType.STRING,
            required=False,
            weight=0.7
        ),
        "operating_hours": FieldDefinition(
            type=FieldType.STRING,
            required=False,
            weight=0.6
        ),
        "broker_name": FieldDefinition(
            type=FieldType.STRING,
            required=False,
            weight=0.6,
            aliases=["leasing agent", "transaction broker", "representative"]
        ),
        "broker_commission": FieldDefinition(
            type=FieldType.CURRENCY,
            required=False,
            weight=0.6,
            aliases=["fee", "leasing fee", "commission payable"]
        ),
        
        # OFFICE PROPERTY TYPE
        "office_class": FieldDefinition(
            type=FieldType.ENUM,
            required=False,
            weight=0.9,  # Increased: critical for office property valuation, appears in all office tests
            values=["A", "B", "C"],
            aliases=["building class", "asset class"]
        ),
        "floor_plate_size": FieldDefinition(
            type=FieldType.INTEGER,
            required=False,
            weight=0.6,
            aliases=["floor size", "plate"]
        ),
        "core_factor": FieldDefinition(
            type=FieldType.FLOAT,
            required=False,
            weight=0.6,
            aliases=["load factor", "efficiency ratio"]
        ),
        "conference_room_access": FieldDefinition(
            type=FieldType.BOOLEAN,
            required=False,
            weight=0.5,
            aliases=["shared meeting rooms"]
        ),
        "after_hours_hvac": FieldDefinition(
            type=FieldType.CURRENCY,
            required=False,
            weight=0.7,
            aliases=["overtime HVAC", "after-hours cooling"]
        ),
        "elevator_ratio": FieldDefinition(
            type=FieldType.STRING,
            required=False,
            weight=0.5,
            aliases=["elevator count", "vertical transport"]
        ),
        "building_certifications": FieldDefinition(
            type=FieldType.ENUM,
            required=False,
            weight=0.6,
            values=["LEED", "WELL", "EnergyStar"],
            aliases=["green building", "sustainability cert"]
        ),
        "spec_suite": FieldDefinition(
            type=FieldType.BOOLEAN,
            required=False,
            weight=0.6,
            aliases=["pre-built", "move-in ready"]
        ),
        "open_plan_ratio": FieldDefinition(
            type=FieldType.FLOAT,
            required=False,
            weight=0.5,
            aliases=["workspace efficiency"]
        ),
        
        # RETAIL PROPERTY TYPE
        "retail_type": FieldDefinition(
            type=FieldType.ENUM,
            required=False,
            weight=0.9,  # Increased: critical for retail property analysis, appears in all retail tests
            values=["inline", "endcap", "pad", "anchor", "outparcel"],
            aliases=["store type"]
        ),
        "co_tenancy_clause": FieldDefinition(
            type=FieldType.BOOLEAN,
            required=False,
            weight=0.9,  # Increased: critical risk factor for retail, appears in anchor lease
            aliases=["anchor dependency"]
        ),
        "percentage_rent": FieldDefinition(
            type=FieldType.FLOAT,
            required=False,
            weight=1.0,  # Increased: critical for retail leases, appears in 2/3 retail tests
            aliases=["sales rent", "overage rent"]
        ),
        "sales_reporting_required": FieldDefinition(
            type=FieldType.BOOLEAN,
            required=False,
            weight=0.7,
            aliases=["gross sales reporting"]
        ),
        "foot_traffic_count": FieldDefinition(
            type=FieldType.INTEGER,
            required=False,
            weight=0.6,
            aliases=["pedestrian count"]
        ),
        "signage_type": FieldDefinition(
            type=FieldType.ENUM,
            required=False,
            weight=0.7,
            values=["pylon", "monument", "façade"],
            aliases=["store signage"]
        ),
        "drive_thru": FieldDefinition(
            type=FieldType.BOOLEAN,
            required=False,
            weight=0.6,
            aliases=["drive through"]
        ),
        "exclusive_retail_use": FieldDefinition(
            type=FieldType.STRING,
            required=False,
            weight=0.7,
            aliases=["no-compete"]
        ),
        "common_area_marketing_fee": FieldDefinition(
            type=FieldType.CURRENCY,
            required=False,
            weight=0.6,
            aliases=["marketing fund", "promotion fee"]
        ),
        
        # INDUSTRIAL PROPERTY TYPE
        "clear_height": FieldDefinition(
            type=FieldType.INTEGER,
            required=False,
            weight=0.9,  # Increased: critical for industrial properties, appears in all industrial tests
            aliases=["ceiling height"]
        ),
        "column_spacing": FieldDefinition(
            type=FieldType.STRING,
            required=False,
            weight=0.6,
            aliases=["bay spacing"]
        ),
        "loading_docks": FieldDefinition(
            type=FieldType.INTEGER,
            required=False,
            weight=0.9,  # Increased: critical for industrial, appears in all industrial tests
            aliases=["dock doors"]
        ),
        "drive_in_doors": FieldDefinition(
            type=FieldType.INTEGER,
            required=False,
            weight=0.7,
            aliases=["grade-level doors"]
        ),
        "trailer_parking_spaces": FieldDefinition(
            type=FieldType.INTEGER,
            required=False,
            weight=0.6,
            aliases=["yard parking"]
        ),
        "power_capacity": FieldDefinition(
            type=FieldType.STRING,
            required=False,
            weight=0.7,
            aliases=["amps", "voltage"]
        ),
        "sprinkler_type": FieldDefinition(
            type=FieldType.ENUM,
            required=False,
            weight=0.7,
            values=["ESFR", "wet", "dry"],
            aliases=["fire suppression"]
        ),
        "floor_load_capacity": FieldDefinition(
            type=FieldType.STRING,
            required=False,
            weight=0.7,
            aliases=["psf rating"]
        ),
        "rail_access": FieldDefinition(
            type=FieldType.BOOLEAN,
            required=False,
            weight=0.6,
            aliases=["rail spur"]
        ),
        "cross_dock": FieldDefinition(
            type=FieldType.BOOLEAN,
            required=False,
            weight=0.6,
            aliases=["through dock"]
        ),
        
        # MULTI-FAMILY PROPERTY TYPE
        "unit_count": FieldDefinition(
            type=FieldType.INTEGER,
            required=False,
            weight=0.8,
            aliases=["number of units"]
        ),
        "unit_mix": FieldDefinition(
            type=FieldType.STRING,
            required=False,
            weight=0.7,
            aliases=["bed/bath mix"]
        ),
        "average_rent_per_unit": FieldDefinition(
            type=FieldType.CURRENCY,
            required=False,
            weight=0.8,
            aliases=["ARPU"]
        ),
        "occupancy_rate": FieldDefinition(
            type=FieldType.FLOAT,
            required=False,
            weight=1.1,  # Increased: critical metric, appears in all multi-family and many other tests
            aliases=["leased percentage"]
        ),
        "concessions": FieldDefinition(
            type=FieldType.STRING,
            required=False,
            weight=0.7,
            aliases=["rent specials"]
        ),
        "pet_policy": FieldDefinition(
            type=FieldType.STRING,
            required=False,
            weight=0.6,
            aliases=["pet restrictions"]
        ),
        "amenities": FieldDefinition(
            type=FieldType.STRING,
            required=False,
            weight=0.7,
            aliases=["pool", "gym", "clubhouse"]
        ),
        "lease_term_options": FieldDefinition(
            type=FieldType.STRING,
            required=False,
            weight=0.6,
            aliases=["short term leases"]
        ),
        "rent_control": FieldDefinition(
            type=FieldType.BOOLEAN,
            required=False,
            weight=0.7,
            aliases=["rent stabilization"]
        ),
        "parking_ratio": FieldDefinition(
            type=FieldType.FLOAT,
            required=False,
            weight=0.6,
            aliases=["spaces per unit"]
        ),
        
        # MIXED-USE PROPERTY TYPE
        "component_breakdown": FieldDefinition(
            type=FieldType.STRING,
            required=False,
            weight=0.9,  # Increased: critical for mixed-use, appears in all mixed-use tests
            aliases=["use allocation"]
        ),
        "retail_percentage": FieldDefinition(
            type=FieldType.FLOAT,
            required=False,
            weight=0.9,  # Increased: critical for mixed-use analysis
            aliases=["ground floor retail"]
        ),
        "office_percentage": FieldDefinition(
            type=FieldType.FLOAT,
            required=False,
            weight=0.9,  # Increased: critical for mixed-use analysis
            aliases=["office portion"]
        ),
        "residential_percentage": FieldDefinition(
            type=FieldType.FLOAT,
            required=False,
            weight=0.9,  # Increased: critical for mixed-use analysis
            aliases=["apartment portion"]
        ),
        "shared_parking": FieldDefinition(
            type=FieldType.BOOLEAN,
            required=False,
            weight=0.6,
            aliases=["common garage"]
        ),
        "separate_entrances": FieldDefinition(
            type=FieldType.BOOLEAN,
            required=False,
            weight=0.6,
            aliases=["dedicated lobbies"]
        ),
        "operating_hours_restrictions": FieldDefinition(
            type=FieldType.STRING,
            required=False,
            weight=0.6,
            aliases=["use conflicts"]
        ),
        "noise_restrictions": FieldDefinition(
            type=FieldType.STRING,
            required=False,
            weight=0.6,
            aliases=["sound limitations"]
        ),
        "zoning_classification": FieldDefinition(
            type=FieldType.STRING,
            required=False,
            weight=0.7,
            aliases=["zoning"]
        ),
        
        # CROSS-PROPERTY UNIVERSAL FIELDS
        "cap_rate": FieldDefinition(
            type=FieldType.FLOAT,
            required=False,
            weight=0.8,
            aliases=["capitalization rate"]
        ),
        "net_operating_income": FieldDefinition(
            type=FieldType.CURRENCY,
            required=False,
            weight=0.8,
            aliases=["NOI"]
        ),
        "gross_rent_multiplier": FieldDefinition(
            type=FieldType.FLOAT,
            required=False,
            weight=0.7,
            aliases=["GRM"]
        ),
        "expense_ratio": FieldDefinition(
            type=FieldType.FLOAT,
            required=False,
            weight=0.7,
            aliases=["opex ratio"]
        ),
        "year_built": FieldDefinition(
            type=FieldType.INTEGER,
            required=False,
            weight=0.7,
            aliases=["construction year"]
        ),
        "renovation_year": FieldDefinition(
            type=FieldType.INTEGER,
            required=False,
            weight=0.6,
            aliases=["last remodel"]
        ),
        "flood_zone": FieldDefinition(
            type=FieldType.STRING,
            required=False,
            weight=0.6,
            aliases=["FEMA zone"]
        ),
        
        # TENANT QUALITY - IDENTITY & CREDITWORTHINESS
        "tenant_duns_number": FieldDefinition(
            type=FieldType.STRING,
            required=False,
            weight=0.6,
            aliases=["DUNS", "duns #", "dun & bradstreet"]
        ),
        "tenant_legal_entity": FieldDefinition(
            type=FieldType.STRING,
            required=False,
            weight=0.6,
            aliases=["legal name", "entity name", "registered name"]
        ),
        "tenant_parent_company": FieldDefinition(
            type=FieldType.STRING,
            required=False,
            weight=0.7,
            aliases=["parent", "ultimate parent", "holding company"]
        ),
        "tenant_guarantor_name": FieldDefinition(
            type=FieldType.STRING,
            required=False,
            weight=0.8,
            aliases=["guarantor", "personal guaranty", "corporate guaranty", "guarantee"]
        ),
        "tenant_credit_rating": FieldDefinition(
            type=FieldType.STRING,
            required=False,
            weight=1.0,
            aliases=["rating", "S&P rating", "Moody's rating", "Fitch rating", "credit grade"]
        ),
        "tenant_credit_score": FieldDefinition(
            type=FieldType.INTEGER,
            required=False,
            weight=0.8,
            aliases=["credit score", "business credit score"]
        ),
        
        # TENANT QUALITY - LEASE PERFORMANCE & PAYMENT RISK
        "payment_history_status": FieldDefinition(
            type=FieldType.ENUM,
            required=False,
            weight=1.3,  # Increased: critical for tenant quality assessment
            values=["on_time", "minor_late", "frequent_late", "delinquent"],
            aliases=["payment history", "collections", "arrears status"]
        ),
        "days_past_due_avg": FieldDefinition(
            type=FieldType.INTEGER,
            required=False,
            weight=1.0,
            aliases=["avg DPD", "average delinquency"]
        ),
        "current_arrears_amount": FieldDefinition(
            type=FieldType.CURRENCY,
            required=False,
            weight=1.1,
            aliases=["past due", "outstanding balance", "arrears"]
        ),
        "nsf_count": FieldDefinition(
            type=FieldType.INTEGER,
            required=False,
            weight=0.7,
            aliases=["returned payment", "bounced check", "NSF"]
        ),
        
        # TENANT QUALITY - LEASE SECURITY & GUARANTEES
        "security_deposit_months": FieldDefinition(
            type=FieldType.FLOAT,
            required=False,
            weight=0.9,
            aliases=["deposit months", "months of deposit"]
        ),
        "guarantee_type": FieldDefinition(
            type=FieldType.ENUM,
            required=False,
            weight=1.1,  # Increased: appears in complex leases, critical for tenant quality assessment
            values=["none", "personal", "corporate", "parent", "good_guy", "limited", "springing"],
            aliases=["guaranty type", "guarantee type", "guarantee structure"]
        ),
        
        # TENANT QUALITY - BUSINESS STRENGTH & DURABILITY
        "tenant_years_in_business": FieldDefinition(
            type=FieldType.INTEGER,
            required=False,
            weight=0.8,
            aliases=["years operating", "established"]
        ),
        "tenant_locations_count": FieldDefinition(
            type=FieldType.INTEGER,
            required=False,
            weight=0.7,
            aliases=["number of locations", "store count", "units (tenant)"]
        ),
        "tenant_is_public_company": FieldDefinition(
            type=FieldType.BOOLEAN,
            required=False,
            weight=0.7,
            aliases=["publicly traded", "listed company"]
        ),
        "tenant_revenue_estimate": FieldDefinition(
            type=FieldType.CURRENCY,
            required=False,
            weight=0.6,
            aliases=["annual revenue", "sales volume", "top-line"]
        ),
        
        # TENANT QUALITY - LEASE-SPECIFIC RISK
        "lease_expiration_risk_bucket": FieldDefinition(
            type=FieldType.ENUM,
            required=False,
            weight=1.3,  # Increased: critical for rollover risk assessment
            values=["0-6", "6-12", "12-24", "24-60", "60+"],
            aliases=["expiration bucket", "rollover risk"]
        ),
        "tenant_rent_concentration_percent": FieldDefinition(
            type=FieldType.FLOAT,
            required=False,
            weight=1.4,  # Already high, keep: critical risk metric
            aliases=["% of rent", "rent share", "income concentration"]
        ),
        "termination_rights": FieldDefinition(
            type=FieldType.ENUM,
            required=False,
            weight=1.2,  # Increased: critical risk factor for lease stability
            values=["none", "tenant_only", "mutual", "kick_out"],
            aliases=["early termination", "break clause", "kick-out clause"]
        ),
        "co_tenancy": FieldDefinition(
            type=FieldType.BOOLEAN,
            required=False,
            weight=0.9,
            aliases=["cotenant", "co-tenancy clause", "anchor clause"]
        ),
        
        # TENANT QUALITY - RETAIL-SPECIFIC
        "percentage_rent_applies": FieldDefinition(
            type=FieldType.BOOLEAN,
            required=False,
            weight=0.8,
            aliases=["overage rent", "sales rent"]
        ),
        "sales_per_sf": FieldDefinition(
            type=FieldType.CURRENCY,
            required=False,
            weight=1.0,
            aliases=["$ per sf sales", "productivity"]
        ),
        
        # TENANT QUALITY - MULTIFAMILY-SPECIFIC
        "income_verification": FieldDefinition(
            type=FieldType.BOOLEAN,
            required=False,
            weight=0.7,
            aliases=["proof of income", "income verified"]
        ),
        "background_check": FieldDefinition(
            type=FieldType.BOOLEAN,
            required=False,
            weight=0.6,
            aliases=["screening", "criminal check"]
        ),
        "rent_to_income_ratio": FieldDefinition(
            type=FieldType.FLOAT,
            required=False,
            weight=0.9,
            aliases=["RTI", "income ratio"]
        ),
        
        # TENANT QUALITY SCORE
        "tenant_quality_score": FieldDefinition(
            type=FieldType.INTEGER,
            required=False,
            weight=1.4,
            aliases=["tenant score", "credit quality score", "tenant strength score"]
        ),
        "tenant_quality_grade": FieldDefinition(
            type=FieldType.ENUM,
            required=False,
            weight=1.2,
            values=["A", "B", "C", "D"],
            aliases=["tenant grade", "quality tier"]
        ),
        "tenant_quality_rationale": FieldDefinition(
            type=FieldType.STRING,
            required=False,
            weight=0.8,
            aliases=["notes", "underwriting notes", "risk notes"]
        ),
        
        # RISK FLAGS
        "risk_flag_short_term": FieldDefinition(
            type=FieldType.BOOLEAN,
            required=False,
            weight=1.0,
            aliases=["<12 months remaining", "near-term rollover"]
        ),
        "risk_flag_high_concentration": FieldDefinition(
            type=FieldType.BOOLEAN,
            required=False,
            weight=1.2,  # Increased: critical risk flag for portfolio analysis
            aliases=["top tenant concentration"]
        ),
        "risk_flag_termination_right": FieldDefinition(
            type=FieldType.BOOLEAN,
            required=False,
            weight=1.2,  # Increased: critical risk flag for lease stability
            aliases=["tenant can terminate", "kick-out"]
        ),
        "risk_flag_frequent_late_pay": FieldDefinition(
            type=FieldType.BOOLEAN,
            required=False,
            weight=1.3,  # Increased: critical risk flag for underwriting
            aliases=["habitual late", "repeat delinquency"]
        ),
        "risk_flag_no_guarantee": FieldDefinition(
            type=FieldType.BOOLEAN,
            required=False,
            weight=1.0,
            aliases=["no guaranty", "no guarantee"]
        ),
        "risk_flag_co_tenancy": FieldDefinition(
            type=FieldType.BOOLEAN,
            required=False,
            weight=0.9,
            aliases=["co-tenancy exposure"]
        ),
        "risk_flag_below_market_rent": FieldDefinition(
            type=FieldType.BOOLEAN,
            required=False,
            weight=0.9,
            aliases=["under market", "below market"]
        ),
        "risk_flag_large_ti_unamortized": FieldDefinition(
            type=FieldType.BOOLEAN,
            required=False,
            weight=1.0,
            aliases=["unamortized TI", "tenant allowance exposure"]
        ),
        
        # PROPERTY-TYPE SPECIFIC TENANT QUALITY
        # Office
        "after_hours_hvac_charges": FieldDefinition(
            type=FieldType.CURRENCY,
            required=False,
            weight=0.7,
            aliases=["overtime HVAC charges"]
        ),
        "tenant_improvement_unamortized": FieldDefinition(
            type=FieldType.CURRENCY,
            required=False,
            weight=0.9,
            aliases=["unamortized TI", "remaining TI allowance"]
        ),
        
        # Retail
        "anchor_dependency": FieldDefinition(
            type=FieldType.BOOLEAN,
            required=False,
            weight=0.9,
            aliases=["anchor tenant dependency"]
        ),
        "exclusive_use_strength": FieldDefinition(
            type=FieldType.STRING,
            required=False,
            weight=0.7,
            aliases=["exclusivity strength", "no-compete strength"]
        ),
        
        # Industrial
        "specialized_improvements": FieldDefinition(
            type=FieldType.STRING,
            required=False,
            weight=0.8,
            aliases=["specialized buildout", "custom improvements", "cold storage", "heavy power", "rail improvements"]
        ),
        
        # Multifamily
        "eviction_history_count": FieldDefinition(
            type=FieldType.INTEGER,
            required=False,
            weight=0.8,
            aliases=["eviction count", "evictions"]
        ),
        
        # Mixed-Use
        "cross_default_clause": FieldDefinition(
            type=FieldType.BOOLEAN,
            required=False,
            weight=1.0,  # Increased: critical risk factor for mixed-use, appears in all mixed-use tests
            aliases=["cross-default", "component cross-default"]
        ),
    }


def get_cre_rent_roll_fields() -> Dict[str, FieldDefinition]:
    """
    Get CRE rent roll field definitions.
    
    Includes property-level and tenant/unit-level fields for rent roll documents.
    Reuses some fields from lease definitions where applicable.
    
    Returns:
        Dictionary mapping field names to field definitions
    """
    # Start with base lease fields that are also used in rent rolls
    base_fields = {
        "tenant_name": FieldDefinition(
            type=FieldType.STRING,
            required=False,
            weight=1.0,
            aliases=["lessee", "occupant"]
        ),
        "lease_start_date": FieldDefinition(
            type=FieldType.DATE,
            required=False,
            weight=1.2,
            aliases=["effective date"]
        ),
        "lease_end_date": FieldDefinition(
            type=FieldType.DATE,
            required=False,
            weight=1.2,
            aliases=["expiration", "maturity"]
        ),
        "base_rent": FieldDefinition(
            type=FieldType.CURRENCY,
            required=False,
            weight=1.3,
            aliases=["minimum rent"]
        ),
            "cam_charges": FieldDefinition(
                type=FieldType.CURRENCY,
                required=False,
                weight=1.1,  # Increased: critical for rent roll analysis
                aliases=["opex", "common area"]
            ),
        "tax_reimbursement": FieldDefinition(
            type=FieldType.CURRENCY,
            required=False,
            weight=0.9,
            aliases=["real estate tax"]
        ),
        "insurance_reimbursement": FieldDefinition(
            type=FieldType.CURRENCY,
            required=False,
            weight=0.9,
            aliases=["insurance pass-through"]
        ),
        "percentage_rent": FieldDefinition(
            type=FieldType.CURRENCY,
            required=False,
            weight=0.9,
            aliases=["overage rent"]
        ),
        "security_deposit": FieldDefinition(
            type=FieldType.CURRENCY,
            required=False,
            weight=1.0,
            aliases=["deposit"]
        ),
        "rentable_square_feet": FieldDefinition(
            type=FieldType.INTEGER,
            required=False,
            weight=1.0,
            aliases=["RSF"]
        ),
        "occupancy_rate": FieldDefinition(
            type=FieldType.FLOAT,
            required=False,
            weight=1.1,
            aliases=["physical occupancy", "leased %"]
        ),
    }
    
    # Add rent roll specific fields
    rent_roll_fields = {
        # PROPERTY LEVEL
        "rent_roll_as_of_date": FieldDefinition(
            type=FieldType.DATE,
            required=True,
            weight=1.5,
            aliases=["report date", "effective date", "as of"]
        ),
        "total_units": FieldDefinition(
            type=FieldType.INTEGER,
            required=False,
            weight=1.2,
            aliases=["unit count", "door count"]
        ),
        "total_square_footage": FieldDefinition(
            type=FieldType.INTEGER,
            required=False,
            weight=1.1,
            aliases=["total RSF", "net rentable area"]
        ),
        "occupied_units": FieldDefinition(
            type=FieldType.INTEGER,
            required=False,
            weight=1.1,
            aliases=["leased units"]
        ),
        "vacant_units": FieldDefinition(
            type=FieldType.INTEGER,
            required=False,
            weight=1.0,
            aliases=["vacancy count"]
        ),
        "economic_occupancy": FieldDefinition(
            type=FieldType.FLOAT,
            required=False,
            weight=1.1,
            aliases=["revenue occupancy"]
        ),
        "gross_potential_rent": FieldDefinition(
            type=FieldType.CURRENCY,
            required=False,
            weight=1.2,
            aliases=["GPR", "market rent total"]
        ),
        "current_gross_rent": FieldDefinition(
            type=FieldType.CURRENCY,
            required=False,
            weight=1.2,
            aliases=["in-place rent", "actual rent"]
        ),
        "vacancy_loss": FieldDefinition(
            type=FieldType.CURRENCY,
            required=False,
            weight=1.0,
            aliases=["lost rent"]
        ),
        "concessions_total": FieldDefinition(
            type=FieldType.CURRENCY,
            required=False,
            weight=1.0,
            aliases=["rent discounts", "free rent impact"]
        ),
        "bad_debt": FieldDefinition(
            type=FieldType.CURRENCY,
            required=False,
            weight=0.9,
            aliases=["collections loss"]
        ),
        
        # TENANT / UNIT LEVEL
        "unit_number": FieldDefinition(
            type=FieldType.STRING,
            required=False,
            weight=1.0,
            aliases=["suite", "apartment", "space", "door"]
        ),
        "lease_status": FieldDefinition(
            type=FieldType.ENUM,
            required=False,
            weight=1.1,
            values=["occupied", "vacant", "notice", "model", "down"],
            aliases=["status"]
        ),
        "move_in_date": FieldDefinition(
            type=FieldType.DATE,
            required=False,
            weight=0.9,
            aliases=["start date", "commencement"]
        ),
        "lease_term_months": FieldDefinition(
            type=FieldType.INTEGER,
            required=False,
            weight=1.0,
            aliases=["term"]
        ),
        "months_remaining": FieldDefinition(
            type=FieldType.INTEGER,
            required=False,
            weight=1.0,
            aliases=["remaining term"]
        ),
        "market_rent": FieldDefinition(
            type=FieldType.CURRENCY,
            required=False,
            weight=1.1,
            aliases=["asking rent"]
        ),
        "in_place_rent": FieldDefinition(
            type=FieldType.CURRENCY,
            required=False,
            weight=1.2,
            aliases=["current rent", "contract rent"]
        ),
        "rent_per_square_foot": FieldDefinition(
            type=FieldType.CURRENCY,
            required=False,
            weight=1.0,
            aliases=["$/SF"]
        ),
        "annual_rent": FieldDefinition(
            type=FieldType.CURRENCY,
            required=False,
            weight=1.1,
            aliases=["annualized rent"]
        ),
        "monthly_rent": FieldDefinition(
            type=FieldType.CURRENCY,
            required=False,
            weight=1.1,
            aliases=["scheduled rent"]
        ),
        
        # RENT COMPONENT BREAKDOWN
        "parking_rent": FieldDefinition(
            type=FieldType.CURRENCY,
            required=False,
            weight=0.8,
            aliases=["garage fee"]
        ),
        "storage_rent": FieldDefinition(
            type=FieldType.CURRENCY,
            required=False,
            weight=0.7,
            aliases=["locker rent"]
        ),
        "other_income": FieldDefinition(
            type=FieldType.CURRENCY,
            required=False,
            weight=0.7,
            aliases=["misc income"]
        ),
        
        # ESCALATIONS & FUTURE RENT
        "rent_step_schedule": FieldDefinition(
            type=FieldType.STRING,
            required=False,
            weight=0.9,
            aliases=["step rents", "rent bumps"]
        ),
        "next_rent_increase_date": FieldDefinition(
            type=FieldType.DATE,
            required=False,
            weight=0.9,
            aliases=["next step"]
        ),
        "future_rent_amount": FieldDefinition(
            type=FieldType.CURRENCY,
            required=False,
            weight=1.0,
            aliases=["pro forma rent"]
        ),
        "rent_escalation_rate": FieldDefinition(
            type=FieldType.FLOAT,
            required=False,
            weight=0.9,
            aliases=["annual increase %"]
        ),
        
        # RISK & EXPOSURE
        "credit_rating": FieldDefinition(
            type=FieldType.STRING,
            required=False,
            weight=0.8,
            aliases=["tenant credit"]
        ),
        "guarantor": FieldDefinition(
            type=FieldType.STRING,
            required=False,
            weight=0.8,
            aliases=["PG", "corporate guarantee"]
        ),
        "lease_expiration_bucket": FieldDefinition(
            type=FieldType.ENUM,
            required=False,
            weight=1.0,
            values=["0-6", "6-12", "12-24", "24+"],
            aliases=["rollover schedule"]
        ),
        "tenant_concentration": FieldDefinition(
            type=FieldType.FLOAT,
            required=False,
            weight=0.9,
            aliases=["rent concentration"]
        ),
        
        # PROPERTY TYPE SPECIFIC - MULTI-FAMILY
        "unit_type": FieldDefinition(
            type=FieldType.STRING,
            required=False,
            weight=0.9,  # Increased: critical for multi-family, appears in all multi-family tests
            aliases=["1x1", "2x2", "studio"]
        ),
        "floor_plan": FieldDefinition(
            type=FieldType.STRING,
            required=False,
            weight=0.7,
            aliases=["layout"]
        ),
        "lease_term_type": FieldDefinition(
            type=FieldType.ENUM,
            required=False,
            weight=0.8,
            values=["6-mo", "9-mo", "12-mo", "month-to-month"]
        ),
        
        # PROPERTY TYPE SPECIFIC - OFFICE
        "tenant_industry": FieldDefinition(
            type=FieldType.STRING,
            required=False,
            weight=0.7,
            aliases=["NAICS", "business type"]
        ),
        "private_offices": FieldDefinition(
            type=FieldType.INTEGER,
            required=False,
            weight=0.6,
            aliases=["office count"]
        ),
        
        # PROPERTY TYPE SPECIFIC - RETAIL
        "gross_sales": FieldDefinition(
            type=FieldType.CURRENCY,
            required=False,
            weight=0.9,
            aliases=["store sales"]
        ),
        "sales_breakpoint": FieldDefinition(
            type=FieldType.CURRENCY,
            required=False,
            weight=0.8,
            aliases=["natural breakpoint"]
        ),
        
        # PROPERTY TYPE SPECIFIC - INDUSTRIAL
        "truck_court_depth": FieldDefinition(
            type=FieldType.INTEGER,
            required=False,
            weight=0.6,
            aliases=["yard depth"]
        ),
        
        # SUMMARY METRICS (Note: These may be calculated, but can be extracted if present)
        "weighted_average_lease_term": FieldDefinition(
            type=FieldType.FLOAT,
            required=False,
            weight=0.9,
            aliases=["WALT"]
        ),
        "top_5_tenants_percent": FieldDefinition(
            type=FieldType.FLOAT,
            required=False,
            weight=0.8,
            aliases=["tenant concentration"]
        ),
        "average_rent_per_sf": FieldDefinition(
            type=FieldType.CURRENCY,
            required=False,
            weight=1.0,
            aliases=["avg $/SF"]
        ),
        "lease_expirations_by_year": FieldDefinition(
            type=FieldType.STRING,  # Stored as JSON string or structured text
            required=False,
            weight=0.8,
            aliases=["rollover schedule"]
        ),
    }
    
    # Merge base fields with rent roll specific fields
    # Base fields take precedence if there are duplicates
    return {**rent_roll_fields, **base_fields}


def get_field_config(industry: str, document_type: str) -> Dict[str, FieldDefinition]:
    """
    Get field configuration for a specific industry and document type.
    
    Args:
        industry: Industry identifier (e.g., 'cre')
        document_type: Document type (e.g., 'lease')
        
    Returns:
        Dictionary mapping field names to field definitions
        
    Raises:
        ValueError: If industry or document type is not supported
    """
    if industry.lower() == "cre":
        if document_type.lower() == "lease":
            return get_cre_lease_fields()
        elif document_type.lower() == "rent_roll":
            return get_cre_rent_roll_fields()
        else:
            raise ValueError(f"CRE document type '{document_type}' not yet supported")
    else:
        raise ValueError(f"Industry '{industry}' not yet supported")


def get_field_definitions_for_prompt(fields: Dict[str, FieldDefinition]) -> str:
    """
    Format field definitions for LLM prompt.
    
    Includes aliases to help LLM recognize field variations.
    
    Args:
        fields: Dictionary of field definitions
        
    Returns:
        Formatted string describing fields for LLM
    """
    lines: List[str] = []
    for field_name, field_def in fields.items():
        field_desc = f"- {field_name}: {field_def.type.value}"
        if field_def.required:
            field_desc += " (required)"
        if field_def.type == FieldType.ENUM and field_def.values:
            field_desc += f" - Allowed values: {', '.join(field_def.values)}"
        if field_def.aliases:
            field_desc += f" - Also known as: {', '.join(field_def.aliases[:5])}"  # Limit to 5 aliases
        lines.append(field_desc)
    return "\n".join(lines)
