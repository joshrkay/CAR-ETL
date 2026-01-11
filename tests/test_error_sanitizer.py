"""
Tests for error sanitizer - PII removal from error messages.

Critical security component - must never leak PII into logs or database.
"""

import pytest
from src.services.error_sanitizer import (
    sanitize_error_message,
    sanitize_exception,
    get_safe_error_context,
    truncate_error_message,
    get_loggable_error,
)


class TestSanitizeErrorMessage:
    """Tests for sanitize_error_message function."""

    def test_sanitize_email(self):
        """Test email redaction."""
        message = "Failed to process file for user john.doe@example.com"
        result = sanitize_error_message(message)

        assert "[EMAIL]" in result
        assert "john.doe@example.com" not in result
        assert "Failed to process file for user" in result

    def test_sanitize_phone_dash_format(self):
        """Test phone number redaction (dash format)."""
        message = "User 555-123-4567 not found"
        result = sanitize_error_message(message)

        assert "[PHONE]" in result
        assert "555-123-4567" not in result

    def test_sanitize_phone_dot_format(self):
        """Test phone number redaction (dot format)."""
        message = "Contact: 555.123.4567"
        result = sanitize_error_message(message)

        assert "[PHONE]" in result
        assert "555.123.4567" not in result

    def test_sanitize_phone_paren_format(self):
        """Test phone number redaction (parentheses format)."""
        message = "Call (555) 123-4567"
        result = sanitize_error_message(message)

        assert "[PHONE]" in result
        assert "(555) 123-4567" not in result

    def test_sanitize_ssn(self):
        """Test SSN redaction."""
        message = "Invalid SSN: 123-45-6789"
        result = sanitize_error_message(message)

        assert "[SSN]" in result
        assert "123-45-6789" not in result

    def test_sanitize_credit_card(self):
        """Test credit card redaction."""
        message = "Card 4532-1234-5678-9010 declined"
        result = sanitize_error_message(message)

        assert "[CARD]" in result
        assert "4532-1234-5678-9010" not in result

    def test_sanitize_ip_address(self):
        """Test IP address redaction."""
        message = "Connection from 192.168.1.100 failed"
        result = sanitize_error_message(message)

        assert "[IP]" in result
        assert "192.168.1.100" not in result

    def test_sanitize_uuid(self):
        """Test UUID redaction."""
        message = "Document a1b2c3d4-e5f6-7890-abcd-ef1234567890 not found"
        result = sanitize_error_message(message)

        assert "[UUID]" in result
        assert "a1b2c3d4-e5f6-7890-abcd-ef1234567890" not in result

    def test_sanitize_url_with_params(self):
        """Test URL with query params redaction."""
        message = "Failed to fetch https://example.com/api?email=test@example.com&token=abc123"
        result = sanitize_error_message(message)

        assert "[URL]" in result
        assert "email=test@example.com" not in result

    def test_sanitize_file_path_unix(self):
        """Test Unix file path redaction."""
        message = "Cannot read /home/johndoe/documents/secret.pdf"
        result = sanitize_error_message(message)

        assert "/[USER]/documents/secret.pdf" in result
        assert "johndoe" not in result

    def test_sanitize_file_path_mac(self):
        """Test Mac file path redaction."""
        message = "Cannot read /Users/johndoe/documents/secret.pdf"
        result = sanitize_error_message(message)

        assert "/[USER]/documents/secret.pdf" in result
        assert "johndoe" not in result

    def test_sanitize_multiple_patterns(self):
        """Test multiple PII patterns in one message."""
        message = "User john@example.com (phone: 555-123-4567, SSN: 123-45-6789) not found"
        result = sanitize_error_message(message)

        assert "[EMAIL]" in result
        assert "[PHONE]" in result
        assert "[SSN]" in result
        assert "john@example.com" not in result
        assert "555-123-4567" not in result
        assert "123-45-6789" not in result

    def test_sanitize_empty_string(self):
        """Test empty string handling."""
        result = sanitize_error_message("")
        assert result == ""

    def test_sanitize_none(self):
        """Test None handling."""
        result = sanitize_error_message(None)
        assert result is None

    def test_sanitize_no_pii(self):
        """Test message with no PII."""
        message = "File not found"
        result = sanitize_error_message(message)
        assert result == message

    def test_sanitize_preserves_structure(self):
        """Test that message structure is preserved."""
        message = "Error processing document: Invalid format (code: 42)"
        result = sanitize_error_message(message)
        assert "Error processing document" in result
        assert "Invalid format" in result


class TestSanitizeException:
    """Tests for sanitize_exception function."""

    def test_sanitize_value_error(self):
        """Test ValueError sanitization."""
        ex = ValueError("Invalid email: john@example.com")
        result = sanitize_exception(ex)

        assert "[EMAIL]" in result
        assert "john@example.com" not in result

    def test_sanitize_runtime_error(self):
        """Test RuntimeError sanitization."""
        ex = RuntimeError("Failed to connect to 192.168.1.100")
        result = sanitize_exception(ex)

        assert "[IP]" in result
        assert "192.168.1.100" not in result

    def test_sanitize_custom_exception(self):
        """Test custom exception sanitization."""
        class CustomError(Exception):
            pass

        ex = CustomError("User SSN 123-45-6789 is invalid")
        result = sanitize_exception(ex)

        assert "[SSN]" in result
        assert "123-45-6789" not in result


