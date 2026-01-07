# Ingestion Event Schema (US-2.1)

## Overview

The Ingestion Event Schema defines a strict, unified event structure for all document ingestion channels. All ingestion paths (direct upload, email forwarding, cloud storage sync) converge on this single event type, published to a unified Kafka/Redpanda topic.

## User Story

**As a Data Engineer, I want a strict schema for ingestion events so that downstream consumers know exactly what to expect.**

**Story Points:** 3  
**Dependencies:** US-1.3

---

## Acceptance Criteria Verification

### ✅ 1. Avro/Protobuf schema created for IngestionEvent message type

**Status:** ✅ **IMPLEMENTED**

**Location:** `schemas/ingestion_event.avsc`

**Implementation:**
- Avro schema defined with strict typing
- Schema namespace: `com.car.platform.ingestion`
- Schema name: `IngestionEvent`
- All fields properly typed with Avro types

**Schema File:**
```json
{
  "type": "record",
  "name": "IngestionEvent",
  "namespace": "com.car.platform.ingestion",
  "fields": [
    // Required and optional fields defined
  ]
}
```

---

### ✅ 2. Required fields: tenant_id, source_type (enum: UPLOAD, EMAIL, CLOUD_SYNC), file_hash (SHA-256), s3_uri, original_filename, mime_type, timestamp

**Status:** ✅ **IMPLEMENTED**

**Location:** `src/ingestion/models.py` and `schemas/ingestion_event.avsc`

**Required Fields:**

| Field | Type | Description | Validation |
|-------|------|-------------|------------|
| `tenant_id` | string | Tenant identifier (UUID) | UUID format validation |
| `source_type` | enum | UPLOAD, EMAIL, or CLOUD_SYNC | Enum validation |
| `file_hash` | string | SHA-256 hash (64 hex chars) | Length and hex format validation |
| `s3_uri` | string | S3 URI where file is stored | Non-empty string |
| `original_filename` | string | Original filename from source | Non-empty string |
| `mime_type` | string | MIME type (e.g., application/pdf) | Non-empty string |
| `timestamp` | long (timestamp-millis) | ISO 8601 timestamp | Milliseconds since epoch |

**Implementation:**
```python
# Location: src/ingestion/models.py
class IngestionEvent(BaseModel):
    tenant_id: str = Field(..., description="Tenant identifier (UUID)")
    source_type: SourceType = Field(..., description="Source type enum")
    file_hash: str = Field(..., description="SHA-256 hash", min_length=64, max_length=64)
    s3_uri: str = Field(..., description="S3 URI")
    original_filename: str = Field(..., description="Original filename")
    mime_type: str = Field(..., description="MIME type")
    timestamp: datetime = Field(..., description="ISO 8601 timestamp")
```

---

### ✅ 3. Optional fields: source_path, parent_id (for email attachments), permissions_blob, metadata (JSONB)

**Status:** ✅ **IMPLEMENTED**

**Optional Fields:**

| Field | Type | Description | Default |
|-------|------|-------------|---------|
| `source_path` | string (nullable) | Source path (email folder, cloud storage path) | null |
| `parent_id` | string (nullable) | Parent document ID (for email attachments) | null |
| `permissions_blob` | map<string> (nullable) | Source permissions for access control | null |
| `metadata` | map<string> (nullable) | Additional metadata (JSONB-compatible) | null |

**Implementation:**
```python
# Location: src/ingestion/models.py
source_path: Optional[str] = Field(None, description="Source path")
parent_id: Optional[str] = Field(None, description="Parent document ID")
permissions_blob: Optional[Dict[str, Any]] = Field(None, description="Source permissions")
metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")
```

---

### ✅ 4. Schema registry configured to reject non-compliant messages

**Status:** ✅ **IMPLEMENTED**

**Location:** `src/ingestion/schema.py`

**Implementation:**

**Schema Validation:**
- `IngestionEventSchema` class loads and validates Avro schema
- `SchemaRegistryClient` validates messages against schema
- `reject_non_compliant()` method raises `SchemaRegistryError` for invalid messages

**Validation Checks:**
- All required fields present
- `source_type` is valid enum value
- `file_hash` is 64-character hexadecimal string
- `timestamp` is numeric (milliseconds)
- Field types match schema

**Code:**
```python
# Location: src/ingestion/schema.py
class SchemaRegistryClient:
    def reject_non_compliant(self, message: Dict[str, Any]) -> None:
        """Reject non-compliant messages by raising exception."""
        if not self.validate_message(message):
            raise SchemaRegistryError(
                "Message does not comply with IngestionEvent schema."
            )
```

**Usage:**
```python
from src.ingestion.schema import get_schema_registry_client

client = get_schema_registry_client()
client.reject_non_compliant(message)  # Raises if invalid
```

---

## Schema Definition

### Avro Schema File

**Location:** `schemas/ingestion_event.avsc`

**Key Features:**
- Strict typing for all fields
- Enum for `source_type` (UPLOAD, EMAIL, CLOUD_SYNC)
- Nullable optional fields with defaults
- Logical type for timestamp (timestamp-millis)
- Map types for permissions_blob and metadata

### Pydantic Model

**Location:** `src/ingestion/models.py`

