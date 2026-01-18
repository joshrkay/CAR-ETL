"""
Upload Routes - Bulk Document Upload

Handles ZIP-based bulk document uploads with batch processing.
Part of Ingestion Plane - validates and buffers data only.
"""

import logging
import zipfile
from typing import Any, Dict, Optional, cast
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status
from pydantic import BaseModel
from supabase import Client

from src.auth.models import AuthContext
from src.auth.decorators import require_permission
from src.dependencies import get_supabase_client
from src.services.bulk_upload import (
    FileProcessingResult,
    create_bulk_upload_service,
)
from src.services.file_storage import FileStorageService, StorageUploadError
from src.services.redaction import presidio_redact_bytes

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/v1/documents/upload",
    tags=["upload"],
)

# Maximum file size for individual files (100MB)
DEFAULT_MAX_FILE_SIZE_BYTES = 100 * 1024 * 1024


class FileResult(BaseModel):
    """Result for a single file in bulk upload."""
    filename: str
    document_id: Optional[str]
    status: str
    error: Optional[str] = None


class BulkUploadResponse(BaseModel):
    """Response model for bulk upload operation."""
    batch_id: str
    total_files: int
    successful: int
    failed: int
    documents: list[FileResult]


@router.post(
    "/bulk",
    response_model=BulkUploadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Bulk upload documents from ZIP",
    description="""
    Upload multiple documents at once via a ZIP file.
    
    Security:
    - Requires authentication and 'documents:write' permission
    - Each file is validated independently
    - Tenant isolation enforced via RLS
    - Maximum ZIP size: 500MB
    - Maximum files per ZIP: 1000
    
    Processing:
    - Extracts ZIP file
    - Validates each file (magic bytes, structure, size)
    - Creates document records for valid files
    - Returns summary with per-file results
    
    The operation is atomic per-file: failures are tracked but
    don't prevent processing of other files in the batch.
    """,
)
async def upload_bulk_documents(
    request: Request,
    file: UploadFile = File(..., description="ZIP file containing documents"),
    auth: AuthContext = Depends(require_permission("documents:write")),
    supabase: Client = Depends(get_supabase_client),
) -> BulkUploadResponse:
    """
    Upload multiple documents from a ZIP file.
    
    This endpoint:
    1. Validates ZIP file structure and size
    2. Extracts and validates each file independently
    3. Creates document records for valid files
    4. Returns detailed results for each file
    
    Args:
        request: FastAPI request object
        file: ZIP file containing documents
        auth: Authenticated user context
        supabase: Supabase client with user JWT
        
    Returns:
        BulkUploadResponse with batch summary and per-file results
        
    Raises:
        HTTPException 400: ZIP validation failed
        HTTPException 401: User not authenticated
        HTTPException 403: Insufficient permissions
        HTTPException 413: ZIP file too large
    """
    request_id = getattr(request.state, "request_id", "unknown")
    tenant_id = str(auth.tenant_id)
    user_id = str(auth.user_id)
    batch_id = str(uuid4())
    
    logger.info(
        "Bulk upload initiated",
        extra={
            "request_id": request_id,
            "tenant_id": tenant_id,
            "user_id": user_id,
            "batch_id": batch_id,
            "filename": file.filename,
        },
    )
    
    # Step 1: Read ZIP file content
    try:
        zip_content = await file.read()
    except (IOError, OSError, RuntimeError) as e:
        logger.error(
            "Failed to read ZIP file",
            extra={
                "request_id": request_id,
                "tenant_id": tenant_id,
                "batch_id": batch_id,
                "error": str(e),
                "error_type": type(e).__name__,
            },
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "FILE_READ_ERROR",
                "message": "Failed to read ZIP file",
            },
        ) from e
    except Exception as e:
        logger.error(
            "Unexpected error reading ZIP file",
            extra={
                "request_id": request_id,
                "tenant_id": tenant_id,
                "batch_id": batch_id,
                "error": str(e),
                "error_type": type(e).__name__,
            },
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "FILE_READ_ERROR",
                "message": "Failed to read uploaded ZIP file",
            },
        )
    
    # Step 2: Get tenant configuration
    tenant_max_size = await fetch_tenant_max_file_size(
        supabase=supabase,
        tenant_id=tenant_id,
    )
    
    # Step 3: Create bulk upload service
    bulk_service = create_bulk_upload_service(
        max_file_size=tenant_max_size or DEFAULT_MAX_FILE_SIZE_BYTES,
    )
    
    # Step 4: Validate ZIP file
    zip_errors = bulk_service.validate_zip_file(zip_content)
    
    if zip_errors:
        logger.warning(
            "ZIP validation failed",
            extra={
                "request_id": request_id,
                "tenant_id": tenant_id,
                "batch_id": batch_id,
                "errors": zip_errors,
            },
        )
        
        # Return 413 for size errors, 400 for other validation errors
        status_code = status.HTTP_413_REQUEST_ENTITY_TOO_LARGE
        if not any("exceeds maximum" in err for err in zip_errors):
            status_code = status.HTTP_400_BAD_REQUEST
        
        raise HTTPException(
            status_code=status_code,
            detail={
                "code": "ZIP_VALIDATION_ERROR",
                "message": "ZIP file validation failed",
                "errors": zip_errors,
            },
        )
    
    # Step 5: Extract files from ZIP
    try:
        extracted_files = bulk_service.extract_and_validate_files(
            zip_content=zip_content,
            tenant_id=tenant_id,
            request_id=request_id,
        )
    except (zipfile.BadZipFile, IOError, OSError, MemoryError) as e:
        logger.error(
            "Failed to extract files from ZIP",
            extra={
                "request_id": request_id,
                "tenant_id": tenant_id,
                "batch_id": batch_id,
                "error": str(e),
                "error_type": type(e).__name__,
            },
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "EXTRACTION_ERROR",
                "message": "Failed to extract files from ZIP",
            },
        ) from e
    except Exception as e:
        logger.error(
            "Unexpected error extracting files from ZIP",
            extra={
                "request_id": request_id,
                "tenant_id": tenant_id,
                "batch_id": batch_id,
                "error": str(e),
                "error_type": type(e).__name__,
            },
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "code": "INTERNAL_ERROR",
                "message": "Unexpected error extracting files",
            },
        )
    
    # Step 6: Process each file
    results: list[FileResult] = []
    successful_count = 0
    failed_count = 0
    
    for filename, content, mime_type in extracted_files:
        # Validate and process file
        processing_result = bulk_service.process_file(
            filename=filename,
            content=content,
            mime_type=mime_type,
        )
        
        # If validation succeeded, redact and store document metadata
        if processing_result.status == "processing":
            # Ensure required fields are present
            if not processing_result.mime_type or not processing_result.document_id:
                processing_result.status = "failed"
                processing_result.error = "Missing required fields (mime_type or document_id)"
                continue
            
            try:
                # SECURITY: Redact PII before storage (defense in depth)
                redacted_content = presidio_redact_bytes(content, processing_result.mime_type)
                
                storage_service = FileStorageService(supabase)
                file_hash = storage_service.calculate_file_hash(redacted_content)
                
                # Generate storage path
                storage_path = f"bulk/{batch_id}/{filename}"
                
                # Upload file to storage before creating document record
                try:
                    storage_service.upload_file(
                        content=redacted_content,
                        storage_path=storage_path,
                        tenant_id=UUID(tenant_id),
                        mime_type=processing_result.mime_type,
                    )
                except StorageUploadError as e:
                    logger.error(
                        "Failed to upload file to storage",
                        extra={
                            "request_id": request_id,
                            "tenant_id": tenant_id,
                            "batch_id": batch_id,
                            "filename": filename,
                            "error": str(e),
                        },
                        exc_info=True,
                    )
                    # Mark as failed and continue to next file
                    processing_result = FileProcessingResult(
                        filename=filename,
                        document_id=None,
                        status="failed",
                        error="Failed to upload file to storage",
                        file_size=processing_result.file_size,
                        mime_type=processing_result.mime_type,
                    )
                    failed_count += 1
                    results.append(
                        FileResult(
                            filename=processing_result.filename,
                            document_id=processing_result.document_id,
                            status=processing_result.status,
                            error=processing_result.error,
                        )
                    )
                    continue
                
                if processing_result.document_id is None or processing_result.mime_type is None:
                    raise ValueError("Processed document metadata is incomplete")

                await store_document_metadata(
                    supabase=supabase,
                    storage_service=storage_service,
                    document_id=processing_result.document_id,
                    tenant_id=tenant_id,
                    user_id=user_id,
                    filename=filename,
                    mime_type=processing_result.mime_type,
                    file_size=len(redacted_content),
                    content=redacted_content,
                    file_hash=file_hash,
                    storage_path=storage_path,
                    batch_id=batch_id,
                )
                
                successful_count += 1
                
                logger.info(
                    "File processed successfully",
                    extra={
                        "request_id": request_id,
                        "tenant_id": tenant_id,
                        "batch_id": batch_id,
                        "document_id": processing_result.document_id,
                        "filename": filename,
                    },
                )
            
            except StorageUploadError as e:
                # This should not happen as upload is handled above, but keep for safety
                logger.error(
                    "Storage upload error in store_document_metadata",
                    extra={
                        "request_id": request_id,
                        "tenant_id": tenant_id,
                        "batch_id": batch_id,
                        "filename": filename,
                        "error": str(e),
                    },
                    exc_info=True,
                )
                
                processing_result = FileProcessingResult(
                    filename=filename,
                    document_id=None,
                    status="failed",
                    error="Failed to upload file to storage",
                    file_size=processing_result.file_size,
                    mime_type=processing_result.mime_type,
                )
                failed_count += 1
            except Exception as e:
                # If storage fails, mark as failed
                logger.error(
                    "Failed to store document metadata",
                    extra={
                        "request_id": request_id,
                        "tenant_id": tenant_id,
                        "batch_id": batch_id,
                        "filename": filename,
                        "error": str(e),
                    },
                    exc_info=True,
                )
                
                processing_result = FileProcessingResult(
                    filename=filename,
                    document_id=None,
                    status="failed",
                    error="Failed to store document metadata",
                    file_size=processing_result.file_size,
                    mime_type=processing_result.mime_type,
                )
                failed_count += 1
        else:
            failed_count += 1
        
        # Add to results
        results.append(
            FileResult(
                filename=processing_result.filename,
                document_id=processing_result.document_id,
                status=processing_result.status,
                error=processing_result.error,
            )
        )
    
    logger.info(
        "Bulk upload completed",
        extra={
            "request_id": request_id,
            "tenant_id": tenant_id,
            "batch_id": batch_id,
            "total": len(extracted_files),
            "successful": successful_count,
            "failed": failed_count,
        },
    )
    
    return BulkUploadResponse(
        batch_id=batch_id,
        total_files=len(extracted_files),
        successful=successful_count,
        failed=failed_count,
        documents=results,
    )


