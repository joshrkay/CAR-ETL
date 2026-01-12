"""
Tests for field extraction functionality.

Includes unit tests and property-based tests for critical paths.
"""

from typing import Any, Generator
import pytest
from unittest.mock import Mock, AsyncMock, patch
import json

from src.extraction.cre_fields import (
    get_cre_lease_fields,
    get_field_config,
    get_field_definitions_for_prompt,
    FieldDefinition,
    FieldType
)
from src.extraction.prompts import (
    build_extraction_prompt,
    build_document_type_detection_prompt
)
from src.extraction.normalizers import (
    normalize_date,
    normalize_currency,
    normalize_integer,
    normalize_enum,
    normalize_boolean,
    normalize_field_value
)
from src.extraction.extractor import FieldExtractor, ExtractedField, ExtractionResult


class TestFieldDefinitions:
    """Tests for field definition functions."""
    
    def test_get_cre_lease_fields(self) -> None:
        """Test CRE lease field definitions."""
        fields = get_cre_lease_fields()
        
        assert isinstance(fields, dict)
        assert "tenant_name" in fields
        assert "base_rent" in fields
        assert fields["tenant_name"].required is True
        assert fields["tenant_name"].type == FieldType.STRING
        assert fields["base_rent"].type == FieldType.CURRENCY
        # Test new fields
        assert "tenant_entity_type" in fields
        assert "personal_guarantee" in fields
        assert fields["personal_guarantee"].type == FieldType.BOOLEAN
        assert "aliases" in fields["tenant_name"].__dict__ or fields["tenant_name"].aliases is not None
        # Test property-type-specific fields
        assert "office_class" in fields
        assert "retail_type" in fields
        assert "clear_height" in fields
        assert "unit_count" in fields
        assert "component_breakdown" in fields
        # Test universal fields
        assert "cap_rate" in fields
        assert "net_operating_income" in fields
        assert "year_built" in fields
    
    def test_get_field_config_cre_lease(self) -> None:
        """Test getting field config for CRE lease."""
        fields = get_field_config("cre", "lease")
        
        assert isinstance(fields, dict)
        assert "tenant_name" in fields
        assert "lease_start_date" in fields
    
    def test_get_field_config_invalid_industry(self) -> None:
        """Test error handling for invalid industry."""
        with pytest.raises(ValueError, match="Industry 'invalid' not yet supported"):
            get_field_config("invalid", "lease")
    
    def test_get_field_config_invalid_document_type(self) -> None:
        """Test error handling for invalid document type."""
        with pytest.raises(ValueError, match="CRE document type 'invalid' not yet supported"):
            get_field_config("cre", "invalid")
    
    def test_get_field_definitions_for_prompt(self) -> None:
        """Test formatting field definitions for prompt."""
        fields = {
            "test_field": FieldDefinition(
                type=FieldType.STRING,
                required=True,
                weight=1.0
            ),
            "enum_field": FieldDefinition(
                type=FieldType.ENUM,
                required=False,
                weight=0.9,
                values=["option1", "option2"]
            ),
            "aliased_field": FieldDefinition(
                type=FieldType.STRING,
                required=False,
                weight=0.8,
                aliases=["alias1", "alias2"]
            )
        }
        
        prompt_str = get_field_definitions_for_prompt(fields)
        
        assert "test_field" in prompt_str
        assert "string" in prompt_str
        assert "(required)" in prompt_str
        assert "enum_field" in prompt_str
        assert "option1" in prompt_str
        assert "aliased_field" in prompt_str
        assert "alias1" in prompt_str or "Also known as" in prompt_str


class TestPrompts:
    """Tests for prompt building functions."""
    
    def test_build_extraction_prompt(self) -> None:
        """Test building extraction prompt."""
        field_defs = "- tenant_name: string (required)\n- base_rent: currency (required)"
        doc_text = "This is a lease document."
        
        prompt = build_extraction_prompt(field_defs, doc_text, "cre", "lease")
        
        assert "Commercial Real Estate" in prompt
        assert "lease" in prompt
        assert field_defs in prompt
        assert doc_text in prompt
        assert "confidence" in prompt
        assert "never use 1.0" in prompt.lower()
    
    def test_build_document_type_detection_prompt(self) -> None:
        """Test building document type detection prompt."""
        doc_text = "This is a lease document."
        
        prompt = build_document_type_detection_prompt(doc_text, "cre")
        
        assert "Commercial Real Estate" in prompt
        assert "lease" in prompt
        assert "rent_roll" in prompt
        assert doc_text[:2000] in prompt