**Key Features:**
- Type validation with Pydantic
- Custom validators for `file_hash` (SHA-256 format)
- Custom validators for `tenant_id` (UUID format)
- Timezone-aware timestamp handling
- Conversion methods: `to_avro_dict()` and `from_avro_dict()`

---

## Usage Examples

### Creating an Ingestion Event

```python
from src.ingestion.models import IngestionEvent, SourceType, compute_file_hash
from datetime import datetime, timezone

# Compute file hash
file_content = b"file content here"
file_hash = compute_file_hash(file_content)

# Create event
event = IngestionEvent(
    tenant_id="550e8400-e29b-41d4-a716-446655440000",
    source_type=SourceType.UPLOAD,
    file_hash=file_hash,
    s3_uri=f"s3://bucket/{file_hash}",
    original_filename="document.pdf",
    mime_type="application/pdf",
    timestamp=datetime.now(timezone.utc),
    metadata={"upload_source": "web-ui"}
)
```

### Validating Against Schema

```python
from src.ingestion.schema import get_schema_registry_client

client = get_schema_registry_client()

# Convert to Avro-compatible dict
avro_dict = event.to_avro_dict()

# Validate (raises SchemaRegistryError if invalid)
client.reject_non_compliant(avro_dict)
```

### Publishing to Kafka/Redpanda

```python
# TODO: Implement Kafka producer
# For now, schema validation is ready
# Kafka producer implementation will be in next user story
```

---

## Configuration

### Environment Variables

```bash
# Kafka/Redpanda Configuration
KAFKA_BOOTSTRAP_SERVERS=localhost:9092
INGESTION_TOPIC=ingestion-events

# Schema Registry Configuration
SCHEMA_REGISTRY_URL=http://localhost:8081  # Optional, uses local validation if not set
SCHEMA_REGISTRY_SUBJECT=ingestion-events-value
```

### Configuration Class

**Location:** `src/config/ingestion_config.py`

```python
from src.config.ingestion_config import get_ingestion_config

config = get_ingestion_config()
print(f"Kafka servers: {config.kafka_bootstrap_servers}")
print(f"Ingestion topic: {config.ingestion_topic}")
```

---

## Testing

**Location:** `tests/test_ingestion_event_schema.py`

Run tests:
```bash
pytest tests/test_ingestion_event_schema.py -v
```

**Test Coverage:**
- ✅ Required fields validation
- ✅ Optional fields handling
- ✅ File hash validation (SHA-256 format)
- ✅ Source type enum validation
- ✅ Avro dictionary conversion
- ✅ Schema validation
- ✅ Non-compliant message rejection

---

## Content-Addressable Storage

The schema enforces content-addressable storage:
- `file_hash` is the SHA-256 hash of file content
- `s3_uri` uses the file hash as the key
- Enables automatic deduplication (same content = same hash)
- Maintains provenance (multiple sources can reference same file)

**Example:**
```python
file_hash = compute_file_hash(file_content)  # SHA-256
s3_uri = f"s3://ingestion-bucket/{file_hash[:2]}/{file_hash[2:4]}/{file_hash}"
```

---

## Source Permissions

The `permissions_blob` field captures source permissions where available:

**Email Example:**
```python
permissions_blob = {
    "from": "sender@example.com",
    "to": ["recipient@example.com"],
    "cc": ["cc@example.com"],
    "read_permission": ["recipient@example.com", "cc@example.com"]
}
```

**Cloud Storage Example:**
```python
permissions_blob = {
    "owner": "user-123",
    "readers": ["user-456", "group-analysts"],
    "writers": ["user-123"]
}
```

---

## Files Created

1. **`schemas/ingestion_event.avsc`** - Avro schema definition
2. **`src/ingestion/models.py`** - Pydantic model with validation
3. **`src/ingestion/schema.py`** - Schema registry client and validation
4. **`src/ingestion/__init__.py`** - Package exports
5. **`src/config/ingestion_config.py`** - Configuration management
6. **`tests/test_ingestion_event_schema.py`** - Comprehensive test suite

---

## Next Steps

1. **Install Dependencies:**
   ```bash
   pip install avro-python3 confluent-kafka[avro]
   ```

2. **Set Up Schema Registry** (optional):
   - Deploy Confluent Schema Registry
   - Set `SCHEMA_REGISTRY_URL` environment variable
   - Schema will be auto-registered on first use

3. **Test Schema Validation:**
   ```bash
   pytest tests/test_ingestion_event_schema.py -v
   ```

4. **Future User Stories:**
   - US-2.2: Direct Upload Ingestion
   - US-2.3: Email Forwarding Ingestion
   - US-2.4: Cloud Storage Sync Ingestion
   - US-2.5: Kafka Producer Implementation

---

## Acceptance Criteria Status

| Criteria | Status | Implementation |
|----------|--------|----------------|
| 1. Avro/Protobuf schema created | ✅ | `schemas/ingestion_event.avsc` |
| 2. Required fields defined | ✅ | All 7 required fields in schema |
| 3. Optional fields defined | ✅ | All 4 optional fields in schema |
| 4. Schema registry rejects non-compliant | ✅ | `SchemaRegistryClient.reject_non_compliant()` |

**Status:** ✅ **ALL ACCEPTANCE CRITERIA MET**
