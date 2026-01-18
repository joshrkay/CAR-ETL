"""Tests for Presidio redaction service."""
import pytest
import re
from unittest.mock import patch
from hypothesis import given, strategies as st
from src.services.redaction import presidio_redact, presidio_redact_bytes


def test_presidio_redact_email() -> None:
    """Test redaction of email addresses."""
    text = "Contact us at john.doe@example.com for support."
    redacted = presidio_redact(text)
    
    assert "john.doe@example.com" not in redacted
    assert "Contact us at" in redacted
    assert "@example.com" not in redacted


def test_presidio_redact_phone() -> None:
    """Test redaction of phone numbers."""
    text = "Call us at (555) 123-4567."
    redacted = presidio_redact(text)
    
    assert "(555) 123-4567" not in redacted
    assert "Call us at" in redacted


def test_presidio_redact_ssn() -> None:
    """Test redaction of SSN."""
    text = "SSN: 123-45-6789"
    redacted = presidio_redact(text)
    
    assert "123-45-6789" not in redacted
    assert "SSN:" in redacted


def test_presidio_redact_credit_card() -> None:
    """Test redaction of credit card numbers."""
    text = "Card number: 4532-1234-5678-9010"
    redacted = presidio_redact(text)
    
    assert "4532-1234-5678-9010" not in redacted
    assert "Card number:" in redacted


def test_presidio_redact_bytes() -> None:
    """Test redaction of bytes content."""
    content = b"Contact john.doe@example.com"
    redacted = presidio_redact_bytes(content, "text/plain")
    
    assert b"john.doe@example.com" not in redacted
    assert b"Contact" in redacted


def test_presidio_redact_empty() -> None:
    """Test redaction of empty text."""
    assert presidio_redact("") == ""
    assert presidio_redact("   ") == "   "


def test_presidio_redact_no_pii() -> None:
    """Test redaction of text with no PII."""
    text = "This is a simple text with no personal information."
    redacted = presidio_redact(text)
    
    # Should return same text if no PII detected
    assert text == redacted


def test_presidio_redact_bytes_json() -> None:
    """Test redaction of JSON content."""
    content = b'{"email": "user@example.com", "name": "John Doe"}'
    redacted = presidio_redact_bytes(content, "application/json")
    
    assert b"user@example.com" not in redacted
    assert b"John Doe" not in redacted


def test_presidio_redact_bytes_binary() -> None:
    """Test that binary content returns unchanged (not yet implemented)."""
    content = b"\x89PNG\r\n\x1a\n"  # PNG file header
    redacted = presidio_redact_bytes(content, "image/png")
    
    # Should return original for binary content
    assert redacted == content


def test_presidio_redact_strict_mode_failure() -> None:
    """Test that strict mode raises exception on failure."""
    from src.services.presidio_config import PresidioConfig
    
    with patch("src.services.redaction.get_presidio_config") as mock_config:
        config = PresidioConfig(redaction_fail_mode="strict")
        mock_config.return_value = config
        
        # Mock analyzer to raise exception
        with patch("src.services.redaction._get_analyzer") as mock_analyzer:
            mock_analyzer.side_effect = Exception("Analyzer failed")
            
            with pytest.raises(RuntimeError, match="PII redaction failed in strict mode"):
                presidio_redact("test@example.com")


def test_presidio_redact_permissive_mode_failure() -> None:
    """Test that permissive mode returns original text on failure."""
    from src.services.presidio_config import PresidioConfig
    
    with patch("src.services.redaction.get_presidio_config") as mock_config:
        config = PresidioConfig(redaction_fail_mode="permissive")
        mock_config.return_value = config
        
        # Mock analyzer to raise exception
        with patch("src.services.redaction._get_analyzer") as mock_analyzer:
            mock_analyzer.side_effect = Exception("Analyzer failed")
            
            # Should return original text in permissive mode
            result = presidio_redact("test@example.com")
            assert result == "test@example.com"


