"""
Bulk Upload Service - Ingestion Plane

Handles ZIP-based bulk document upload with file validation and batch processing.
Each file is validated independently and processed with tenant isolation.
"""

import hashlib
import logging
import os
import tempfile
import zipfile
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Optional
from uuid import uuid4

from src.services.file_validator import FileValidator, ValidationResult

logger = logging.getLogger(__name__)

# Maximum ZIP file size (500MB as per requirements)
MAX_ZIP_SIZE_BYTES = 500 * 1024 * 1024

# Maximum number of files allowed in a single ZIP
MAX_FILES_PER_ZIP = 1000

# Maximum compression ratio (compressed/uncompressed) to detect ZIP bombs
# A ratio < 0.01 (1%) indicates extreme compression, likely a bomb
MAX_COMPRESSION_RATIO = 0.01

# Maximum uncompressed size per file (10x the compressed ZIP limit as safety)
# This prevents memory exhaustion from decompression bombs
MAX_UNCOMPRESSED_FILE_SIZE = 10 * MAX_ZIP_SIZE_BYTES


@dataclass
class FileProcessingResult:
    """Result of processing a single file from ZIP."""
    filename: str
    document_id: Optional[str]
    status: str  # "processing", "failed"
    error: Optional[str]
    file_size: int
    mime_type: Optional[str]


@dataclass
class BulkUploadResult:
    """Result of bulk upload operation."""
    batch_id: str
    total_files: int
    successful: int
    failed: int
    results: list[FileProcessingResult]


