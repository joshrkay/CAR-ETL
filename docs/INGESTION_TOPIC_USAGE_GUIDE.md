# Ingestion Topic - Quick Usage Guide

## Overview

The `ingestion-events` topic decouples document capture from processing. All ingestion sources (upload, email, cloud sync) publish to this topic, and extraction workers consume from it.

---

## Quick Start

### 1. Start Redpanda

```bash
cd /Users/joshuakay/Downloads/CAR-ETL-main
docker compose up -d
```

### 2. Create Topics

```bash
python scripts/setup_ingestion_topic.py
```

### 3. Verify Setup

```bash
# List topics
docker exec -it redpanda rpk topic list

# Describe ingestion topic
docker exec -it redpanda rpk topic describe ingestion-events

# Describe DLQ topic
docker exec -it redpanda rpk topic describe ingestion-events-dlq
```

---

## Producer Pattern

### Publishing Ingestion Events

```python
import json
import time
from confluent_kafka import Producer
from src.ingestion.partitioning import get_partition_key
from src.config.ingestion_config import get_ingestion_config

# Initialize producer
config = get_ingestion_config()
producer = Producer({
    'bootstrap.servers': config.kafka_bootstrap_servers,
    'acks': config.kafka_producer_acks,  # 'all' for durability
    'retries': config.kafka_producer_retries,  # 3 retries
    'compression.type': 'snappy',
})

def delivery_callback(err, msg):
    """Called on message delivery success or failure."""
    if err:
        logger.error(f"Message delivery failed: {err}")
    else:
        logger.info(f"Message delivered: partition={msg.partition()}, offset={msg.offset()}")

# Create ingestion event
event = {
    'tenant_id': 'tenant-uuid-here',
    'source_type': 'UPLOAD',
    'file_hash': 'sha256-hash-here',
    's3_uri': 's3://bucket/path/to/file',
    'original_filename': 'document.pdf',
    'mime_type': 'application/pdf',
    'timestamp': int(time.time() * 1000),
    'source_path': None,
    'parent_id': None,
    'permissions_blob': None,
    'metadata': {'uploader_ip': '192.168.1.1'}
}

# Publish with tenant-based partitioning
partition_key = get_partition_key(event['tenant_id'])
producer.produce(
    config.ingestion_topic,
    key=partition_key,  # Ensures tenant consistency
    value=json.dumps(event).encode('utf-8'),
    callback=delivery_callback
)

# Wait for message delivery
producer.flush()
```

### Key Points

✅ **Always use `tenant_id` as partition key** - Ensures ordering per tenant  
✅ **Use delivery callbacks** - Monitor delivery success/failure  
✅ **Flush before shutdown** - Ensure messages are sent  
✅ **Set `acks='all'`** - Durability guarantee

---

## Consumer Pattern

### Extraction Worker Consumer

```python
import json
import logging
from confluent_kafka import Consumer, KafkaError
from src.ingestion.consumer_groups import get_consumer_group_manager
from src.config.ingestion_config import get_ingestion_config

logger = logging.getLogger(__name__)

# Initialize consumer
config = get_ingestion_config()
group_manager = get_consumer_group_manager()
group_id = group_manager.get_extraction_worker_group_name()

consumer = Consumer({
    'bootstrap.servers': config.kafka_bootstrap_servers,
    'group.id': group_id,  # ingestion-events-extraction-workers
    'auto.offset.reset': 'earliest',  # Start from beginning on first run
    'enable.auto.commit': False,  # Manual commit for reliability
    'max.poll.interval.ms': 300000,  # 5 minutes processing time
})

# Subscribe to topic
consumer.subscribe([config.ingestion_topic])

def process_event(event: dict) -> None:
    """Process ingestion event (extraction logic)."""
    tenant_id = event['tenant_id']
    file_hash = event['file_hash']
    s3_uri = event['s3_uri']
    
    logger.info(f"Processing: TenantID={tenant_id}, Hash={file_hash}")
    
    # TODO: Implement extraction logic
    # 1. Download file from S3
    # 2. Apply redaction (Presidio)
    # 3. Extract text/metadata
    # 4. Store in Data Plane
    
    pass

# Consumption loop
try:
    while True:
        msg = consumer.poll(timeout=1.0)
        
        if msg is None:
            continue
        
        if msg.error():
            if msg.error().code() == KafkaError._PARTITION_EOF:
                logger.info(f"Reached end of partition {msg.partition()}")
            else:
                logger.error(f"Consumer error: {msg.error()}")
            continue
        
        # Parse event
        try:
            event = json.loads(msg.value().decode('utf-8'))
            tenant_id = event.get('tenant_id')
            
            # Process event
            process_event(event)
            
            # Commit offset after successful processing
            consumer.commit(message=msg)
            logger.info(f"Committed offset: TenantID={tenant_id}, Offset={msg.offset()}")
            
        except Exception as e:
            logger.error(f"Failed to process event: {e}", exc_info=True)
            
            # Send to DLQ
            send_to_dlq(event, error=str(e))
            
            # Commit offset (message handled, even if failed)
            consumer.commit(message=msg)

except KeyboardInterrupt:
    logger.info("Consumer interrupted")

finally:
    consumer.close()
```

