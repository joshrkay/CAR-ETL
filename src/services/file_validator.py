"""
File Validation Service - Ingestion Plane

Validates uploaded files using magic byte verification and structural checks.
Enforces size limits and MIME type integrity.

Security Layer: Defense in depth - never trust file extensions or client-provided MIME types.
"""

import logging
import zipfile
from io import BytesIO
from typing import Optional
from pydantic import BaseModel


# Maximum file size in bytes (100MB default)
DEFAULT_MAX_FILE_SIZE = 100 * 1024 * 1024

# Magic byte signatures for supported file types
MAGIC_BYTES: dict[str, Optional[list[bytes]]] = {
    "application/pdf": [b"%PDF"],
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": [b"PK\x03\x04"],
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": [b"PK\x03\x04"],
    "image/png": [b"\x89PNG"],
    "image/jpeg": [b"\xff\xd8\xff"],
    "text/plain": None,  # No magic bytes
    "text/csv": None,
}

# Office Open XML content types for DOCX/XLSX validation
OFFICE_CONTENT_TYPES = {
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml",
}


class ValidationResult(BaseModel):
    """Result of file validation."""
    valid: bool
    mime_type: str
    file_size: int
    errors: list[str] = []


class FileValidator:
    """
    Validates file content integrity and security.
    
    Responsibilities:
    - Magic byte verification
    - Office Open XML structural validation
    - Size limit enforcement
    """

    def __init__(self, max_file_size: int = DEFAULT_MAX_FILE_SIZE):
        """
        Initialize validator with size limit.
        
        Args:
            max_file_size: Maximum allowed file size in bytes
        """
        self.max_file_size = max_file_size

    def validate_file(self, content: bytes, claimed_mime: str) -> ValidationResult:
        """
        Validate file content against claimed MIME type.
        
        Args:
            content: Raw file bytes
            claimed_mime: Client-provided MIME type
            
        Returns:
            ValidationResult with validation status and errors
        """
        errors: list[str] = []
        file_size = len(content)

        # Check size limit
        if not self._validate_size(file_size):
            errors.append(f"File size {file_size} exceeds maximum {self.max_file_size} bytes")

        # Check MIME type is supported
        if claimed_mime not in MAGIC_BYTES:
            errors.append(f"Unsupported MIME type: {claimed_mime}")
            return ValidationResult(
                valid=False,
                mime_type=claimed_mime,
                file_size=file_size,
                errors=errors
            )

        # Validate magic bytes
        if not self._validate_magic_bytes(content, claimed_mime):
            errors.append(f"Magic bytes do not match claimed MIME type: {claimed_mime}")

        # Additional validation for Office documents
        if claimed_mime in OFFICE_CONTENT_TYPES:
            office_errors = self._validate_office_document(content, claimed_mime)
            errors.extend(office_errors)

        return ValidationResult(
            valid=len(errors) == 0,
            mime_type=claimed_mime,
            file_size=file_size,
            errors=errors
        )

    def _validate_size(self, file_size: int) -> bool:
        """Check if file size is within limit."""
        return 0 < file_size <= self.max_file_size

    def _validate_magic_bytes(self, content: bytes, claimed_mime: str) -> bool:
        """
        Verify file content matches claimed MIME type.
        
        Args:
            content: Raw file bytes
            claimed_mime: Claimed MIME type
            
        Returns:
            True if magic bytes match or no validation required
        """
        expected = MAGIC_BYTES.get(claimed_mime)
        if expected is None:
            return True  # No validation for text files

        if len(content) == 0:
            return False

        return any(content.startswith(magic) for magic in expected)

    def _validate_office_document(self, content: bytes, claimed_mime: str) -> list[str]:
        """
        Validate Office Open XML document structure.
        
        Checks for presence of [Content_Types].xml to verify legitimate Office document.
        
        Args:
            content: Raw file bytes
            claimed_mime: Claimed MIME type (DOCX or XLSX)
            
        Returns:
            List of validation errors (empty if valid)
        """
        errors: list[str] = []

        try:
            with zipfile.ZipFile(BytesIO(content), 'r') as zip_file:
                # Check for [Content_Types].xml
                if '[Content_Types].xml' not in zip_file.namelist():
                    errors.append("Missing [Content_Types].xml - not a valid Office Open XML document")
                    return errors

                # Read and verify content types
                content_types_xml = zip_file.read('[Content_Types].xml').decode('utf-8')
                expected_content_type = OFFICE_CONTENT_TYPES[claimed_mime]

                if expected_content_type not in content_types_xml:
                    errors.append(f"Content types do not match claimed MIME type: {claimed_mime}")

        except zipfile.BadZipFile:
            errors.append("Corrupted ZIP structure - not a valid Office document")
        except (IOError, OSError, MemoryError) as e:
            errors.append(f"Office document validation failed: {str(e)}")
        except Exception as e:
            logger = logging.getLogger(__name__)
            logger.warning(
                "Unexpected error during Office document validation",
                extra={
                    "error": str(e),
                    "error_type": type(e).__name__,
                },
                exc_info=True,
            )
            errors.append(f"Office document validation failed: {str(e)}")

        return errors


def validate_file_with_tenant_config(
    content: bytes,
    claimed_mime: str,
    tenant_max_size: Optional[int] = None
) -> ValidationResult:
    """
    Validate file with tenant-specific configuration.
    
    Args:
        content: Raw file bytes
        claimed_mime: Client-provided MIME type
        tenant_max_size: Optional tenant-specific size limit
        
    Returns:
        ValidationResult with validation status
    """
    max_size = tenant_max_size if tenant_max_size is not None else DEFAULT_MAX_FILE_SIZE
    validator = FileValidator(max_file_size=max_size)
    return validator.validate_file(content, claimed_mime)
