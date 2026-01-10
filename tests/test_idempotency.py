"""
Tests for idempotency guards - prevent duplicate processing.

Critical for data integrity - .cursorrules requirement.
"""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, Mock, patch
from uuid import uuid4

import pytest

from src.extraction.idempotency import (
    acquire_processing_lock,
    check_duplicate_queue_items,
    check_processing_lock,
    cleanup_stale_locks,
    ensure_idempotent_processing,
    is_already_processed,
)


class TestCheckProcessingLock:
    """Tests for check_processing_lock function."""

    @pytest.mark.asyncio
    async def test_no_active_lock(self):
        """Test when no active extraction exists."""
        document_id = uuid4()
        mock_supabase = Mock()

        mock_supabase.table.return_value.select.return_value.eq.return_value.eq.return_value.gt.return_value.order.return_value.limit.return_value.execute.return_value = Mock(
            data=[]
        )

        result = await check_processing_lock(mock_supabase, document_id)

        assert result is None

    @pytest.mark.asyncio
    async def test_active_lock_exists(self):
        """Test when active extraction exists."""
        document_id = uuid4()
        extraction_id = uuid4()

        active_extraction = {
            "id": str(extraction_id),
            "document_id": str(document_id),
            "status": "processing",
            "created_at": datetime.utcnow().isoformat(),
        }

        mock_supabase = Mock()
        mock_supabase.table.return_value.select.return_value.eq.return_value.eq.return_value.gt.return_value.order.return_value.limit.return_value.execute.return_value = Mock(
            data=[active_extraction]
        )

        result = await check_processing_lock(mock_supabase, document_id)

        assert result is not None
        assert result["id"] == str(extraction_id)
        assert result["status"] == "processing"

    @pytest.mark.asyncio
    async def test_old_processing_ignored(self):
        """Test that old processing extractions are ignored."""
        document_id = uuid4()

        # Old extraction (2 hours ago)
        {
            "id": str(uuid4()),
            "created_at": (datetime.utcnow() - timedelta(hours=2)).isoformat(),
        }

        mock_supabase = Mock()
        # Simulating that query filters out old items
        mock_supabase.table.return_value.select.return_value.eq.return_value.eq.return_value.gt.return_value.order.return_value.limit.return_value.execute.return_value = Mock(
            data=[]  # Old items filtered by gt() clause
        )

        result = await check_processing_lock(mock_supabase, document_id)

        assert result is None


class TestAcquireProcessingLock:
    """Tests for acquire_processing_lock function."""

    @pytest.mark.asyncio
    async def test_acquire_when_no_lock(self):
        """Test acquiring lock when none exists."""
        document_id = uuid4()
        mock_supabase = Mock()

        with patch("src.extraction.idempotency.check_processing_lock", new_callable=AsyncMock) as mock_check:
            mock_check.return_value = None  # No existing lock

            result = await acquire_processing_lock(mock_supabase, document_id)

            assert result is True
            mock_check.assert_called_once()

    @pytest.mark.asyncio
    async def test_cannot_acquire_when_locked(self):
        """Test cannot acquire when lock exists."""
        document_id = uuid4()
        mock_supabase = Mock()

        existing_lock = {
            "id": str(uuid4()),
            "status": "processing",
        }

        with patch("src.extraction.idempotency.check_processing_lock", new_callable=AsyncMock) as mock_check:
            mock_check.return_value = existing_lock

            result = await acquire_processing_lock(mock_supabase, document_id)

            assert result is False

    @pytest.mark.asyncio
    async def test_force_acquire(self):
        """Test force acquiring lock even if exists."""
        document_id = uuid4()
        mock_supabase = Mock()

        with patch("src.extraction.idempotency.check_processing_lock", new_callable=AsyncMock) as mock_check:
            mock_check.return_value = {"id": str(uuid4())}

            result = await acquire_processing_lock(mock_supabase, document_id, force=True)

            assert result is True
            # Should not check for existing lock when force=True
            mock_check.assert_not_called()


class TestCheckDuplicateQueueItems:
    """Tests for check_duplicate_queue_items function."""

    @pytest.mark.asyncio
    async def test_no_duplicates(self):
        """Test when only one queue item exists."""
        document_id = uuid4()
        mock_supabase = Mock()

        mock_supabase.table.return_value.select.return_value.eq.return_value.in_.return_value.order.return_value.execute.return_value = Mock(
            data=[{"id": str(uuid4()), "status": "pending"}]
        )

        result = await check_duplicate_queue_items(mock_supabase, document_id)

        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_duplicates_found(self):
        """Test when multiple queue items exist."""
        document_id = uuid4()

        items = [
            {"id": str(uuid4()), "status": "pending"},
            {"id": str(uuid4()), "status": "pending"},
            {"id": str(uuid4()), "status": "processing"},
        ]

        mock_supabase = Mock()
        mock_supabase.table.return_value.select.return_value.eq.return_value.in_.return_value.order.return_value.execute.return_value = Mock(
            data=items
        )

        result = await check_duplicate_queue_items(mock_supabase, document_id)

        assert len(result) == 3

    @pytest.mark.asyncio
    async def test_no_queue_items(self):
        """Test when no queue items exist."""
        document_id = uuid4()
        mock_supabase = Mock()

        mock_supabase.table.return_value.select.return_value.eq.return_value.in_.return_value.order.return_value.execute.return_value = Mock(
            data=[]
        )

        result = await check_duplicate_queue_items(mock_supabase, document_id)

        assert len(result) == 0