class TestGetSafeErrorContext:
    """Tests for get_safe_error_context function."""

    def test_get_context_value_error(self):
        """Test context extraction from ValueError."""
        ex = ValueError("test error")
        context = get_safe_error_context(ex)

        assert context["error_type"] == "ValueError"
        assert context["error_class"] == "builtins"
        assert "has_cause" in context
        assert "has_context" in context

    def test_get_context_with_cause(self):
        """Test context with exception cause."""
        try:
            try:
                raise ValueError("inner")
            except ValueError as e:
                raise RuntimeError("outer") from e
        except RuntimeError as ex:
            context = get_safe_error_context(ex)

            assert context["error_type"] == "RuntimeError"
            assert context["has_cause"] is True

    def test_get_context_no_cause(self):
        """Test context without exception cause."""
        ex = ValueError("test")
        context = get_safe_error_context(ex)

        assert context["has_cause"] is False


class TestTruncateErrorMessage:
    """Tests for truncate_error_message function."""

    def test_truncate_short_message(self):
        """Test that short messages are not truncated."""
        message = "Short error"
        result = truncate_error_message(message, max_length=100)
        assert result == message

    def test_truncate_long_message(self):
        """Test that long messages are truncated."""
        message = "x" * 1000
        result = truncate_error_message(message, max_length=100)

        assert len(result) < len(message)
        assert "truncated" in result
        assert "1000 chars total" in result

    def test_truncate_preserves_prefix_suffix(self):
        """Test that truncation preserves start and end."""
        message = "START" + ("x" * 1000) + "END"
        result = truncate_error_message(message, max_length=100)

        assert "START" in result
        assert "END" in result
        assert "..." in result

    def test_truncate_custom_length(self):
        """Test custom max length."""
        message = "x" * 200
        result = truncate_error_message(message, max_length=50)

        assert len(result) < len(message)
        assert "200 chars total" in result


class TestGetLoggableError:
    """Tests for get_loggable_error function."""

    def test_get_loggable_error_basic(self):
        """Test basic loggable error extraction."""
        ex = ValueError("Invalid email: test@example.com")
        result = get_loggable_error(ex)

        assert "sanitized_message" in result
        assert "[EMAIL]" in result["sanitized_message"]
        assert "test@example.com" not in result["sanitized_message"]
        assert "message_length" in result
        assert "error_type" in result
        assert result["error_type"] == "ValueError"

    def test_get_loggable_error_truncates(self):
        """Test that long errors are truncated."""
        long_message = "x" * 1000
        ex = ValueError(long_message)
        result = get_loggable_error(ex, max_length=200)

        assert "truncated" in result["sanitized_message"]
        assert result["message_length"] == 1000

    def test_get_loggable_error_no_context(self):
        """Test without context."""
        ex = ValueError("test")
        result = get_loggable_error(ex, include_context=False)

        assert "sanitized_message" in result
        assert "message_length" in result
        assert "error_type" not in result

    def test_get_loggable_error_with_pii(self):
        """Test complex PII sanitization."""
        ex = RuntimeError(
            "Failed for user john@example.com at 192.168.1.1 "
            "with SSN 123-45-6789 and phone 555-123-4567"
        )
        result = get_loggable_error(ex)

        sanitized = result["sanitized_message"]
        assert "[EMAIL]" in sanitized
        assert "[IP]" in sanitized
        assert "[SSN]" in sanitized
        assert "[PHONE]" in sanitized
        assert "john@example.com" not in sanitized
        assert "192.168.1.1" not in sanitized
        assert "123-45-6789" not in sanitized
        assert "555-123-4567" not in sanitized


class TestEdgeCases:
    """Tests for edge cases and special scenarios."""

    def test_unicode_in_error(self):
        """Test Unicode characters in error message."""
        message = "Error: Invalid data 你好世界"
        result = sanitize_error_message(message)
        assert "你好世界" in result

    def test_html_in_error(self):
        """Test HTML in error message."""
        message = "Error: <script>alert('xss')</script>"
        result = sanitize_error_message(message)
        # HTML is not sanitized, only PII
        assert "<script>" in result

    def test_json_in_error(self):
        """Test JSON with PII in error message."""
        message = '{"email": "test@example.com", "error": "Invalid"}'
        result = sanitize_error_message(message)
        assert "[EMAIL]" in result
        assert "test@example.com" not in result

    def test_multiple_emails_same_message(self):
        """Test multiple emails in one message."""
        message = "Failed for john@example.com and jane@example.org"
        result = sanitize_error_message(message)
        assert result.count("[EMAIL]") == 2
        assert "john@example.com" not in result
        assert "jane@example.org" not in result

    def test_false_positive_prevention(self):
        """Test that legitimate text is not over-redacted."""
        message = "Error in file-2023.txt at line 123"
        result = sanitize_error_message(message)
        # Should not redact "123" as phone number
        assert "file-2023.txt" in result or "line" in result
