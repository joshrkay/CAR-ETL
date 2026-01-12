"""
Tests for extraction worker background processing.

Comprehensive test coverage for ExtractionWorker class including:
- Initialization and configuration
from typing import Any

- Start/stop lifecycle
- Batch processing and concurrency
- Retry logic and dead letter queue
- Idempotency integration
- Graceful shutdown
- Error handling and sanitization
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from uuid import uuid4
from datetime import datetime, timedelta

from src.workers.extraction_worker import (
    ExtractionWorker,
    DEFAULT_CONCURRENCY,
    DEFAULT_POLL_INTERVAL,
    DEFAULT_MAX_ATTEMPTS,
    DEFAULT_RETRY_DELAY,
    DEFAULT_STALE_TIMEOUT,
)


class TestExtractionWorkerInit:
    """Tests for ExtractionWorker initialization."""

    def test_init_with_defaults(self) -> None:
        """Test worker initialization with default parameters."""
        worker = ExtractionWorker()

        assert worker.concurrency == DEFAULT_CONCURRENCY
        assert worker.poll_interval == DEFAULT_POLL_INTERVAL
        assert worker.max_attempts == DEFAULT_MAX_ATTEMPTS
        assert worker.retry_delay == DEFAULT_RETRY_DELAY
        assert worker.stale_timeout == DEFAULT_STALE_TIMEOUT
        assert worker.supabase is None
        assert worker.running is False
        assert len(worker.processing_ids) == 0
        assert worker.stats["processed"] == 0
        assert worker.stats["succeeded"] == 0
        assert worker.stats["failed"] == 0
        assert worker.stats["dead_lettered"] == 0

    def test_init_with_custom_parameters(self) -> None:
        """Test worker initialization with custom parameters."""
        worker = ExtractionWorker(
            concurrency=10,
            poll_interval=3,
            max_attempts=5,
            retry_delay=120,
            stale_timeout=7200,
        )

        assert worker.concurrency == 10
        assert worker.poll_interval == 3
        assert worker.max_attempts == 5
        assert worker.retry_delay == 120
        assert worker.stale_timeout == 7200

    def test_get_stats(self) -> None:
        """Test get_stats method."""
        worker = ExtractionWorker()
        worker.processing_ids.add("test-id")
        worker.stats["processed"] = 10
        worker.stats["succeeded"] = 8
        worker.running = True

        stats = worker.get_stats()

        assert stats["processed"] == 10
        assert stats["succeeded"] == 8
        assert stats["active_count"] == 1
        assert stats["running"] is True


class TestExtractionWorkerLifecycle:
    """Tests for worker start/stop lifecycle."""

    @pytest.mark.asyncio
    async def test_stop_sets_flags(self) -> None:
        """Test that stop method sets shutdown flags."""
        worker = ExtractionWorker()
        worker.running = True

        await worker.stop()

        assert worker.running is False
        assert worker.shutdown_event.is_set()

    @pytest.mark.asyncio
    async def test_start_initializes_supabase(self) -> None:
        """Test that start initializes Supabase client."""
        worker = ExtractionWorker(poll_interval=1)

        with patch("src.workers.extraction_worker.create_service_client") as mock_create:
            mock_supabase = Mock()
            mock_create.return_value = mock_supabase

            # Mock the methods called during startup
            with patch.object(worker, "_setup_signal_handlers"):
                with patch.object(worker, "_reset_stale_items", new_callable=AsyncMock):
                    with patch.object(worker, "_cleanup_stale_extraction_locks", new_callable=AsyncMock):
                        with patch.object(worker, "_process_batch", new_callable=AsyncMock):
                            # Stop worker after first iteration
                            async def stop_after_batch():
                                await worker.stop()

                            worker._process_batch.side_effect = stop_after_batch

                            await worker.start()

            assert worker.supabase == mock_supabase
            assert worker.running is False  # Should be False after stop

    @pytest.mark.asyncio
    async def test_start_resets_stale_items(self) -> None:
        """Test that start resets stale items."""
        worker = ExtractionWorker(poll_interval=1)

        with patch("src.workers.extraction_worker.create_service_client") as mock_create:
            mock_supabase = Mock()
            mock_create.return_value = mock_supabase

            with patch.object(worker, "_setup_signal_handlers"):
                with patch.object(worker, "_reset_stale_items", new_callable=AsyncMock) as mock_reset:
                    with patch.object(worker, "_cleanup_stale_extraction_locks", new_callable=AsyncMock):
                        with patch.object(worker, "_process_batch", new_callable=AsyncMock):
                            # Stop immediately
                            async def stop_now():
                                await worker.stop()

                            worker._process_batch.side_effect = stop_now

                            await worker.start()

                            mock_reset.assert_called_once()

    @pytest.mark.asyncio
    async def test_start_cleanups_stale_locks(self) -> None:
        """Test that start cleanups stale extraction locks."""
        worker = ExtractionWorker(poll_interval=1)

        with patch("src.workers.extraction_worker.create_service_client") as mock_create:
            mock_supabase = Mock()
            mock_create.return_value = mock_supabase

            with patch.object(worker, "_setup_signal_handlers"):
                with patch.object(worker, "_reset_stale_items", new_callable=AsyncMock):
                    with patch.object(worker, "_cleanup_stale_extraction_locks", new_callable=AsyncMock) as mock_cleanup:
                        with patch.object(worker, "_process_batch", new_callable=AsyncMock):
                            # Stop immediately
                            async def stop_now():
                                await worker.stop()

                            worker._process_batch.side_effect = stop_now

                            await worker.start()

                            mock_cleanup.assert_called_once()


class TestResetStaleItems:
    """Tests for _reset_stale_items method."""

    @pytest.mark.asyncio
    async def test_reset_stale_items_success(self) -> None:
        """Test successful reset of stale items."""
        worker = ExtractionWorker(stale_timeout=3600)
        worker.supabase = Mock()

        stale_items = [
            {"id": str(uuid4()), "status": "processing"},
            {"id": str(uuid4()), "status": "processing"},
        ]

        mock_response = Mock(data=stale_items)
        worker.supabase.table.return_value.update.return_value.eq.return_value.lt.return_value.execute.return_value = mock_response

        await worker._reset_stale_items()

        # Verify update was called with correct status
        worker.supabase.table.assert_called_with("processing_queue")
        worker.supabase.table.return_value.update.assert_called_once()
        update_data = worker.supabase.table.return_value.update.call_args[0][0]
        assert update_data["status"] == "pending"
        assert update_data["started_at"] is None

    @pytest.mark.asyncio
    async def test_reset_stale_items_none_found(self) -> None:
        """Test reset when no stale items exist."""
        worker = ExtractionWorker()
        worker.supabase = Mock()

        mock_response = Mock(data=None)
        worker.supabase.table.return_value.update.return_value.eq.return_value.lt.return_value.execute.return_value = mock_response

        # Should not raise exception
        await worker._reset_stale_items()

    @pytest.mark.asyncio
    async def test_reset_stale_items_error_handling(self) -> None:
        """Test error handling in reset stale items."""
        worker = ExtractionWorker()
        worker.supabase = Mock()

        worker.supabase.table.return_value.update.return_value.eq.return_value.lt.return_value.execute.side_effect = Exception(
            "Database error"
        )

        # Should not raise exception - errors are logged
        await worker._reset_stale_items()


class TestCleanupStaleLocks:
    """Tests for _cleanup_stale_extraction_locks method."""

    @pytest.mark.asyncio
    async def test_cleanup_stale_locks_found(self) -> None:
        """Test cleanup when stale locks are found."""
        worker = ExtractionWorker()
        worker.supabase = Mock()

        with patch("src.workers.extraction_worker.cleanup_stale_locks", new_callable=AsyncMock) as mock_cleanup:
            mock_cleanup.return_value = 3

            await worker._cleanup_stale_extraction_locks()

            mock_cleanup.assert_called_once_with(worker.supabase)

    @pytest.mark.asyncio
    async def test_cleanup_stale_locks_none_found(self) -> None:
        """Test cleanup when no stale locks exist."""
        worker = ExtractionWorker()
        worker.supabase = Mock()

        with patch("src.workers.extraction_worker.cleanup_stale_locks", new_callable=AsyncMock) as mock_cleanup:
            mock_cleanup.return_value = 0

            await worker._cleanup_stale_extraction_locks()

            mock_cleanup.assert_called_once_with(worker.supabase)

    @pytest.mark.asyncio
    async def test_cleanup_stale_locks_error_handling(self) -> None:
        """Test error handling in cleanup stale locks."""
        worker = ExtractionWorker()
        worker.supabase = Mock()

        with patch("src.workers.extraction_worker.cleanup_stale_locks", new_callable=AsyncMock) as mock_cleanup:
            mock_cleanup.side_effect = Exception("Cleanup failed")

            # Should not raise exception - errors are logged
            await worker._cleanup_stale_extraction_locks()


class TestFetchPendingItems:
    """Tests for _fetch_pending_items method."""

    @pytest.mark.asyncio
    async def test_fetch_pending_items_success(self) -> None:
        """Test successful fetching of pending items."""
        worker = ExtractionWorker()
        worker.supabase = Mock()

        pending_items = [
            {
                "id": str(uuid4()),
                "document_id": str(uuid4()),
                "status": "pending",
                "attempts": 0,
                "priority": 1,
            },
            {
                "id": str(uuid4()),
                "document_id": str(uuid4()),
                "status": "pending",
                "attempts": 1,
                "priority": 2,
            },
        ]

        # Mock pending query response
        mock_response = Mock(data=pending_items)
        pending_chain = (
            worker.supabase.table.return_value.select.return_value.eq.return_value.lt.return_value
            .order.return_value.order.return_value.limit.return_value.execute
        )
        pending_chain.return_value = mock_response

        # Mock retry query to return empty
        retry_empty = Mock(data=[])
        retry_chain = (
            worker.supabase.table.return_value.select.return_value.eq.return_value.lt.return_value
            .lt.return_value.order.return_value.order.return_value.limit.return_value.execute
        )
        retry_chain.return_value = retry_empty

        result = await worker._fetch_pending_items(limit=5)

        assert len(result) == 2
        assert result[0]["status"] == "pending"
        assert result[1]["status"] == "pending"

    @pytest.mark.asyncio
    async def test_fetch_pending_items_includes_retries(self) -> None:
        """Test that fetch includes failed items ready for retry."""
        worker = ExtractionWorker(retry_delay=60)
        worker.supabase = Mock()

        pending_items = [
            {
                "id": str(uuid4()),
                "status": "pending",
                "attempts": 0,
            }
        ]

        retry_items = [
            {
                "id": str(uuid4()),
                "status": "failed",
                "attempts": 1,
                "completed_at": (datetime.utcnow() - timedelta(seconds=120)).isoformat(),
            }
        ]

        # Mock pending query
        mock_pending_response = Mock(data=pending_items)
        pending_chain = (
            worker.supabase.table.return_value.select.return_value.eq.return_value.lt.return_value
            .order.return_value.order.return_value.limit.return_value.execute
        )
        pending_chain.return_value = mock_pending_response

        # Mock retry query
        retry_response = Mock(data=retry_items)
        retry_chain = (
            worker.supabase.table.return_value.select.return_value.eq.return_value.lt.return_value
            .lt.return_value.order.return_value.order.return_value.limit.return_value.execute
        )
        retry_chain.return_value = retry_response

        result = await worker._fetch_pending_items(limit=5)

        assert len(result) == 2
        assert result[0]["status"] == "pending"
        assert result[1]["status"] == "failed"

    @pytest.mark.asyncio
    async def test_fetch_pending_items_database_error(self) -> None:
        """Test error handling when database query fails."""
        worker = ExtractionWorker()
        worker.supabase = Mock()

        worker.supabase.table.return_value.select.return_value.eq.return_value.lt.return_value.order.return_value.order.return_value.limit.return_value.execute.side_effect = Exception(
            "Database error"
        )

        result = await worker._fetch_pending_items(limit=5)

        # Should return empty list on error
        assert result == []


class TestProcessBatch:
    """Tests for _process_batch method."""

    @pytest.mark.asyncio
    async def test_process_batch_no_slots_available(self) -> None:
        """Test that batch processing skips when all slots are busy."""
        worker = ExtractionWorker(concurrency=2)
        worker.processing_ids = {"id1", "id2"}

        with patch.object(worker, "_fetch_pending_items", new_callable=AsyncMock) as mock_fetch:
            await worker._process_batch()

            # Should not fetch items if no slots available
            mock_fetch.assert_not_called()

    @pytest.mark.asyncio
    async def test_process_batch_no_pending_items(self) -> None:
        """Test batch processing when no items are pending."""
        worker = ExtractionWorker(concurrency=5)

        with patch.object(worker, "_fetch_pending_items", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = []

            await worker._process_batch()

            mock_fetch.assert_called_once_with(limit=5)

    @pytest.mark.asyncio
    async def test_process_batch_processes_items_concurrently(self) -> None:
        """Test that batch processing handles multiple items concurrently."""
        worker = ExtractionWorker(concurrency=5)
        worker.supabase = Mock()

        items = [
            {"id": str(uuid4()), "document_id": str(uuid4()), "attempts": 0},
            {"id": str(uuid4()), "document_id": str(uuid4()), "attempts": 0},
        ]

        with patch.object(worker, "_fetch_pending_items", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = items

            with patch.object(worker, "_process_queue_item", new_callable=AsyncMock) as mock_process:
                await worker._process_batch()

                mock_fetch.assert_called_once_with(limit=5)
                assert mock_process.call_count == 2

    @pytest.mark.asyncio
    async def test_process_batch_respects_available_slots(self) -> None:
        """Test that batch processing respects available concurrency slots."""
        worker = ExtractionWorker(concurrency=5)
        worker.processing_ids = {"id1", "id2"}  # 2 slots occupied

        items = [
            {"id": str(uuid4()), "document_id": str(uuid4()), "attempts": 0},
        ]

        with patch.object(worker, "_fetch_pending_items", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = items

            with patch.object(worker, "_process_queue_item", new_callable=AsyncMock):
                await worker._process_batch()

                # Should request only 3 items (5 total - 2 occupied)
                mock_fetch.assert_called_once_with(limit=3)


class TestProcessQueueItem:
    """Tests for _process_queue_item method."""

    @pytest.mark.asyncio
    async def test_process_queue_item_success(self) -> None:
        """Test successful processing of queue item."""
        worker = ExtractionWorker(max_attempts=3)
        worker.supabase = Mock()

        item_id = str(uuid4())
        document_id = uuid4()
        item = {
            "id": item_id,
            "document_id": str(document_id),
            "attempts": 0,
        }

        with patch("src.workers.extraction_worker.ensure_idempotent_processing", new_callable=AsyncMock) as mock_idempotent:
            mock_idempotent.return_value = (True, None)

            with patch("src.workers.extraction_worker.process_document", new_callable=AsyncMock) as mock_process:
                mock_process.return_value = {
                    "status": "ready",
                    "extraction_id": str(uuid4()),
                }

                with patch.object(worker, "_update_queue_status", new_callable=AsyncMock) as mock_update:
                    await worker._process_queue_item(item)

                    # Should update to processing, then to completed
                    assert mock_update.call_count == 2
                    # First call: status=processing
                    assert mock_update.call_args_list[0][1]["status"] == "processing"
                    assert mock_update.call_args_list[0][1]["increment_attempts"] is True
                    # Second call: status=completed
                    assert mock_update.call_args_list[1][1]["status"] == "completed"

                    assert worker.stats["processed"] == 1
                    assert worker.stats["succeeded"] == 1

    @pytest.mark.asyncio
    async def test_process_queue_item_idempotency_skip(self) -> None:
        """Test that item is skipped when already processed."""
        worker = ExtractionWorker()
        worker.supabase = Mock()

        item_id = str(uuid4())
        document_id = uuid4()
        item = {
            "id": item_id,
            "document_id": str(document_id),
            "attempts": 0,
        }

        with patch("src.workers.extraction_worker.ensure_idempotent_processing", new_callable=AsyncMock) as mock_idempotent:
            mock_idempotent.return_value = (False, "already_completed")

            with patch.object(worker, "_update_queue_status", new_callable=AsyncMock) as mock_update:
                await worker._process_queue_item(item)

                # Should only update to completed (skip processing)
                assert mock_update.call_count == 1
                assert mock_update.call_args[1]["status"] == "completed"

                assert worker.stats["processed"] == 1
                assert worker.stats["succeeded"] == 1

    @pytest.mark.asyncio
    async def test_process_queue_item_failure_with_retry(self) -> None:
        """Test processing failure that will be retried."""
        worker = ExtractionWorker(max_attempts=3)
        worker.supabase = Mock()

        item_id = str(uuid4())
        document_id = uuid4()
        item = {
            "id": item_id,
            "document_id": str(document_id),
            "attempts": 1,
        }

        with patch("src.workers.extraction_worker.ensure_idempotent_processing", new_callable=AsyncMock) as mock_idempotent:
            mock_idempotent.return_value = (True, None)

            with patch("src.workers.extraction_worker.process_document", new_callable=AsyncMock) as mock_process:
                mock_process.return_value = {
                    "status": "failed",
                    "error": "Extraction failed",
                }

                with patch.object(worker, "_update_queue_status", new_callable=AsyncMock) as mock_update:
                    await worker._process_queue_item(item)

                    # Should update to processing, then to failed
                    assert mock_update.call_count == 2
                    assert mock_update.call_args_list[1][1]["status"] == "failed"

                    assert worker.stats["processed"] == 1
                    assert worker.stats["failed"] == 1
                    assert worker.stats["dead_lettered"] == 0

    @pytest.mark.asyncio
    async def test_process_queue_item_max_attempts_dead_letter(self) -> None:
        """Test that item is dead lettered after max attempts."""
        worker = ExtractionWorker(max_attempts=3)
        worker.supabase = Mock()

        item_id = str(uuid4())
        document_id = uuid4()
        item = {
            "id": item_id,
            "document_id": str(document_id),
            "attempts": 2,  # Will be 3 after increment
        }

        with patch("src.workers.extraction_worker.ensure_idempotent_processing", new_callable=AsyncMock) as mock_idempotent:
            mock_idempotent.return_value = (True, None)

            with patch("src.workers.extraction_worker.process_document", new_callable=AsyncMock) as mock_process:
                mock_process.return_value = {
                    "status": "failed",
                    "error": "Extraction failed",
                }

                with patch.object(worker, "_update_queue_status", new_callable=AsyncMock):
                    with patch.object(worker, "_dead_letter_item", new_callable=AsyncMock) as mock_dead_letter:
                        await worker._process_queue_item(item)

                        mock_dead_letter.assert_called_once()
                        assert worker.stats["processed"] == 1

    @pytest.mark.asyncio
    async def test_process_queue_item_unexpected_exception(self) -> None:
        """Test handling of unexpected exceptions during processing."""
        worker = ExtractionWorker(max_attempts=3)
        worker.supabase = Mock()

        item_id = str(uuid4())
        document_id = uuid4()
        item = {
            "id": item_id,
            "document_id": str(document_id),
            "attempts": 0,
        }

        with patch("src.workers.extraction_worker.ensure_idempotent_processing", new_callable=AsyncMock) as mock_idempotent:
            mock_idempotent.side_effect = Exception("Unexpected error")

            with patch.object(worker, "_update_queue_status", new_callable=AsyncMock) as mock_update:
                await worker._process_queue_item(item)

                # Should update with error
                mock_update.assert_called_once()
                assert mock_update.call_args[1]["status"] == "failed"

                assert worker.stats["failed"] == 1

    @pytest.mark.asyncio
    async def test_process_queue_item_removes_from_processing_set(self) -> None:
        """Test that item is removed from processing set on completion."""
        worker = ExtractionWorker()
        worker.supabase = Mock()

        item_id = str(uuid4())
        document_id = uuid4()
        item = {
            "id": item_id,
            "document_id": str(document_id),
            "attempts": 0,
        }

        with patch("src.workers.extraction_worker.ensure_idempotent_processing", new_callable=AsyncMock) as mock_idempotent:
            mock_idempotent.return_value = (False, "skip")

            with patch.object(worker, "_update_queue_status", new_callable=AsyncMock):
                await worker._process_queue_item(item)

                # Should not be in processing set
                assert item_id not in worker.processing_ids


class TestUpdateQueueStatus:
    """Tests for _update_queue_status method."""

    @pytest.mark.asyncio
    async def test_update_queue_status_basic(self) -> None:
        """Test basic queue status update."""
        worker = ExtractionWorker()
        worker.supabase = Mock()

        item_id = str(uuid4())

        await worker._update_queue_status(item_id, status="completed")

        worker.supabase.table.assert_called_with("processing_queue")
        worker.supabase.table.return_value.update.assert_called_once()
        update_data = worker.supabase.table.return_value.update.call_args[0][0]
        assert update_data["status"] == "completed"

    @pytest.mark.asyncio
    async def test_update_queue_status_with_increment_attempts(self) -> None:
        """Test queue status update with attempt increment."""
        worker = ExtractionWorker()
        worker.supabase = Mock()

        item_id = str(uuid4())

        await worker._update_queue_status(
            item_id,
            status="processing",
            increment_attempts=True,
        )

        # Should call RPC to increment attempts
        worker.supabase.rpc.assert_called_once_with(
            "increment_processing_queue_attempts",
            {"item_id": item_id},
        )

    @pytest.mark.asyncio
    async def test_update_queue_status_with_timestamps(self) -> None:
        """Test queue status update with timestamps."""
        worker = ExtractionWorker()
        worker.supabase = Mock()

        item_id = str(uuid4())
        started_at = datetime.utcnow()
        completed_at = datetime.utcnow()

        await worker._update_queue_status(
            item_id,
            status="completed",
            started_at=started_at,
            completed_at=completed_at,
        )

        update_data = worker.supabase.table.return_value.update.call_args[0][0]
        assert update_data["started_at"] == started_at.isoformat()
        assert update_data["completed_at"] == completed_at.isoformat()

    @pytest.mark.asyncio
    async def test_update_queue_status_with_error(self) -> None:
        """Test queue status update with error message."""
        worker = ExtractionWorker()
        worker.supabase = Mock()

        item_id = str(uuid4())
        error_message = "Processing failed: invalid format"

        await worker._update_queue_status(
            item_id,
            status="failed",
            last_error=error_message,
        )

        update_data = worker.supabase.table.return_value.update.call_args[0][0]
        assert update_data["last_error"] == error_message

    @pytest.mark.asyncio
    async def test_update_queue_status_error_handling(self) -> None:
        """Test error handling in queue status update."""
        worker = ExtractionWorker()
        worker.supabase = Mock()

        item_id = str(uuid4())

        worker.supabase.table.return_value.update.return_value.eq.return_value.execute.side_effect = Exception(
            "Database error"
        )

        # Should not raise exception - errors are logged
        await worker._update_queue_status(item_id, status="failed")


class TestDeadLetterItem:
    """Tests for _dead_letter_item method."""

    @pytest.mark.asyncio
    async def test_dead_letter_item_success(self) -> None:
        """Test successful dead letter item."""
        worker = ExtractionWorker(max_attempts=3)
        worker.supabase = Mock()

        item_id = str(uuid4())
        error_message = "Final error message"

        with patch.object(worker, "_update_queue_status", new_callable=AsyncMock) as mock_update:
            await worker._dead_letter_item(item_id, error_message)

            mock_update.assert_called_once()
            assert mock_update.call_args[1]["status"] == "failed"
            assert "Dead lettered" in mock_update.call_args[1]["last_error"]
            assert error_message in mock_update.call_args[1]["last_error"]

            assert worker.stats["dead_lettered"] == 1

    @pytest.mark.asyncio
    async def test_dead_letter_item_error_handling(self) -> None:
        """Test error handling in dead letter item."""
        worker = ExtractionWorker()
        worker.supabase = Mock()

        item_id = str(uuid4())

        with patch.object(worker, "_update_queue_status", new_callable=AsyncMock) as mock_update:
            mock_update.side_effect = Exception("Update failed")

            # Should not raise exception - errors are logged
            await worker._dead_letter_item(item_id, "error message")


class TestShutdown:
    """Tests for _shutdown method."""

    @pytest.mark.asyncio
    async def test_shutdown_waits_for_active_items(self) -> None:
        """Test that shutdown waits for active items to complete."""
        worker = ExtractionWorker()
        worker.processing_ids = {"id1", "id2"}

        # Simulate items completing during shutdown
        async def remove_items():
            await asyncio.sleep(0.1)
            worker.processing_ids.clear()

        asyncio.create_task(remove_items())

        await worker._shutdown()

        # Should have waited for items to complete
        assert len(worker.processing_ids) == 0

    @pytest.mark.asyncio
    async def test_shutdown_timeout_with_remaining_items(self) -> None:
        """Test shutdown timeout when items don't complete."""
        worker = ExtractionWorker()
        worker.processing_ids = {"id1", "id2"}

        # Don't remove items - test timeout
        with patch("src.workers.extraction_worker.datetime") as mock_datetime:
            # Mock time to simulate timeout
            start_time = datetime.utcnow()
            end_time = start_time + timedelta(seconds=61)

            mock_datetime.utcnow.side_effect = [start_time, end_time]

            await worker._shutdown()

            # Should have timed out with items remaining
            assert len(worker.processing_ids) == 2

    @pytest.mark.asyncio
    async def test_shutdown_no_active_items(self) -> None:
        """Test shutdown when no active items exist."""
        worker = ExtractionWorker()
        worker.stats["processed"] = 10
        worker.stats["succeeded"] = 8

        await worker._shutdown()

        # Should complete without waiting
        assert len(worker.processing_ids) == 0