class TestIsAlreadyProcessed:
    """Tests for is_already_processed function."""

    @pytest.mark.asyncio
    async def test_not_processed(self):
        """Test when document not processed."""
        document_id = uuid4()
        mock_supabase = Mock()

        mock_supabase.table.return_value.select.return_value.eq.return_value.eq.return_value.eq.return_value.limit.return_value.execute.return_value = Mock(
            data=[]
        )

        result = await is_already_processed(mock_supabase, document_id)

        assert result is False

    @pytest.mark.asyncio
    async def test_already_processed(self):
        """Test when document already processed."""
        document_id = uuid4()

        completed_extraction = {
            "id": str(uuid4()),
            "status": "completed",
            "is_current": True,
            "created_at": datetime.utcnow().isoformat(),
        }

        mock_supabase = Mock()
        mock_supabase.table.return_value.select.return_value.eq.return_value.eq.return_value.eq.return_value.limit.return_value.execute.return_value = Mock(
            data=[completed_extraction]
        )

        result = await is_already_processed(mock_supabase, document_id)

        assert result is True


class TestEnsureIdempotentProcessing:
    """Tests for ensure_idempotent_processing function."""

    @pytest.mark.asyncio
    async def test_safe_to_process(self):
        """Test when safe to process (no conflicts)."""
        document_id = uuid4()
        mock_supabase = Mock()

        with patch("src.extraction.idempotency.is_already_processed", new_callable=AsyncMock) as mock_is_processed, \
             patch("src.extraction.idempotency.check_processing_lock", new_callable=AsyncMock) as mock_check_lock, \
             patch("src.extraction.idempotency.check_duplicate_queue_items", new_callable=AsyncMock) as mock_check_dupes:

            mock_is_processed.return_value = False
            mock_check_lock.return_value = None
            mock_check_dupes.return_value = [{"id": str(uuid4())}]  # Single item

            should_process, skip_reason = await ensure_idempotent_processing(
                mock_supabase,
                document_id,
            )

            assert should_process is True
            assert skip_reason is None

    @pytest.mark.asyncio
    async def test_skip_already_completed(self):
        """Test skip when already completed."""
        document_id = uuid4()
        mock_supabase = Mock()

        with patch("src.extraction.idempotency.is_already_processed", new_callable=AsyncMock) as mock_is_processed:
            mock_is_processed.return_value = True

            should_process, skip_reason = await ensure_idempotent_processing(
                mock_supabase,
                document_id,
            )

            assert should_process is False
            assert skip_reason == "already_completed"

    @pytest.mark.asyncio
    async def test_skip_already_processing(self):
        """Test skip when already processing."""
        document_id = uuid4()
        mock_supabase = Mock()

        active_lock = {
            "id": str(uuid4()),
            "status": "processing",
        }

        with patch("src.extraction.idempotency.is_already_processed", new_callable=AsyncMock) as mock_is_processed, \
             patch("src.extraction.idempotency.check_processing_lock", new_callable=AsyncMock) as mock_check_lock:

            mock_is_processed.return_value = False
            mock_check_lock.return_value = active_lock

            should_process, skip_reason = await ensure_idempotent_processing(
                mock_supabase,
                document_id,
            )

            assert should_process is False
            assert skip_reason == "already_processing"

    @pytest.mark.asyncio
    async def test_warn_on_duplicates_but_allow(self):
        """Test warns on duplicate queue items but allows processing."""
        document_id = uuid4()
        mock_supabase = Mock()

        duplicate_items = [
            {"id": str(uuid4())},
            {"id": str(uuid4())},
            {"id": str(uuid4())},
        ]

        with patch("src.extraction.idempotency.is_already_processed", new_callable=AsyncMock) as mock_is_processed, \
             patch("src.extraction.idempotency.check_processing_lock", new_callable=AsyncMock) as mock_check_lock, \
             patch("src.extraction.idempotency.check_duplicate_queue_items", new_callable=AsyncMock) as mock_check_dupes:

            mock_is_processed.return_value = False
            mock_check_lock.return_value = None
            mock_check_dupes.return_value = duplicate_items

            should_process, skip_reason = await ensure_idempotent_processing(
                mock_supabase,
                document_id,
            )

            # Should still process (first worker wins)
            assert should_process is True
            assert skip_reason is None

    @pytest.mark.asyncio
    async def test_fail_safe_on_error(self):
        """Test fails safe (allows processing) on error."""
        document_id = uuid4()
        mock_supabase = Mock()

        with patch("src.extraction.idempotency.is_already_processed", new_callable=AsyncMock) as mock_is_processed:
            mock_is_processed.side_effect = Exception("Database error")

            # Should fail safe: allow processing
            should_process, skip_reason = await ensure_idempotent_processing(
                mock_supabase,
                document_id,
            )

            assert should_process is True
            assert skip_reason is None


