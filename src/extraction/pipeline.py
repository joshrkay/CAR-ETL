"""
Extraction Pipeline - Understanding Plane

Orchestrates the end-to-end document extraction workflow:
1. Validate document (exists, accessible)
2. Route to parser
3. Parse document
4. Redact PII (if enabled)
5. Extract CRE fields
6. Calculate confidence
7. Store results
8. Update document status
9. Index for search (TODO)
"""

import logging
from datetime import datetime
from typing import Dict, Any, Optional
from uuid import UUID

from supabase import Client

from src.extraction.router import route_document
from src.extraction.extractor import FieldExtractor, ExtractionResult
from src.services.redaction import presidio_redact
from src.db.models.extraction import (
    ExtractionStatus,
    ExtractionSource,
)
from src.exceptions import (
    NotFoundError,
    ValidationError,
    ParserError,
)
from src.services.error_sanitizer import sanitize_exception, get_loggable_error

logger = logging.getLogger(__name__)


class DocumentNotFoundError(NotFoundError):
    """Document not found in database."""
    pass


class DocumentAccessError(ValidationError):
    """Document not accessible from storage."""
    pass


class ExtractionPipelineError(Exception):
    """Base exception for extraction pipeline errors."""
    pass


async def get_document(supabase: Client, document_id: UUID) -> Dict[str, Any]:
    """
    Get document from database.

    Args:
        supabase: Supabase client (service role)
        document_id: Document UUID

    Returns:
        Document record as dictionary

    Raises:
        DocumentNotFoundError: If document doesn't exist
    """
    try:
        response = supabase.table("documents").select("*").eq("id", str(document_id)).execute()

        if not response.data or len(response.data) == 0:
            raise DocumentNotFoundError(f"Document not found: {document_id}")

        document = response.data[0]
        logger.info(
            "Document retrieved",
            extra={
                "document_id": str(document_id),
                "tenant_id": document.get("tenant_id"),
                "mime_type": document.get("mime_type"),
                "status": document.get("status"),
            },
        )
        return document

    except Exception as e:
        if isinstance(e, DocumentNotFoundError):
            raise
        error_info = get_loggable_error(e)
        logger.error(
            "Failed to retrieve document",
            extra={
                "document_id": str(document_id),
                **error_info,
            },
            exc_info=True,
        )
        raise ExtractionPipelineError(
            f"Failed to retrieve document: {error_info['sanitized_message']}"
        ) from e


async def download_document(supabase: Client, storage_path: str, tenant_id: UUID) -> bytes:
    """
    Download document content from Supabase Storage.

    Args:
        supabase: Supabase client (service role)
        storage_path: Path within storage bucket
        tenant_id: Tenant UUID for bucket selection

    Returns:
        Document content as bytes

    Raises:
        DocumentAccessError: If document cannot be accessed
    """
    bucket_name = f"documents-{tenant_id}"

    try:
        # Download file from storage
        response = supabase.storage.from_(bucket_name).download(storage_path)

        if not response:
            raise DocumentAccessError(
                f"Failed to download document from storage: {storage_path}"
            )

        logger.info(
            "Document downloaded from storage",
            extra={
                "bucket": bucket_name,
                "storage_path": storage_path,
                "size": len(response),
            },
        )
        return response

    except Exception as e:
        if isinstance(e, DocumentAccessError):
            raise
        error_info = get_loggable_error(e)
        logger.error(
            "Failed to download document from storage",
            extra={
                "bucket": bucket_name,
                "storage_path": storage_path,
                **error_info,
            },
            exc_info=True,
        )
        raise DocumentAccessError(
            f"Failed to download document from storage: {error_info['sanitized_message']}"
        ) from e


