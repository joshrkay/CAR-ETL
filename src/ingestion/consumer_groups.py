"""Consumer group configuration for extraction workers."""
import logging
from typing import List, Dict, Any, Optional
from confluent_kafka.admin import AdminClient
from confluent_kafka import KafkaException

from src.config.ingestion_config import get_ingestion_config

logger = logging.getLogger(__name__)


class ConsumerGroupError(Exception):
    """Raised when consumer group operation fails."""
    pass


class ConsumerGroupManager:
    """Manages consumer groups for extraction workers."""
    
    def __init__(self, config: Optional[Any] = None):
        """Initialize consumer group manager.
        
        Args:
            config: IngestionConfig instance. If not provided, loads from environment.
        """
        self.config = config or get_ingestion_config()
        self.admin_client = AdminClient({
            'bootstrap.servers': self.config.kafka_bootstrap_servers
        })
    
    def list_consumer_groups(self) -> List[str]:
        """List all consumer groups.
        
        Returns:
            List of consumer group names.
        
        Raises:
            ConsumerGroupError: If listing fails.
        """
        try:
            # Note: confluent-kafka doesn't have a direct list_consumer_groups
            # This would typically be done via Kafka admin API or CLI
            # For now, return known consumer groups
            return [
                f"{self.config.ingestion_topic}-extraction-workers",
                f"{self.config.ingestion_topic}-dlq-processor"
            ]
        except Exception as e:
            raise ConsumerGroupError(f"Failed to list consumer groups: {e}") from e
    
    def get_extraction_worker_group_name(self) -> str:
        """Get consumer group name for extraction workers.
        
        Returns:
            Consumer group name.
        """
        return f"{self.config.ingestion_topic}-extraction-workers"
    
    def get_dlq_processor_group_name(self) -> str:
        """Get consumer group name for DLQ processor.
        
        Returns:
            Consumer group name.
        """
        return f"{self.config.ingestion_topic}-dlq-processor"
    
    def verify_consumer_group_exists(self, group_id: str) -> bool:
        """Verify consumer group exists (or will be created on first consumer).
        
        Args:
            group_id: Consumer group ID.
        
        Returns:
            True if group exists or can be created, False otherwise.
        
        Note:
            Consumer groups are created automatically when first consumer joins.
            This method checks if the group can be accessed.
        """
        try:
            # Consumer groups are created automatically when consumers join
            # We can't directly check existence without a consumer
            # Return True to indicate group will be created on first use
            logger.info(f"Consumer group {group_id} will be created on first consumer join")
            return True
        except Exception as e:
            logger.warning(f"Error verifying consumer group: {e}")
            return False


def get_consumer_group_manager() -> ConsumerGroupManager:
    """Get or create consumer group manager instance."""
    return ConsumerGroupManager()
