"""List and describe Kafka/Redpanda topics using Python client."""
import sys
import logging
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def main():
    """List and describe Kafka topics."""
    try:
        from confluent_kafka.admin import AdminClient
        from src.config.ingestion_config import get_ingestion_config
        
        config = get_ingestion_config()
        bootstrap_servers = config.kafka_bootstrap_servers
        
        print("=" * 70)
        print("Kafka/Redpanda Topics")
        print("=" * 70)
        print(f"Bootstrap Server: {bootstrap_servers}")
        print()
        
        # Create admin client
        admin_client = AdminClient({
            'bootstrap.servers': bootstrap_servers
        })
        
        # List topics
        print("1. Listing all topics...")
        print("-" * 70)
        try:
            metadata = admin_client.list_topics(timeout=10)
            
            if not metadata.topics:
                print("[WARN] No topics found. Kafka/Redpanda may not be running.")
                print("       Start Kafka/Redpanda first, then create topics with:")
                print("       python scripts/setup_ingestion_topic.py")
                return 1
            
            topics = sorted(metadata.topics.keys())
            print(f"[OK] Found {len(topics)} topic(s):")
            for topic in topics:
                print(f"  - {topic}")
            
        except Exception as e:
            print(f"[ERROR] Failed to list topics: {e}")
            print()
            print("Possible issues:")
            print("  1. Kafka/Redpanda is not running")
            print("  2. Wrong bootstrap server address")
            print("  3. Network/firewall blocking connection")
            print()
            print("To start Redpanda with Docker:")
            print("  docker compose up -d")
            print()
            print("Or check bootstrap server in .env:")
            print(f"  KAFKA_BOOTSTRAP_SERVERS={bootstrap_servers}")
            return 1
        
        # Describe ingestion-events topic if it exists
        print()
        print("2. Describing 'ingestion-events' topic...")
        print("-" * 70)
        
        if 'ingestion-events' in metadata.topics:
            topic_metadata = metadata.topics['ingestion-events']
            print(f"[OK] Topic: ingestion-events")
            print(f"  Partitions: {len(topic_metadata.partitions)}")
            
            for partition_id, partition in topic_metadata.partitions.items():
                leader = partition.leader if partition.leader is not None else "N/A"
                replicas = len(partition.replicas) if partition.replicas else 0
                print(f"  Partition {partition_id}: leader={leader}, replicas={replicas}")
            
            # Try to get topic config
            try:
                from confluent_kafka.admin import ConfigResource
                resource = ConfigResource(ConfigResource.TOPIC, 'ingestion-events')
                futures = admin_client.describe_configs([resource])
                
                for resource_future, future in futures.items():
                    try:
                        config_result = future.result()
                        print()
                        print("  Configuration:")
                        retention_ms = config_result.get('retention.ms', 'N/A')
                        retention_days = int(retention_ms.value) / (24 * 60 * 60 * 1000) if retention_ms != 'N/A' and retention_ms.value else 'N/A'
                        print(f"    retention.ms: {retention_ms.value if retention_ms != 'N/A' else 'N/A'}")
                        if retention_days != 'N/A':
                            print(f"    retention: ~{retention_days:.1f} days")
                    except Exception as e:
                        logger.debug(f"Could not get topic config: {e}")
            except Exception as e:
                logger.debug(f"Could not describe topic config: {e}")
        else:
            print("[WARN] Topic 'ingestion-events' does not exist.")
            print("       Create it with: python scripts/setup_ingestion_topic.py")
        
        # Check for DLQ topic
        print()
        print("3. Checking for DLQ topic...")
        print("-" * 70)
        
        dlq_topic = 'ingestion-events-dlq'
        if dlq_topic in metadata.topics:
            dlq_metadata = metadata.topics[dlq_topic]
            print(f"[OK] DLQ topic exists: {dlq_topic}")
            print(f"  Partitions: {len(dlq_metadata.partitions)}")
        else:
            print(f"[WARN] DLQ topic '{dlq_topic}' does not exist.")
            print("       It will be created by: python scripts/setup_ingestion_topic.py")
        
        print()
        print("=" * 70)
        print("Summary")
        print("=" * 70)
        print(f"Total topics: {len(topics)}")
        print(f"Ingestion topic exists: {'Yes' if 'ingestion-events' in metadata.topics else 'No'}")
        print(f"DLQ topic exists: {'Yes' if dlq_topic in metadata.topics else 'No'}")
        
        if 'ingestion-events' not in metadata.topics:
            print()
            print("Next step: Create topics with:")
            print("  python scripts/setup_ingestion_topic.py")
        
        return 0
        
    except ImportError as e:
        print(f"[ERROR] Missing dependencies: {e}")
        print("Install with: pip install confluent-kafka[avro]")
        return 1
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