async def parse_document_content(content: bytes, mime_type: str) -> Dict[str, Any]:
    """
    Parse document using router to select optimal parser.

    Args:
        content: Raw document bytes
        mime_type: Document MIME type

    Returns:
        ParseResult with extracted content

    Raises:
        ParserError: If parsing fails
    """
    try:
        parse_result = await route_document(content, mime_type)

        logger.info(
            "Document parsed successfully",
            extra={
                "mime_type": mime_type,
                "text_length": len(parse_result.text),
                "pages": len(parse_result.pages),
                "tables": len(parse_result.tables),
            },
        )

        return {
            "text": parse_result.text,
            "pages": parse_result.pages,
            "tables": parse_result.tables,
            "metadata": parse_result.metadata,
        }

    except Exception as e:
        error_info = get_loggable_error(e)
        logger.error(
            "Failed to parse document",
            extra={
                "mime_type": mime_type,
                **error_info,
            },
            exc_info=True,
        )
        raise ParserError(
            f"Failed to parse document: {error_info['sanitized_message']}"
        ) from e


async def redact_pii(text: str, enabled: bool = True) -> str:
    """
    Redact PII from document text using Presidio.

    Args:
        text: Document text
        enabled: Whether PII redaction is enabled (default: True)

    Returns:
        Redacted text
    """
    if not enabled:
        logger.debug("PII redaction disabled, returning original text")
        return text

    try:
        redacted_text = presidio_redact(text)
        logger.info(
            "PII redaction completed",
            extra={
                "original_length": len(text),
                "redacted_length": len(redacted_text),
            },
        )
        return redacted_text

    except Exception as e:
        error_info = get_loggable_error(e)
        logger.error(
            "PII redaction failed",
            extra=error_info,
            exc_info=True,
        )
        # Re-raise to let caller decide how to handle
        raise


async def extract_cre_fields(
    document_text: str,
    document_type: Optional[str] = None,
) -> ExtractionResult:
    """
    Extract CRE fields from document using LLM.

    Args:
        document_text: Document text (should be redacted)
        document_type: Optional document type hint

    Returns:
        ExtractionResult with extracted fields and confidence

    Raises:
        Exception: If extraction fails
    """
    try:
        extractor = FieldExtractor()

        # Detect document type if not provided
        if document_type is None:
            detection = await extractor.detect_document_type(document_text, "cre")
            document_type = detection["document_type"]
            logger.info(
                "Document type detected",
                extra={
                    "document_type": document_type,
                    "confidence": detection["confidence"],
                },
            )

        # Extract fields
        extraction_result = await extractor.extract_fields(
            document_text,
            industry="cre",
            document_type=document_type,
        )

        logger.info(
            "CRE fields extracted",
            extra={
                "document_type": extraction_result.document_type,
                "field_count": len(extraction_result.fields),
                "overall_confidence": extraction_result.overall_confidence,
            },
        )

        return extraction_result

    except Exception as e:
        error_info = get_loggable_error(e)
        logger.error(
            "Failed to extract CRE fields",
            extra=error_info,
            exc_info=True,
        )
        raise


async def save_extraction(
    supabase: Client,
    document_id: UUID,
    tenant_id: UUID,
    extraction_result: ExtractionResult,
    parser_used: str,
) -> UUID:
    """
    Save extraction results to database.

    Creates extraction record and associated field records.

    Args:
        supabase: Supabase client (service role)
        document_id: Document UUID
        tenant_id: Tenant UUID
        extraction_result: Extraction results from LLM
        parser_used: Parser that was used (ragflow, tika, etc.)

    Returns:
        Extraction UUID

    Raises:
        ExtractionPipelineError: If save fails
    """
    try:
        # Create extraction record
        extraction_data = {
            "tenant_id": str(tenant_id),
            "document_id": str(document_id),
            "status": ExtractionStatus.COMPLETED.value,
            "overall_confidence": extraction_result.overall_confidence,
            "document_type": extraction_result.document_type,
            "parser_used": parser_used,
            "extracted_at": datetime.utcnow().isoformat(),
        }

        extraction_response = (
            supabase.table("extractions")
            .insert(extraction_data)
            .execute()
        )

        if not extraction_response.data:
            raise ExtractionPipelineError("Failed to create extraction record")

        extraction_id = extraction_response.data[0]["id"]

        logger.info(
            "Extraction record created",
            extra={
                "extraction_id": extraction_id,
                "document_id": str(document_id),
                "document_type": extraction_result.document_type,
            },
        )

        # Create extraction field records
        field_records = []
        for field_name, field_data in extraction_result.fields.items():
            field_record = {
                "extraction_id": extraction_id,
                "field_name": field_name,
                "field_value": field_data.value if field_data.value is not None else {},
                "raw_value": field_data.quote,
                "confidence": field_data.confidence,
                "source": ExtractionSource.LLM.value,
                "page_number": field_data.page,
            }
            field_records.append(field_record)

        if field_records:
            supabase.table("extraction_fields").insert(field_records).execute()
            logger.info(
                "Extraction fields saved",
                extra={
                    "extraction_id": extraction_id,
                    "field_count": len(field_records),
                },
            )

        return UUID(extraction_id)

    except Exception as e:
        error_info = get_loggable_error(e)
        logger.error(
            "Failed to save extraction",
            extra={
                "document_id": str(document_id),
                **error_info,
            },
            exc_info=True,
        )
        raise ExtractionPipelineError(
            f"Failed to save extraction: {error_info['sanitized_message']}"
        ) from e


