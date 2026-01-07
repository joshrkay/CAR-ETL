"""Kafka/Redpanda topic management for ingestion events."""
import logging
from typing import Optional, Dict, Any, List
from confluent_kafka.admin import AdminClient, NewTopic, ConfigResource
from confluent_kafka import KafkaException

from src.config.ingestion_config import get_ingestion_config

logger = logging.getLogger(__name__)


class TopicManagerError(Exception):
    """Raised when topic management operation fails."""
    pass


class TopicManager:
    """Manages Kafka/Redpanda topics for ingestion events."""
    
    def __init__(self, config: Optional[Any] = None):
        """Initialize topic manager.
        
        Args:
            config: IngestionConfig instance. If not provided, loads from environment.
        """
        self.config = config or get_ingestion_config()
        self.admin_client = AdminClient({
            'bootstrap.servers': self.config.kafka_bootstrap_servers
        })
    
    def create_ingestion_topic(
        self,
        num_partitions: int = 6,
        replication_factor: int = 1
    ) -> None:
        """Create ingestion-events topic with appropriate configuration.
        
        Topic is partitioned by tenant_id to ensure all events for a tenant
        go to the same partition for ordering guarantees.
        
        Args:
            num_partitions: Number of partitions (default: 6 for multi-tenant).
            replication_factor: Replication factor (default: 1 for single-node).
        
        Raises:
            TopicManagerError: If topic creation fails.
        """
        topic_name = self.config.ingestion_topic
        
        # Check if topic already exists
        if self.topic_exists(topic_name):
            logger.info(f"Topic {topic_name} already exists, skipping creation")
            return
        
        # Create topic with retention and partitioning configuration
        topic = NewTopic(
            topic_name,
            num_partitions=num_partitions,
            replication_factor=replication_factor,
            config={
                # Retention: 7 days (in milliseconds)
                'retention.ms': str(7 * 24 * 60 * 60 * 1000),  # 7 days
                # Alternative retention config (whichever is reached first)
                'retention.bytes': '-1',  # No size-based retention
                # Compression for efficiency
                'compression.type': 'snappy',
                # Enable log compaction for deduplication (optional)
                'cleanup.policy': 'delete',  # Use 'compact' for key-based deduplication
            }
        )
        
        try:
            # Create topic
            futures = self.admin_client.create_topics([topic])
            
            # Wait for topic creation
            for topic_name_future, future in futures.items():
                try:
                    future.result()  # Wait for operation to complete
                    logger.info(f"Topic {topic_name} created successfully")
                except Exception as e:
                    raise TopicManagerError(f"Failed to create topic {topic_name}: {e}") from e
                    
        except KafkaException as e:
            raise TopicManagerError(f"Kafka error creating topic: {e}") from e
        except Exception as e:
            raise TopicManagerError(f"Unexpected error creating topic: {e}") from e
    
    def create_dlq_topic(
        self,
        num_partitions: int = 3,
        replication_factor: int = 1
    ) -> None:
        """Create dead letter queue topic for failed ingestion events.
        
        Args:
            num_partitions: Number of partitions (default: 3).
            replication_factor: Replication factor (default: 1).
        
        Raises:
            TopicManagerError: If DLQ topic creation fails.
        """
        dlq_topic_name = f"{self.config.ingestion_topic}-dlq"
        
        # Check if topic already exists
        if self.topic_exists(dlq_topic_name):
            logger.info(f"DLQ topic {dlq_topic_name} already exists, skipping creation")
            return
        
        # DLQ topic with longer retention for debugging
        topic = NewTopic(
            dlq_topic_name,
            num_partitions=num_partitions,
            replication_factor=replication_factor,
            config={
                # Longer retention for DLQ (30 days for debugging)
                'retention.ms': str(30 * 24 * 60 * 60 * 1000),  # 30 days
                'retention.bytes': '-1',
                'compression.type': 'snappy',
                'cleanup.policy': 'delete',
            }
        )
        
        try:
            futures = self.admin_client.create_topics([topic])
            
            for topic_name_future, future in futures.items():
                try:
                    future.result()
                    logger.info(f"DLQ topic {dlq_topic_name} created successfully")
                except Exception as e:
                    raise TopicManagerError(f"Failed to create DLQ topic: {dlq_topic_name}: {e}") from e
                    
        except KafkaException as e:
            raise TopicManagerError(f"Kafka error creating DLQ topic: {e}") from e
        except Exception as e:
            raise TopicManagerError(f"Unexpected error creating DLQ topic: {e}") from e
    
    def topic_exists(self, topic_name: str) -> bool:
        """Check if topic exists.
        
        Args:
            topic_name: Name of topic to check.
        
        Returns:
            True if topic exists, False otherwise.
        """
        try:
            metadata = self.admin_client.list_topics(timeout=10)
            return topic_name in metadata.topics
        except Exception as e:
            logger.warning(f"Error checking if topic exists: {e}")
            return False
    
    def get_topic_config(self, topic_name: str) -> Dict[str, Any]:
        """Get topic configuration.
        
        Args:
            topic_name: Name of topic.
        
        Returns:
            Dictionary of topic configuration.
        
        Raises:
            TopicManagerError: If topic does not exist or config retrieval fails.
        """
        if not self.topic_exists(topic_name):
            raise TopicManagerError(f"Topic {topic_name} does not exist")
        
        try:
            resource = ConfigResource(ConfigResource.TOPIC, topic_name)
            futures = self.admin_client.describe_configs([resource])
            
            config = {}
            for resource_future, future in futures.items():
                try:
                    config_result = future.result()
                    for key, entry in config_result.items():
                        config[key] = entry.value
                except Exception as e:
                    raise TopicManagerError(f"Failed to get config for {topic_name}: {e}") from e
            
            return config
            
        except KafkaException as e:
            raise TopicManagerError(f"Kafka error getting topic config: {e}") from e
        except Exception as e:
            raise TopicManagerError(f"Unexpected error getting topic config: {e}") from e
    
    def verify_retention(self, topic_name: str, expected_days: int = 7) -> bool:
        """Verify topic retention is configured correctly.
        
        Args:
            topic_name: Name of topic to verify.
            expected_days: Expected retention in days (default: 7).
        
        Returns:
            True if retention matches expected value, False otherwise.
        """
        try:
            config = self.get_topic_config(topic_name)
            retention_ms = config.get('retention.ms')
            
            if retention_ms is None:
                logger.warning(f"Topic {topic_name} has no retention.ms configured")
                return False
            
            expected_ms = expected_days * 24 * 60 * 60 * 1000
            actual_ms = int(retention_ms)
            
            # Allow small tolerance (within 1 hour)
            tolerance_ms = 60 * 60 * 1000
            is_valid = abs(actual_ms - expected_ms) <= tolerance_ms
            
            if not is_valid:
                logger.warning(
                    f"Topic {topic_name} retention mismatch: "
                    f"expected {expected_ms}ms ({expected_days} days), "
                    f"got {actual_ms}ms"
                )
            
            return is_valid
            
        except Exception as e:
            logger.error(f"Error verifying retention: {e}")
            return False


def get_topic_manager() -> TopicManager:
    """Get or create topic manager instance."""
    return TopicManager()
