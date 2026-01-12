"""
Unit Tests for File Validator Service

Tests include:
- Magic byte validation
- Office document structural validation
- Size limit enforcement
- Malicious file detection
- Property-based fuzzing tests
"""

import zipfile
from io import BytesIO
from src.services.file_validator import (
    FileValidator,
    ValidationResult,
    validate_file_with_tenant_config,
)


class TestMagicByteValidation:
    """Test magic byte verification for various file types."""

    def test_valid_pdf(self) -> None:
        """Valid PDF with correct magic bytes."""
        content = b"%PDF-1.4\n%\xE2\xE3\xCF\xD3\n"
        validator = FileValidator()
        result = validator.validate_file(content, "application/pdf")
        
        assert result.valid is True
        assert result.mime_type == "application/pdf"
        assert result.file_size == len(content)
        assert len(result.errors) == 0

    def test_valid_png(self) -> None:
        """Valid PNG with correct magic bytes."""
        content = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR"
        validator = FileValidator()
        result = validator.validate_file(content, "image/png")
        
        assert result.valid is True
        assert result.mime_type == "image/png"
        assert len(result.errors) == 0

    def test_valid_jpeg(self) -> None:
        """Valid JPEG with correct magic bytes."""
        content = b"\xff\xd8\xff\xe0\x00\x10JFIF"
        validator = FileValidator()
        result = validator.validate_file(content, "image/jpeg")
        
        assert result.valid is True
        assert result.mime_type == "image/jpeg"
        assert len(result.errors) == 0

    def test_valid_text_plain(self) -> None:
        """Text files have no magic byte requirements."""
        content = b"This is plain text content"
        validator = FileValidator()
        result = validator.validate_file(content, "text/plain")
        
        assert result.valid is True
        assert result.mime_type == "text/plain"
        assert len(result.errors) == 0

    def test_valid_csv(self) -> None:
        """CSV files have no magic byte requirements."""
        content = b"col1,col2,col3\nval1,val2,val3"
        validator = FileValidator()
        result = validator.validate_file(content, "text/csv")
        
        assert result.valid is True
        assert result.mime_type == "text/csv"
        assert len(result.errors) == 0

    def test_invalid_magic_bytes_pdf_as_jpeg(self) -> None:
        """PDF disguised as JPEG should fail."""
        content = b"%PDF-1.4\n%\xE2\xE3\xCF\xD3\n"
        validator = FileValidator()
        result = validator.validate_file(content, "image/jpeg")
        
        assert result.valid is False
        assert "Magic bytes do not match" in result.errors[0]

    def test_invalid_magic_bytes_text_as_pdf(self) -> None:
        """Text file disguised as PDF should fail."""
        content = b"This is not a PDF"
        validator = FileValidator()
        result = validator.validate_file(content, "application/pdf")
        
        assert result.valid is False
        assert "Magic bytes do not match" in result.errors[0]

    def test_empty_file(self) -> None:
        """Empty files should fail validation."""
        content = b""
        validator = FileValidator()
        result = validator.validate_file(content, "application/pdf")
        
        assert result.valid is False
        assert any("size" in error.lower() or "magic" in error.lower() for error in result.errors)


