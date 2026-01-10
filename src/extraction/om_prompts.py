"""
OM extraction prompts - Understanding Plane.
"""

from __future__ import annotations

from .om_fields import OM_FIELDS, OMFieldDefinition, format_om_field_definitions_for_prompt


def build_om_extraction_prompt(
    document_text: str,
    field_defs: dict[str, OMFieldDefinition] | None = None,
) -> str:
    """
    Build the OM extraction prompt with marketing-aware guidance.
    """
    definitions = field_defs or OM_FIELDS
    field_definitions_str = format_om_field_definitions_for_prompt(definitions)

    return f"""
You are a CRE investment analyst extracting data from an Offering Memorandum.

CRITICAL DISTINCTIONS:
1. IN-PLACE vs PRO FORMA: Always identify which type each financial metric is
2. ACTUAL vs PROJECTED: Current occupancy vs stabilized occupancy
3. TRAILING vs ANNUALIZED: T12 NOI vs annualized from partial year

For each field, provide:
- value: The extracted value
- value_type: One of [actual, trailing_12, annualized, pro_forma, stabilized, broker_estimate]
- source_section: Where in the OM you found this [executive_summary, financial_summary_page, detailed_exhibits, investment_highlights, market_overview, pro_forma_projections]
- confidence: Your confidence 0-1 (be conservative with marketing claims)
- page: Page number
- quote: Supporting text

EXTRACTION WARNINGS:
- If a value seems inconsistent with others, note it
- If pro forma assumptions seem aggressive, flag it
- If critical fields are missing, list them

Fields to extract:
{field_definitions_str}

Document text:
{document_text}

Respond in JSON:
{{
  "property_info": {{}},
  "financials_in_place": {{}},
  "financials_pro_forma": {{}},
  "rent_roll_summary": {{}},
  "debt_info": {{}},
  "transaction_info": {{}},
  "warnings": [...],
  "missing_critical": [...]
}}
"""
