"""
Review Queue API Routes - Understanding Plane

Provides endpoints for managing the prioritized review queue for extractions
requiring human review.
"""

import logging
from typing import Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Request, Query, Path, status
from supabase import Client

from src.auth.models import AuthContext
from src.auth.decorators import require_permission
from src.dependencies import get_supabase_client
from src.services.review_queue import ReviewQueueService
from src.db.models.review_queue import (
    ReviewQueueListResponse,
    ClaimRequest,
    ClaimResponse,
    CompleteRequest,
    CompleteResponse,
    SkipRequest,
    SkipResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/v1/review",
    tags=["review"],
)


@router.get(
    "/queue",
    response_model=ReviewQueueListResponse,
    status_code=status.HTTP_200_OK,
    summary="List review queue items",
    description="""
    List prioritized review queue items requiring human review.

    Queue items are sorted by priority (highest first) where priority is calculated based on:
    - Lower confidence = higher priority
    - Critical field issues (base_rent, lease dates < 0.80 confidence)
    - Age bonus (older extractions get higher priority)

    Security:
    - Requires authentication and 'documents:read' permission
    - Tenant isolation enforced via RLS
    - Only shows queue items for your tenant

    Automatically releases stale claims (>30 minutes) before listing.
    """,
)
async def list_queue(
    request: Request,
    status_filter: Optional[str] = Query(
        None,
        alias="status",
        regex="^(pending|claimed|completed|skipped)$",
        description="Filter by status: pending, claimed, completed, skipped",
    ),
    limit: int = Query(50, ge=1, le=100, description="Maximum items to return"),
    offset: int = Query(0, ge=0, description="Number of items to skip (pagination)"),
    auth: AuthContext = Depends(require_permission("documents:read")),
    supabase: Client = Depends(get_supabase_client),
) -> ReviewQueueListResponse:
    """
    List review queue items with pagination.

    Args:
        request: FastAPI request object
        status_filter: Optional status filter
        limit: Maximum number of items to return
        offset: Number of items to skip
        auth: Authenticated user context
        supabase: Supabase client with user JWT

    Returns:
        ReviewQueueListResponse with queue items

    Raises:
        HTTPException 401: User not authenticated
        HTTPException 403: Insufficient permissions
        HTTPException 500: Server error
    """
    request_id = getattr(request.state, "request_id", "unknown")
    tenant_id = str(auth.tenant_id)
    user_id = str(auth.user_id)

    logger.info(
        "Listing review queue",
        extra={
            "request_id": request_id,
            "tenant_id": tenant_id,
            "user_id": user_id,
            "status_filter": status_filter,
            "limit": limit,
            "offset": offset,
        },
    )

    try:
        service = ReviewQueueService(supabase)
        result = await service.list_queue(
            status=status_filter,
            limit=limit,
            offset=offset,
        )

        logger.info(
            "Listed review queue",
            extra={
                "request_id": request_id,
                "tenant_id": tenant_id,
                "item_count": len(result.items),
                "pending_count": result.pending_count,
            },
        )

        return result

    except Exception as e:
        logger.error(
            "Failed to list review queue",
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
            detail="Failed to list review queue",
        )


@router.post(
    "/queue/{item_id}/claim",
    response_model=ClaimResponse,
    status_code=status.HTTP_200_OK,
    summary="Claim queue item for review",
    description="""
    Claim a queue item for review.

    Only pending items can be claimed. Once claimed, the item is locked to the
    claiming user for 30 minutes. After 30 minutes, the claim is automatically
    released and the item becomes available again.

    Uses optimistic locking to prevent race conditions when multiple users
    try to claim the same item.

    Security:
    - Requires authentication and 'documents:write' permission
    - Tenant isolation enforced via RLS
    - Can only claim items from your tenant

    Returns claimed item with full details including document info.
    """,
)
async def claim_item(
    request: Request,
    item_id: UUID = Path(..., description="Queue item UUID to claim"),
    auth: AuthContext = Depends(require_permission("documents:write")),
    supabase: Client = Depends(get_supabase_client),
) -> ClaimResponse:
    """
    Claim a queue item for review.

    Args:
        request: FastAPI request object
        item_id: Queue item UUID
        auth: Authenticated user context
        supabase: Supabase client with user JWT

    Returns:
        ClaimResponse with success status and item details

    Raises:
        HTTPException 401: User not authenticated
        HTTPException 403: Insufficient permissions
        HTTPException 500: Server error
    """
    request_id = getattr(request.state, "request_id", "unknown")
    tenant_id = str(auth.tenant_id)
    user_id = str(auth.user_id)

    logger.info(
        "Claiming queue item",
        extra={
            "request_id": request_id,
            "tenant_id": tenant_id,
            "user_id": user_id,
            "item_id": str(item_id),
        },
    )

    try:
        service = ReviewQueueService(supabase)
        result = await service.claim_item(
            item_id=item_id,
            user_id=UUID(user_id),
        )

        logger.info(
            "Claim attempt completed",
            extra={
                "request_id": request_id,
                "tenant_id": tenant_id,
                "user_id": user_id,
                "item_id": str(item_id),
                "success": result.success,
            },
        )

        return result

    except Exception as e:
        logger.error(
            "Failed to claim queue item",
            extra={
                "request_id": request_id,
                "tenant_id": tenant_id,
                "item_id": str(item_id),
                "error": str(e),
                "error_type": type(e).__name__,
            },
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to claim queue item",
        )


