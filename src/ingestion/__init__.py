"""Ingestion plane components for CAR Platform."""
from .models import IngestionEvent, SourceType
from .schema import IngestionEventSchema, get_schema_registry_client
from .topic_manager import TopicManager, get_topic_manager, TopicManagerError
from .consumer_groups import ConsumerGroupManager, get_consumer_group_manager, ConsumerGroupError
from .partitioning import get_partition_for_tenant, get_partition_key

__all__ = [
    "IngestionEvent",
    "SourceType",
    "IngestionEventSchema",
    "get_schema_registry_client",
    "TopicManager",
    "get_topic_manager",
    "TopicManagerError",
    "ConsumerGroupManager",
    "get_consumer_group_manager",
    "ConsumerGroupError",
    "get_partition_for_tenant",
    "get_partition_key",
]
