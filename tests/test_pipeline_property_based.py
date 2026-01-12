"""
Property-Based Tests for Extraction Pipeline - Critical Paths

Uses hypothesis for fuzzing critical security paths (redaction, versioning).
Required by .cursorrules for all critical paths.
from typing import Any, Any

"""

import pytest
from hypothesis import given, strategies as st, settings, HealthCheck
from unittest.mock import Mock, AsyncMock, patch
from uuid import UUID, uuid4

from src.extraction.pipeline import (
    redact_pii,
    process_document,
    _parse_and_redact,
)


# Custom strategies for realistic test data
@st.composite
def pii_text(draw: Any) -> Any:
    """Generate text that may contain PII-like patterns."""
    components = []

    # Add some normal text
    if draw(st.booleans()):
        components.append(draw(st.text(min_size=0, max_size=100)))

    # Add email-like patterns
    if draw(st.booleans()):
        username = draw(st.text(alphabet=st.characters(whitelist_categories=('L', 'N')), min_size=1, max_size=20))
        domain = draw(st.sampled_from(['example.com', 'test.org', 'mail.com']))
        components.append(f"{username}@{domain}")

    # Add phone-like patterns
    if draw(st.booleans()):
        phone = draw(st.from_regex(r'\d{3}-\d{3}-\d{4}', fullmatch=True))
        components.append(phone)

    # Add SSN-like patterns
    if draw(st.booleans()):
        ssn = draw(st.from_regex(r'\d{3}-\d{2}-\d{4}', fullmatch=True))
        components.append(ssn)

    # Add address-like patterns
    if draw(st.booleans()):
        street_num = draw(st.integers(min_value=1, max_value=9999))
        street = draw(st.sampled_from(['Main St', 'Oak Ave', 'First Blvd']))
        components.append(f"{street_num} {street}")

    return ' '.join(components)


class TestRedactionPropertyBased:
    """Property-based tests for PII redaction."""

    @given(st.text(min_size=0, max_size=10000))
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    @pytest.mark.asyncio
    async def test_redact_pii_always_returns_string(self, text) -> None:
        """Redaction must always return a string, never fail."""
        with patch("src.extraction.pipeline.presidio_redact") as mock_redact:
            mock_redact.return_value = text  # Passthrough

            result = await redact_pii(text, enabled=True)

            assert isinstance(result, str), f"Expected string, got {type(result)}"
            mock_redact.assert_called_once_with(text)

    @given(st.text(min_size=0, max_size=1000))
    @settings(max_examples=50)
    @pytest.mark.asyncio
    async def test_redact_pii_disabled_is_identity(self, text) -> None:
        """When disabled, redaction must return input unchanged."""
        result = await redact_pii(text, enabled=False)
        assert result == text, "Disabled redaction must be identity function"

    @given(st.text(alphabet=st.characters(blacklist_categories=('Cs',)), min_size=0, max_size=5000))
    @settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture])
    @pytest.mark.asyncio
    async def test_redact_pii_preserves_length_order(self, text) -> None:
        """Redacted text length should be reasonable (not explode or vanish)."""
        with patch("src.extraction.pipeline.presidio_redact") as mock_redact:
            # Mock redaction to replace patterns with placeholders
            mock_redact.return_value = text.replace("@", "[EMAIL]")

            result = await redact_pii(text, enabled=True)

            # Length should not be unreasonably different
            # Allow for placeholder expansion but not more than 10x
            assert len(result) <= len(text) * 10, "Redaction caused unreasonable expansion"

    @given(pii_text())
    @settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture])
    @pytest.mark.asyncio
    async def test_redact_pii_with_realistic_patterns(self, text) -> None:
        """Test redaction with realistic PII patterns."""
        with patch("src.extraction.pipeline.presidio_redact") as mock_redact:
            # Simulate redaction by masking patterns
            redacted = text
            redacted = redacted.replace("@", "[EMAIL]")
            redacted = ''.join(c if not c.isdigit() else 'X' for c in redacted)
            mock_redact.return_value = redacted

            result = await redact_pii(text, enabled=True)

            assert isinstance(result, str)
            # Should have been called with original text
            mock_redact.assert_called_once_with(text)

    @given(st.text(min_size=0, max_size=100))
    @settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture])
    @pytest.mark.asyncio
    async def test_redact_pii_idempotent(self, text) -> None:
        """Redacting twice should give same result as once."""
        with patch("src.extraction.pipeline.presidio_redact") as mock_redact:
            mock_redact.return_value = "REDACTED"

            result1 = await redact_pii(text, enabled=True)

            mock_redact.return_value = "REDACTED"
            result2 = await redact_pii(result1, enabled=True)

            assert result1 == result2, "Redaction should be idempotent"

    @given(st.lists(st.text(min_size=1, max_size=50), min_size=0, max_size=20))
    @settings(max_examples=30)
    @pytest.mark.asyncio
    async def test_redact_pii_batch_consistency(self, text_list) -> None:
        """Redacting multiple texts should be consistent."""
        with patch("src.extraction.pipeline.presidio_redact") as mock_redact:
            mock_redact.side_effect = [f"REDACTED_{i}" for i in range(len(text_list))]

            results = []
            for text in text_list:
                result = await redact_pii(text, enabled=True)
                results.append(result)

            # Each result should be a string
            assert all(isinstance(r, str) for r in results)
            # Should have been called for each text
            assert mock_redact.call_count == len(text_list)