class TestCleanupStaleLocks:
    """Tests for cleanup_stale_locks function."""

    @pytest.mark.asyncio
    async def test_no_stale_locks(self):
        """Test when no stale locks exist."""
        mock_supabase = Mock()

        mock_supabase.table.return_value.select.return_value.eq.return_value.lt.return_value.execute.return_value = Mock(
            data=[]
        )

        count = await cleanup_stale_locks(mock_supabase)

        assert count == 0

    @pytest.mark.asyncio
    async def test_cleanup_stale_locks(self):
        """Test cleaning up stale locks."""
        stale_extractions = [
            {
                "id": str(uuid4()),
                "document_id": str(uuid4()),
                "created_at": (datetime.utcnow() - timedelta(hours=2)).isoformat(),
            },
            {
                "id": str(uuid4()),
                "document_id": str(uuid4()),
                "created_at": (datetime.utcnow() - timedelta(hours=3)).isoformat(),
            },
        ]

        mock_supabase = Mock()

        # Mock select query
        mock_supabase.table.return_value.select.return_value.eq.return_value.lt.return_value.execute.return_value = Mock(
            data=stale_extractions
        )

        # Mock update query
        mock_supabase.table.return_value.update.return_value.in_.return_value.execute.return_value = Mock(
            data=stale_extractions
        )

        count = await cleanup_stale_locks(mock_supabase)

        assert count == 2

        # Verify update was called
        mock_supabase.table.return_value.update.assert_called_once()


class TestIdempotencyIntegration:
    """Integration tests for idempotency workflow."""

    @pytest.mark.asyncio
    async def test_concurrent_processing_prevented(self):
        """Test that concurrent processing is prevented."""
        document_id = uuid4()
        mock_supabase = Mock()

        # Simulate worker 1 checking lock - none exists
        with patch("src.extraction.idempotency.is_already_processed", new_callable=AsyncMock) as mock_is_processed, \
             patch("src.extraction.idempotency.check_processing_lock", new_callable=AsyncMock) as mock_check_lock, \
             patch("src.extraction.idempotency.check_duplicate_queue_items", new_callable=AsyncMock) as mock_check_dupes:

            mock_is_processed.return_value = False
            mock_check_lock.return_value = None
            mock_check_dupes.return_value = [{"id": str(uuid4())}]

            # Worker 1 proceeds
            should_process_1, _ = await ensure_idempotent_processing(
                mock_supabase,
                document_id,
            )
            assert should_process_1 is True

            # Simulate worker 2 checking lock - now exists
            mock_check_lock.return_value = {
                "id": str(uuid4()),
                "status": "processing",
            }

            # Worker 2 should skip
            should_process_2, reason_2 = await ensure_idempotent_processing(
                mock_supabase,
                document_id,
            )
            assert should_process_2 is False
            assert reason_2 == "already_processing"

    @pytest.mark.asyncio
    async def test_retry_after_completion(self):
        """Test that completed documents are skipped on retry."""
        document_id = uuid4()
        mock_supabase = Mock()

        with patch("src.extraction.idempotency.is_already_processed", new_callable=AsyncMock) as mock_is_processed, \
             patch("src.extraction.idempotency.check_processing_lock", new_callable=AsyncMock) as mock_check_lock, \
             patch("src.extraction.idempotency.check_duplicate_queue_items", new_callable=AsyncMock) as mock_check_dupes:

            # First attempt: not completed
            mock_is_processed.return_value = False
            mock_check_lock.return_value = None
            mock_check_dupes.return_value = [{"id": str(uuid4())}]

            should_process_1, _ = await ensure_idempotent_processing(
                mock_supabase,
                document_id,
            )
            assert should_process_1 is True

            # Second attempt: now completed
            mock_is_processed.return_value = True

            should_process_2, reason_2 = await ensure_idempotent_processing(
                mock_supabase,
                document_id,
            )
            assert should_process_2 is False
            assert reason_2 == "already_completed"
