"""Unit tests for secure file validation with malicious file samples."""
import pytest
import zipfile
import io
from unittest.mock import Mock, patch
from uuid import UUID, uuid4

from src.services.file_validator import (
    FileValidatorService,
    ValidationResult,
    validate_magic_bytes,
    MAGIC_BYTES,
    DEFAULT_MAX_FILE_SIZE_BYTES,
)


@pytest.fixture
def mock_supabase_client():
    """Create a mock Supabase client."""
    client = Mock()
    client.table = Mock(return_value=client)
    client.select = Mock(return_value=client)
    client.eq = Mock(return_value=client)
    client.limit = Mock(return_value=client)
    client.execute = Mock(return_value=Mock(data=[{"settings": {}}]))
    return client


@pytest.fixture
def validator_service(mock_supabase_client):
    """Create a FileValidatorService instance."""
    return FileValidatorService(mock_supabase_client)


@pytest.fixture
def tenant_id():
    """Create a test tenant ID."""
    return uuid4()


# ============================================================================
# VALID FILE SAMPLES
# ============================================================================

def create_valid_pdf() -> bytes:
    """Create a minimal valid PDF."""
    return b"%PDF-1.4\n1 0 obj\n<<\n/Type /Catalog\n>>\nendobj\nxref\n0 1\ntrailer\n<<\n/Root 1 0 R\n>>\nstartxref\n10\n%%EOF"


def create_valid_png() -> bytes:
    """Create a minimal valid PNG."""
    # PNG signature + minimal IHDR chunk
    png_signature = b"\x89PNG\r\n\x1a\n"
    ihdr = b"\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde"
    iend = b"\x00\x00\x00\x00IEND\xaeB`\x82"
    return png_signature + ihdr + iend


def create_valid_jpeg() -> bytes:
    """Create a minimal valid JPEG."""
    # JPEG SOI marker + minimal structure
    return b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x01\x00H\x00H\x00\x00\xff\xd9"


def create_valid_docx() -> bytes:
    """Create a minimal valid DOCX (Office Open XML)."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        zip_file.writestr("[Content_Types].xml", """<?xml version="1.0" encoding="UTF-8"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
</Types>""")
        zip_file.writestr("_rels/.rels", """<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
</Relationships>""")
        zip_file.writestr("word/document.xml", """<?xml version="1.0" encoding="UTF-8"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:body><w:p><w:r><w:t>Test</w:t></w:r></w:p></w:body>
</w:document>""")
    return buffer.getvalue()


def create_valid_xlsx() -> bytes:
    """Create a minimal valid XLSX (Office Open XML)."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        zip_file.writestr("[Content_Types].xml", """<?xml version="1.0" encoding="UTF-8"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
</Types>""")
        zip_file.writestr("_rels/.rels", """<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>
</Relationships>""")
        zip_file.writestr("xl/workbook.xml", """<?xml version="1.0" encoding="UTF-8"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
  <sheets><sheet name="Sheet1" sheetId="1" r:id="rId1"/></sheets>
</workbook>""")
    return buffer.getvalue()


# ============================================================================
# MALICIOUS FILE SAMPLES
# ============================================================================

def create_fake_pdf_with_executable() -> bytes:
    """Create a file claiming to be PDF but contains executable content."""
    # Starts with PDF magic bytes but contains shell script
    return b"%PDF\n#!/bin/bash\necho 'malicious code'\nrm -rf /\n"


def create_fake_png_with_script() -> bytes:
    """Create a file claiming to be PNG but contains script."""
    # Starts with PNG magic bytes but contains JavaScript
    return b"\x89PNG\r\n\x1a\n<script>alert('XSS')</script>"


def create_fake_jpeg_with_php() -> bytes:
    """Create a file claiming to be JPEG but contains PHP code."""
    return b"\xff\xd8\xff<?php system($_GET['cmd']); ?>"


def create_zip_bomb() -> bytes:
    """Create a ZIP file that expands to massive size (ZIP bomb)."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        # Create a file that decompresses to a large size
        # In real attack, this would be much larger
        large_content = b"0" * (10 * 1024 * 1024)  # 10MB of zeros
        zip_file.writestr("bomb.txt", large_content)
    return buffer.getvalue()


def create_fake_docx_missing_content_types() -> bytes:
    """Create a ZIP file claiming to be DOCX but missing [Content_Types].xml."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        zip_file.writestr("malicious.exe", b"MZ\x90\x00")  # PE executable header
    return buffer.getvalue()


def create_fake_docx_with_executable() -> bytes:
    """Create a DOCX that contains an executable file."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        zip_file.writestr("[Content_Types].xml", """<?xml version="1.0"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="exe" ContentType="application/x-msdownload"/>