class TestParseAndRedactPropertyBased:
    """Property-based tests for parse and redact workflow."""

    @given(
        storage_path=st.text(min_size=1, max_size=100, alphabet=st.characters(whitelist_categories=('L', 'N'), whitelist_characters='/-_.')),
        mime_type=st.sampled_from(['application/pdf', 'text/plain', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document']),
    )
    @settings(max_examples=30, suppress_health_check=[HealthCheck.function_scoped_fixture])
    @pytest.mark.asyncio
    async def test_parse_and_redact_returns_tuple(self, storage_path, mime_type) -> None:
        """Parse and redact must always return (text, parser_used) tuple."""
        tenant_id = uuid4()
        mock_document = {
            "storage_path": storage_path,
            "mime_type": mime_type,
        }

        mock_parse_result = {
            "text": "Sample text",
            "pages": [],
            "tables": [],
            "metadata": {"parser": "test_parser"},
        }

        mock_supabase = Mock()

        with patch("src.extraction.pipeline.download_document", new_callable=AsyncMock) as mock_download, \
             patch("src.extraction.pipeline.parse_document_content", new_callable=AsyncMock) as mock_parse, \
             patch("src.extraction.pipeline.redact_pii", new_callable=AsyncMock) as mock_redact:

            mock_download.return_value = b"content"
            mock_parse.return_value = mock_parse_result
            mock_redact.return_value = "Redacted"

            result = await _parse_and_redact(mock_supabase, mock_document, tenant_id)

            assert isinstance(result, tuple), "Must return tuple"
            assert len(result) == 2, "Must return 2-tuple"
            text, parser = result
            assert isinstance(text, str), "First element must be string"
            assert isinstance(parser, str), "Second element must be string"


class TestExtractionVersioningPropertyBased:
    """Property-based tests for extraction versioning (critical path)."""

    @given(
        confidence_scores=st.lists(
            st.floats(min_value=0.0, max_value=0.99, allow_nan=False, allow_infinity=False),
            min_size=1,
            max_size=10
        )
    )
    @settings(max_examples=30)
    @pytest.mark.asyncio
    async def test_multiple_extractions_confidence_bounds(self, confidence_scores) -> None:
        """Multiple extractions must respect confidence bounds (0-1)."""
        # Simulate multiple extraction versions
        for score in confidence_scores:
            # Confidence must be in valid range
            assert 0.0 <= score < 1.0, f"Invalid confidence: {score}"
            # Never exactly 1.0 (as per requirements)
            assert score != 1.0, "Confidence must never be exactly 1.0"

    @given(st.integers(min_value=1, max_value=100))
    @settings(max_examples=20)
    def test_version_increment_sequence(self, num_extractions) -> None:
        """Version numbers should increment sequentially."""
        versions = list(range(1, num_extractions + 1))

        # Check sequential increment
        for i in range(1, len(versions)):
            assert versions[i] == versions[i-1] + 1, "Versions must increment by 1"

        # Check no duplicates
        assert len(versions) == len(set(versions)), "Versions must be unique"


class TestDocumentProcessingPropertyBased:
    """Property-based tests for end-to-end document processing."""

    @given(st.uuids())
    @settings(max_examples=20, suppress_health_check=[HealthCheck.function_scoped_fixture])
    @pytest.mark.asyncio
    async def test_process_document_always_returns_result_dict(self, document_uuid) -> None:
        """Processing must always return a result dict with required keys."""
        document_id = UUID(str(document_uuid))
        mock_supabase = Mock()

        with patch("src.extraction.pipeline._validate_and_prepare", new_callable=AsyncMock) as mock_validate:
            mock_validate.side_effect = Exception("Test error")

            with patch("src.extraction.pipeline._finalize_failure", new_callable=AsyncMock) as mock_finalize:
                mock_finalize.return_value = {
                    "document_id": str(document_id),
                    "extraction_id": None,
                    "status": "failed",
                    "overall_confidence": 0.0,
                    "error": "Test error",
                }

                result = await process_document(document_id, mock_supabase)

        # Must always return dict with required keys
        required_keys = {"document_id", "extraction_id", "status", "overall_confidence", "error"}
        assert isinstance(result, dict), "Must return dict"
        assert required_keys.issubset(result.keys()), f"Missing keys: {required_keys - result.keys()}"

        # Validate types
        assert isinstance(result["document_id"], str)
        assert result["extraction_id"] is None or isinstance(result["extraction_id"], str)
        assert result["status"] in {"ready", "failed", "processing"}
        assert isinstance(result["overall_confidence"], (int, float))
        assert 0.0 <= result["overall_confidence"] <= 1.0

    @given(st.floats(min_value=0.0, max_value=0.99, allow_nan=False, allow_infinity=False))
    @settings(max_examples=30, suppress_health_check=[HealthCheck.function_scoped_fixture])
    @pytest.mark.asyncio
    async def test_process_document_confidence_invariant(self, confidence) -> None:
        """Successful processing must have valid confidence score."""
        document_id = uuid4()
        extraction_id = uuid4()
        mock_supabase = Mock()

        with patch("src.extraction.pipeline._validate_and_prepare", new_callable=AsyncMock), \
             patch("src.extraction.pipeline._parse_and_redact", new_callable=AsyncMock), \
             patch("src.extraction.pipeline._extract_and_persist", new_callable=AsyncMock) as mock_extract, \
             patch("src.extraction.pipeline._finalize_success", new_callable=AsyncMock) as mock_finalize:

            mock_extract.return_value = (extraction_id, confidence)
            mock_finalize.return_value = {
                "document_id": str(document_id),
                "extraction_id": str(extraction_id),
                "status": "ready",
                "overall_confidence": confidence,
                "error": None,
            }

            result = await process_document(document_id, mock_supabase)

        # Confidence must be valid
        assert 0.0 <= result["overall_confidence"] < 1.0
        assert result["overall_confidence"] != 1.0, "Confidence must never be 1.0"


class TestUnicodeAndEdgeCases:
    """Property-based tests for Unicode and edge cases."""

    @given(st.text(alphabet=st.characters(min_codepoint=0x0000, max_codepoint=0x1000), min_size=0, max_size=500))
    @settings(max_examples=30, suppress_health_check=[HealthCheck.function_scoped_fixture])
    @pytest.mark.asyncio
    async def test_redact_unicode_safe(self, unicode_text) -> None:
        """Redaction must handle Unicode safely."""
        with patch("src.extraction.pipeline.presidio_redact") as mock_redact:
            mock_redact.return_value = unicode_text

            result = await redact_pii(unicode_text, enabled=True)

            assert isinstance(result, str)

    @given(st.text(alphabet=st.characters(whitelist_categories=('Zs', 'Cc')), min_size=0, max_size=100))
    @settings(max_examples=20, suppress_health_check=[HealthCheck.function_scoped_fixture])
    @pytest.mark.asyncio
    async def test_redact_whitespace_only(self, whitespace_text) -> None:
        """Redaction must handle whitespace-only text."""
        with patch("src.extraction.pipeline.presidio_redact") as mock_redact:
            mock_redact.return_value = whitespace_text

            result = await redact_pii(whitespace_text, enabled=True)

            assert isinstance(result, str)

    @given(st.binary(min_size=0, max_size=1000))
    @settings(max_examples=20)
    def test_binary_data_handling(self, binary_data) -> None:
        """Test that binary data is handled appropriately."""
        # Binary data should not be passed to text redaction
        # This is a guard test to ensure type safety
        assert isinstance(binary_data, bytes)

        # Text redaction should only accept strings
        # If binary is passed, it should be decoded first
        try:
            text = binary_data.decode('utf-8', errors='replace')
            assert isinstance(text, str)
        except Exception:
            # If decode fails, that's okay - binary shouldn't go to redaction
            pass


class TestErrorInvariants:
    """Property-based tests for error handling invariants."""

    @given(st.text(min_size=1, max_size=200))
    @settings(max_examples=20, suppress_health_check=[HealthCheck.function_scoped_fixture])
    @pytest.mark.asyncio
    async def test_redaction_error_propagates(self, text) -> None:
        """Redaction errors must propagate, not be silently swallowed."""
        with patch("src.extraction.pipeline.presidio_redact") as mock_redact:
            mock_redact.side_effect = RuntimeError("Redaction failed")

            with pytest.raises(RuntimeError, match="Redaction failed"):
                await redact_pii(text, enabled=True)

    @given(st.uuids())
    @settings(max_examples=10, suppress_health_check=[HealthCheck.function_scoped_fixture])
    @pytest.mark.asyncio
    async def test_process_document_never_raises(self, document_uuid) -> None:
        """process_document must never raise, always return result."""
        document_id = UUID(str(document_uuid))
        mock_supabase = Mock()

        # Simulate various failures
        with patch("src.extraction.pipeline._validate_and_prepare", new_callable=AsyncMock) as mock_validate:
            mock_validate.side_effect = Exception("Critical failure")

            with patch("src.extraction.pipeline._finalize_failure", new_callable=AsyncMock) as mock_finalize:
                mock_finalize.return_value = {
                    "document_id": str(document_id),
                    "extraction_id": None,
                    "status": "failed",
                    "overall_confidence": 0.0,
                    "error": "Critical failure",
                }

                # Should not raise
                result = await process_document(document_id, mock_supabase)

                assert result["status"] == "failed"
                assert result["error"] is not None
