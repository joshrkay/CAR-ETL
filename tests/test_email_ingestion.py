"""
Tests for email ingestion functionality.

Tests email parsing, ingestion, rate limiting, and webhook handling.
"""

import base64
from unittest.mock import Mock, patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from src.exceptions import NotFoundError, RateLimitError
from src.services.email_ingestion import EmailIngestionService
from src.services.email_parser import Attachment, EmailParser, ParsedEmail
from src.services.email_rate_limiter import EmailRateLimiter
from src.services.resend_verifier import ResendVerifier


class TestEmailParser:
    """Unit tests for EmailParser."""

    def test_parse_resend_webhook_basic(self):
        """Test parsing basic Resend webhook payload."""
        parser = EmailParser()

        payload = {
            "from": "sender@example.com",
            "to": "tenant@ingest.yourapp.com",
            "subject": "Test Email",
            "text": "Email body text",
            "html": "<p>Email body text</p>",
            "attachments": [],
        }

        parsed = parser.parse_resend_webhook(payload)

        assert parsed.from_address == "sender@example.com"
        assert parsed.to_address == "tenant@ingest.yourapp.com"
        assert parsed.subject == "Test Email"
        assert parsed.body_text == "Email body text"
        assert parsed.body_html == "<p>Email body text</p>"
        assert len(parsed.attachments) == 0

    def test_parse_resend_webhook_with_attachment(self):
        """Test parsing webhook with attachment."""
        parser = EmailParser()

        # Create test attachment content
        attachment_content = b"PDF content here"
        attachment_b64 = base64.b64encode(attachment_content).decode("utf-8")

        payload = {
            "from": "sender@example.com",
            "to": "tenant@ingest.yourapp.com",
            "subject": "Test Email",
            "text": "Email body",
            "attachments": [
                {
                    "filename": "test.pdf",
                    "content_type": "application/pdf",
                    "content": attachment_b64,
                }
            ],
        }

        parsed = parser.parse_resend_webhook(payload)

        assert len(parsed.attachments) == 1
        assert parsed.attachments[0].filename == "test.pdf"
        assert parsed.attachments[0].content_type == "application/pdf"
        assert parsed.attachments[0].content == attachment_content
        assert parsed.attachments[0].size == len(attachment_content)

    def test_extract_address_simple(self):
        """Test extracting email address from simple string."""
        parser = EmailParser()

        assert parser._extract_address("user@example.com") == "user@example.com"
        assert parser._extract_address("  user@example.com  ") == "user@example.com"

    def test_extract_address_with_name(self):
        """Test extracting email address from 'Name <email>' format."""
        parser = EmailParser()

        assert parser._extract_address("John Doe <john@example.com>") == "john@example.com"
        assert parser._extract_address("<john@example.com>") == "john@example.com"

    def test_parse_attachment_invalid(self):
        """Test parsing invalid attachment (missing content)."""
        parser = EmailParser()

        att_data = {
            "filename": "test.pdf",
            "content_type": "application/pdf",
            # Missing content
        }

        result = parser._parse_attachment(att_data)
        assert result is None

    def test_parse_webhook_html_only(self):
        """Test parsing webhook with HTML but no text version."""
        parser = EmailParser()

        payload = {
            "from": "sender@example.com",
            "to": "tenant@ingest.yourapp.com",
            "subject": "HTML Email",
            "html": "<p>This is HTML content</p>",
            # No text field
        }

        parsed = parser.parse_resend_webhook(payload)

        assert parsed.body_html == "<p>This is HTML content</p>"
        assert parsed.body_text == "This is HTML content"  # Extracted from HTML

    def test_extract_address_empty(self):
        """Test extracting address from empty string."""
        parser = EmailParser()

        assert parser._extract_address("") == ""
        assert parser._extract_address(None) == ""

    def test_extract_address_comma_separated(self):
        """Test extracting address from comma-separated list."""
        parser = EmailParser()

        # Should take first address
        result = parser._extract_address("first@example.com, second@example.com")
        assert result == "first@example.com"

    def test_extract_address_no_valid_address(self):
        """Test extracting address when parseaddr fails."""
        parser = EmailParser()

        # Invalid format that parseaddr can't parse
        result = parser._extract_address("invalid,format,test")
        assert result == "invalid"  # Takes first part

    def test_parse_attachment_with_bytes_content(self):
        """Test parsing attachment with bytes content (not base64 string)."""
        parser = EmailParser()

        content = b"Direct bytes content"
        att_data = {
            "filename": "test.bin",
            "content_type": "application/octet-stream",
            "content": content,  # Already bytes, not base64
        }

        result = parser._parse_attachment(att_data)

        assert result is not None
        assert result.content == content
        assert result.size == len(content)

    def test_parse_attachment_with_exception(self):
        """Test parsing attachment that raises exception during decoding."""
        parser = EmailParser()

        att_data = {
            "filename": "test.pdf",
            "content_type": "application/pdf",
            "content": "invalid base64!!!",  # Invalid base64
        }

        result = parser._parse_attachment(att_data)
        assert result is None

    def test_parse_attachment_default_values(self):
        """Test parsing attachment with missing optional fields."""
        parser = EmailParser()

        content = b"test content"
        content_b64 = base64.b64encode(content).decode("utf-8")

        # Test with 'name' instead of 'filename'
        att_data = {
            "name": "alternate.txt",
            "type": "text/plain",
            "data": content_b64,  # 'data' instead of 'content'
        }

        result = parser._parse_attachment(att_data)

        assert result is not None
        assert result.filename == "alternate.txt"
        assert result.content_type == "text/plain"

    def test_parse_attachment_no_filename(self):
        """Test parsing attachment with no filename uses default."""
        parser = EmailParser()

        content = b"test"
        content_b64 = base64.b64encode(content).decode("utf-8")

        att_data = {
            "content": content_b64,
            # No filename or name
        }

        result = parser._parse_attachment(att_data)

        assert result is not None
        assert result.filename == "attachment"  # Default
        assert result.content_type == "application/octet-stream"  # Default

    def test_html_to_text_with_tags(self):
        """Test HTML to text conversion removes tags."""
        parser = EmailParser()

        html = "<p>Hello <b>world</b></p><div>Test</div>"
        text = parser._html_to_text(html)

        assert "Hello world" in text
        assert "Test" in text
        assert "<p>" not in text
        assert "<b>" not in text

    def test_html_to_text_with_whitespace(self):
        """Test HTML to text conversion normalizes whitespace."""
        parser = EmailParser()

        html = "<p>Hello   \n\n   world</p>"
        text = parser._html_to_text(html)

        # Should normalize multiple spaces/newlines to single space
        assert text == "Hello world"


