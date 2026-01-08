"""Secure file validation service with magic byte checking and size limits."""
import zipfile
import io
import logging
from typing import Optional
from uuid import UUID
from pydantic import BaseModel, Field
from supabase import Client

logger = logging.getLogger(__name__)

# Default max file size: 100MB
DEFAULT_MAX_FILE_SIZE_BYTES = 100 * 1024 * 1024

# Magic bytes for file type validation
MAGIC_BYTES = {
    "application/pdf": [b"%PDF"],
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": [b"PK\x03\x04"],
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": [b"PK\x03\x04"],
    "image/png": [b"\x89PNG"],
    "image/jpeg": [b"\xff\xd8\xff"],
    "text/plain": None,  # No magic bytes
    "text/csv": None,  # No magic bytes
}


def validate_magic_bytes(content: bytes, claimed_mime: str) -> bool:
    """
    Verify file content matches claimed MIME type.
    
    Args:
        content: File content bytes
        claimed_mime: Claimed MIME type
        
    Returns:
        True if magic bytes match or no validation required, False otherwise
    """
    expected = MAGIC_BYTES.get(claimed_mime)
    if expected is None:
        return True  # No validation for text files
    return any(content.startswith(magic) for magic in expected)


class ValidationResult(BaseModel):
    """Result of file validation."""
    
    valid: bool = Field(..., description="Whether file passed validation")
    mime_type: str = Field(..., description="Detected/claimed MIME type")
    file_size: int = Field(..., description="File size in bytes")
    errors: list[str] = Field(default_factory=list, description="List of validation errors")


class FileValidatorService:
    """Service for validating uploaded files with security checks."""
    
    def __init__(self, supabase_client: Client):
        """
        Initialize file validator service.
        
        Args:
            supabase_client: Supabase client for fetching tenant settings
        """
        self.client = supabase_client
    
    def _get_tenant_max_file_size(self, tenant_id: UUID) -> int:
        """
        Get max file size for tenant from settings.
        
        Args:
            tenant_id: Tenant UUID
            
        Returns:
            Max file size in bytes (defaults to DEFAULT_MAX_FILE_SIZE_BYTES)
        """
        try:
            result = (
                self.client.table("tenants")
                .select("settings")
                .eq("id", str(tenant_id))
                .limit(1)
                .execute()
            )
            
            if not result.data:
                logger.warning(f"Tenant {tenant_id} not found, using default max file size")
                return DEFAULT_MAX_FILE_SIZE_BYTES
            
            settings = result.data[0].get("settings", {})
            max_size = settings.get("max_file_size")
            
            if max_size is None:
                return DEFAULT_MAX_FILE_SIZE_BYTES
            
            # Convert to bytes if provided in MB
            if isinstance(max_size, int):
                # Assume bytes if reasonable, otherwise assume MB
                if max_size < 1024:
                    return max_size * 1024 * 1024  # Convert MB to bytes
                return max_size
            
            logger.warning(f"Invalid max_file_size for tenant {tenant_id}, using default")
            return DEFAULT_MAX_FILE_SIZE_BYTES
            
        except Exception as e:
            logger.error(f"Error fetching tenant settings for {tenant_id}: {e}")
            return DEFAULT_MAX_FILE_SIZE_BYTES
    
    def _validate_magic_bytes(self, content: bytes, claimed_mime: str) -> Optional[str]:
        """
        Verify file content matches claimed MIME type via magic bytes.
        
        Args:
            content: File content bytes
            claimed_mime: Claimed MIME type
            
        Returns:
            Error message if validation fails, None if passes
        """
        expected = MAGIC_BYTES.get(claimed_mime)
        
        if expected is None:
            # No magic bytes for this type (text files)
            return None
        
        if not any(content.startswith(magic) for magic in expected):
            return f"Magic bytes do not match claimed MIME type '{claimed_mime}'"
        
        return None
    
    def _validate_office_open_xml(self, content: bytes, mime_type: str) -> Optional[str]:
        """
        Validate DOCX/XLSX files are valid Office Open XML (ZIP with [Content_Types].xml).
        
        Args:
            content: File content bytes
            mime_type: MIME type (must be DOCX or XLSX)
            
        Returns:
            Error message if validation fails, None if passes
        """
        office_mime_types = [
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        ]
        
        if mime_type not in office_mime_types:
            return None  # Not an Office Open XML file
        
        try:
            with zipfile.ZipFile(io.BytesIO(content), 'r') as zip_file:
                # Check for [Content_Types].xml (required for Office Open XML)
                if "[Content_Types].xml" not in zip_file.namelist():
                    return "Invalid Office Open XML: missing [Content_Types].xml"
                
                # Verify it's a valid ZIP structure
                zip_file.testzip()
                
        except zipfile.BadZipFile:
            return "Invalid Office Open XML: not a valid ZIP archive"
        except Exception as e:
            logger.error(f"Error validating Office Open XML: {e}")
            return f"Error validating Office Open XML: {str(e)}"
        
        return None
    
    def validate_file(
        self,
        content: bytes,
        claimed_mime: str,
        tenant_id: UUID,
    ) -> ValidationResult:
        """
        Validate file content with security checks.
        
        Performs:
        1. Magic byte validation
        2. Office Open XML structure validation (for DOCX/XLSX)
        3. Size limit check (tenant-configurable)
        
        Args:
            content: File content bytes
            claimed_mime: Claimed MIME type
            tenant_id: Tenant UUID for size limit lookup
            
        Returns:
            ValidationResult with validation status and errors
        """
        errors: list[str] = []
        file_size = len(content)
        
        # Check size limit
        max_size = self._get_tenant_max_file_size(tenant_id)
        if file_size > max_size:
            errors.append(
                f"File size {file_size} bytes exceeds maximum {max_size} bytes "
                f"({max_size / (1024 * 1024):.1f} MB)"
            )
        
        # Validate magic bytes
        magic_error = self._validate_magic_bytes(content, claimed_mime)
        if magic_error:
            errors.append(magic_error)
        
        # Validate Office Open XML structure (for DOCX/XLSX)
        ooxml_error = self._validate_office_open_xml(content, claimed_mime)
        if ooxml_error:
            errors.append(ooxml_error)
        
        return ValidationResult(
            valid=len(errors) == 0,
            mime_type=claimed_mime,
            file_size=file_size,
            errors=errors,
        )
