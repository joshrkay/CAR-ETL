"""
Document Upload Routes - Ingestion Plane

Handles document upload with file validation, tenant isolation, and audit logging.
This is the entry point for file ingestion into the CAR Platform.
"""

import logging
from typing import Optional, cast, Any
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status
from pydantic import BaseModel

from src.auth.models import AuthContext
from src.auth.decorators import require_permission
from src.dependencies import get_supabase_client
from src.services.file_validator import (
    FileValidator,
)
from src.services.file_storage import FileStorageService, StorageUploadError
from src.services.redaction import presidio_redact_bytes
from supabase import Client

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/v1/documents",
    tags=["documents"],
)

# Maximum file size configuration (can be overridden per tenant)
DEFAULT_MAX_FILE_SIZE_BYTES = 100 * 1024 * 1024  # 100MB


class DocumentUploadResponse(BaseModel):
    """Response model for successful document upload."""
    document_id: str
    filename: str
    mime_type: str
    file_size: int
    status: str = "pending"
    message: str


class DocumentUploadError(BaseModel):
    """Response model for document upload validation failure."""
    error: str
    validation_errors: list[str]
    file_size: int
    mime_type: str


@router.post(
    "/upload",
    response_model=DocumentUploadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload document for processing",
    description="""
    Upload a document file for ingestion into the CAR Platform.
    
    Security:
    - Requires authentication and 'documents:write' permission
    - File content is validated (magic bytes, structure, size)
    - Tenant isolation is enforced via RLS
    - All uploads are audited
    
    Supported file types:
    - PDF (application/pdf)
    - DOCX (application/vnd.openxmlformats-officedocument.wordprocessingml.document)
    - XLSX (application/vnd.openxmlformats-officedocument.spreadsheetml.sheet)
    - PNG (image/png)
    - JPEG (image/jpeg)
    - Plain text (text/plain)
    - CSV (text/csv)
    
    The file is validated and queued for processing. Processing status can be
    checked via the GET /api/v1/documents/{document_id} endpoint.
    """,
)
async def upload_document(
    request: Request,
    file: UploadFile = File(..., description="Document file to upload"),
    description: str = Form(None, description="Optional document description"),
    auth: AuthContext = Depends(require_permission("documents:write")),
    supabase: Client = Depends(get_supabase_client),
) -> DocumentUploadResponse:
    """
    Upload and validate a document file.
    
    This endpoint:
    1. Validates file content (magic bytes, structure, size)
    2. Stores metadata in database (with tenant isolation)
    3. Queues document for processing
    4. Returns upload confirmation
    
    Args:
        request: FastAPI request object
        file: Uploaded file from multipart/form-data
        description: Optional document description
        auth: Authenticated user context (injected by dependency)
        supabase: Supabase client with user JWT (injected by dependency)
        
    Returns:
        DocumentUploadResponse with document ID and status
        
    Raises:
        HTTPException 400: File validation failed
        HTTPException 401: User not authenticated
        HTTPException 403: Insufficient permissions
        HTTPException 413: File too large
    """
    request_id = getattr(request.state, "request_id", "unknown")
    tenant_id = str(auth.tenant_id)
    user_id = str(auth.user_id)
    
    logger.info(
        "Document upload initiated",
        extra={
            "request_id": request_id,
            "tenant_id": tenant_id,
            "user_id": user_id,
            "filename": file.filename,
            "content_type": file.content_type,
        },
    )
    
    # Step 1: Read file content
    try:
        content = await file.read()
    except (IOError, OSError, RuntimeError) as e:
        logger.error(
            "Failed to read uploaded file",
            extra={
                "request_id": request_id,
                "tenant_id": tenant_id,
                "error": str(e),
                "error_type": type(e).__name__,
            },
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "FILE_READ_ERROR",
                "message": "Failed to read uploaded file",
            },
        ) from e
    except Exception as e:
        logger.error(
            "Unexpected error reading uploaded file",
            extra={
                "request_id": request_id,
                "tenant_id": tenant_id,
                "error": str(e),
                "error_type": type(e).__name__,
            },
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "code": "FILE_READ_ERROR",
                "message": "Failed to read uploaded file",
            },
        )
    
    # Step 2: Get tenant-specific file size limit
    tenant_max_size = await fetch_tenant_max_file_size(
        supabase=supabase,
        tenant_id=tenant_id,
    )
    
    # Step 3: Validate file
    validator = FileValidator(max_file_size=tenant_max_size or DEFAULT_MAX_FILE_SIZE_BYTES)
    
    claimed_mime_type = file.content_type or "application/octet-stream"
    
    validation_result = validator.validate_file(
        content=content,
        claimed_mime=claimed_mime_type,
    )
    
    # Step 4: Reject invalid files
    if not validation_result.valid:
        logger.warning(
            "File validation failed",
            extra={
                "request_id": request_id,
                "tenant_id": tenant_id,
                "filename": file.filename,
                "errors": validation_result.errors,
                "file_size": validation_result.file_size,
            },
        )
        
        # Return 413 for size errors, 400 for other validation errors
        status_code = status.HTTP_413_REQUEST_ENTITY_TOO_LARGE
        if not any("exceeds maximum" in err for err in validation_result.errors):
            status_code = status.HTTP_400_BAD_REQUEST
        
        raise HTTPException(
            status_code=status_code,
            detail={
                "code": "VALIDATION_ERROR",
                "message": "File validation failed",
                "validation_errors": validation_result.errors,
                "file_size": validation_result.file_size,
                "mime_type": validation_result.mime_type,
            },
        )
    
    # Step 5: Redact PII before storage (defense in depth)
    redacted_content = presidio_redact_bytes(content, validation_result.mime_type)
    
    # Step 6: Upload file to storage and store document metadata
    document_id = str(uuid4())
    storage_service = FileStorageService(supabase)
    
    # Calculate SHA-256 hash of redacted content
    file_hash = storage_service.calculate_file_hash(redacted_content)
    
    try:
        await store_document_metadata(
            supabase=supabase,
            storage_service=storage_service,
            document_id=document_id,
            tenant_id=tenant_id,
            user_id=user_id,
            filename=file.filename or "untitled",
            mime_type=validation_result.mime_type,
            file_size=len(redacted_content),
            content=redacted_content,
            file_hash=file_hash,
            description=description,
        )
    except StorageUploadError as e:
        logger.error(
            "Failed to upload file to storage",
            extra={
                "request_id": request_id,
                "tenant_id": tenant_id,
                "document_id": document_id,
                "error": str(e),
            },
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "code": "STORAGE_ERROR",
                "message": "Failed to upload file to storage",
            },
        )
    except Exception as e:
        logger.error(
            "Unexpected error storing document metadata",
            extra={
                "request_id": request_id,
                "tenant_id": tenant_id,
                "error": str(e),
                "error_type": type(e).__name__,
            },
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "code": "STORAGE_ERROR",
                "message": "Failed to store document metadata",
            },
        ) from e
    
    logger.info(
        "Document uploaded successfully",
        extra={
            "request_id": request_id,
            "tenant_id": tenant_id,
            "document_id": document_id,
            "filename": file.filename,
            "file_size": validation_result.file_size,
        },
    )
    
    return DocumentUploadResponse(
        document_id=document_id,
        filename=file.filename or "untitled",
        mime_type=validation_result.mime_type,
        file_size=validation_result.file_size,
        status="pending",
        message="Document uploaded successfully and queued for processing",
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
        Maximum file size in bytes (defaults to 100MB if not configured)
    """
    try:
        # Query tenant settings table for max file size
        result = (
            supabase.table("tenants")
            .select("settings")
            .eq("id", tenant_id)
            .maybe_single()
            .execute()
        )
        
        if result.data and result.data.get("settings"):
            data = cast(dict[str, Any], result.data)
            settings = cast(dict[str, Any], data.get("settings", {}))
            return int(settings.get("max_file_size_bytes", DEFAULT_MAX_FILE_SIZE_BYTES))
        
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
    description: Optional[str],
) -> None:
    """
    Upload file to storage and store document metadata in database.
    
    This function:
    1. Uploads file content to Supabase Storage
    2. Creates a record in the documents table which automatically
       triggers document processing via database trigger.
    
    Args:
        supabase: Supabase client with user JWT
        storage_service: File storage service for uploading files
        document_id: Unique document identifier
        tenant_id: Tenant identifier
        user_id: User identifier
        filename: Original filename
        mime_type: Validated MIME type
        file_size: File size in bytes
        content: File content bytes
        file_hash: SHA-256 hash of file content (already calculated)
        description: Optional document description (stored in source_path)
        
    Raises:
        StorageUploadError: If file upload fails
        Exception: If database insert fails
    """
    # SECURITY: Content is already redacted before this function is called
    # Generate storage path (tenant isolation via bucket, not path)
    storage_path = f"uploads/{document_id}/{filename}"
    
    # Upload file to storage
    storage_service.upload_file(
        content=content,
        storage_path=storage_path,
        tenant_id=UUID(tenant_id),
        mime_type=mime_type,
    )
    
    logger.info(
        "File uploaded to storage successfully",
        extra={
            "document_id": document_id,
            "tenant_id": tenant_id,
            "storage_path": storage_path,
            "bucket_name": f"documents-{tenant_id}",
            "file_size": file_size,
        },
    )
    
    # Store document metadata
    document_data = {
        "id": document_id,
        "tenant_id": tenant_id,
        "uploaded_by": user_id,
        "file_hash": file_hash,
        "storage_path": storage_path,
        "original_filename": filename,
        "mime_type": mime_type,
        "file_size_bytes": file_size,
        "source_type": "upload",
        "source_path": description,  # Store description in source_path if provided
        "status": "pending",
    }
    
    result = supabase.table("documents").insert(document_data).execute()
    
    # Verify insert succeeded
    if not result.data:
        raise Exception("Database insert returned no data")
    
    logger.info(
        "Document uploaded and metadata stored",
        extra={
            "document_id": document_id,
            "tenant_id": tenant_id,
            "filename": filename,
            "file_hash": file_hash,
        },
    )
