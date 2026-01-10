"""
Review Queue Service - Understanding Plane

Manages prioritized review queue for extractions requiring human review.
Enforces tenant isolation and implements claim mechanism with auto-release.
"""

import logging
from typing import Optional, List, Dict, Any, cast
from uuid import UUID
from supabase import Client

from src.db.models.review_queue import (
    ReviewQueueItem,
    ReviewQueueListResponse,
    ClaimResponse,
    CompleteResponse,
    SkipResponse,
)

logger = logging.getLogger(__name__)


class ReviewQueueService:
    """
    Service for managing review queue.

    Enforces tenant isolation via RLS.
    """

    def __init__(self, supabase_client: Client):
        """
        Initialize review queue service.

        Args:
            supabase_client: Supabase client with user JWT (for tenant isolation)
        """
        self.client = supabase_client

    async def list_queue(
        self,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> ReviewQueueListResponse:
        """
        List review queue items with pagination.

        Args:
            status: Filter by status (pending, claimed, completed, skipped)
            limit: Maximum number of items to return
            offset: Number of items to skip (for pagination)

        Returns:
            ReviewQueueListResponse with queue items sorted by priority
        """
        logger.info(
            "Listing review queue",
            extra={
                "status_filter": status,
                "limit": limit,
                "offset": offset,
            },
        )

        # Release stale claims before listing
        await self.release_stale_claims()

        # Build query for queue items
        query = self.client.table('review_queue').select(
            '''
            id,
            tenant_id,
            document_id,
            extraction_id,
            priority,
            status,
            claimed_by,
            claimed_at,
            completed_at,
            created_at,
            documents(original_filename),
            extractions(overall_confidence, document_type)
            '''
        )

        # Apply status filter if provided
        if status:
            query = query.eq('status', status)

        # Order by priority descending (highest priority first)
        query = query.order('priority', desc=True)

        # Apply pagination
        query = query.range(offset, offset + limit - 1)

        # Execute query
        result = query.execute()

        # Transform results
        items = self._transform_queue_items(result.data)

        # Get counts for different statuses
        counts = await self._get_status_counts()

        logger.info(
            "Listed review queue",
            extra={
                "item_count": len(items),
                "pending_count": counts['pending'],
                "claimed_count": counts['claimed'],
            },
        )

        return ReviewQueueListResponse(
            items=items,
            total_count=counts['total'],
            pending_count=counts['pending'],
            claimed_count=counts['claimed'],
        )

    async def claim_item(
        self,
        item_id: UUID,
        user_id: UUID,
    ) -> ClaimResponse:
        """
        Claim a queue item for review.

        Only pending items can be claimed.
        Uses optimistic locking to prevent race conditions.

        Args:
            item_id: Queue item UUID
            user_id: User UUID claiming the item

        Returns:
            ClaimResponse with success status and item
        """
        logger.info(
            "Claiming queue item",
            extra={
                "item_id": str(item_id),
                "user_id": str(user_id),
            },
        )

        # Attempt to claim (optimistic lock: only update if status is 'pending')
        result = self.client.table('review_queue').update({
            'status': 'claimed',
            'claimed_by': str(user_id),
            'claimed_at': 'now()',
        }).eq('id', str(item_id)).eq('status', 'pending').execute()

        # Check if claim succeeded
        if not result.data or len(result.data) == 0:
            logger.warning(
                "Failed to claim queue item (already claimed or not found)",
                extra={
                    "item_id": str(item_id),
                    "user_id": str(user_id),
                },
            )
            return ClaimResponse(
                success=False,
                item=None,
                message="Item is no longer available (already claimed or completed)",
            )

        # Fetch full item details with joins
        item_result = self.client.table('review_queue').select(
            '''
            id,
            tenant_id,
            document_id,
            extraction_id,
            priority,
            status,
            claimed_by,
            claimed_at,
            completed_at,
            created_at,
            documents(original_filename),
            extractions(overall_confidence, document_type)
            '''
        ).eq('id', str(item_id)).single().execute()

        item = self._transform_queue_item(item_result.data)

        logger.info(
            "Successfully claimed queue item",
            extra={
                "item_id": str(item_id),
                "user_id": str(user_id),
                "extraction_id": str(item.extraction_id),
            },
        )

        return ClaimResponse(
            success=True,
            item=item,
            message="Item claimed successfully",
        )

    async def complete_item(
        self,
        item_id: UUID,
        user_id: UUID,
    ) -> CompleteResponse:
        """
        Mark queue item as completed.

        Only claimed items can be completed, and only by the user who claimed them.

        Args:
            item_id: Queue item UUID
            user_id: User UUID completing the item

        Returns:
            CompleteResponse with success status
        """
        logger.info(
            "Completing queue item",
            extra={
                "item_id": str(item_id),
                "user_id": str(user_id),
            },
        )

        # Update to completed (only if claimed by this user)
        result = self.client.table('review_queue').update({
            'status': 'completed',
            'completed_at': 'now()',
        }).eq('id', str(item_id)).eq('claimed_by', str(user_id)).eq('status', 'claimed').execute()

        # Check if completion succeeded
        if not result.data or len(result.data) == 0:
            logger.warning(
                "Failed to complete queue item (not claimed by user or not found)",
                extra={
                    "item_id": str(item_id),
                    "user_id": str(user_id),
                },
            )
            return CompleteResponse(
                success=False,
                message="Item cannot be completed (not claimed by you or not found)",
            )

        logger.info(
            "Successfully completed queue item",
            extra={
                "item_id": str(item_id),
                "user_id": str(user_id),
            },
        )

        return CompleteResponse(
            success=True,
            message="Item completed successfully",
        )

    async def skip_item(
        self,
        item_id: UUID,
        user_id: UUID,
    ) -> SkipResponse:
        """
        Mark queue item as skipped.

        Only claimed items can be skipped, and only by the user who claimed them.

        Args:
            item_id: Queue item UUID
            user_id: User UUID skipping the item

        Returns:
            SkipResponse with success status
        """
        logger.info(
            "Skipping queue item",
            extra={
                "item_id": str(item_id),
                "user_id": str(user_id),
            },
        )

        # Update to skipped (only if claimed by this user)
        result = self.client.table('review_queue').update({
            'status': 'skipped',
            'completed_at': 'now()',
        }).eq('id', str(item_id)).eq('claimed_by', str(user_id)).eq('status', 'claimed').execute()

        # Check if skip succeeded
        if not result.data or len(result.data) == 0:
            logger.warning(
                "Failed to skip queue item (not claimed by user or not found)",
                extra={
                    "item_id": str(item_id),
                    "user_id": str(user_id),
                },
            )
            return SkipResponse(
                success=False,
                message="Item cannot be skipped (not claimed by you or not found)",
            )

        logger.info(
            "Successfully skipped queue item",
            extra={
                "item_id": str(item_id),
                "user_id": str(user_id),
            },
        )

        return SkipResponse(
            success=True,
            message="Item skipped successfully",
        )

    async def release_stale_claims(self) -> int:
        """
        Release queue items claimed for more than 30 minutes.

        Returns:
            Number of items released
        """
        try:
            # Call database function to release stale claims
            result = self.client.rpc('release_stale_claims', {}).execute()

            released_count = result.data if result.data is not None else 0

            if released_count > 0:
                logger.info(
                    "Released stale queue claims",
                    extra={
                        "released_count": released_count,
                    },
                )

            return released_count

        except Exception as e:
            logger.error(
                "Failed to release stale claims",
                extra={
                    "error": str(e),
                    "error_type": type(e).__name__,
                },
                exc_info=True,
            )
            return 0

    async def _get_status_counts(self) -> Dict[str, int]:
        """
        Get counts for different queue statuses.

        Returns:
            Dictionary with counts for total, pending, and claimed
        """
        try:
            # Get all counts in one query
            all_result = self.client.table('review_queue').select(
                'id', count='exact'
            ).execute()

            pending_result = self.client.table('review_queue').select(
                'id', count='exact'
            ).eq('status', 'pending').execute()

            claimed_result = self.client.table('review_queue').select(
                'id', count='exact'
            ).eq('status', 'claimed').execute()

            return {
                'total': all_result.count or 0,
                'pending': pending_result.count or 0,
                'claimed': claimed_result.count or 0,
            }

        except Exception as e:
            logger.error(
                "Failed to get status counts",
                extra={
                    "error": str(e),
                    "error_type": type(e).__name__,
                },
                exc_info=True,
            )
            return {'total': 0, 'pending': 0, 'claimed': 0}

    def _transform_queue_items(self, data: List[Dict[str, Any]]) -> List[ReviewQueueItem]:
        """
        Transform database rows into ReviewQueueItem models.

        Args:
            data: List of database rows with joined data

        Returns:
            List of ReviewQueueItem models
        """
        items = []
        for row in data:
            items.append(self._transform_queue_item(row))
        return items

    def _transform_queue_item(self, row: Dict[str, Any]) -> ReviewQueueItem:
        """
        Transform a single database row into ReviewQueueItem model.

        Args:
            row: Database row with joined data

        Returns:
            ReviewQueueItem model
        """
        # Extract joined data
        documents_data = row.get('documents')
        extractions_data = row.get('extractions')

        # Handle both list and dict formats from Supabase joins
        document_name = None
        if documents_data:
            if isinstance(documents_data, list) and len(documents_data) > 0:
                document_name = documents_data[0].get('original_filename')
            elif isinstance(documents_data, dict):
                document_name = documents_data.get('original_filename')

        overall_confidence = None
        document_type = None
        if extractions_data:
            if isinstance(extractions_data, list) and len(extractions_data) > 0:
                overall_confidence = extractions_data[0].get('overall_confidence')
                document_type = extractions_data[0].get('document_type')
            elif isinstance(extractions_data, dict):
                overall_confidence = extractions_data.get('overall_confidence')
                document_type = extractions_data.get('document_type')

        return ReviewQueueItem(
            id=UUID(row['id']),
            tenant_id=UUID(row['tenant_id']),
            document_id=UUID(row['document_id']),
            extraction_id=UUID(row['extraction_id']),
            priority=row['priority'],
            status=row['status'],
            claimed_by=UUID(row['claimed_by']) if row.get('claimed_by') else None,
            claimed_at=row.get('claimed_at'),
            completed_at=row.get('completed_at'),
            created_at=row['created_at'],
            document_name=document_name,
            overall_confidence=overall_confidence,
            document_type=document_type,
        )