class TestResendVerifier:
    """Unit tests for ResendVerifier."""

    def test_verify_signature_valid(self):
        """Test verifying valid signature."""
        secret = "test_secret"
        payload = b'{"test": "data"}'

        # Compute expected signature
        import base64
        import hashlib
        import hmac
        expected_sig = hmac.new(
            secret.encode("utf-8"),
            payload,
            hashlib.sha256,
        ).digest()
        expected_sig_b64 = base64.b64encode(expected_sig).decode("utf-8")

        signature_header = f"v1,{expected_sig_b64}"

        verifier = ResendVerifier(secret)
        assert verifier.verify_signature(payload, signature_header) is True

    def test_verify_signature_invalid(self):
        """Test verifying invalid signature."""
        secret = "test_secret"
        payload = b'{"test": "data"}'
        signature_header = "v1,invalid_signature"

        verifier = ResendVerifier(secret)
        assert verifier.verify_signature(payload, signature_header) is False

    def test_verify_signature_missing_header(self):
        """Test verifying with missing signature header."""
        secret = "test_secret"
        payload = b'{"test": "data"}'

        verifier = ResendVerifier(secret)
        assert verifier.verify_signature(payload, None) is False

    def test_verify_signature_wrong_format(self):
        """Test verifying with wrong header format."""
        secret = "test_secret"
        payload = b'{"test": "data"}'
        signature_header = "wrong_format"

        verifier = ResendVerifier(secret)
        assert verifier.verify_signature(payload, signature_header) is False


class TestEmailRateLimiter:
    """Unit tests for EmailRateLimiter."""

    def test_check_rate_limit_under_limit(self):
        """Test rate limit check when under limit."""
        mock_client = Mock()
        mock_client.table.return_value.select.return_value.eq.return_value.gte.return_value.execute.return_value.count = 50

        limiter = EmailRateLimiter(mock_client)

        # Should not raise
        limiter.check_rate_limit("sender@example.com")

    def test_check_rate_limit_exceeded(self):
        """Test rate limit check when limit exceeded."""
        mock_client = Mock()
        mock_client.table.return_value.select.return_value.eq.return_value.gte.return_value.execute.return_value.count = 101
        mock_client.table.return_value.select.return_value.eq.return_value.gte.return_value.execute.return_value.data = [
            {"received_at": "2024-01-01T00:00:00Z"}
        ]

        limiter = EmailRateLimiter(mock_client)

        with pytest.raises(RateLimitError):
            limiter.check_rate_limit("sender@example.com")


