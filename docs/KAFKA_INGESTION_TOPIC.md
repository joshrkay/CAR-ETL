# Kafka/Redpanda Ingestion Topic (US-2.2)

## Overview

This document describes the Kafka/Redpanda topic setup for ingestion events, enabling decoupled capture and processing of documents.

## User Story

**As a Platform Engineer, I want a message broker topic for ingestion events so that capture and processing are decoupled.**

**Story Points:** 3  
**Dependencies:** US-2.1

---

## Acceptance Criteria Verification

### ✅ 1. Topic 'ingestion-events' created with appropriate partitioning (by tenant_id)

**Status:** ✅ **IMPLEMENTED**

**Location:** `src/ingestion/topic_manager.py`

**Implementation:**
- Topic name: `ingestion-events` (configurable via `INGESTION_TOPIC`)
- Default partitions: 6 (configurable)
- Partitioning strategy: Consistent hashing by `tenant_id`
- All messages for a tenant go to the same partition (ordering guarantee)

**Partitioning Logic:**
```python
# Location: src/ingestion/partitioning.py
def get_partition_for_tenant(tenant_id: str, num_partitions: int) -> int:
    """Get partition number for a tenant_id using consistent hashing."""
    hash_bytes = hashlib.md5(tenant_id.encode('utf-8')).digest()
    hash_int = int.from_bytes(hash_bytes, byteorder='big')
    return hash_int % num_partitions
```

**Usage:**
```python
from src.ingestion.partitioning import get_partition_key

# When producing messages
partition_key = get_partition_key(tenant_id)  # Returns tenant_id as bytes
producer.produce(topic, value=message, key=partition_key)
```

**Verification:**
- ✅ Topic created with configurable partitions
- ✅ Partitioning by tenant_id ensures ordering per tenant
- ✅ Consistent hashing ensures same tenant always goes to same partition

---

### ✅ 2. Retention configured for 7 days to allow reprocessing

**Status:** ✅ **IMPLEMENTED**

**Location:** `src/ingestion/topic_manager.py`

**Implementation:**
- Retention: 7 days (604,800,000 milliseconds)
- Configuration: `retention.ms = 604800000`
- No size-based retention: `retention.bytes = -1`
- Allows reprocessing of events within 7-day window

**Code:**
```python
# Location: src/ingestion/topic_manager.py
topic = NewTopic(
    topic_name,
    num_partitions=num_partitions,
    replication_factor=replication_factor,
    config={
        'retention.ms': str(7 * 24 * 60 * 60 * 1000),  # 7 days
        'retention.bytes': '-1',  # No size-based retention
        'compression.type': 'snappy',
        'cleanup.policy': 'delete',
    }
)
```

**Verification:**
- ✅ Retention set to 7 days (604,800,000 ms)
- ✅ Verification method: `verify_retention()` checks configuration
- ✅ Allows reprocessing within retention window

---

### ✅ 3. Consumer groups configured for extraction workers

**Status:** ✅ **IMPLEMENTED**

**Location:** `src/ingestion/consumer_groups.py`

**Implementation:**
- Consumer group name: `ingestion-events-extraction-workers`
- Consumer groups created automatically when first consumer joins
- Supports multiple extraction workers in same group (load balancing)

**Consumer Group Manager:**
```python
# Location: src/ingestion/consumer_groups.py
class ConsumerGroupManager:
    def get_extraction_worker_group_name(self) -> str:
        """Get consumer group name for extraction workers."""
        return f"{self.config.ingestion_topic}-extraction-workers"
```

**Usage:**
```python
from confluent_kafka import Consumer
from src.ingestion.consumer_groups import get_consumer_group_manager

group_manager = get_consumer_group_manager()
group_id = group_manager.get_extraction_worker_group_name()

consumer = Consumer({
    'bootstrap.servers': 'localhost:9092',
    'group.id': group_id,
    'auto.offset.reset': 'earliest'
})
```

**Verification:**
- ✅ Consumer group name defined: `ingestion-events-extraction-workers`
- ✅ Groups created automatically on first consumer join
- ✅ Supports horizontal scaling (multiple workers)