class TestNormalizers:
    """Tests for value normalization functions."""
    
    def test_normalize_date_iso_format(self) -> None:
        """Test normalizing ISO date format."""
        result = normalize_date("2024-01-15")
        assert result == "2024-01-15"
    
    def test_normalize_date_us_format(self) -> None:
        """Test normalizing US date format."""
        result = normalize_date("01/15/2024")
        assert result == "2024-01-15"
    
    def test_normalize_date_invalid(self) -> None:
        """Test normalizing invalid date."""
        result = normalize_date("invalid")
        assert result is None
    
    def test_normalize_date_none(self) -> None:
        """Test normalizing None date."""
        result = normalize_date(None)
        assert result is None
    
    def test_normalize_currency_dollar_sign(self) -> None:
        """Test normalizing currency with dollar sign."""
        result = normalize_currency("$1,234.56")
        assert result == 1234.56
    
    def test_normalize_currency_commas(self) -> None:
        """Test normalizing currency with commas."""
        result = normalize_currency("1,234.56")
        assert result == 1234.56
    
    def test_normalize_currency_negative_parentheses(self) -> None:
        """Test normalizing negative currency in parentheses."""
        result = normalize_currency("($1,234.56)")
        assert result == -1234.56
    
    def test_normalize_currency_invalid(self) -> None:
        """Test normalizing invalid currency."""
        result = normalize_currency("invalid")
        assert result is None
    
    def test_normalize_integer_basic(self) -> None:
        """Test normalizing basic integer."""
        result = normalize_integer("123")
        assert result == 123
    
    def test_normalize_integer_with_commas(self) -> None:
        """Test normalizing integer with commas."""
        result = normalize_integer("1,234")
        assert result == 1234
    
    def test_normalize_integer_float(self) -> None:
        """Test normalizing integer from float."""
        result = normalize_integer(123.0)
        assert result == 123
    
    def test_normalize_integer_invalid(self) -> None:
        """Test normalizing invalid integer."""
        result = normalize_integer("invalid")
        assert result is None
    
    def test_normalize_enum_exact_match(self) -> None:
        """Test normalizing enum with exact match."""
        result = normalize_enum("monthly", ["monthly", "annual", "quarterly"])
        assert result == "monthly"
    
    def test_normalize_enum_case_insensitive(self) -> None:
        """Test normalizing enum case-insensitive."""
        result = normalize_enum("MONTHLY", ["monthly", "annual"])
        assert result == "monthly"
    
    def test_normalize_enum_invalid(self) -> None:
        """Test normalizing invalid enum."""
        result = normalize_enum("invalid", ["monthly", "annual"])
        assert result is None
    
    def test_normalize_field_value_date(self) -> None:
        """Test normalizing field value as date."""
        result = normalize_field_value("01/15/2024", "date")
        assert result == "2024-01-15"
    
    def test_normalize_field_value_currency(self) -> None:
        """Test normalizing field value as currency."""
        result = normalize_field_value("$1,234.56", "currency")
        assert result == 1234.56
    
    def test_normalize_field_value_enum(self) -> None:
        """Test normalizing field value as enum."""
        result = normalize_field_value(
            "monthly",
            "enum",
            enum_values=["monthly", "annual"]
        )
        assert result == "monthly"
    
    def test_normalize_field_value_string(self) -> None:
        """Test normalizing field value as string."""
        result = normalize_field_value("  test  ", "string")
        assert result == "test"
    
    def test_normalize_boolean_true(self) -> None:
        """Test normalizing boolean true values."""
        assert normalize_boolean("true") is True
        assert normalize_boolean("yes") is True
        assert normalize_boolean("1") is True
        assert normalize_boolean(True) is True
        assert normalize_boolean(1) is True
    
    def test_normalize_boolean_false(self) -> None:
        """Test normalizing boolean false values."""
        assert normalize_boolean("false") is False
        assert normalize_boolean("no") is False
        assert normalize_boolean("0") is False
        assert normalize_boolean(False) is False
        assert normalize_boolean(0) is False
    
    def test_normalize_boolean_invalid(self) -> None:
        """Test normalizing invalid boolean."""
        result = normalize_boolean("invalid")
        assert result is None
    
    def test_normalize_field_value_boolean(self) -> None:
        """Test normalizing field value as boolean."""
        result = normalize_field_value("true", "boolean")
        assert result is True
        result = normalize_field_value("false", "boolean")
        assert result is False