class TestErrorSanitization:
    """Tests for error sanitization in worker."""

    @pytest.mark.asyncio
    async def test_error_sanitization_in_processing(self) -> None:
        """Test that errors are sanitized before storing."""
        worker = ExtractionWorker()
        worker.supabase = Mock()

        item_id = str(uuid4())
        document_id = uuid4()
        item = {
            "id": item_id,
            "document_id": str(document_id),
            "attempts": 0,
        }

        with patch("src.workers.extraction_worker.ensure_idempotent_processing", new_callable=AsyncMock) as mock_idempotent:
            mock_idempotent.return_value = (True, None)

            with patch("src.workers.extraction_worker.process_document", new_callable=AsyncMock) as mock_process:
                # Return error with potentially sensitive information
                mock_process.return_value = {
                    "status": "failed",
                    "error": "Database connection failed: host=secret-db.internal",
                }

                with patch("src.workers.extraction_worker.sanitize_exception") as mock_sanitize:
                    mock_sanitize.return_value = "Database connection failed"

                    with patch.object(worker, "_update_queue_status", new_callable=AsyncMock):
                        await worker._process_queue_item(item)

                        # Should sanitize error
                        mock_sanitize.assert_called_once()

    @pytest.mark.asyncio
    async def test_error_sanitization_in_exception_handling(self) -> None:
        """Test that unexpected exceptions are sanitized."""
        worker = ExtractionWorker()
        worker.supabase = Mock()

        item_id = str(uuid4())
        document_id = uuid4()
        item = {
            "id": item_id,
            "document_id": str(document_id),
            "attempts": 0,
        }

        with patch("src.workers.extraction_worker.ensure_idempotent_processing", new_callable=AsyncMock):
            with patch("src.workers.extraction_worker.get_loggable_error") as mock_get_error:
                mock_get_error.return_value = {
                    "sanitized_message": "Internal error",
                    "error_type": "Exception",
                }

                # Raise exception
                with patch("src.workers.extraction_worker.process_document", new_callable=AsyncMock) as mock_process:
                    mock_process.side_effect = Exception("Sensitive error info")

                    with patch.object(worker, "_update_queue_status", new_callable=AsyncMock):
                        await worker._process_queue_item(item)

                        # Should get loggable error
                        mock_get_error.assert_called()


