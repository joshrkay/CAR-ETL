"""Pydantic models for review queue."""
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class ReviewQueueItem(BaseModel):
    """Review queue item with priority and status."""
    id: UUID = Field(..., description="Queue item UUID")
    tenant_id: UUID = Field(..., description="Tenant UUID")
    document_id: UUID = Field(..., description="Document UUID")
    extraction_id: UUID = Field(..., description="Extraction UUID")
    priority: int = Field(..., ge=0, description="Priority score (higher = more urgent)")
    status: str = Field(..., description="Status: pending, claimed, completed, skipped")
    claimed_by: UUID | None = Field(None, description="User who claimed this item")
    claimed_at: datetime | None = Field(None, description="When item was claimed")
    completed_at: datetime | None = Field(None, description="When item was completed")
    created_at: datetime = Field(..., description="When item was added to queue")

    # Enriched data (joined from other tables)
    document_name: str | None = Field(None, description="Original document filename")
    overall_confidence: float | None = Field(None, ge=0.0, le=1.0, description="Extraction confidence")
    document_type: str | None = Field(None, description="Document type")


class ReviewQueueListResponse(BaseModel):
    """Response for listing review queue items."""
    items: list[ReviewQueueItem] = Field(
        default_factory=list, description="Queue items sorted by priority"
    )
    total_count: int = Field(..., ge=0, description="Total number of items in queue")
    pending_count: int = Field(..., ge=0, description="Number of pending items")
    claimed_count: int = Field(..., ge=0, description="Number of claimed items")


class ClaimRequest(BaseModel):
    """Request to claim a queue item."""
    pass  # No body needed, user derived from auth context


class ClaimResponse(BaseModel):
    """Response after claiming a queue item."""
    success: bool = Field(..., description="Whether claim was successful")
    item: ReviewQueueItem | None = Field(None, description="Claimed queue item")
    message: str = Field(..., description="Status message")


class CompleteRequest(BaseModel):
    """Request to mark queue item as complete."""
    pass  # No body needed, completion is just a status change


class CompleteResponse(BaseModel):
    """Response after completing a queue item."""
    success: bool = Field(..., description="Whether completion was successful")
    message: str = Field(..., description="Status message")


class SkipRequest(BaseModel):
    """Request to skip a queue item."""
    pass  # No body needed, skip is just a status change


class SkipResponse(BaseModel):
    """Response after skipping a queue item."""
    success: bool = Field(..., description="Whether skip was successful")
    message: str = Field(..., description="Status message")