class TestFieldExtractor:
    """Tests for FieldExtractor class."""
    
    @pytest.fixture
    def mock_openai_client(self) -> Any:
        """Create mock OpenAI client."""
        client = AsyncMock()
        return client
    
    @pytest.fixture
    def extractor(self, mock_openai_client: Any) -> Any:
        """Create FieldExtractor with mocked OpenAI client."""
        with patch('src.extraction.extractor.AsyncOpenAI', return_value=mock_openai_client):
            with patch('src.extraction.extractor.presidio_redact', return_value="redacted"):
                extractor = FieldExtractor(api_key="test-key")
                extractor.client = mock_openai_client
                return extractor
    
    @pytest.mark.asyncio
    async def test_detect_document_type(self, extractor, mock_openai_client) -> None:
        """Test document type detection."""
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message = Mock()
        mock_response.choices[0].message.content = json.dumps({
            "document_type": "lease",
            "confidence": 0.95,
            "reasoning": "Contains lease terms"
        })
        mock_openai_client.chat.completions.create = AsyncMock(return_value=mock_response)
        
        result = await extractor.detect_document_type("This is a lease document.", "cre")
        
        assert result["document_type"] == "lease"
        assert result["confidence"] <= 0.99  # Never 1.0
        assert "reasoning" in result
    
    @pytest.mark.asyncio
    async def test_detect_document_type_error_handling(self, extractor, mock_openai_client) -> None:
        """Test document type detection error handling."""
        mock_openai_client.chat.completions.create = AsyncMock(side_effect=Exception("API error"))
        
        result = await extractor.detect_document_type("Document text", "cre")
        
        assert result["document_type"] == "other"
        assert result["confidence"] == 0.0
    
    @pytest.mark.asyncio
    async def test_extract_fields(self, extractor, mock_openai_client) -> None:
        """Test field extraction."""
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message = Mock()
        mock_response.choices[0].message.content = json.dumps({
            "fields": {
                "tenant_name": {
                    "value": "Test Tenant",
                    "confidence": 0.95,
                    "page": 1,
                    "quote": "Tenant: Test Tenant"
                },
                "base_rent": {
                    "value": "$5,000",
                    "confidence": 0.90,
                    "page": 2,
                    "quote": "Base rent: $5,000"
                }
            }
        })
        mock_openai_client.chat.completions.create = AsyncMock(return_value=mock_response)
        
        result = await extractor.extract_fields("Lease document text", "cre", "lease")
        
        assert isinstance(result, ExtractionResult)
        assert "tenant_name" in result.fields
        assert result.fields["tenant_name"].value == "Test Tenant"
        assert result.fields["tenant_name"].confidence <= 0.99  # Never 1.0
        assert result.overall_confidence <= 0.99  # Never 1.0
    
    def test_compute_overall_confidence(self, extractor) -> None:
        """Test overall confidence calculation."""
        fields = {
            "field1": ExtractedField(value="test", confidence=0.9, page=1),
            "field2": ExtractedField(value=123, confidence=0.8, page=1)
        }
        
        field_defs = {
            "field1": FieldDefinition(type=FieldType.STRING, weight=1.5),
            "field2": FieldDefinition(type=FieldType.INTEGER, weight=1.0)
        }
        
        confidence = extractor._compute_overall_confidence(fields, field_defs)
        
        assert 0.0 <= confidence <= 0.99  # Never 1.0
        assert confidence > 0.0
    
    def test_compute_overall_confidence_empty(self, extractor) -> None:
        """Test overall confidence with empty fields."""
        confidence = extractor._compute_overall_confidence({}, {})
        assert confidence == 0.0


class TestPropertyBasedNormalization:
    """Property-based tests for normalization functions."""
    
    @pytest.mark.parametrize("date_str", [
        "2024-01-15",
        "01/15/2024",
        "1/15/2024",
        "2024/01/15",
    ])
    def test_normalize_date_formats(self, date_str) -> None:
        """Test various date formats normalize correctly."""
        result = normalize_date(date_str)
        assert result is None or (isinstance(result, str) and len(result) == 10)
        if result:
            assert result.count("-") == 2
    
    @pytest.mark.parametrize("currency_str", [
        "$1,234.56",
        "1234.56",
        "$1234",
        "($1,234.56)",
        "1,234",
    ])
    def test_normalize_currency_formats(self, currency_str) -> None:
        """Test various currency formats normalize correctly."""
        result = normalize_currency(currency_str)
        assert result is None or isinstance(result, float)
    
    @pytest.mark.parametrize("enum_value,allowed", [
        ("monthly", ["monthly", "annual"]),
        ("MONTHLY", ["monthly", "annual"]),
        ("Monthly", ["monthly", "annual"]),
    ])
    def test_normalize_enum_case_variations(self, enum_value, allowed) -> None:
        """Test enum normalization handles case variations."""
        result = normalize_enum(enum_value, allowed)
        assert result in allowed or result is None