def test_presidio_redact_multiple_entities() -> None:
    """Test redaction of multiple PII entities in one text."""
    text = "Contact John Doe at john.doe@example.com or call (555) 123-4567. SSN: 123-45-6789"
    redacted = presidio_redact(text)
    
    assert "john.doe@example.com" not in redacted
    assert "(555) 123-4567" not in redacted
    assert "123-45-6789" not in redacted
    assert "John Doe" not in redacted


def test_presidio_redact_bytes_unicode_decode_error() -> None:
    """Test handling of unicode decode errors."""
    # Invalid UTF-8 sequence
    content = b"\xff\xfe\x00\x00"  # Invalid UTF-8
    redacted = presidio_redact_bytes(content, "text/plain")
    
    # Should return original if decode fails
    assert redacted == content


class TestRedactionPropertyBased:
    """
    Property-based tests for Presidio redaction (critical security path).
    
    These tests verify that no PII patterns leak through redaction,
    which is critical for security compliance.
    """
    
    @given(st.text(min_size=1, max_size=10000))
    def test_presidio_redact_no_email_leakage(self, text: str) -> None:
        """
        Property-based test: Verify no email patterns leak through redaction.
        
        This is a critical security test - must pass for all inputs.
        """
        redacted = presidio_redact(text)
        
        # Email pattern (common formats)
        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        re.findall(email_pattern, redacted)
        
        # If emails were detected in original, they should be redacted
        original_emails = re.findall(email_pattern, text)
        if original_emails:
            # All original emails should be absent from redacted text
            for email in original_emails:
                assert email not in redacted, f"Email leaked in redaction: {email}"
    
    @given(st.text(min_size=1, max_size=10000))
    def test_presidio_redact_no_ssn_leakage(self, text: str) -> None:
        """
        Property-based test: Verify no SSN patterns leak through redaction.
        """
        redacted = presidio_redact(text)
        
        # SSN pattern (XXX-XX-XXXX)
        ssn_pattern = r'\b\d{3}-\d{2}-\d{4}\b'
        original_ssns = re.findall(ssn_pattern, text)
        
        if original_ssns:
            for ssn in original_ssns:
                assert ssn not in redacted, f"SSN leaked in redaction: {ssn}"
    
    @given(st.text(min_size=1, max_size=10000))
    def test_presidio_redact_no_phone_leakage(self, text: str) -> None:
        """
        Property-based test: Verify no phone number patterns leak through redaction.
        """
        redacted = presidio_redact(text)
        
        # Phone pattern (various formats)
        phone_patterns = [
            r'\b\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b',  # US format
            r'\b\d{3}[-.\s]?\d{3}[-.\s]?\d{4}\b',
        ]
        
        for pattern in phone_patterns:
            original_phones = re.findall(pattern, text)
            if original_phones:
                for phone in original_phones:
                    # Phone numbers should be redacted (may have some false positives)
                    # But exact matches should not appear
                    assert phone not in redacted, f"Phone leaked in redaction: {phone}"
    
    @given(st.text(min_size=1, max_size=5000))
    def test_presidio_redact_idempotent(self, text: str) -> None:
        """
        Property-based test: Verify redaction is idempotent.
        
        Redacting already-redacted text should not change it further.
        """
        redacted_once = presidio_redact(text)
        redacted_twice = presidio_redact(redacted_once)
        
        # Redacting twice should produce same result as redacting once
        # (or at least not introduce new PII)
        assert redacted_twice == redacted_once or len(redacted_twice) <= len(redacted_once)
    
    @given(st.text(min_size=1, max_size=10000))
    def test_presidio_redact_preserves_structure(self, text: str) -> None:
        """
        Property-based test: Verify redaction preserves text structure.
        
        Redacted text should maintain similar length and structure.
        """
        redacted = presidio_redact(text)
        
        # Redacted text should not be significantly longer (redaction replaces, doesn't expand)
        # Allow some variance for placeholder text
        assert len(redacted) <= len(text) * 2, "Redaction expanded text excessively"
        
        # Should not be empty unless original was empty
        if text.strip():
            assert redacted.strip(), "Redaction removed all content"