async def update_document_status(
    supabase: Client,
    document_id: UUID,
    status: str,
    error_message: Optional[str] = None,
) -> None:
    """
    Update document status in database.

    Args:
        supabase: Supabase client (service role)
        document_id: Document UUID
        status: New status (pending, processing, ready, failed)
        error_message: Optional error message if status is failed

    Raises:
        ExtractionPipelineError: If update fails
    """
    try:
        update_data = {
            "status": status,
            "updated_at": datetime.utcnow().isoformat(),
        }

        if error_message:
            update_data["error_message"] = error_message

        supabase.table("documents").update(update_data).eq(
            "id", str(document_id)
        ).execute()

        logger.info(
            "Document status updated",
            extra={
                "document_id": str(document_id),
                "status": status,
                "has_error": error_message is not None,
            },
        )

    except Exception as e:
        error_info = get_loggable_error(e)
        logger.error(
            "Failed to update document status",
            extra={
                "document_id": str(document_id),
                "status": status,
                **error_info,
            },
            exc_info=True,
        )
        raise ExtractionPipelineError(
            f"Failed to update document status: {error_info['sanitized_message']}"
        ) from e


async def _validate_and_prepare(
    supabase: Client,
    document_id: UUID,
) -> tuple[Dict[str, Any], UUID]:
    """
    Validate document exists and prepare for processing.

    Args:
        supabase: Supabase client (service role)
        document_id: Document UUID

    Returns:
        Tuple of (document dict, tenant_id)

    Raises:
        DocumentNotFoundError: If document doesn't exist
    """
    document = await get_document(supabase, document_id)
    tenant_id = UUID(document["tenant_id"])
    await update_document_status(supabase, document_id, "processing")
    return document, tenant_id


async def _parse_and_redact(
    supabase: Client,
    document: Dict[str, Any],
    tenant_id: UUID,
) -> tuple[str, str]:
    """
    Download, parse, and redact document content.

    Args:
        supabase: Supabase client (service role)
        document: Document record
        tenant_id: Tenant UUID

    Returns:
        Tuple of (redacted_text, parser_used)

    Raises:
        DocumentAccessError: If download fails
        ParserError: If parsing fails
    """
    content = await download_document(
        supabase,
        document["storage_path"],
        tenant_id,
    )

    parse_result = await parse_document_content(
        content,
        document["mime_type"],
    )

    # TODO: Make redaction configurable via feature flags
    redacted_text = await redact_pii(parse_result["text"], enabled=True)
    parser_used = parse_result["metadata"].get("parser", "unknown")

    return redacted_text, parser_used