class BulkUploadService:
    """
    Service for handling bulk document uploads via ZIP files.
    
    Responsibilities:
    - Extract ZIP archives securely
    - Validate individual files
    - Process files in batch
    - Track success/failure for each file
    """

    def __init__(
        self,
        file_validator: FileValidator,
        max_zip_size: int = MAX_ZIP_SIZE_BYTES,
        max_files: int = MAX_FILES_PER_ZIP,
    ):
        """
        Initialize bulk upload service.
        
        Args:
            file_validator: File validator instance for individual files
            max_zip_size: Maximum ZIP file size in bytes
            max_files: Maximum number of files allowed in ZIP
        """
        self.file_validator = file_validator
        self.max_zip_size = max_zip_size
        self.max_files = max_files
        # Get max file size from validator for ZIP bomb protection
        self.max_file_size = file_validator.max_file_size

    def validate_zip_file(self, content: bytes) -> list[str]:
        """
        Validate ZIP file structure and constraints.
        
        Args:
            content: ZIP file bytes
            
        Returns:
            List of validation errors (empty if valid)
        """
        errors: list[str] = []
        
        # Check size
        if len(content) > self.max_zip_size:
            errors.append(
                f"ZIP file size {len(content)} exceeds maximum {self.max_zip_size} bytes"
            )
            return errors
        
        if len(content) == 0:
            errors.append("ZIP file is empty")
            return errors
        
        # Validate ZIP structure
        try:
            with zipfile.ZipFile(BytesIO(content), 'r') as zip_file:
                # Test ZIP integrity
                if zip_file.testzip() is not None:
                    errors.append("ZIP file is corrupted")
                    return errors
                
                # Count files (exclude directories)
                file_count = sum(
                    1 for name in zip_file.namelist()
                    if not name.endswith('/') and not self._is_system_file(name)
                )
                
                if file_count == 0:
                    errors.append("ZIP file contains no valid files")
                
                if file_count > self.max_files:
                    errors.append(
                        f"ZIP contains {file_count} files, maximum is {self.max_files}"
                    )
        
        except zipfile.BadZipFile:
            errors.append("Invalid ZIP file format")
        except (IOError, OSError, MemoryError) as e:
            errors.append(f"ZIP validation failed: {str(e)}")
        except Exception as e:
            logger.warning(
                "Unexpected error during ZIP validation",
                extra={
                    "error": str(e),
                    "error_type": type(e).__name__,
                },
                exc_info=True,
            )
            errors.append(f"ZIP validation failed: {str(e)}")
        
        return errors

    def extract_and_validate_files(
        self,
        zip_content: bytes,
        tenant_id: str,
        request_id: str,
    ) -> list[tuple[str, bytes, str]]:
        """
        Extract files from ZIP and return valid file data.
        
        Args:
            zip_content: ZIP file bytes
            tenant_id: Tenant identifier for logging
            request_id: Request identifier for logging
            
        Returns:
            List of tuples: (filename, content, detected_mime_type)
            
        Raises:
            Exception: If ZIP extraction fails
        """
        valid_files: list[tuple[str, bytes, str]] = []
        
        try:
            with zipfile.ZipFile(BytesIO(zip_content), 'r') as zip_file:
                for file_info in zip_file.infolist():
                    # Skip directories and system files
                    if file_info.is_dir() or self._is_system_file(file_info.filename):
                        continue
                    
                    # ZIP bomb protection: Check uncompressed size before reading
                    uncompressed_size = file_info.file_size
                    compressed_size = file_info.compress_size
                    
                    # Skip empty files (they'll be rejected by validator anyway)
                    if uncompressed_size == 0:
                        continue
                    
                    # Skip files with invalid compression data (corrupted ZIP)
                    if compressed_size == 0 and uncompressed_size > 0:
                        logger.warning(
                            "Skipping file: invalid compression data (corrupted ZIP entry)",
                            extra={
                                "request_id": request_id,
                                "tenant_id": tenant_id,
                                "filename": file_info.filename,
                            },
                        )
                        continue
                    
                    # Check uncompressed size against limit
                    if uncompressed_size > self.max_file_size:
                        logger.warning(
                            "Skipping file: uncompressed size exceeds limit",
                            extra={
                                "request_id": request_id,
                                "tenant_id": tenant_id,
                                "filename": file_info.filename,
                                "uncompressed_size": uncompressed_size,
                                "max_size": self.max_file_size,
                            },
                        )
                        continue
                    
                    # Check for ZIP bomb: suspicious compression ratio
                    if compressed_size > 0:
                        compression_ratio = compressed_size / uncompressed_size
                        if compression_ratio < MAX_COMPRESSION_RATIO:
                            logger.warning(
                                "Skipping file: suspicious compression ratio (possible ZIP bomb)",
                                extra={
                                    "request_id": request_id,
                                    "tenant_id": tenant_id,
                                    "filename": file_info.filename,
                                    "compressed_size": compressed_size,
                                    "uncompressed_size": uncompressed_size,
                                    "compression_ratio": compression_ratio,
                                },
                            )
                            continue
                    
                    # Additional safety: check against absolute maximum
                    if uncompressed_size > MAX_UNCOMPRESSED_FILE_SIZE:
                        logger.warning(
                            "Skipping file: uncompressed size exceeds absolute maximum",
                            extra={
                                "request_id": request_id,
                                "tenant_id": tenant_id,
                                "filename": file_info.filename,
                                "uncompressed_size": uncompressed_size,
                                "max_uncompressed": MAX_UNCOMPRESSED_FILE_SIZE,
                            },
                        )
                        continue
                    
                    # Extract file content (now safe - size checked)
                    try:
                        file_content = zip_file.read(file_info.filename)
                        
                        # Detect MIME type from filename extension
                        mime_type = self._detect_mime_type(file_info.filename)
                        
                        if mime_type:
                            valid_files.append((file_info.filename, file_content, mime_type))
                        else:
                            logger.warning(
                                "Skipping file with unsupported extension",
                                extra={
                                    "request_id": request_id,
                                    "tenant_id": tenant_id,
                                    "filename": file_info.filename,
                                },
                            )
                    
                    except (zipfile.BadZipFile, IOError, OSError, MemoryError) as e:
                        logger.error(
                            "Failed to extract file from ZIP",
                            extra={
                                "request_id": request_id,
                                "tenant_id": tenant_id,
                                "filename": file_info.filename,
                                "error": str(e),
                                "error_type": type(e).__name__,
                            },
                            exc_info=True,
                        )
                        continue
                    except Exception as e:
                        logger.error(
                            "Unexpected error extracting file from ZIP",
                            extra={
                                "request_id": request_id,
                                "tenant_id": tenant_id,
                                "filename": file_info.filename,
                                "error": str(e),
                                "error_type": type(e).__name__,
                            },
                            exc_info=True,
                        )
                        continue
        
        except (zipfile.BadZipFile, IOError, OSError, MemoryError) as e:
            logger.error(
                "Failed to process ZIP file",
                extra={
                    "request_id": request_id,
                    "tenant_id": tenant_id,
                    "error": str(e),
                    "error_type": type(e).__name__,
                },
                exc_info=True,
            )
            raise
        except Exception as e:
            logger.error(
                "Unexpected error processing ZIP file",
                extra={
                    "request_id": request_id,
                    "tenant_id": tenant_id,
                    "error": str(e),
                    "error_type": type(e).__name__,
                },
                exc_info=True,
            )
            raise
        
        return valid_files

    def process_file(
        self,
        filename: str,
        content: bytes,
        mime_type: str,
    ) -> FileProcessingResult:
        """
        Process a single file: validate and prepare for storage.
        
        Args:
            filename: Original filename
            content: File content bytes
            mime_type: Detected MIME type
            
        Returns:
            FileProcessingResult with validation outcome
        """
        # Validate file content
        validation_result = self.file_validator.validate_file(
            content=content,
            claimed_mime=mime_type,
        )
        
        # If validation failed, return error result
        if not validation_result.valid:
            return FileProcessingResult(
                filename=filename,
                document_id=None,
                status="failed",
                error="; ".join(validation_result.errors),
                file_size=len(content),
                mime_type=mime_type,
            )
        
        # Generate document ID for valid file
        document_id = str(uuid4())
        
        return FileProcessingResult(
            filename=filename,
            document_id=document_id,
            status="processing",
            error=None,
            file_size=validation_result.file_size,
            mime_type=validation_result.mime_type,
        )

    def calculate_file_hash(self, content: bytes) -> str:
        """
        Calculate SHA-256 hash of file content.
        
        Args:
            content: File content bytes
            
        Returns:
            Hexadecimal hash string
        """
        return hashlib.sha256(content).hexdigest()

    def _is_system_file(self, filename: str) -> bool:
        """
        Check if filename represents a system/metadata file.
        
        Args:
            filename: File path within ZIP
            
        Returns:
            True if system file should be skipped
        """
        # Skip macOS metadata files
        if filename.startswith('__MACOSX/'):
            return True
        
        # Skip hidden files
        if Path(filename).name.startswith('.'):
            return True
        
        # Skip Windows thumbs
        if Path(filename).name.lower() == 'thumbs.db':
            return True
        
        return False

    def _detect_mime_type(self, filename: str) -> Optional[str]:
        """
        Detect MIME type from file extension.
        
        Args:
            filename: Original filename
            
        Returns:
            MIME type string or None if unsupported
        """
        extension_map = {
            '.pdf': 'application/pdf',
            '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            '.xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            '.png': 'image/png',
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.txt': 'text/plain',
            '.csv': 'text/csv',
        }
        
        extension = Path(filename).suffix.lower()
        return extension_map.get(extension)


def create_bulk_upload_service(max_file_size: int) -> BulkUploadService:
    """
    Factory function to create BulkUploadService with configured validator.
    
    Args:
        max_file_size: Maximum individual file size in bytes
        
    Returns:
        Configured BulkUploadService instance
    """
    file_validator = FileValidator(max_file_size=max_file_size)
    return BulkUploadService(file_validator=file_validator)
