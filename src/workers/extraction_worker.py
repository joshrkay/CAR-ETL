"""
Extraction Worker - Background Processing

Polls the processing queue and orchestrates document extraction workflow.
Features:
- Concurrent processing (configurable, default: 5 parallel)
- Automatic retry on failure (max 3 attempts)
- Dead letter queue for permanent failures
- Graceful shutdown handling
"""

import asyncio
import logging
import signal
import sys
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Set
from uuid import UUID

from supabase import Client

from src.auth.client import create_service_client
from src.extraction.pipeline import process_document

logger = logging.getLogger(__name__)

# Configuration
DEFAULT_CONCURRENCY = 5
DEFAULT_POLL_INTERVAL = 5  # seconds
DEFAULT_MAX_ATTEMPTS = 3
DEFAULT_RETRY_DELAY = 60  # seconds before retrying failed items
DEFAULT_STALE_TIMEOUT = 3600  # seconds (1 hour) - consider processing items stale after this


class ExtractionWorker:
    """
    Background worker for processing documents from queue.

    Polls the processing_queue table for pending items and processes them
    concurrently with retry logic and dead letter queue handling.
    """

    def __init__(
        self,
        concurrency: int = DEFAULT_CONCURRENCY,
        poll_interval: int = DEFAULT_POLL_INTERVAL,
        max_attempts: int = DEFAULT_MAX_ATTEMPTS,
        retry_delay: int = DEFAULT_RETRY_DELAY,
        stale_timeout: int = DEFAULT_STALE_TIMEOUT,
    ):
        """
        Initialize extraction worker.

        Args:
            concurrency: Number of documents to process in parallel (default: 5)
            poll_interval: Seconds between queue polls (default: 5)
            max_attempts: Maximum retry attempts before dead letter (default: 3)
            retry_delay: Seconds to wait before retrying failed items (default: 60)
            stale_timeout: Seconds before considering processing items stale (default: 3600)
        """
        self.concurrency = concurrency
        self.poll_interval = poll_interval
        self.max_attempts = max_attempts
        self.retry_delay = retry_delay
        self.stale_timeout = stale_timeout

        self.supabase: Optional[Client] = None
        self.running = False
        self.processing_ids: Set[str] = set()  # Track items currently being processed
        self.shutdown_event = asyncio.Event()

        # Statistics
        self.stats = {
            "processed": 0,
            "succeeded": 0,
            "failed": 0,
            "dead_lettered": 0,
        }

    async def start(self) -> None:
        """
        Start the extraction worker.

        Runs continuously until shutdown signal received.
        """
        # Initialize Supabase service client (bypasses RLS for queue operations)
        self.supabase = create_service_client()
        self.running = True

        logger.info(
            "Extraction worker starting",
            extra={
                "concurrency": self.concurrency,
                "poll_interval": self.poll_interval,
                "max_attempts": self.max_attempts,
            },
        )

        # Setup signal handlers for graceful shutdown
        self._setup_signal_handlers()

        # Reset stale processing items
        await self._reset_stale_items()

        try:
            # Main worker loop
            while self.running and not self.shutdown_event.is_set():
                try:
                    await self._process_batch()
                except Exception as e:
                    logger.error(
                        "Error in worker batch processing",
                        extra={"error": str(e)},
                        exc_info=True,
                    )

                # Wait before next poll
                try:
                    await asyncio.wait_for(
                        self.shutdown_event.wait(),
                        timeout=self.poll_interval,
                    )
                except asyncio.TimeoutError:
                    # Normal timeout - continue polling
                    pass

        except asyncio.CancelledError:
            logger.info("Worker task cancelled")
        finally:
            await self._shutdown()

    async def stop(self) -> None:
        """
        Stop the extraction worker gracefully.

        Waits for currently processing items to complete.
        """
        logger.info("Extraction worker stopping")
        self.running = False
        self.shutdown_event.set()

    def _setup_signal_handlers(self) -> None:
        """Setup signal handlers for graceful shutdown."""
        def signal_handler(sig, frame):
            logger.info(f"Received signal {sig}, initiating shutdown")
            asyncio.create_task(self.stop())

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

    async def _reset_stale_items(self) -> None:
        """
        Reset stale processing items back to pending.

        Items stuck in 'processing' status for longer than stale_timeout
        are considered stale and reset to 'pending' for retry.
        """
        try:
            stale_cutoff = datetime.utcnow() - timedelta(seconds=self.stale_timeout)

            result = (
                self.supabase.table("processing_queue")
                .update({
                    "status": "pending",
                    "started_at": None,
                })
                .eq("status", "processing")
                .lt("started_at", stale_cutoff.isoformat())
                .execute()
            )

            if result.data:
                logger.warning(
                    "Reset stale processing items",
                    extra={"count": len(result.data)},
                )

        except Exception as e:
            logger.error(
                "Failed to reset stale items",
                extra={"error": str(e)},
                exc_info=True,
            )

    async def _process_batch(self) -> None:
        """
        Process a batch of pending queue items.

        Fetches up to `concurrency` pending items and processes them in parallel.
        """
        # Calculate how many slots are available
        available_slots = self.concurrency - len(self.processing_ids)

        if available_slots <= 0:
            # All slots busy, wait for next poll
            return

        # Fetch pending items from queue
        pending_items = await self._fetch_pending_items(limit=available_slots)

        if not pending_items:
            logger.debug("No pending items in queue")
            return

        logger.info(
            "Processing batch",
            extra={
                "batch_size": len(pending_items),
                "available_slots": available_slots,
            },
        )

        # Process items concurrently
        tasks = []
        for item in pending_items:
            task = asyncio.create_task(self._process_queue_item(item))
            tasks.append(task)

        # Wait for all tasks to complete
        await asyncio.gather(*tasks, return_exceptions=True)

    async def _fetch_pending_items(self, limit: int) -> List[Dict[str, Any]]:
        """
        Fetch pending items from processing queue.

        Selects items with:
        - status = 'pending'
        - attempts < max_attempts
        - Ordered by priority DESC, created_at ASC

        Also includes failed items where retry_delay has elapsed.

        Args:
            limit: Maximum number of items to fetch

        Returns:
            List of queue items
        """
        try:
            # Fetch pending items
            pending_response = (
                self.supabase.table("processing_queue")
                .select("*")
                .eq("status", "pending")
                .lt("attempts", self.max_attempts)
                .order("priority", desc=True)
                .order("created_at", desc=False)
                .limit(limit)
                .execute()
            )

            items = pending_response.data if pending_response.data else []

            # Also check for failed items ready for retry
            if len(items) < limit:
                retry_cutoff = datetime.utcnow() - timedelta(seconds=self.retry_delay)
                retry_response = (
                    self.supabase.table("processing_queue")
                    .select("*")
                    .eq("status", "failed")
                    .lt("attempts", self.max_attempts)
                    .lt("completed_at", retry_cutoff.isoformat())
                    .order("priority", desc=True)
                    .order("created_at", desc=False)
                    .limit(limit - len(items))
                    .execute()
                )

                if retry_response.data:
                    items.extend(retry_response.data)
                    logger.info(
                        "Found items ready for retry",
                        extra={"count": len(retry_response.data)},
                    )

            return items

        except Exception as e:
            logger.error(
                "Failed to fetch pending items",
                extra={"error": str(e)},
                exc_info=True,
            )
            return []

    async def _process_queue_item(self, item: Dict[str, Any]) -> None:
        """
        Process a single queue item.

        Args:
            item: Queue item dictionary
        """
        item_id = item["id"]
        document_id = UUID(item["document_id"])
        attempts = item["attempts"]

        # Add to processing set
        self.processing_ids.add(item_id)

        try:
            logger.info(
                "Processing queue item",
                extra={
                    "item_id": item_id,
                    "document_id": str(document_id),
                    "attempt": attempts + 1,
                    "max_attempts": self.max_attempts,
                },
            )

            # Update queue item status to processing
            await self._update_queue_status(
                item_id,
                status="processing",
                increment_attempts=True,
                started_at=datetime.utcnow(),
            )

            # Process the document
            result = await process_document(document_id, self.supabase)

            # Check result status
            if result["status"] == "ready":
                # Success - mark as completed
                await self._update_queue_status(
                    item_id,
                    status="completed",
                    completed_at=datetime.utcnow(),
                )
                self.stats["succeeded"] += 1
                logger.info(
                    "Document processing succeeded",
                    extra={
                        "item_id": item_id,
                        "document_id": str(document_id),
                        "extraction_id": result.get("extraction_id"),
                    },
                )

            else:
                # Failed - check if should retry or dead letter
                new_attempts = attempts + 1
                if new_attempts >= self.max_attempts:
                    # Max attempts reached - dead letter
                    await self._dead_letter_item(item_id, result.get("error"))
                else:
                    # Retry later
                    await self._update_queue_status(
                        item_id,
                        status="failed",
                        last_error=result.get("error"),
                        completed_at=datetime.utcnow(),
                    )
                    self.stats["failed"] += 1
                    logger.warning(
                        "Document processing failed, will retry",
                        extra={
                            "item_id": item_id,
                            "document_id": str(document_id),
                            "attempt": new_attempts,
                            "max_attempts": self.max_attempts,
                            "error": result.get("error"),
                        },
                    )

            self.stats["processed"] += 1

        except Exception as e:
            # Unexpected error in processing
            error_message = str(e)
            logger.error(
                "Unexpected error processing queue item",
                extra={
                    "item_id": item_id,
                    "document_id": str(document_id),
                    "error": error_message,
                },
                exc_info=True,
            )

            # Update queue item
            new_attempts = attempts + 1
            if new_attempts >= self.max_attempts:
                await self._dead_letter_item(item_id, error_message)
            else:
                await self._update_queue_status(
                    item_id,
                    status="failed",
                    last_error=error_message,
                    completed_at=datetime.utcnow(),
                )

            self.stats["failed"] += 1

        finally:
            # Remove from processing set
            self.processing_ids.discard(item_id)

    async def _update_queue_status(
        self,
        item_id: str,
        status: str,
        increment_attempts: bool = False,
        last_error: Optional[str] = None,
        started_at: Optional[datetime] = None,
        completed_at: Optional[datetime] = None,
    ) -> None:
        """
        Update queue item status.

        Args:
            item_id: Queue item UUID
            status: New status (pending, processing, completed, failed)
            increment_attempts: Whether to increment attempts counter
            last_error: Optional error message
            started_at: Optional start timestamp
            completed_at: Optional completion timestamp
        """
        try:
            update_data = {"status": status}

            if increment_attempts:
                # Use Supabase RPC to increment atomically
                # For now, fetch current value and increment
                current = (
                    self.supabase.table("processing_queue")
                    .select("attempts")
                    .eq("id", item_id)
                    .execute()
                )
                if current.data:
                    update_data["attempts"] = current.data[0]["attempts"] + 1

            if last_error is not None:
                update_data["last_error"] = last_error

            if started_at is not None:
                update_data["started_at"] = started_at.isoformat()

            if completed_at is not None:
                update_data["completed_at"] = completed_at.isoformat()

            self.supabase.table("processing_queue").update(update_data).eq(
                "id", item_id
            ).execute()

        except Exception as e:
            logger.error(
                "Failed to update queue status",
                extra={
                    "item_id": item_id,
                    "status": status,
                    "error": str(e),
                },
                exc_info=True,
            )

    async def _dead_letter_item(self, item_id: str, error_message: Optional[str]) -> None:
        """
        Move item to dead letter queue (mark as permanently failed).

        Args:
            item_id: Queue item UUID
            error_message: Final error message
        """
        try:
            # For now, we'll mark as failed with max attempts
            # In future, could move to separate dead_letter_queue table
            await self._update_queue_status(
                item_id,
                status="failed",
                last_error=f"Dead lettered after {self.max_attempts} attempts: {error_message}",
                completed_at=datetime.utcnow(),
            )

            self.stats["dead_lettered"] += 1

            logger.error(
                "Queue item dead lettered",
                extra={
                    "item_id": item_id,
                    "attempts": self.max_attempts,
                    "error": error_message,
                },
            )

        except Exception as e:
            logger.error(
                "Failed to dead letter item",
                extra={
                    "item_id": item_id,
                    "error": str(e),
                },
                exc_info=True,
            )

    async def _shutdown(self) -> None:
        """
        Graceful shutdown - wait for active processing to complete.
        """
        if self.processing_ids:
            logger.info(
                "Waiting for active processing to complete",
                extra={"active_count": len(self.processing_ids)},
            )

            # Wait up to 60 seconds for active items to complete
            wait_timeout = 60
            wait_start = datetime.utcnow()

            while self.processing_ids and (datetime.utcnow() - wait_start).seconds < wait_timeout:
                await asyncio.sleep(1)

            if self.processing_ids:
                logger.warning(
                    "Shutdown timeout - some items still processing",
                    extra={"remaining_count": len(self.processing_ids)},
                )

        logger.info(
            "Extraction worker stopped",
            extra={
                "stats": self.stats,
            },
        )

    def get_stats(self) -> Dict[str, Any]:
        """
        Get worker statistics.

        Returns:
            Dictionary with processing stats
        """
        return {
            **self.stats,
            "active_count": len(self.processing_ids),
            "running": self.running,
        }


async def main():
    """
    Main entry point for extraction worker.

    Can be run as standalone script:
        python -m src.workers.extraction_worker
    """
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout),
        ],
    )

    # Create and start worker
    worker = ExtractionWorker(
        concurrency=int(os.getenv("WORKER_CONCURRENCY", DEFAULT_CONCURRENCY)),
        poll_interval=int(os.getenv("WORKER_POLL_INTERVAL", DEFAULT_POLL_INTERVAL)),
        max_attempts=int(os.getenv("WORKER_MAX_ATTEMPTS", DEFAULT_MAX_ATTEMPTS)),
    )

    try:
        await worker.start()
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received")
    finally:
        await worker.stop()


if __name__ == "__main__":
    import os
    asyncio.run(main())