async def _extract_and_persist(
    supabase: Client,
    document_id: UUID,
    tenant_id: UUID,
    redacted_text: str,
    parser_used: str,
) -> tuple[UUID, float]:
    """
    Extract fields and persist to database.

    Args:
        supabase: Supabase client (service role)
        document_id: Document UUID
        tenant_id: Tenant UUID
        redacted_text: Redacted document text
        parser_used: Parser name (ragflow, tika, etc.)

    Returns:
        Tuple of (extraction_id, overall_confidence)

    Raises:
        ExtractionPipelineError: If extraction or save fails
    """
    extraction_result = await extract_cre_fields(redacted_text)

    extraction_id = await save_extraction(
        supabase,
        document_id,
        tenant_id,
        extraction_result,
        parser_used=parser_used,
    )

    return extraction_id, extraction_result.overall_confidence


async def _finalize_success(
    supabase: Client,
    document_id: UUID,
    extraction_id: UUID,
    overall_confidence: float,
) -> Dict[str, Any]:
    """
    Finalize successful processing.

    Args:
        supabase: Supabase client (service role)
        document_id: Document UUID
        extraction_id: Extraction UUID
        overall_confidence: Confidence score

    Returns:
        Success result dictionary
    """
    await update_document_status(supabase, document_id, "ready")

    logger.info(
        "Document processing completed",
        extra={
            "document_id": str(document_id),
            "extraction_id": str(extraction_id),
            "overall_confidence": overall_confidence,
        },
    )

    return {
        "document_id": str(document_id),
        "extraction_id": str(extraction_id),
        "status": "ready",
        "overall_confidence": overall_confidence,
        "error": None,
    }


async def _finalize_failure(
    supabase: Client,
    document_id: UUID,
    error: Exception,
) -> Dict[str, Any]:
    """
    Finalize failed processing.

    SECURITY: Sanitizes error message before logging and database storage
    to prevent PII leakage.

    Args:
        supabase: Supabase client (service role)
        document_id: Document UUID
        error: Exception that caused failure

    Returns:
        Failure result dictionary with sanitized error
    """
    # CRITICAL: Sanitize error message to remove PII before logging/storage
    error_info = get_loggable_error(error)
    sanitized_message = error_info["sanitized_message"]

    logger.error(
        "Document processing failed",
        extra={
            "document_id": str(document_id),
            **error_info,
        },
        exc_info=True,
    )

    try:
        # Store ONLY sanitized error in database
        await update_document_status(
            supabase,
            document_id,
            "failed",
            error_message=sanitized_message,
        )
    except Exception as status_error:
        status_error_info = get_loggable_error(status_error)
        logger.error(
            "Failed to update document status after error",
            extra={
                "document_id": str(document_id),
                **status_error_info,
            },
        )

    return {
        "document_id": str(document_id),
        "extraction_id": None,
        "status": "failed",
        "overall_confidence": 0.0,
        "error": sanitized_message,
    }


async def process_document(document_id: UUID, supabase: Client) -> Dict[str, Any]:
    """
    Process a single document through the extraction pipeline.

    Pipeline steps:
    1. Validate document (exists, accessible)
    2. Route to parser
    3. Parse document
    4. Redact PII (if enabled)
    5. Extract CRE fields
    6. Calculate confidence
    7. Store results
    8. Update document status
    9. Index for search (TODO)

    Args:
        document_id: Document UUID to process
        supabase: Supabase client (service role)

    Returns:
        Dictionary with processing results

    Raises:
        Exception: Pipeline errors are caught and logged, status updated
    """
    logger.info(
        "Starting document processing",
        extra={"document_id": str(document_id)},
    )

    try:
        # Step 1: Validate document and prepare
        document, tenant_id = await _validate_and_prepare(supabase, document_id)

        # Steps 2-4: Parse and redact
        redacted_text, parser_used = await _parse_and_redact(
            supabase,
            document,
            tenant_id,
        )

        # Steps 5-7: Extract and persist
        extraction_id, confidence = await _extract_and_persist(
            supabase,
            document_id,
            tenant_id,
            redacted_text,
            parser_used,
        )

        # Step 8: Finalize success
        return await _finalize_success(
            supabase,
            document_id,
            extraction_id,
            confidence,
        )

    except Exception as e:
        return await _finalize_failure(supabase, document_id, e)