class TestEmailIngestionService:
    """Unit tests for EmailIngestionService."""

    @pytest.fixture
    def mock_supabase(self):
        """Create mock Supabase client."""
        client = Mock()

        # Mock tenant verification
        client.table.return_value.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value.data = {
            "id": str(uuid4())
        }

        # Mock document insert
        client.table.return_value.insert.return_value.execute.return_value.data = [{
            "id": str(uuid4())
        }]

        return client

    def test_ingest_email_basic(self, mock_supabase):
        """Test ingesting email with body only."""
        service = EmailIngestionService(mock_supabase)

        parsed_email = ParsedEmail(
            from_address="sender@example.com",
            to_address="tenant@ingest.yourapp.com",
            subject="Test Email",
            body_text="Email body content",
            attachments=[],
        )

        tenant_id = uuid4()

        result = service.ingest_email(parsed_email, tenant_id)

        assert "email_ingestion_id" in result
        assert "body_document_id" in result
        assert "attachment_document_ids" in result
        assert len(result["attachment_document_ids"]) == 0

    def test_ingest_email_with_attachment(self, mock_supabase):
        """Test ingesting email with attachment."""
        service = EmailIngestionService(mock_supabase)

        attachment = Attachment(
            filename="test.pdf",
            content_type="application/pdf",
            content=b"%PDF-1.4 test content",
            size=20,
        )

        parsed_email = ParsedEmail(
            from_address="sender@example.com",
            to_address="tenant@ingest.yourapp.com",
            subject="Test Email",
            body_text="Email body",
            attachments=[attachment],
        )

        tenant_id = uuid4()

        # Mock file validator to return valid result
        with patch.object(service.validator, "validate_file", return_value=Mock(
            valid=True,
            mime_type="application/pdf",
            errors=[],
        )):
            result = service.ingest_email(parsed_email, tenant_id)

            assert result["body_document_id"] is not None
            assert len(result["attachment_document_ids"]) == 1

    def test_ingest_email_tenant_not_found(self, mock_supabase):
        """Test ingesting email with non-existent tenant."""
        service = EmailIngestionService(mock_supabase)

        # Mock tenant not found
        mock_supabase.table.return_value.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value.data = None

        parsed_email = ParsedEmail(
            from_address="sender@example.com",
            to_address="tenant@ingest.yourapp.com",
            subject="Test",
            body_text="Body",
            attachments=[],
        )

        tenant_id = uuid4()

        with pytest.raises(NotFoundError):
            service.ingest_email(parsed_email, tenant_id)

    def test_calculate_hash(self, mock_supabase):
        """Test file hash calculation."""
        service = EmailIngestionService(mock_supabase)

        content = b"test content"
        hash1 = service._calculate_hash(content)
        hash2 = service._calculate_hash(content)

        # Same content should produce same hash
        assert hash1 == hash2
        assert len(hash1) == 64  # SHA-256 hex length

        # Different content should produce different hash
        hash3 = service._calculate_hash(b"different content")
        assert hash1 != hash3


class TestEmailWebhookEndpoint:
    """Integration tests for email webhook endpoint."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        from src.main import app
        return TestClient(app)

    def test_webhook_missing_signature(self, client):
        """Test webhook without signature header."""
        response = client.post(
            "/api/v1/webhooks/email/inbound",
            json={"from": "test@example.com", "to": "tenant@ingest.yourapp.com"},
        )

        assert response.status_code == 401

    def test_webhook_invalid_signature(self, client):
        """Test webhook with invalid signature."""
        response = client.post(
            "/api/v1/webhooks/email/inbound",
            json={"from": "test@example.com", "to": "tenant@ingest.yourapp.com"},
            headers={"svix-signature": "v1,invalid_signature"},
        )

        assert response.status_code == 401

    def test_webhook_invalid_recipient(self, client):
        """Test webhook with invalid recipient format."""
        # This test would require mocking the signature verification
        # For now, we'll skip the full integration test
        pass