@router.post(
    "/queue/{item_id}/complete",
    response_model=CompleteResponse,
    status_code=status.HTTP_200_OK,
    summary="Mark queue item as completed",
    description="""
    Mark a claimed queue item as completed after review.

    Only the user who claimed the item can mark it as completed.
    The item must be in 'claimed' status.

    Security:
    - Requires authentication and 'documents:write' permission
    - Tenant isolation enforced via RLS
    - Can only complete items claimed by you

    Marks the item with completion timestamp and changes status to 'completed'.
    """,
)
async def complete_item(
    request: Request,
    item_id: UUID = Path(..., description="Queue item UUID to complete"),
    auth: AuthContext = Depends(require_permission("documents:write")),
    supabase: Client = Depends(get_supabase_client),
) -> CompleteResponse:
    """
    Mark queue item as completed.

    Args:
        request: FastAPI request object
        item_id: Queue item UUID
        auth: Authenticated user context
        supabase: Supabase client with user JWT

    Returns:
        CompleteResponse with success status

    Raises:
        HTTPException 401: User not authenticated
        HTTPException 403: Insufficient permissions
        HTTPException 500: Server error
    """
    request_id = getattr(request.state, "request_id", "unknown")
    tenant_id = str(auth.tenant_id)
    user_id = str(auth.user_id)

    logger.info(
        "Completing queue item",
        extra={
            "request_id": request_id,
            "tenant_id": tenant_id,
            "user_id": user_id,
            "item_id": str(item_id),
        },
    )

    try:
        service = ReviewQueueService(supabase)
        result = await service.complete_item(
            item_id=item_id,
            user_id=UUID(user_id),
        )

        logger.info(
            "Complete attempt finished",
            extra={
                "request_id": request_id,
                "tenant_id": tenant_id,
                "user_id": user_id,
                "item_id": str(item_id),
                "success": result.success,
            },
        )

        return result

    except Exception as e:
        logger.error(
            "Failed to complete queue item",
            extra={
                "request_id": request_id,
                "tenant_id": tenant_id,
                "item_id": str(item_id),
                "error": str(e),
                "error_type": type(e).__name__,
            },
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to complete queue item",
        )


@router.post(
    "/queue/{item_id}/skip",
    response_model=SkipResponse,
    status_code=status.HTTP_200_OK,
    summary="Skip queue item",
    description="""
    Mark a claimed queue item as skipped.

    Only the user who claimed the item can skip it.
    The item must be in 'claimed' status.

    Use this when you want to skip an item during review without completing it.
    Skipped items are marked with completion timestamp and status 'skipped'.

    Security:
    - Requires authentication and 'documents:write' permission
    - Tenant isolation enforced via RLS
    - Can only skip items claimed by you
    """,
)
async def skip_item(
    request: Request,
    item_id: UUID = Path(..., description="Queue item UUID to skip"),
    auth: AuthContext = Depends(require_permission("documents:write")),
    supabase: Client = Depends(get_supabase_client),
) -> SkipResponse:
    """
    Skip queue item.

    Args:
        request: FastAPI request object
        item_id: Queue item UUID
        auth: Authenticated user context
        supabase: Supabase client with user JWT

    Returns:
        SkipResponse with success status

    Raises:
        HTTPException 401: User not authenticated
        HTTPException 403: Insufficient permissions
        HTTPException 500: Server error
    """
    request_id = getattr(request.state, "request_id", "unknown")
    tenant_id = str(auth.tenant_id)
    user_id = str(auth.user_id)

    logger.info(
        "Skipping queue item",
        extra={
            "request_id": request_id,
            "tenant_id": tenant_id,
            "user_id": user_id,
            "item_id": str(item_id),
        },
    )

    try:
        service = ReviewQueueService(supabase)
        result = await service.skip_item(
            item_id=item_id,
            user_id=UUID(user_id),
        )

        logger.info(
            "Skip attempt finished",
            extra={
                "request_id": request_id,
                "tenant_id": tenant_id,
                "user_id": user_id,
                "item_id": str(item_id),
                "success": result.success,
            },
        )

        return result

    except Exception as e:
        logger.error(
            "Failed to skip queue item",
            extra={
                "request_id": request_id,
                "tenant_id": tenant_id,
                "item_id": str(item_id),
                "error": str(e),
                "error_type": type(e).__name__,
            },
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to skip queue item",
        )