### Key Points

✅ **Manual offset commits** - Only commit after successful processing  
✅ **Handle errors gracefully** - Send failures to DLQ  
✅ **Set appropriate timeout** - `max.poll.interval.ms` for processing time  
✅ **Subscribe, don't assign** - Let Kafka handle partition assignment

---

## Dead Letter Queue Pattern

### Sending to DLQ

```python
import json
import time
import logging
from confluent_kafka import Producer
from src.config.ingestion_config import get_ingestion_config

logger = logging.getLogger(__name__)

def send_to_dlq(event: dict, error: str) -> None:
    """Send failed event to DLQ with error context."""
    config = get_ingestion_config()
    dlq_topic = f"{config.ingestion_topic}-dlq"
    
    # Initialize DLQ producer
    dlq_producer = Producer({
        'bootstrap.servers': config.kafka_bootstrap_servers,
        'acks': 'all',
    })
    
    # Add error context to event
    dlq_event = {
        **event,
        'dlq_timestamp': int(time.time() * 1000),
        'error': error,
        'retry_count': event.get('retry_count', 0) + 1,
    }
    
    # Publish to DLQ
    tenant_id = event['tenant_id']
    dlq_producer.produce(
        dlq_topic,
        key=tenant_id.encode('utf-8'),
        value=json.dumps(dlq_event).encode('utf-8'),
    )
    dlq_producer.flush()
    
    logger.error(
        f"Event sent to DLQ: TenantID={tenant_id}, Error={error}, "
        f"RetryCount={dlq_event['retry_count']}"
    )
```

### DLQ Processor

```python
from confluent_kafka import Consumer
from src.ingestion.consumer_groups import get_consumer_group_manager
from src.config.ingestion_config import get_ingestion_config

# Initialize DLQ consumer
config = get_ingestion_config()
group_manager = get_consumer_group_manager()
dlq_group_id = group_manager.get_dlq_processor_group_name()

dlq_consumer = Consumer({
    'bootstrap.servers': config.kafka_bootstrap_servers,
    'group.id': dlq_group_id,  # ingestion-events-dlq-processor
    'auto.offset.reset': 'earliest',
    'enable.auto.commit': False,
})

dlq_topic = f"{config.ingestion_topic}-dlq"
dlq_consumer.subscribe([dlq_topic])

# Process DLQ messages
while True:
    msg = dlq_consumer.poll(timeout=1.0)
    
    if msg is None or msg.error():
        continue
    
    try:
        dlq_event = json.loads(msg.value().decode('utf-8'))
        retry_count = dlq_event.get('retry_count', 0)
        
        if retry_count < 3:
            # Retry processing
            retry_process_event(dlq_event)
        else:
            # Too many retries, alert for manual intervention
            logger.error(f"Event exceeded retry limit: TenantID={dlq_event['tenant_id']}")
            alert_ops_team(dlq_event)
        
        dlq_consumer.commit(message=msg)
        
    except Exception as e:
        logger.error(f"DLQ processing failed: {e}", exc_info=True)
        dlq_consumer.commit(message=msg)
```

