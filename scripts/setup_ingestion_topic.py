"""Script to set up Kafka/Redpanda ingestion topic."""
import sys
import logging
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def main():
    """Set up ingestion topic and DLQ."""
    try:
        from src.ingestion.topic_manager import get_topic_manager
        from src.ingestion.consumer_groups import get_consumer_group_manager
        
        print("=" * 70)
        print("Kafka/Redpanda Ingestion Topic Setup")
        print("=" * 70)
        print()
        
        # Initialize managers
        topic_manager = get_topic_manager()
        consumer_group_manager = get_consumer_group_manager()
        
        # Create ingestion-events topic
        print("1. Creating ingestion-events topic...")
        print("-" * 70)
        try:
            topic_manager.create_ingestion_topic(
                num_partitions=6,  # Partitioned by tenant_id
                replication_factor=1
            )
            print("[OK] Topic 'ingestion-events' created or already exists")
        except Exception as e:
            print(f"[ERROR] Failed to create topic: {e}")
            return 1
        
        # Verify retention
        print()
        print("2. Verifying retention configuration (7 days)...")
        print("-" * 70)
        if topic_manager.verify_retention("ingestion-events", expected_days=7):
            print("[OK] Retention configured correctly (7 days)")
        else:
            print("[WARN] Retention verification failed (may need manual configuration)")
        
        # Create DLQ topic
        print()
        print("3. Creating dead letter queue topic...")
        print("-" * 70)
        try:
            topic_manager.create_dlq_topic(
                num_partitions=3,
                replication_factor=1
            )
            print("[OK] DLQ topic 'ingestion-events-dlq' created or already exists")
        except Exception as e:
            print(f"[ERROR] Failed to create DLQ topic: {e}")
            return 1
        
        # Consumer groups
        print()
        print("4. Consumer group configuration...")
        print("-" * 70)
        extraction_group = consumer_group_manager.get_extraction_worker_group_name()
        dlq_group = consumer_group_manager.get_dlq_processor_group_name()
        print(f"[OK] Extraction workers group: {extraction_group}")
        print(f"[OK] DLQ processor group: {dlq_group}")
        print("[INFO] Consumer groups will be created automatically when consumers join")
        
        # Summary
        print()
        print("=" * 70)
        print("[OK] Topic Setup Complete")
        print("=" * 70)
        print()
        print("Topics created:")
        print("  - ingestion-events (partitioned by tenant_id, 7-day retention)")
        print("  - ingestion-events-dlq (30-day retention)")
        print()
        print("Consumer groups:")
        print(f"  - {extraction_group}")
        print(f"  - {dlq_group}")
        print()
        print("Next steps:")
        print("  1. Verify topics: kafka-topics --list --bootstrap-server localhost:9092")
        print("  2. Start extraction workers with consumer group:", extraction_group)
        print("  3. Monitor DLQ for failed messages")
        
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
