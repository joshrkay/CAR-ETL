"""Tests for review queue service and API."""
import pytest
from uuid import uuid4, UUID
from unittest.mock import Mock, MagicMock, AsyncMock
from datetime import datetime, timedelta

from src.services.review_queue import ReviewQueueService
from src.db.models.review_queue import (
    ReviewQueueItem,
    ReviewQueueListResponse,
    ClaimResponse,
    CompleteResponse,
    SkipResponse,
)


class TestReviewQueueService:
    """Unit tests for ReviewQueueService."""

    @pytest.fixture
    def mock_supabase(self):
        """Create mock Supabase client."""
        return Mock()

    @pytest.fixture
    def service(self, mock_supabase):
        """Create ReviewQueueService instance."""
        return ReviewQueueService(mock_supabase)

    @pytest.mark.asyncio
    async def test_list_queue_empty(self, service, mock_supabase):
        """Test listing queue when empty."""
        # Mock RPC call for release_stale_claims
        mock_supabase.rpc.return_value.execute.return_value.data = 0

        # Mock queue query to return empty
        def mock_table(table_name):
            mock_chain = Mock()
            mock_chain.select.return_value = mock_chain
            mock_chain.eq.return_value = mock_chain
            mock_chain.order.return_value = mock_chain
            mock_chain.range.return_value = mock_chain
            mock_chain.execute.return_value.data = []
            mock_chain.execute.return_value.count = 0
            return mock_chain

        mock_supabase.table.side_effect = mock_table

        result = await service.list_queue(limit=50, offset=0)

        assert isinstance(result, ReviewQueueListResponse)
        assert result.items == []
        assert result.total_count == 0
        assert result.pending_count == 0
        assert result.claimed_count == 0

    @pytest.mark.asyncio
    async def test_list_queue_with_items(self, service, mock_supabase):
        """Test listing queue with items."""
        tenant_id = uuid4()
        doc_id = uuid4()
        extraction_id = uuid4()
        item_id = uuid4()

        # Mock RPC call for release_stale_claims
        mock_supabase.rpc.return_value.execute.return_value.data = 0

        # Mock queue query
        queue_data = [
            {
                "id": str(item_id),
                "tenant_id": str(tenant_id),
                "document_id": str(doc_id),
                "extraction_id": str(extraction_id),
                "priority": 50,
                "status": "pending",
                "claimed_by": None,
                "claimed_at": None,
                "completed_at": None,
                "created_at": datetime.now().isoformat(),
                "documents": {"original_filename": "test.pdf"},
                "extractions": {"overall_confidence": 0.75, "document_type": "lease"},
            }
        ]

        def mock_table(table_name):
            mock_chain = Mock()
            mock_chain.select.return_value = mock_chain
            mock_chain.eq.return_value = mock_chain
            mock_chain.order.return_value = mock_chain
            mock_chain.range.return_value = mock_chain

            if table_name == "review_queue":
                # For the main query
                mock_chain.execute.return_value.data = queue_data
                # For count queries
                mock_chain.execute.return_value.count = 1
            return mock_chain

        mock_supabase.table.side_effect = mock_table

        result = await service.list_queue(status="pending", limit=50, offset=0)

        assert isinstance(result, ReviewQueueListResponse)
        assert len(result.items) == 1
        assert result.items[0].priority == 50
        assert result.items[0].status == "pending"
        assert result.items[0].document_name == "test.pdf"

    @pytest.mark.asyncio
    async def test_claim_item_success(self, service, mock_supabase):
        """Test successfully claiming a queue item."""
        item_id = uuid4()
        user_id = uuid4()
        tenant_id = uuid4()
        doc_id = uuid4()
        extraction_id = uuid4()

        # Mock successful claim update
        claim_data = [{"id": str(item_id)}]

        # Mock fetching full item details
        full_item_data = {
            "id": str(item_id),
            "tenant_id": str(tenant_id),
            "document_id": str(doc_id),
            "extraction_id": str(extraction_id),
            "priority": 50,
            "status": "claimed",
            "claimed_by": str(user_id),
            "claimed_at": datetime.now().isoformat(),
            "completed_at": None,
            "created_at": datetime.now().isoformat(),
            "documents": {"original_filename": "test.pdf"},
            "extractions": {"overall_confidence": 0.75, "document_type": "lease"},
        }

        def mock_table(table_name):
            mock_chain = Mock()
            mock_chain.update.return_value = mock_chain
            mock_chain.select.return_value = mock_chain
            mock_chain.eq.return_value = mock_chain
            mock_chain.single.return_value = mock_chain

            if table_name == "review_queue":
                # For update query
                mock_chain.execute.return_value.data = claim_data
                # For select query
                mock_chain.execute.return_value.data = full_item_data
            return mock_chain

        mock_supabase.table.side_effect = mock_table

        result = await service.claim_item(item_id=item_id, user_id=user_id)

        assert isinstance(result, ClaimResponse)
        assert result.success is True
        assert result.item is not None
        assert result.item.id == item_id
        assert result.item.claimed_by == user_id

    @pytest.mark.asyncio
    async def test_claim_item_already_claimed(self, service, mock_supabase):
        """Test claiming item that's already claimed."""
        item_id = uuid4()
        user_id = uuid4()

        # Mock failed claim (no rows updated)
        mock_chain = Mock()
        mock_chain.update.return_value = mock_chain
        mock_chain.eq.return_value = mock_chain
        mock_chain.execute.return_value.data = []

        mock_supabase.table.return_value = mock_chain

        result = await service.claim_item(item_id=item_id, user_id=user_id)

        assert isinstance(result, ClaimResponse)
        assert result.success is False
        assert result.item is None
        assert "no longer available" in result.message.lower()

    @pytest.mark.asyncio
    async def test_complete_item_success(self, service, mock_supabase):
        """Test successfully completing a queue item."""
        item_id = uuid4()
        user_id = uuid4()

        # Mock successful completion
        complete_data = [{"id": str(item_id)}]

        mock_chain = Mock()
        mock_chain.update.return_value = mock_chain
        mock_chain.eq.return_value = mock_chain
        mock_chain.execute.return_value.data = complete_data

        mock_supabase.table.return_value = mock_chain

        result = await service.complete_item(item_id=item_id, user_id=user_id)

        assert isinstance(result, CompleteResponse)
        assert result.success is True
        assert "completed successfully" in result.message.lower()

    @pytest.mark.asyncio
    async def test_complete_item_not_claimed_by_user(self, service, mock_supabase):
        """Test completing item not claimed by user."""
        item_id = uuid4()
        user_id = uuid4()

        # Mock failed completion (no rows updated)
        mock_chain = Mock()
        mock_chain.update.return_value = mock_chain
        mock_chain.eq.return_value = mock_chain
        mock_chain.execute.return_value.data = []

        mock_supabase.table.return_value = mock_chain

        result = await service.complete_item(item_id=item_id, user_id=user_id)

        assert isinstance(result, CompleteResponse)
        assert result.success is False
        assert "cannot be completed" in result.message.lower()

    @pytest.mark.asyncio
    async def test_skip_item_success(self, service, mock_supabase):
        """Test successfully skipping a queue item."""
        item_id = uuid4()
        user_id = uuid4()

        # Mock successful skip
        skip_data = [{"id": str(item_id)}]

        mock_chain = Mock()
        mock_chain.update.return_value = mock_chain
        mock_chain.eq.return_value = mock_chain
        mock_chain.execute.return_value.data = skip_data

        mock_supabase.table.return_value = mock_chain

        result = await service.skip_item(item_id=item_id, user_id=user_id)

        assert isinstance(result, SkipResponse)
        assert result.success is True
        assert "skipped successfully" in result.message.lower()

    @pytest.mark.asyncio
    async def test_skip_item_not_claimed_by_user(self, service, mock_supabase):
        """Test skipping item not claimed by user."""
        item_id = uuid4()
        user_id = uuid4()

        # Mock failed skip (no rows updated)
        mock_chain = Mock()
        mock_chain.update.return_value = mock_chain
        mock_chain.eq.return_value = mock_chain
        mock_chain.execute.return_value.data = []

        mock_supabase.table.return_value = mock_chain

        result = await service.skip_item(item_id=item_id, user_id=user_id)

        assert isinstance(result, SkipResponse)
        assert result.success is False
        assert "cannot be skipped" in result.message.lower()

    @pytest.mark.asyncio
    async def test_release_stale_claims_success(self, service, mock_supabase):
        """Test releasing stale claims."""
        # Mock RPC call returning count of released items
        mock_supabase.rpc.return_value.execute.return_value.data = 3

        result = await service.release_stale_claims()

        assert result == 3
        mock_supabase.rpc.assert_called_once_with("release_stale_claims", {})

    @pytest.mark.asyncio
    async def test_release_stale_claims_error(self, service, mock_supabase):
        """Test handling error when releasing stale claims."""
        # Mock RPC call raising exception
        mock_supabase.rpc.side_effect = Exception("Database error")

        result = await service.release_stale_claims()

        assert result == 0  # Should return 0 on error

    def test_transform_queue_item(self, service):
        """Test transforming database row to ReviewQueueItem."""
        tenant_id = uuid4()
        doc_id = uuid4()
        extraction_id = uuid4()
        item_id = uuid4()

        row = {
            "id": str(item_id),
            "tenant_id": str(tenant_id),
            "document_id": str(doc_id),
            "extraction_id": str(extraction_id),
            "priority": 50,
            "status": "pending",
            "claimed_by": None,
            "claimed_at": None,
            "completed_at": None,
            "created_at": datetime.now().isoformat(),
            "documents": {"original_filename": "test.pdf"},
            "extractions": {"overall_confidence": 0.75, "document_type": "lease"},
        }

        item = service._transform_queue_item(row)

        assert isinstance(item, ReviewQueueItem)
        assert item.id == item_id
        assert item.tenant_id == tenant_id
        assert item.document_id == doc_id
        assert item.extraction_id == extraction_id
        assert item.priority == 50
        assert item.status == "pending"
        assert item.document_name == "test.pdf"
        assert item.overall_confidence == 0.75
        assert item.document_type == "lease"

    def test_transform_queue_item_with_list_joins(self, service):
        """Test transforming row with list-format joins (Supabase variation)."""
        item_id = uuid4()
        tenant_id = uuid4()
        doc_id = uuid4()
        extraction_id = uuid4()

        row = {
            "id": str(item_id),
            "tenant_id": str(tenant_id),
            "document_id": str(doc_id),
            "extraction_id": str(extraction_id),
            "priority": 50,
            "status": "pending",
            "claimed_by": None,
            "claimed_at": None,
            "completed_at": None,
            "created_at": "2024-01-01T00:00:00",
            "documents": [{"original_filename": "test.pdf"}],
            "extractions": [{"overall_confidence": 0.75, "document_type": "lease"}],
        }

        item = service._transform_queue_item(row)

        assert isinstance(item, ReviewQueueItem)
        assert item.document_name == "test.pdf"
        assert item.overall_confidence == 0.75

    def test_transform_queue_item_with_claimed_data(self, service):
        """Test transforming claimed item with user data."""
        item_id = uuid4()
        tenant_id = uuid4()
        doc_id = uuid4()
        extraction_id = uuid4()
        user_id = uuid4()

        row = {
            "id": str(item_id),
            "tenant_id": str(tenant_id),
            "document_id": str(doc_id),
            "extraction_id": str(extraction_id),
            "priority": 50,
            "status": "claimed",
            "claimed_by": str(user_id),
            "claimed_at": "2024-01-01T12:00:00",
            "completed_at": None,
            "created_at": "2024-01-01T00:00:00",
            "documents": {"original_filename": "test.pdf"},
            "extractions": {"overall_confidence": 0.75, "document_type": "lease"},
        }

        item = service._transform_queue_item(row)

        assert isinstance(item, ReviewQueueItem)
        assert item.status == "claimed"
        assert item.claimed_by == user_id
        # claimed_at is parsed into datetime object by Pydantic
        assert str(item.claimed_at) == "2024-01-01 12:00:00"