### Key Points

✅ **Add error context** - Include error message and timestamp  
✅ **Track retry count** - Prevent infinite retry loops  
✅ **Alert on repeated failures** - Manual intervention for persistent issues  
✅ **30-day retention** - Extended retention for debugging

---

## Monitoring

### Topic Metrics

```bash
# Describe topic
docker exec -it redpanda rpk topic describe ingestion-events

# Get partition details
docker exec -it redpanda rpk topic describe ingestion-events --detailed

# Check consumer group lag
docker exec -it redpanda rpk group describe ingestion-events-extraction-workers
```

### Consumer Group Lag

```python
from confluent_kafka.admin import AdminClient

admin_client = AdminClient({'bootstrap.servers': 'localhost:19092'})

# List consumer groups
groups = admin_client.list_groups(timeout=10)
for group in groups.valid:
    print(f"Group: {group.id}")
```

### Key Metrics to Monitor

- **Messages/second** - Throughput
- **Consumer lag** - Processing delay
- **DLQ message count** - Error rate
- **Partition distribution** - Load balancing

---

## Environment Variables

Create `.env` file:

```bash
# Kafka/Redpanda Configuration
KAFKA_BOOTSTRAP_SERVERS=localhost:19092  # External port for Redpanda
INGESTION_TOPIC=ingestion-events

# Producer Configuration
KAFKA_PRODUCER_ACKS=all  # Durability guarantee
KAFKA_PRODUCER_RETRIES=3  # Retry failed sends

# Optional: Schema Registry
SCHEMA_REGISTRY_URL=http://localhost:18081
SCHEMA_REGISTRY_SUBJECT=ingestion-events-value
```

---

## Common Issues

### Issue: Consumer lag increasing

**Cause:** Processing too slow or too few workers  
**Solution:** Scale extraction workers horizontally

```bash
# Start multiple extraction workers
# They'll join the same consumer group and share partitions
python extraction_worker.py &  # Worker 1
python extraction_worker.py &  # Worker 2
python extraction_worker.py &  # Worker 3
```

### Issue: Messages not being consumed

**Cause:** Consumer group offset reset  
**Solution:** Check offset configuration

```python
consumer = Consumer({
    'auto.offset.reset': 'earliest',  # Start from beginning
    # OR
    'auto.offset.reset': 'latest',    # Only new messages
})
```

### Issue: Redpanda not starting

**Cause:** Port conflicts or resource constraints  
**Solution:** Check Docker logs

```bash
docker compose logs redpanda
docker compose ps
```

---

## Best Practices

### Producer
1. ✅ Always use `tenant_id` as partition key
2. ✅ Set `acks='all'` for durability
3. ✅ Use delivery callbacks to monitor failures
4. ✅ Flush before application shutdown
5. ✅ Log tenant ID and metadata (never PII)

### Consumer
1. ✅ Manual offset commits after successful processing
2. ✅ Handle errors gracefully (DLQ pattern)
3. ✅ Set appropriate `max.poll.interval.ms`
4. ✅ Monitor consumer lag
5. ✅ Scale horizontally as needed

### Security
1. ✅ Never log raw message payloads (PII)
2. ✅ Apply redaction before downstream processing
3. ✅ Audit failed messages in DLQ
4. ✅ Encrypt messages at rest (Redpanda/Kafka config)

---

## References

- **Detailed Documentation:** `docs/KAFKA_INGESTION_TOPIC.md`
- **Acceptance Criteria:** `docs/INGESTION_TOPIC_ACCEPTANCE_CRITERIA.md`
- **Avro Schema:** `schemas/ingestion_event.avsc`
- **Tests:** `tests/test_ingestion_topic.py`
- **Setup Script:** `scripts/setup_ingestion_topic.py`

---

**Need Help?** Check logs or run diagnostics:

```bash
# Check Redpanda health
docker compose ps

# View logs
docker compose logs redpanda -f

# Topic list
docker exec -it redpanda rpk topic list

# Consumer groups
docker exec -it redpanda rpk group list
```
