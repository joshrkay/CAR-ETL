"""
Extraction Prompts - Understanding Plane

LLM prompts for document field extraction.
Prompts are industry and document-type specific.
"""



def build_extraction_prompt(
    field_definitions: str,
    document_text: str,
    industry: str,
    document_type: str
) -> str:
    """
    Build extraction prompt for LLM.

    Args:
        field_definitions: Formatted string of field definitions
        document_text: Extracted document text
        industry: Industry identifier (e.g., 'cre')
        document_type: Document type (e.g., 'lease')

    Returns:
        Complete prompt string for LLM
    """
    industry_name = _get_industry_display_name(industry)
    doc_type_name = _get_document_type_display_name(document_type)

    prompt = f"""You are a {industry_name} document analyst. Extract the following fields from this {doc_type_name} document.

For each field, provide:
- value: The extracted value (use null if not found)
- confidence: Your confidence 0-1 (be conservative, never use 1.0)
- page: Page number where found (1-indexed)
- quote: Exact text supporting the extraction

Fields to extract:
{field_definitions}

Document text:
{document_text}

Respond in JSON format:
{{
  "fields": {{
    "field_name": {{"value": "...", "confidence": 0.95, "page": 1, "quote": "..."}},
    ...
  }}
}}
"""
    return prompt


def build_document_type_detection_prompt(document_text: str, industry: str) -> str:
    """
    Build prompt for document type detection.

    Args:
        document_text: First page of document text (truncated)
        industry: Industry identifier (e.g., 'cre')

    Returns:
        Prompt string for document type detection
    """
    industry_name = _get_industry_display_name(industry)
    document_types = _get_document_types_for_industry(industry)

    prompt = f"""You are a {industry_name} document classifier. Analyze this document and determine its type.

Document types:
{', '.join(document_types)}

Document text (first page):
{document_text[:2000]}

Respond in JSON format:
{{
  "document_type": "lease",
  "confidence": 0.95,
  "reasoning": "Brief explanation of classification"
}}
"""
    return prompt


def _get_industry_display_name(industry: str) -> str:
    """Get display name for industry."""
    industry_map: dict[str, str] = {
        "cre": "Commercial Real Estate",
    }
    return industry_map.get(industry.lower(), industry.upper())


def _get_document_type_display_name(document_type: str) -> str:
    """Get display name for document type."""
    doc_type_map: dict[str, str] = {
        "lease": "lease",
        "rent_roll": "rent roll",
        "financial_statement": "financial statement",
        "operating_agreement": "operating agreement",
    }
    return doc_type_map.get(document_type.lower(), document_type)


def _get_document_types_for_industry(industry: str) -> list[str]:
    """Get supported document types for industry."""
    if industry.lower() == "cre":
        return ["lease", "rent_roll", "financial_statement", "operating_agreement", "other"]
    return ["other"]
