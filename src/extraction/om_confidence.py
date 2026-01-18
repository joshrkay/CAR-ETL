"""
Offering Memorandum confidence calculation.
"""

from __future__ import annotations

from typing import Dict, List, Optional

from pydantic import BaseModel, Field

from .om_fields import get_om_fields, OMFieldDefinition


class OMExtractedField(BaseModel):
    """Extracted OM field with metadata for scoring."""

    name: str
    value: Optional[object]
    confidence: float = Field(..., ge=0.0, le=1.0)
    source_section: Optional[str] = None
    value_type: Optional[str] = None


# Source and value factors
SOURCE_RELIABILITY: Dict[str, float] = {
    "executive_summary": 0.95,
    "financial_summary_page": 0.92,
    "detailed_exhibits": 0.98,
    "investment_highlights": 0.75,
    "market_overview": 0.80,
    "pro_forma_projections": 0.70,
    "broker_assumptions": 0.65,
}

VALUE_TYPE_FACTORS: Dict[str, float] = {
    "actual": 1.0,
    "trailing_12": 0.98,
    "annualized": 0.92,
    "pro_forma": 0.80,
    "stabilized": 0.75,
    "broker_estimate": 0.70,
}


def check_om_consistency(fields: Dict[str, float]) -> Dict[str, float]:
    """
    Check internal consistency of extracted OM fields.
    Returns per-field penalty multipliers (<1.0) when inconsistencies are found.
    """
    issues: Dict[str, float] = {}

    if all(k in fields for k in ["cap_rate_in_place", "noi_in_place", "asking_price"]):
        asking = fields["asking_price"]
        if asking:
            calculated_cap = fields["noi_in_place"] / asking
            stated_cap = fields["cap_rate_in_place"]
            if abs(calculated_cap - stated_cap) > 0.005:
                issues["cap_rate_in_place"] = 0.85

    if all(k in fields for k in ["price_psf", "asking_price", "total_sf"]):
        if fields["price_psf"] and fields["total_sf"]:
            calculated_psf = fields["asking_price"] / fields["total_sf"]
            stated_psf = fields["price_psf"]
            if stated_psf and abs(calculated_psf - stated_psf) / stated_psf > 0.02:
                issues["price_psf"] = 0.90

    if "occupancy_current" in fields:
        occ = fields["occupancy_current"]
        if occ is not None:
            if occ > 1.0 or occ < 0:
                issues["occupancy_current"] = 0.50
            elif occ > 0.98:
                issues["occupancy_current"] = 0.85

    if all(k in fields for k in ["noi_in_place", "noi_pro_forma"]):
        in_place = fields["noi_in_place"]
        pro_forma = fields["noi_pro_forma"]
        if in_place and pro_forma:
            growth = pro_forma / in_place
            if growth > 1.5:
                issues["noi_pro_forma"] = 0.70
            elif growth > 1.3:
                issues["noi_pro_forma"] = 0.80

    return issues


def calculate_om_field_confidence(
    field_name: str,
    base_confidence: float,
    source_section: Optional[str],
    value_type: Optional[str],
    fields: Dict[str, float],
    field_definitions: Optional[Dict[str, OMFieldDefinition]] = None,
) -> float:
    """
    Calculate marketing-aware confidence for a single field.
    """
    definitions = field_definitions or OM_FIELDS
    field_def = definitions.get(field_name)
    conf = base_confidence

    source_factor = SOURCE_RELIABILITY.get(source_section or "", 0.85)
    conf *= source_factor

    value_factor = VALUE_TYPE_FACTORS.get(value_type or "", 0.85)
    conf *= value_factor

    skepticism = field_def.skepticism if field_def else 1.0
    conf *= skepticism

    consistency_penalties = check_om_consistency(fields)
    if field_name in consistency_penalties:
        conf *= consistency_penalties[field_name]

    return max(0.0, min(1.0, conf))


def calculate_om_document_confidence(
    fields: List[OMExtractedField], field_definitions: Optional[Dict[str, OMFieldDefinition]] = None
) -> float:
    """
    Compute document-level confidence with critical field emphasis.
    """
    definitions = field_definitions or OM_FIELDS
    critical_fields = {"asking_price", "cap_rate_in_place", "noi_in_place", "total_sf", "property_type", "occupancy_current"}

    total_weight = 0.0
    weighted_sum = 0.0
    critical_found = 0

    for field in fields:
        definition = definitions.get(field.name)
        weight = definition.weight if definition else 1.0
        weighted_sum += field.confidence * weight
        total_weight += weight
        if field.name in critical_fields and field.value is not None:
            critical_found += 1

    base_confidence = (weighted_sum / total_weight) if total_weight else 0.0

    coverage = critical_found / len(critical_fields)
    if coverage < 0.8:
        base_confidence *= (0.5 + 0.5 * coverage)

    return max(0.0, min(1.0, base_confidence))


OM_FIELDS: Dict[str, OMFieldDefinition] = get_om_fields()