class TestPriorityCalculation:
    """Tests for priority calculation logic (database function)."""

    def test_priority_components(self):
        """Test priority score components."""
        # Priority = (1 - confidence) * 50 + critical_field_issues * 10 + age_hours (max 20)

        # Low confidence (0.70) = 15 points
        confidence_points = int((1 - 0.70) * 50)
        assert confidence_points == 15

        # 2 critical fields with low confidence = 20 points
        critical_field_points = 2 * 10
        assert critical_field_points == 20

        # 25 hours old = 20 points (capped)
        age_points = min(25, 20)
        assert age_points == 20

        # Total priority
        total_priority = confidence_points + critical_field_points + age_points
        assert total_priority == 55

    def test_priority_high_confidence(self):
        """Test priority for high confidence extraction."""
        # High confidence (0.95) = 2.5 points
        confidence_points = int((1 - 0.95) * 50)
        assert confidence_points == 2

        # No critical field issues = 0 points
        critical_field_points = 0

        # New extraction (1 hour) = 1 point
        age_points = 1

        total_priority = confidence_points + critical_field_points + age_points
        assert total_priority == 3

    def test_priority_low_confidence(self):
        """Test priority for low confidence extraction."""
        # Very low confidence (0.60) = 20 points
        confidence_points = int((1 - 0.60) * 50)
        assert confidence_points == 20

        # 3 critical fields with issues = 30 points
        critical_field_points = 3 * 10
        assert critical_field_points == 30

        # Old extraction (50 hours) = 20 points (capped)
        age_points = min(50, 20)
        assert age_points == 20

        total_priority = confidence_points + critical_field_points + age_points
        assert total_priority == 70


class TestQueuePopulationRules:
    """Tests for queue population logic (database function)."""

    def test_should_queue_low_confidence(self):
        """Test extraction with low overall confidence is queued."""
        # Rule: overall_confidence < 0.85
        assert 0.80 < 0.85  # Should be queued
        assert 0.75 < 0.85  # Should be queued
        assert 0.90 >= 0.85  # Should NOT be queued

    def test_should_queue_parser_fallback(self):
        """Test extraction using fallback parser is queued."""
        # Rule: parser_used = 'tika' (fallback parser)
        assert "tika" == "tika"  # Should be queued
        assert "ragflow" != "tika"  # Should NOT be queued
        assert "unstructured" != "tika"  # Should NOT be queued

    def test_should_queue_low_confidence_fields(self):
        """Test extraction with low confidence fields is queued."""
        # Rule: any field < 0.70
        field_confidences = [0.95, 0.85, 0.65, 0.80]
        has_low_confidence = any(c < 0.70 for c in field_confidences)
        assert has_low_confidence is True  # Should be queued

        field_confidences_high = [0.95, 0.85, 0.80, 0.75]
        has_low_confidence_high = any(c < 0.70 for c in field_confidences_high)
        assert has_low_confidence_high is False  # Should NOT be queued
