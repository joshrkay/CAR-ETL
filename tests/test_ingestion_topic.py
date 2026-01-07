"""Tests for ingestion topic management."""
import pytest
from unittest.mock import Mock, patch, MagicMock
from confluent_kafka import KafkaException

from src.ingestion.topic_manager import TopicManager, TopicManagerError
from src.ingestion.consumer_groups import ConsumerGroupManager, ConsumerGroupError
from src.ingestion.partitioning import get_partition_for_tenant, get_partition_key


def test_get_partition_for_tenant():
    """Test tenant-based partitioning."""
    tenant_id = "550e8400-e29b-41d4-a716-446655440000"
    num_partitions = 6
    
    partition = get_partition_for_tenant(tenant_id, num_partitions)
    
    assert 0 <= partition < num_partitions
    # Same tenant should always get same partition
    partition2 = get_partition_for_tenant(tenant_id, num_partitions)
    assert partition == partition2


def test_get_partition_for_tenant_different_tenants():
    """Test different tenants get different partitions (usually)."""
    tenant1 = "550e8400-e29b-41d4-a716-446655440000"
    tenant2 = "660e8400-e29b-41d4-a716-446655440001"
    num_partitions = 6
    
    partition1 = get_partition_for_tenant(tenant1, num_partitions)
    partition2 = get_partition_for_tenant(tenant2, num_partitions)
    
    # Partitions should be valid
    assert 0 <= partition1 < num_partitions
    assert 0 <= partition2 < num_partitions


def test_get_partition_for_tenant_invalid_partitions():
    """Test error handling for invalid partition count."""
    with pytest.raises(ValueError, match="num_partitions must be greater than 0"):
        get_partition_for_tenant("tenant-id", 0)
    
    with pytest.raises(ValueError, match="num_partitions must be greater than 0"):
        get_partition_for_tenant("tenant-id", -1)


def test_get_partition_key():
    """Test partition key generation."""
    tenant_id = "550e8400-e29b-41d4-a716-446655440000"
    key = get_partition_key(tenant_id)
    
    assert isinstance(key, bytes)
    assert key == tenant_id.encode('utf-8')


@patch('src.ingestion.topic_manager.AdminClient')
def test_topic_manager_initialization(mock_admin_client):
    """Test topic manager initialization."""
    manager = TopicManager()
    
    assert manager.admin_client is not None
    mock_admin_client.assert_called_once()


@patch('src.ingestion.topic_manager.AdminClient')
def test_topic_exists(mock_admin_client):
    """Test topic existence check."""
    # Mock metadata
    mock_metadata = MagicMock()
    mock_metadata.topics = {"ingestion-events", "other-topic"}
    
    mock_client_instance = MagicMock()
    mock_client_instance.list_topics.return_value = mock_metadata
    mock_admin_client.return_value = mock_client_instance
    
    manager = TopicManager()
    
    assert manager.topic_exists("ingestion-events") is True
    assert manager.topic_exists("nonexistent-topic") is False


@patch('src.ingestion.topic_manager.AdminClient')
def test_create_ingestion_topic_success(mock_admin_client):
    """Test successful topic creation."""
    mock_future = MagicMock()
    mock_future.result.return_value = None  # Success
    
    mock_client_instance = MagicMock()
    mock_client_instance.list_topics.return_value = MagicMock(topics={})
    mock_client_instance.create_topics.return_value = {
        "ingestion-events": mock_future
    }
    mock_admin_client.return_value = mock_client_instance
    
    manager = TopicManager()
    manager.create_ingestion_topic()
    
    mock_client_instance.create_topics.assert_called_once()


@patch('src.ingestion.topic_manager.AdminClient')
def test_create_ingestion_topic_already_exists(mock_admin_client):
    """Test topic creation when topic already exists."""
    mock_client_instance = MagicMock()
    mock_client_instance.list_topics.return_value = MagicMock(
        topics={"ingestion-events"}
    )
    mock_admin_client.return_value = mock_client_instance
    
    manager = TopicManager()
    manager.create_ingestion_topic()  # Should not raise
    
    # Should not call create_topics if topic exists
    mock_client_instance.create_topics.assert_not_called()


@patch('src.ingestion.topic_manager.AdminClient')
def test_create_dlq_topic_success(mock_admin_client):
    """Test successful DLQ topic creation."""
    mock_future = MagicMock()
    mock_future.result.return_value = None
    
    mock_client_instance = MagicMock()
    mock_client_instance.list_topics.return_value = MagicMock(topics={})
    mock_client_instance.create_topics.return_value = {
        "ingestion-events-dlq": mock_future
    }
    mock_admin_client.return_value = mock_client_instance
    
    manager = TopicManager()
    manager.create_dlq_topic()
    
    mock_client_instance.create_topics.assert_called_once()


def test_consumer_group_manager_initialization():
    """Test consumer group manager initialization."""
    manager = ConsumerGroupManager()
    
    assert manager.admin_client is not None


def test_get_extraction_worker_group_name():
    """Test extraction worker group name generation."""
    manager = ConsumerGroupManager()
    group_name = manager.get_extraction_worker_group_name()
    
    assert "extraction-workers" in group_name
    assert "ingestion-events" in group_name


def test_get_dlq_processor_group_name():
    """Test DLQ processor group name generation."""
    manager = ConsumerGroupManager()
    group_name = manager.get_dlq_processor_group_name()
    
    assert "dlq-processor" in group_name
    assert "ingestion-events" in group_name


def test_verify_consumer_group_exists():
    """Test consumer group existence verification."""
    manager = ConsumerGroupManager()
    result = manager.verify_consumer_group_exists("test-group")
    
    # Should return True (groups created automatically)
    assert result is True
