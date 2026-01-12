import json
from unittest.mock import AsyncMock, Mock, patch

import pytest

from src.extraction.om_fields import get_om_fields
from src.extraction.om_confidence import (
    calculate_om_field_confidence,
    calculate_om_document_confidence,
    OMExtractedField,
)
from src.extraction.om_extractor import OMExtractor
from src.extraction.om_prompts import build_om_extraction_prompt
from typing import Any


def test_field_definitions_have_critical_fields() -> None:
    fields = get_om_fields()
    for required in ["property_name", "property_address", "property_type", "asking_price", "cap_rate_in_place"]:
        assert required in fields
    assert fields["cap_rate_in_place"].type.value == "percent"
    assert fields["investment_highlights"].type.value == "list[string]"


def test_field_confidence_applies_skepticism_and_source() -> None:
    fields = {"noi_in_place": 1_000_000.0}
    conf = calculate_om_field_confidence(
        field_name="noi_pro_forma",
        base_confidence=0.9,
        source_section="pro_forma_projections",
        value_type="pro_forma",
        fields=fields,
    )
    # 0.9 * 0.70 * 0.80 * 0.85 ≈ 0.4284
    assert 0.4 < conf < 0.5


def test_document_confidence_penalizes_missing_critical() -> None:
    extracted = [
        OMExtractedField(name="asking_price", value=10_000_000, confidence=0.9),
        OMExtractedField(name="total_sf", value=100_000, confidence=0.9),
    ]
    doc_conf = calculate_om_document_confidence(extracted)
    # Missing most critical fields -> significant penalty
    assert doc_conf < 0.7


@pytest.mark.asyncio
async def test_om_extractor_mock_llm() -> None:
    mock_response = {
        "property_info": {
            "property_name": {"value": "Harbor Point", "confidence": 0.92, "page": 1, "quote": "Harbor Point"},
            "property_type": {"value": "multifamily", "confidence": 0.9, "page": 1, "quote": "Multifamily"}
        },
        "financials_in_place": {
            "noi_in_place": {"value": "$1,200,000", "confidence": 0.9, "source_section": "financial_summary_page", "value_type": "actual"},
            "cap_rate_in_place": {"value": "6.0%", "confidence": 0.88, "source_section": "financial_summary_page", "value_type": "actual"},
            "asking_price": {"value": "$20,000,000", "confidence": 0.9, "source_section": "financial_summary_page", "value_type": "actual"},
        },
        "financials_pro_forma": {
            "noi_pro_forma": {"value": "$1,500,000", "confidence": 0.9, "source_section": "pro_forma_projections", "value_type": "pro_forma"}
        },
        "warnings": ["Pro forma NOI is +25% above in-place"],
        "missing_critical": []
    }

    mock_llm = AsyncMock()
    mock_llm.chat.completions.create = AsyncMock(
        return_value=Mock(choices=[Mock(message=Mock(content=json.dumps(mock_response)))])
    )

    with patch("openai.AsyncOpenAI", return_value=mock_llm):
        with patch("src.extraction.om_extractor.presidio_redact", return_value=lambda x: x):
            extractor = OMExtractor(api_key="test-key")
            extractor.client = mock_llm
            result = await extractor.extract_fields("Sample OM text")

    assert "noi_in_place" in result.fields
    assert result.fields["cap_rate_in_place"].value == 0.06  # normalized percent
    assert result.fields["noi_in_place"].value == 1_200_000.0
    assert 0 < result.overall_confidence <= 0.99
    assert result.warnings


def test_prompt_includes_critical_sections() -> None:
    prompt = build_om_extraction_prompt("Document text")
    assert "IN-PLACE vs PRO FORMA" in prompt
    assert "value_type" in prompt
    assert "investment_highlights" in prompt
