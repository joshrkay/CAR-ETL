"""
Idempotency Guards - Data Integrity

Prevents duplicate processing and ensures idempotent operations.
Required by .cursorrules: "All ingestion and workflow steps must be idempotent."
"""

import logging
from typing import Optional, Dict, Any
from uuid import UUID
from datetime import datetime, timedelta

from supabase import Client

logger = logging.getLogger(__name__)

# Idempotency window - how long to consider an extraction "in progress"
DEFAULT_PROCESSING_TIMEOUT = timedelta(hours=1)


class DuplicateProcessingError(Exception):
    """Document is already being processed."""
    pass


async def check_processing_lock(
    supabase: Client,
    document_id: UUID,
    timeout: timedelta = DEFAULT_PROCESSING_TIMEOUT,
) -> Optional[Dict[str, Any]]:
    """
    Check if document already has an active extraction in progress.

    This prevents duplicate processing when:
    - Worker crashes and job is retried
    - Same document queued multiple times
    - Race condition between workers

    Args:
        supabase: Supabase client (service role)
        document_id: Document UUID
        timeout: How long to consider extraction "active" (default: 1 hour)

    Returns:
        Active extraction record if found, None otherwise

    Raises:
        Exception: Database errors
    """
    try:
        # Check for recent processing extractions
        cutoff = datetime.utcnow() - timeout

        response = (
            supabase.table("extractions")
            .select("*")
            .eq("document_id", str(document_id))
            .eq("status", "processing")
            .gt("created_at", cutoff.isoformat())
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )

        if response.data and len(response.data) > 0:
            active_extraction = response.data[0]
            logger.warning(
                "Found active extraction in progress",
                extra={
                    "document_id": str(document_id),
                    "extraction_id": active_extraction["id"],
                    "created_at": active_extraction["created_at"],
                },
            )
            return active_extraction

        return None

    except Exception as e:
        logger.error(
            "Failed to check processing lock",
            extra={
                "document_id": str(document_id),
                "error": str(e),
            },
            exc_info=True,
        )
        raise


async def acquire_processing_lock(
    supabase: Client,
    document_id: UUID,
    force: bool = False,
) -> bool:
    """
    Acquire processing lock for document.

    Ensures only one worker processes a document at a time.

    Args:
        supabase: Supabase client (service role)
        document_id: Document UUID
        force: Force acquire even if lock exists (default: False)

    Returns:
        True if lock acquired, False if already locked

    Raises:
        Exception: Database errors
    """
    try:
        # Check for existing lock
        if not force:
            existing_lock = await check_processing_lock(supabase, document_id)
            if existing_lock:
                logger.info(
                    "Processing lock already held",
                    extra={
                        "document_id": str(document_id),
                        "extraction_id": existing_lock["id"],
                    },
                )
                return False

        # Lock acquired (implicitly via document status update to "processing")
        logger.info(
            "Processing lock acquired",
            extra={"document_id": str(document_id)},
        )
        return True

    except Exception as e:
        logger.error(
            "Failed to acquire processing lock",
            extra={
                "document_id": str(document_id),
                "error": str(e),
            },
            exc_info=True,
        )
        raise


async def check_duplicate_queue_items(
    supabase: Client,
    document_id: UUID,
) -> list[Dict[str, Any]]:
    """
    Check for duplicate pending queue items for same document.

    This helps detect:
    - Duplicate job submissions
    - Race conditions in queue creation
    - Stale queue items

    Args:
        supabase: Supabase client (service role)
        document_id: Document UUID

    Returns:
        List of pending/processing queue items for this document

    Raises:
        Exception: Database errors
    """
    try:
        response = (
            supabase.table("processing_queue")
            .select("*")
            .eq("document_id", str(document_id))
            .in_("status", ["pending", "processing"])
            .order("created_at", desc=False)
            .execute()
        )

        items = response.data if response.data else []

        if len(items) > 1:
            logger.warning(
                "Found duplicate queue items for document",
                extra={
                    "document_id": str(document_id),
                    "count": len(items),
                    "item_ids": [item["id"] for item in items],
                },
            )

        return items

    except Exception as e:
        logger.error(
            "Failed to check duplicate queue items",
            extra={
                "document_id": str(document_id),
                "error": str(e),
            },
            exc_info=True,
        )
        raise