class TestOfficeDocumentValidation:
    """Test Office Open XML document validation."""

    def _create_valid_docx(self) -> bytes:
        """Create a minimal valid DOCX file."""
        buffer = BytesIO()
        with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            # Add [Content_Types].xml
            content_types = '''<?xml version="1.0" encoding="UTF-8"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
    <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
    <Default Extension="xml" ContentType="application/xml"/>
    <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
</Types>'''
            zip_file.writestr('[Content_Types].xml', content_types)
            
            # Add minimal document.xml
            zip_file.writestr('word/document.xml', '<?xml version="1.0"?><document/>')
        
        return buffer.getvalue()

    def _create_valid_xlsx(self) -> bytes:
        """Create a minimal valid XLSX file."""
        buffer = BytesIO()
        with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            # Add [Content_Types].xml
            content_types = '''<?xml version="1.0" encoding="UTF-8"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
    <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
    <Default Extension="xml" ContentType="application/xml"/>
    <Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
</Types>'''
            zip_file.writestr('[Content_Types].xml', content_types)
            
            # Add minimal workbook.xml
            zip_file.writestr('xl/workbook.xml', '<?xml version="1.0"?><workbook/>')
        
        return buffer.getvalue()

    def test_valid_docx(self) -> None:
        """Valid DOCX with correct structure."""
        content = self._create_valid_docx()
        validator = FileValidator()
        result = validator.validate_file(
            content,
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        )
        
        assert result.valid is True
        assert len(result.errors) == 0

    def test_valid_xlsx(self) -> None:
        """Valid XLSX with correct structure."""
        content = self._create_valid_xlsx()
        validator = FileValidator()
        result = validator.validate_file(
            content,
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        
        assert result.valid is True
        assert len(result.errors) == 0

    def test_docx_missing_content_types(self) -> None:
        """DOCX without [Content_Types].xml should fail."""
        buffer = BytesIO()
        with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            zip_file.writestr('word/document.xml', '<?xml version="1.0"?><document/>')
        
        content = buffer.getvalue()
        validator = FileValidator()
        result = validator.validate_file(
            content,
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        )
        
        assert result.valid is False
        assert any("[Content_Types].xml" in error for error in result.errors)

    def test_docx_wrong_content_type(self) -> None:
        """DOCX with XLSX content type should fail."""
        buffer = BytesIO()
        with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            # Add [Content_Types].xml with XLSX content type
            content_types = '''<?xml version="1.0" encoding="UTF-8"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
    <Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
</Types>'''
            zip_file.writestr('[Content_Types].xml', content_types)
        
        content = buffer.getvalue()
        validator = FileValidator()
        result = validator.validate_file(
            content,
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        )
        
        assert result.valid is False
        assert any("Content types do not match" in error for error in result.errors)

    def test_corrupted_zip_as_docx(self) -> None:
        """Corrupted ZIP disguised as DOCX should fail."""
        content = b"PK\x03\x04CORRUPTED_DATA_NOT_VALID_ZIP"
        validator = FileValidator()
        result = validator.validate_file(
            content,
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        )
        
        assert result.valid is False
        assert any("ZIP" in error or "Office document" in error for error in result.errors)


class TestSizeLimitValidation:
    """Test file size limit enforcement."""

    def test_file_within_default_limit(self) -> None:
        """File within default 100MB limit."""
        content = b"A" * (50 * 1024 * 1024)  # 50MB
        validator = FileValidator()
        result = validator.validate_file(content, "text/plain")
        
        assert result.valid is True
        assert result.file_size == len(content)

    def test_file_exceeds_default_limit(self) -> None:
        """File exceeding default 100MB limit."""
        content = b"A" * (101 * 1024 * 1024)  # 101MB
        validator = FileValidator()
        result = validator.validate_file(content, "text/plain")
        
        assert result.valid is False
        assert any("exceeds maximum" in error for error in result.errors)

    def test_file_within_custom_limit(self) -> None:
        """File within custom size limit."""
        content = b"A" * (5 * 1024 * 1024)  # 5MB
        validator = FileValidator(max_file_size=10 * 1024 * 1024)  # 10MB limit
        result = validator.validate_file(content, "text/plain")
        
        assert result.valid is True

    def test_file_exceeds_custom_limit(self) -> None:
        """File exceeding custom size limit."""
        content = b"A" * (15 * 1024 * 1024)  # 15MB
        validator = FileValidator(max_file_size=10 * 1024 * 1024)  # 10MB limit
        result = validator.validate_file(content, "text/plain")
        
        assert result.valid is False
        assert any("exceeds maximum" in error for error in result.errors)

    def test_tenant_config_size_limit(self) -> None:
        """Test tenant-specific size limit."""
        content = b"A" * (15 * 1024 * 1024)  # 15MB
        result = validate_file_with_tenant_config(
            content,
            "text/plain",
            tenant_max_size=10 * 1024 * 1024  # 10MB tenant limit
        )
        
        assert result.valid is False
        assert any("exceeds maximum" in error for error in result.errors)

    def test_tenant_config_default_size(self) -> None:
        """Test with no tenant-specific limit (uses default)."""
        content = b"A" * (50 * 1024 * 1024)  # 50MB
        result = validate_file_with_tenant_config(content, "text/plain")
        
        assert result.valid is True


class TestMaliciousFileDetection:
    """Test detection of malicious file samples."""

    def test_exe_disguised_as_pdf(self) -> None:
        """Executable with .pdf extension should fail."""
        # Windows PE executable header
        content = b"MZ\x90\x00\x03\x00\x00\x00"
        validator = FileValidator()
        result = validator.validate_file(content, "application/pdf")
        
        assert result.valid is False
        assert any("Magic bytes" in error for error in result.errors)

    def test_html_disguised_as_docx(self) -> None:
        """HTML file disguised as DOCX should fail."""
        content = b"<!DOCTYPE html><html><body>Malicious</body></html>"
        validator = FileValidator()
        result = validator.validate_file(
            content,
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        )
        
        assert result.valid is False
        assert len(result.errors) > 0

    def test_script_disguised_as_csv(self) -> None:
        """Script disguised as CSV (CSV has no magic bytes, so this passes)."""
        content = b"#!/bin/bash\nrm -rf /"
        validator = FileValidator()
        result = validator.validate_file(content, "text/csv")
        
        # Note: CSV has no magic byte validation, this is expected behavior
        # Content filtering should be done at a different layer
        assert result.valid is True

    def test_zip_bomb_detection_via_size(self) -> None:
        """Massive file should be rejected by size limit."""
        content = b"A" * (500 * 1024 * 1024)  # 500MB
        validator = FileValidator()
        result = validator.validate_file(content, "text/plain")
        
        assert result.valid is False
        assert any("exceeds maximum" in error for error in result.errors)

    def test_null_bytes_in_pdf(self) -> None:
        """PDF with embedded null bytes."""
        content = b"%PDF-1.4\n\x00\x00\x00\x00malicious content"
        validator = FileValidator()
        result = validator.validate_file(content, "application/pdf")
        
        # Magic bytes are correct, so this passes basic validation
        # Content inspection is a separate concern
        assert result.valid is True


class TestUnsupportedMimeTypes:
    """Test handling of unsupported MIME types."""

    def test_unsupported_mime_type(self) -> None:
        """Unsupported MIME type should be rejected."""
        content = b"Some content"
        validator = FileValidator()
        result = validator.validate_file(content, "application/x-executable")
        
        assert result.valid is False
        assert any("Unsupported MIME type" in error for error in result.errors)

    def test_empty_mime_type(self) -> None:
        """Empty MIME type should be rejected."""
        content = b"Some content"
        validator = FileValidator()
        result = validator.validate_file(content, "")
        
        assert result.valid is False
        assert any("Unsupported MIME type" in error for error in result.errors)


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_single_byte_file(self) -> None:
        """Single byte file."""
        content = b"A"
        validator = FileValidator()
        result = validator.validate_file(content, "text/plain")
        
        assert result.valid is True
        assert result.file_size == 1

    def test_exactly_max_size(self) -> None:
        """File exactly at maximum size."""
        max_size = 1024
        content = b"A" * max_size
        validator = FileValidator(max_file_size=max_size)
        result = validator.validate_file(content, "text/plain")
        
        assert result.valid is True
        assert result.file_size == max_size

    def test_one_byte_over_max(self) -> None:
        """File one byte over maximum size."""
        max_size = 1024
        content = b"A" * (max_size + 1)
        validator = FileValidator(max_file_size=max_size)
        result = validator.validate_file(content, "text/plain")
        
        assert result.valid is False
        assert any("exceeds maximum" in error for error in result.errors)

    def test_partial_magic_bytes(self) -> None:
        """File with partial magic bytes should fail."""
        content = b"%PD"  # Incomplete PDF magic
        validator = FileValidator()
        result = validator.validate_file(content, "application/pdf")
        
        assert result.valid is False

    def test_magic_bytes_at_wrong_position(self) -> None:
        """Magic bytes not at start of file should fail."""
        content = b"GARBAGE%PDF-1.4"
        validator = FileValidator()
        result = validator.validate_file(content, "application/pdf")
        
        assert result.valid is False


class TestPropertyBasedValidation:
    """Property-based tests for critical validation paths."""

    def test_size_validation_property(self) -> None:
        """Property: File size in result always matches actual content length."""
        test_cases = [
            (b"", "text/plain"),
            (b"A", "text/plain"),
            (b"A" * 100, "text/plain"),
            (b"A" * 10000, "text/plain"),
            (b"%PDF" * 1000, "application/pdf"),
        ]
        
        validator = FileValidator()
        for content, mime_type in test_cases:
            result = validator.validate_file(content, mime_type)
            assert result.file_size == len(content)

    def test_validation_idempotency(self) -> None:
        """Property: Validating same file multiple times gives same result."""
        content = b"%PDF-1.4\nTest content"
        validator = FileValidator()
        
        result1 = validator.validate_file(content, "application/pdf")
        result2 = validator.validate_file(content, "application/pdf")
        result3 = validator.validate_file(content, "application/pdf")
        
        assert result1.valid == result2.valid == result3.valid
        assert result1.errors == result2.errors == result3.errors
        assert result1.file_size == result2.file_size == result3.file_size

    def test_error_accumulation(self) -> None:
        """Property: Multiple violations result in multiple errors."""
        # Too large AND wrong magic bytes
        content = b"NOTPDF" * (50 * 1024 * 1024)  # 300MB of garbage
        validator = FileValidator()
        result = validator.validate_file(content, "application/pdf")
        
        assert result.valid is False
        assert len(result.errors) >= 2  # Should have both size and magic byte errors

    def test_unicode_content_handling(self) -> None:
        """Property: Validator handles unicode content in text files."""
        test_cases = [
            b"Hello \xe2\x9c\x93 World",  # UTF-8
            b"\xef\xbb\xbfBOM test",  # UTF-8 BOM
            "Ελληνικά".encode('utf-8'),  # Greek
            "日本語".encode('utf-8'),  # Japanese
            "🚀 Rocket".encode('utf-8'),  # Emoji
        ]
        
        validator = FileValidator()
        for content in test_cases:
            result = validator.validate_file(content, "text/plain")
            assert result.valid is True
            assert result.file_size == len(content)


class TestValidationResultModel:
    """Test ValidationResult model behavior."""

    def test_validation_result_structure(self) -> None:
        """ValidationResult has correct structure."""
        result = ValidationResult(
            valid=True,
            mime_type="application/pdf",
            file_size=1024,
            errors=[]
        )
        
        assert result.valid is True
        assert result.mime_type == "application/pdf"
        assert result.file_size == 1024
        assert result.errors == []

    def test_validation_result_with_errors(self) -> None:
        """ValidationResult can contain multiple errors."""
        result = ValidationResult(
            valid=False,
            mime_type="application/pdf",
            file_size=1024,
            errors=["Error 1", "Error 2", "Error 3"]
        )
        
        assert result.valid is False
        assert len(result.errors) == 3