async def fetch_tenant_max_file_size(
    supabase: Client,
    tenant_id: str,
) -> int:
    """
    Fetch tenant-specific maximum file size from Control Plane.
    
    Args:
        supabase: Supabase client with user JWT
        tenant_id: Tenant identifier
        
    Returns:
        Maximum file size in bytes
    """
    try:
        result = (
            supabase.table("tenants")
            .select("settings")
            .eq("id", tenant_id)
            .maybe_single()
            .execute()
        )
        
        if result and result.data:
            tenant_dict = cast(Dict[str, Any], result.data)
            settings = tenant_dict.get("settings")
            if isinstance(settings, dict):
                max_size = settings.get("max_file_size_bytes", DEFAULT_MAX_FILE_SIZE_BYTES)
                if isinstance(max_size, int):
                    return max_size
        
        return DEFAULT_MAX_FILE_SIZE_BYTES
    
    except Exception as e:
        logger.warning(
            "Failed to fetch tenant max file size, using default",
            extra={
                "tenant_id": tenant_id,
                "error": str(e),
                "error_type": type(e).__name__,
                "default_size": DEFAULT_MAX_FILE_SIZE_BYTES,
            },
            exc_info=True,
        )
        return DEFAULT_MAX_FILE_SIZE_BYTES


async def store_document_metadata(
    supabase: Client,
    storage_service: FileStorageService,
    document_id: str,
    tenant_id: str,
    user_id: str,
    filename: str,
    mime_type: str,
    file_size: int,
    content: bytes,
    file_hash: str,
    storage_path: str,
    batch_id: str,
) -> None:
    """
    Store document metadata in database.
    
    Note: File should already be uploaded to storage before calling this function.
    
    This function:
    1. Creates a record in the documents table which automatically
       triggers document processing via database trigger.
    
    Args:
        supabase: Supabase client with user JWT
        storage_service: File storage service (unused, kept for compatibility)
        document_id: Unique document identifier
        tenant_id: Tenant identifier
        user_id: User identifier
        filename: Original filename
        mime_type: Validated MIME type
        file_size: File size in bytes
        content: File content bytes (unused, kept for compatibility)
        file_hash: SHA-256 hash of file content
        storage_path: Storage path where file was uploaded
        batch_id: Batch identifier for bulk upload
        
    Raises:
        Exception: If database insert fails
    """
    # SECURITY: Content is already redacted before this function is called
    # File is already uploaded to storage before this function is called
    
    # Store document metadata
    document_data: Dict[str, Any] = {
        "id": document_id,
        "tenant_id": tenant_id,
        "uploaded_by": user_id,
        "file_hash": file_hash,
        "storage_path": storage_path,
        "original_filename": filename,
        "mime_type": mime_type,
        "file_size_bytes": file_size,
        "source_type": "upload",
        "source_path": f"bulk_upload_batch:{batch_id}",
        "status": "pending",
    }
    
    result = supabase.table("documents").insert(document_data).execute()
    
    # Verify insert succeeded
    if not result.data:
        raise Exception("Database insert returned no data")