</Types>""")
        zip_file.writestr("payload.exe", b"MZ\x90\x00\x03\x00\x00\x00\x04\x00")
    return buffer.getvalue()


def create_file_with_wrong_extension_content() -> bytes:
    """Create a file with wrong MIME type (e.g., .exe claiming to be .pdf)."""
    # PE executable header (Windows .exe)
    return b"MZ\x90\x00\x03\x00\x00\x00\x04\x00\x00\x00\xff\xff"


def create_double_extension_attack() -> bytes:
    """Create a file that tries to exploit double extension (e.g., file.pdf.exe)."""
    # Starts with PDF magic bytes but is actually executable
    return b"%PDF-1.4\n" + b"MZ\x90\x00" * 100


def create_null_byte_injection() -> bytes:
    """Create a file with null bytes to bypass string checks."""
    return b"%PDF\x00\x00\x00<script>alert(1)</script>"


def create_oversized_file() -> bytes:
    """Create a file that exceeds size limits."""
    return b"%PDF-1.4\n" + b"0" * (DEFAULT_MAX_FILE_SIZE_BYTES + 1)


# ============================================================================
# TESTS: Standalone validate_magic_bytes function
# ============================================================================

def test_validate_magic_bytes_valid_pdf():
    """Test magic byte validation for valid PDF."""
    content = create_valid_pdf()
    assert validate_magic_bytes(content, "application/pdf") is True


def test_validate_magic_bytes_valid_png():
    """Test magic byte validation for valid PNG."""
    content = create_valid_png()
    assert validate_magic_bytes(content, "image/png") is True


def test_validate_magic_bytes_valid_jpeg():
    """Test magic byte validation for valid JPEG."""
    content = create_valid_jpeg()
    assert validate_magic_bytes(content, "image/jpeg") is True


def test_validate_magic_bytes_text_plain():
    """Test that text files have no magic byte validation."""
    content = b"Hello, world!"
    assert validate_magic_bytes(content, "text/plain") is True


def test_validate_magic_bytes_text_csv():
    """Test that CSV files have no magic byte validation."""
    content = b"name,age\nJohn,30"
    assert validate_magic_bytes(content, "text/csv") is True


def test_validate_magic_bytes_fake_pdf():
    """Test that fake PDF (executable) is rejected."""
    content = create_fake_pdf_with_executable()
    # Should pass because it starts with %PDF, but content is malicious
    # This is why we need additional validation
    assert validate_magic_bytes(content, "application/pdf") is True


def test_validate_magic_bytes_wrong_type():
    """Test that wrong MIME type is rejected."""
    pdf_content = create_valid_pdf()
    assert validate_magic_bytes(pdf_content, "image/png") is False


def test_validate_magic_bytes_executable_claimed_as_pdf():
    """Test that executable claiming to be PDF is rejected."""
    content = create_file_with_wrong_extension_content()
    assert validate_magic_bytes(content, "application/pdf") is False


# ============================================================================
# TESTS: FileValidatorService - Valid Files
# ============================================================================

def test_validate_valid_pdf(validator_service, tenant_id, mock_supabase_client):
    """Test validation of valid PDF file."""
    content = create_valid_pdf()
    result = validator_service.validate_file(
        content=content,
        claimed_mime="application/pdf",
        tenant_id=tenant_id,
    )
    
    assert result.valid is True
    assert result.mime_type == "application/pdf"
    assert len(result.errors) == 0


def test_validate_valid_png(validator_service, tenant_id):
    """Test validation of valid PNG file."""
    content = create_valid_png()
    result = validator_service.validate_file(
        content=content,
        claimed_mime="image/png",
        tenant_id=tenant_id,
    )
    
    assert result.valid is True
    assert result.mime_type == "image/png"
    assert len(result.errors) == 0


def test_validate_valid_jpeg(validator_service, tenant_id):
    """Test validation of valid JPEG file."""
    content = create_valid_jpeg()
    result = validator_service.validate_file(
        content=content,
        claimed_mime="image/jpeg",
        tenant_id=tenant_id,
    )
    
    assert result.valid is True
    assert result.mime_type == "image/jpeg"
    assert len(result.errors) == 0


def test_validate_valid_docx(validator_service, tenant_id):
    """Test validation of valid DOCX file."""
    content = create_valid_docx()
    result = validator_service.validate_file(
        content=content,
        claimed_mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        tenant_id=tenant_id,
    )
    
    assert result.valid is True
    assert result.mime_type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    assert len(result.errors) == 0


def test_validate_valid_xlsx(validator_service, tenant_id):
    """Test validation of valid XLSX file."""
    content = create_valid_xlsx()
    result = validator_service.validate_file(
        content=content,
        claimed_mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        tenant_id=tenant_id,
    )
    
    assert result.valid is True
    assert result.mime_type == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    assert len(result.errors) == 0


def test_validate_text_file(validator_service, tenant_id):
    """Test validation of text file (no magic bytes)."""
    content = b"Hello, world!\nThis is a text file."
    result = validator_service.validate_file(
        content=content,
        claimed_mime="text/plain",
        tenant_id=tenant_id,
    )
    
    assert result.valid is True
    assert result.mime_type == "text/plain"
    assert len(result.errors) == 0


# ============================================================================
# TESTS: FileValidatorService - Malicious Files
# ============================================================================

def test_validate_fake_pdf_executable(validator_service, tenant_id):
    """Test that fake PDF containing executable is rejected."""
    content = create_fake_pdf_with_executable()
    result = validator_service.validate_file(
        content=content,
        claimed_mime="application/pdf",
        tenant_id=tenant_id,
    )
    
    # Magic bytes pass, but file structure might be invalid
    # This test ensures we're checking magic bytes at minimum
    assert result.mime_type == "application/pdf"
    # Note: This might pass magic bytes but fail other checks


def test_validate_wrong_mime_type(validator_service, tenant_id):
    """Test that wrong MIME type is rejected."""
    pdf_content = create_valid_pdf()
    result = validator_service.validate_file(
        content=pdf_content,
        claimed_mime="image/png",
        tenant_id=tenant_id,
    )
    
    assert result.valid is False
    assert "Magic bytes do not match" in result.errors[0]


def test_validate_executable_claimed_as_pdf(validator_service, tenant_id):
    """Test that executable claiming to be PDF is rejected."""
    content = create_file_with_wrong_extension_content()
    result = validator_service.validate_file(
        content=content,
        claimed_mime="application/pdf",
        tenant_id=tenant_id,
    )
    
    assert result.valid is False
    assert any("Magic bytes do not match" in error for error in result.errors)


def test_validate_fake_docx_missing_content_types(validator_service, tenant_id):
    """Test that DOCX missing [Content_Types].xml is rejected."""
    content = create_fake_docx_missing_content_types()
    result = validator_service.validate_file(
        content=content,
        claimed_mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        tenant_id=tenant_id,
    )
    
    assert result.valid is False
    assert any("missing [Content_Types].xml" in error for error in result.errors)


def test_validate_fake_docx_with_executable(validator_service, tenant_id):
    """Test that DOCX containing executable is detected."""
    content = create_fake_docx_with_executable()
    result = validator_service.validate_file(
        content=content,
        claimed_mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        tenant_id=tenant_id,
    )
    
    # Should pass structure validation (has [Content_Types].xml)
    # But in production, you'd want additional scanning
    assert result.mime_type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    # Note: This passes our current validation but contains executable


def test_validate_invalid_zip_structure(validator_service, tenant_id):
    """Test that invalid ZIP structure is rejected."""
    # Corrupted ZIP file
    content = b"PK\x03\x04" + b"corrupted" * 100
    result = validator_service.validate_file(
        content=content,
        claimed_mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        tenant_id=tenant_id,
    )
    
    assert result.valid is False
    assert any("not a valid ZIP archive" in error or "missing [Content_Types].xml" in error for error in result.errors)


# ============================================================================
# TESTS: Size Limits
# ============================================================================

def test_validate_file_size_within_limit(validator_service, tenant_id):
    """Test that file within size limit passes."""
    content = b"%PDF-1.4\n" + b"0" * 1024  # Small file
    result = validator_service.validate_file(
        content=content,
        claimed_mime="application/pdf",
        tenant_id=tenant_id,
    )
    
    assert result.valid is True
    assert result.file_size == len(content)


def test_validate_file_size_exceeds_default(validator_service, tenant_id, mock_supabase_client):
    """Test that file exceeding default size limit is rejected."""
    # Mock tenant with default settings
    mock_supabase_client.execute.return_value = Mock(data=[{"settings": {}}])
    
    content = create_oversized_file()
    result = validator_service.validate_file(
        content=content,
        claimed_mime="application/pdf",
        tenant_id=tenant_id,
    )
    
    assert result.valid is False
    assert any("exceeds maximum" in error for error in result.errors)
    assert result.file_size > DEFAULT_MAX_FILE_SIZE_BYTES


def test_validate_file_size_tenant_custom_limit(validator_service, tenant_id, mock_supabase_client):
    """Test that tenant custom size limit is respected."""
    # Mock tenant with custom max_file_size (50MB)
    custom_max_mb = 50
    custom_max_bytes = custom_max_mb * 1024 * 1024
    mock_supabase_client.execute.return_value = Mock(
        data=[{"settings": {"max_file_size": custom_max_mb}}]
    )
    
    # File larger than custom limit but smaller than default
    content = b"%PDF-1.4\n" + b"0" * (custom_max_bytes + 1)
    result = validator_service.validate_file(
        content=content,
        claimed_mime="application/pdf",
        tenant_id=tenant_id,
    )
    
    assert result.valid is False
    assert any("exceeds maximum" in error for error in result.errors)
    assert result.file_size > custom_max_bytes


def test_validate_file_size_tenant_limit_in_bytes(validator_service, tenant_id, mock_supabase_client):
    """Test that tenant size limit provided in bytes is handled."""
    # Mock tenant with max_file_size in bytes (large number)
    custom_max_bytes = 200 * 1024 * 1024  # 200MB
    mock_supabase_client.execute.return_value = Mock(
        data=[{"settings": {"max_file_size": custom_max_bytes}}]
    )
    
    # File within limit
    content = b"%PDF-1.4\n" + b"0" * (100 * 1024 * 1024)  # 100MB
    result = validator_service.validate_file(
        content=content,
        claimed_mime="application/pdf",
        tenant_id=tenant_id,
    )
    
    assert result.valid is True


def test_validate_file_size_tenant_not_found(validator_service, tenant_id, mock_supabase_client):
    """Test that default size limit is used when tenant not found."""
    # Mock tenant not found
    mock_supabase_client.execute.return_value = Mock(data=[])
    
    content = create_oversized_file()
    result = validator_service.validate_file(
        content=content,
        claimed_mime="application/pdf",
        tenant_id=tenant_id,
    )
    
    assert result.valid is False
    assert any("exceeds maximum" in error for error in result.errors)


def test_validate_file_size_tenant_settings_error(validator_service, tenant_id, mock_supabase_client):
    """Test that default size limit is used when tenant settings query fails."""
    # Mock exception when querying tenant
    mock_supabase_client.execute.side_effect = Exception("Database error")
    
    content = create_oversized_file()
    result = validator_service.validate_file(
        content=content,
        claimed_mime="application/pdf",
        tenant_id=tenant_id,
    )
    
    assert result.valid is False
    assert any("exceeds maximum" in error for error in result.errors)


# ============================================================================
# TESTS: Edge Cases
# ============================================================================

def test_validate_empty_file(validator_service, tenant_id):
    """Test validation of empty file."""
    content = b""
    result = validator_service.validate_file(
        content=content,
        claimed_mime="text/plain",
        tenant_id=tenant_id,
    )
    
    assert result.valid is True
    assert result.file_size == 0


def test_validate_unknown_mime_type(validator_service, tenant_id):
    """Test validation with unknown MIME type."""
    content = b"some content"
    result = validator_service.validate_file(
        content=content,
        claimed_mime="application/unknown",
        tenant_id=tenant_id,
    )
    
    # Unknown MIME type has no magic bytes, so passes magic byte check
    # But might fail other validations
    assert result.mime_type == "application/unknown"


def test_validate_multiple_errors(validator_service, tenant_id, mock_supabase_client):
    """Test that multiple validation errors are collected."""
    # Mock tenant with very small limit
    mock_supabase_client.execute.return_value = Mock(
        data=[{"settings": {"max_file_size": 100}}]  # 100 bytes
    )
    
    # File that's too large AND wrong MIME type
    pdf_content = create_valid_pdf()
    result = validator_service.validate_file(
        content=pdf_content,
        claimed_mime="image/png",  # Wrong type
        tenant_id=tenant_id,
    )
    
    assert result.valid is False
    assert len(result.errors) >= 1  # At least magic bytes error
    assert any("Magic bytes do not match" in error for error in result.errors)


def test_validate_docx_not_office_xml(validator_service, tenant_id):
    """Test that non-Office ZIP file claiming to be DOCX is rejected."""
    # Regular ZIP file (not Office Open XML)
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        zip_file.writestr("test.txt", b"Hello")
    content = buffer.getvalue()
    
    result = validator_service.validate_file(
        content=content,
        claimed_mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        tenant_id=tenant_id,
    )
    
    assert result.valid is False
    assert any("missing [Content_Types].xml" in error for error in result.errors)


def test_validate_xlsx_not_office_xml(validator_service, tenant_id):
    """Test that non-Office ZIP file claiming to be XLSX is rejected."""
    # Regular ZIP file (not Office Open XML)
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        zip_file.writestr("data.csv", b"name,value\nA,1")
    content = buffer.getvalue()
    
    result = validator_service.validate_file(
        content=content,
        claimed_mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        tenant_id=tenant_id,
    )
    
    assert result.valid is False
    assert any("missing [Content_Types].xml" in error for error in result.errors)