class TestConcurrencyControl:
    """Tests for concurrency control."""

    @pytest.mark.asyncio
    async def test_processing_ids_tracked(self) -> None:
        """Test that processing IDs are tracked during processing."""
        worker = ExtractionWorker()
        worker.supabase = Mock()

        item_id = str(uuid4())
        document_id = uuid4()
        item = {
            "id": item_id,
            "document_id": str(document_id),
            "attempts": 0,
        }

        processing_ids_during_processing = None

        async def capture_processing_ids(*args, **kwargs):
            nonlocal processing_ids_during_processing
            processing_ids_during_processing = worker.processing_ids.copy()
            return (False, "skip")

        with patch("src.workers.extraction_worker.ensure_idempotent_processing", new_callable=AsyncMock) as mock_idempotent:
            mock_idempotent.side_effect = capture_processing_ids

            with patch.object(worker, "_update_queue_status", new_callable=AsyncMock):
                await worker._process_queue_item(item)

                # Should have been in processing set during execution
                assert item_id in processing_ids_during_processing
                # Should be removed after completion
                assert item_id not in worker.processing_ids

    @pytest.mark.asyncio
    async def test_concurrent_item_limit(self) -> None:
        """Test that concurrent processing respects limits."""
        worker = ExtractionWorker(concurrency=2)

        # Simulate 3 items trying to process
        worker.processing_ids = {"id1", "id2"}

        with patch.object(worker, "_fetch_pending_items", new_callable=AsyncMock) as mock_fetch:
            await worker._process_batch()

            # Should not fetch when at capacity
            mock_fetch.assert_not_called()