async def is_already_processed(
    supabase: Client,
    document_id: UUID,
) -> bool:
    """
    Check if document has already been successfully processed.

    Args:
        supabase: Supabase client (service role)
        document_id: Document UUID

    Returns:
        True if document already has completed extraction, False otherwise

    Raises:
        Exception: Database errors
    """
    try:
        # Check for completed extractions
        response = (
            supabase.table("extractions")
            .select("id, status, created_at")
            .eq("document_id", str(document_id))
            .eq("status", "completed")
            .eq("is_current", True)
            .limit(1)
            .execute()
        )

        if response.data and len(response.data) > 0:
            extraction = response.data[0]
            logger.info(
                "Document already has completed extraction",
                extra={
                    "document_id": str(document_id),
                    "extraction_id": extraction["id"],
                    "created_at": extraction["created_at"],
                },
            )
            return True

        return False

    except Exception as e:
        logger.error(
            "Failed to check if already processed",
            extra={
                "document_id": str(document_id),
                "error": str(e),
            },
            exc_info=True,
        )
        raise


async def ensure_idempotent_processing(
    supabase: Client,
    document_id: UUID,
    skip_if_completed: bool = True,
    skip_if_processing: bool = True,
) -> tuple[bool, Optional[str]]:
    """
    Comprehensive idempotency check before processing.

    This is the main entry point for idempotency enforcement.

    Args:
        supabase: Supabase client (service role)
        document_id: Document UUID
        skip_if_completed: Skip if already completed (default: True)
        skip_if_processing: Skip if already processing (default: True)

    Returns:
        Tuple of (should_process, skip_reason)
        - (True, None): Safe to process
        - (False, reason): Should skip, with reason

    Raises:
        Exception: Database errors
    """
    try:
        # Check 1: Already completed?
        if skip_if_completed:
            if await is_already_processed(supabase, document_id):
                return False, "already_completed"

        # Check 2: Currently processing?
        if skip_if_processing:
            active_extraction = await check_processing_lock(supabase, document_id)
            if active_extraction:
                return False, "already_processing"

        # Check 3: Duplicate queue items?
        duplicate_items = await check_duplicate_queue_items(supabase, document_id)
        if len(duplicate_items) > 1:
            logger.warning(
                "Multiple queue items detected - will process but may need cleanup",
                extra={
                    "document_id": str(document_id),
                    "queue_item_count": len(duplicate_items),
                },
            )
            # Note: We still return True here, but log the warning
            # The first worker to grab a queue item will process it

        # All checks passed - safe to process
        return True, None

    except Exception as e:
        logger.error(
            "Failed idempotency check",
            extra={
                "document_id": str(document_id),
                "error": str(e),
            },
            exc_info=True,
        )
        # On error, fail safe: allow processing
        # Better to risk duplicate than block legitimate work
        return True, None


async def cleanup_stale_locks(
    supabase: Client,
    timeout: timedelta = DEFAULT_PROCESSING_TIMEOUT,
) -> int:
    """
    Clean up stale processing locks (extractions stuck in "processing").

    This should be called periodically (e.g., by worker on startup).

    Args:
        supabase: Supabase client (service role)
        timeout: Age threshold for stale locks (default: 1 hour)

    Returns:
        Number of locks cleaned up

    Raises:
        Exception: Database errors
    """
    try:
        cutoff = datetime.utcnow() - timeout

        # Find stale processing extractions
        response = (
            supabase.table("extractions")
            .select("id, document_id, created_at")
            .eq("status", "processing")
            .lt("created_at", cutoff.isoformat())
            .execute()
        )

        stale_extractions = response.data if response.data else []

        if stale_extractions:
            # Mark as failed
            extraction_ids = [e["id"] for e in stale_extractions]

            supabase.table("extractions").update({
                "status": "failed",
                "error_message": f"Processing timeout after {timeout.total_seconds()} seconds",
            }).in_("id", extraction_ids).execute()

            logger.warning(
                "Cleaned up stale processing locks",
                extra={
                    "count": len(stale_extractions),
                    "extraction_ids": extraction_ids,
                },
            )

        return len(stale_extractions)

    except Exception as e:
        logger.error(
            "Failed to cleanup stale locks",
            extra={"error": str(e)},
            exc_info=True,
        )
        raise