---

### ✅ 4. Dead letter queue configured for failed message handling

**Status:** ✅ **IMPLEMENTED**

**Location:** `src/ingestion/topic_manager.py`

**Implementation:**
- DLQ topic name: `ingestion-events-dlq`
- Retention: 30 days (for debugging and analysis)
- Partitions: 3 (configurable)
- Separate consumer group: `ingestion-events-dlq-processor`

**DLQ Topic Creation:**
```python
# Location: src/ingestion/topic_manager.py
def create_dlq_topic(self, num_partitions: int = 3, replication_factor: int = 1):
    """Create dead letter queue topic for failed ingestion events."""
    dlq_topic_name = f"{self.config.ingestion_topic}-dlq"
    
    topic = NewTopic(
        dlq_topic_name,
        num_partitions=num_partitions,
        replication_factor=replication_factor,
        config={
            'retention.ms': str(30 * 24 * 60 * 60 * 1000),  # 30 days
            'retention.bytes': '-1',
            'compression.type': 'snappy',
            'cleanup.policy': 'delete',
        }
    )
```

**DLQ Consumer Group:**
```python
# Location: src/ingestion/consumer_groups.py
def get_dlq_processor_group_name(self) -> str:
    """Get consumer group name for DLQ processor."""
    return f"{self.config.ingestion_topic}-dlq-processor"
```

**Usage Pattern:**
```python
# In extraction worker
try:
    process_event(event)
except Exception as e:
    # Send to DLQ
    dlq_producer.produce('ingestion-events-dlq', value=event, key=tenant_id)
    logger.error(f"Failed to process event, sent to DLQ: {e}")
```

**Verification:**
- ✅ DLQ topic: `ingestion-events-dlq`
- ✅ Longer retention (30 days) for debugging
- ✅ Separate consumer group for DLQ processing
- ✅ Ready for failed message handling

---

## Topic Configuration Summary

### Main Topic: `ingestion-events`

| Setting | Value | Description |
|---------|-------|-------------|
| Partitions | 6 (default) | Partitioned by tenant_id |
| Replication Factor | 1 (default) | Single-node setup |
| Retention | 7 days | Allows reprocessing |
| Compression | snappy | Efficient compression |
| Cleanup Policy | delete | Standard deletion |

### DLQ Topic: `ingestion-events-dlq`

| Setting | Value | Description |
|---------|-------|-------------|
| Partitions | 3 (default) | Fewer partitions for DLQ |
| Replication Factor | 1 (default) | Single-node setup |
| Retention | 30 days | Longer retention for debugging |
| Compression | snappy | Efficient compression |
| Cleanup Policy | delete | Standard deletion |

### Consumer Groups

| Group Name | Purpose |
|------------|---------|
| `ingestion-events-extraction-workers` | Main extraction workers |
| `ingestion-events-dlq-processor` | DLQ message processing |

---

## Setup Instructions

### 1. Install Dependencies

```bash
pip install confluent-kafka[avro]
```

### 2. Set Environment Variables

```bash
# Kafka/Redpanda Configuration
KAFKA_BOOTSTRAP_SERVERS=localhost:9092
INGESTION_TOPIC=ingestion-events

# Optional: Schema Registry
SCHEMA_REGISTRY_URL=http://localhost:8081
```

### 3. Create Topics

```bash
python scripts/setup_ingestion_topic.py
```

Or programmatically:
```python
from src.ingestion.topic_manager import get_topic_manager

topic_manager = get_topic_manager()
topic_manager.create_ingestion_topic(num_partitions=6)
topic_manager.create_dlq_topic(num_partitions=3)
```

### 4. Verify Topics

```bash
# List topics
kafka-topics --list --bootstrap-server localhost:9092

# Describe topic
kafka-topics --describe --topic ingestion-events --bootstrap-server localhost:9092
```

---

## Partitioning Strategy

### Tenant-Based Partitioning

All messages for a tenant are routed to the same partition using consistent hashing:

```python
from src.ingestion.partitioning import get_partition_for_tenant, get_partition_key

tenant_id = "550e8400-e29b-41d4-a716-446655440000"
partition = get_partition_for_tenant(tenant_id, num_partitions=6)
key = get_partition_key(tenant_id)  # Use as Kafka message key
```

**Benefits:**
- ✅ Ordering guarantee per tenant
- ✅ Efficient processing (all tenant events in one partition)
- ✅ Consistent routing (same tenant → same partition)

---

## Consumer Group Configuration

### Extraction Workers

```python
from confluent_kafka import Consumer
from src.ingestion.consumer_groups import get_consumer_group_manager

group_manager = get_consumer_group_manager()
group_id = group_manager.get_extraction_worker_group_name()

consumer = Consumer({
    'bootstrap.servers': 'localhost:9092',
    'group.id': group_id,
    'auto.offset.reset': 'earliest',  # Start from beginning
    'enable.auto.commit': False,  # Manual commit for reliability
})
```

### DLQ Processor

```python
dlq_group_id = group_manager.get_dlq_processor_group_name()

dlq_consumer = Consumer({
    'bootstrap.servers': 'localhost:9092',
    'group.id': dlq_group_id,
    'auto.offset.reset': 'earliest',
})
```

---

## Dead Letter Queue Pattern

### Sending to DLQ

```python
from confluent_kafka import Producer

dlq_producer = Producer({'bootstrap.servers': 'localhost:9092'})

try:
    process_ingestion_event(event)
except Exception as e:
    # Send failed event to DLQ
    dlq_producer.produce(
        'ingestion-events-dlq',
        value=json.dumps(event).encode('utf-8'),
        key=event['tenant_id'].encode('utf-8'),
        callback=delivery_callback
    )
    logger.error(f"Event sent to DLQ: {e}")
```

### Processing DLQ

```python
# DLQ processor consumer
for message in dlq_consumer:
    event = json.loads(message.value())
    
    # Retry processing or manual intervention
    try:
        retry_process_event(event)
    except Exception as e:
        logger.error(f"DLQ event still failing: {e}")
        # Alert or store for manual review
```

---

## Testing

Run tests:
```bash
pytest tests/test_ingestion_topic.py -v
```

**Test Coverage:**
- ✅ Topic creation
- ✅ Partitioning logic
- ✅ Consumer group management
- ✅ DLQ topic creation
- ✅ Retention verification

---

## Files Created

1. **`src/ingestion/topic_manager.py`** - Topic management utilities
2. **`src/ingestion/consumer_groups.py`** - Consumer group configuration
3. **`src/ingestion/partitioning.py`** - Tenant-based partitioning
4. **`scripts/setup_ingestion_topic.py`** - Topic setup script
5. **`tests/test_ingestion_topic.py`** - Test suite
6. **`docs/KAFKA_INGESTION_TOPIC.md`** - This documentation

---

## Acceptance Criteria Status

| Criteria | Status | Implementation |
|----------|--------|----------------|
| 1. Topic created with tenant_id partitioning | ✅ | `TopicManager.create_ingestion_topic()` |
| 2. Retention configured for 7 days | ✅ | `retention.ms = 604800000` |
| 3. Consumer groups for extraction workers | ✅ | `ingestion-events-extraction-workers` |
| 4. Dead letter queue configured | ✅ | `ingestion-events-dlq` topic + consumer group |

**Status:** ✅ **ALL ACCEPTANCE CRITERIA MET**

---

## Next Steps

1. **Start Kafka/Redpanda:**
   ```bash
   # Redpanda
   redpanda start

   # Or Kafka
   kafka-server-start.sh config/server.properties
   ```

2. **Create Topics:**
   ```bash
   python scripts/setup_ingestion_topic.py
   ```

3. **Start Extraction Workers:**
   - Use consumer group: `ingestion-events-extraction-workers`
   - Process messages from `ingestion-events` topic
   - Send failures to `ingestion-events-dlq`

4. **Monitor:**
   - Topic metrics (messages/sec, lag)
   - Consumer group lag
   - DLQ message count
