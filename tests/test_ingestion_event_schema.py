"""Tests for ingestion event schema validation."""
import pytest
from datetime import datetime, timezone
from typing import Dict, Any
from pydantic import ValidationError

from src.ingestion.models import IngestionEvent, SourceType, compute_file_hash
from src.ingestion.schema import IngestionEventSchema, SchemaRegistryClient, SchemaRegistryError


def test_ingestion_event_required_fields():
    """Test that all required fields are validated."""
    # Valid event
    event = IngestionEvent(
        tenant_id="550e8400-e29b-41d4-a716-446655440000",
        source_type=SourceType.UPLOAD,
        file_hash="a" * 64,  # Valid SHA-256 hash format
        s3_uri="s3://bucket/file-hash-key",
        original_filename="test.pdf",
        mime_type="application/pdf",
        timestamp=datetime.now(timezone.utc)
    )
    
    assert event.tenant_id is not None
    assert event.source_type == SourceType.UPLOAD
    assert len(event.file_hash) == 64


def test_ingestion_event_optional_fields():
    """Test that optional fields can be omitted."""
    event = IngestionEvent(
        tenant_id="550e8400-e29b-41d4-a716-446655440000",
        source_type=SourceType.EMAIL,
        file_hash="b" * 64,
        s3_uri="s3://bucket/file-hash-key",
        original_filename="attachment.pdf",
        mime_type="application/pdf",
        timestamp=datetime.now(timezone.utc),
        parent_id="parent-email-id",
        source_path="/inbox/important"
    )
    
    assert event.parent_id == "parent-email-id"
    assert event.source_path == "/inbox/important"
    assert event.permissions_blob is None
    assert event.metadata is None


def test_ingestion_event_file_hash_validation():
    """Test file_hash validation (must be 64 hex characters)."""
    # Valid hash
    valid_hash = "a" * 64
    event = IngestionEvent(
        tenant_id="550e8400-e29b-41d4-a716-446655440000",
        source_type=SourceType.UPLOAD,
        file_hash=valid_hash,
        s3_uri="s3://bucket/key",
        original_filename="test.pdf",
        mime_type="application/pdf",
        timestamp=datetime.now(timezone.utc)
    )
    assert event.file_hash == valid_hash.lower()  # Normalized to lowercase
    
    # Invalid hash (too short)
    with pytest.raises(ValidationError):
        IngestionEvent(
            tenant_id="550e8400-e29b-41d4-a716-446655440000",
            source_type=SourceType.UPLOAD,
            file_hash="short",
            s3_uri="s3://bucket/key",
            original_filename="test.pdf",
            mime_type="application/pdf",
            timestamp=datetime.now(timezone.utc)
        )
    
    # Invalid hash (non-hexadecimal)
    with pytest.raises(ValidationError):
        IngestionEvent(
            tenant_id="550e8400-e29b-41d4-a716-446655440000",
            source_type=SourceType.UPLOAD,
            file_hash="g" * 64,  # 'g' is not hexadecimal
            s3_uri="s3://bucket/key",
            original_filename="test.pdf",
            mime_type="application/pdf",
            timestamp=datetime.now(timezone.utc)
        )


def test_ingestion_event_source_type_enum():
    """Test that source_type must be valid enum value."""
    for source_type in SourceType:
        event = IngestionEvent(
            tenant_id="550e8400-e29b-41d4-a716-446655440000",
            source_type=source_type,
            file_hash="a" * 64,
            s3_uri="s3://bucket/key",
            original_filename="test.pdf",
            mime_type="application/pdf",
            timestamp=datetime.now(timezone.utc)
        )
        assert event.source_type == source_type


def test_ingestion_event_to_avro_dict():
    """Test conversion to Avro-compatible dictionary."""
    timestamp = datetime.now(timezone.utc)
    event = IngestionEvent(
        tenant_id="550e8400-e29b-41d4-a716-446655440000",
        source_type=SourceType.CLOUD_SYNC,
        file_hash="a" * 64,
        s3_uri="s3://bucket/key",
        original_filename="test.pdf",
        mime_type="application/pdf",
        timestamp=timestamp,
        source_path="/cloud/path",
        metadata={"key": "value"}
    )
    
    avro_dict = event.to_avro_dict()
    
    assert avro_dict["tenant_id"] == "550e8400-e29b-41d4-a716-446655440000"
    assert avro_dict["source_type"] == "CLOUD_SYNC"
    assert avro_dict["file_hash"] == "a" * 64
    assert avro_dict["source_path"] == "/cloud/path"
    assert avro_dict["metadata"] == {"key": "value"}
    assert isinstance(avro_dict["timestamp"], int)  # Milliseconds


def test_ingestion_event_from_avro_dict():
    """Test creation from Avro dictionary."""
    timestamp_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
    
    avro_dict = {
        "tenant_id": "550e8400-e29b-41d4-a716-446655440000",
        "source_type": "UPLOAD",
        "file_hash": "a" * 64,
        "s3_uri": "s3://bucket/key",
        "original_filename": "test.pdf",
        "mime_type": "application/pdf",
        "timestamp": timestamp_ms,
        "parent_id": None,
        "source_path": None,
        "permissions_blob": None,
        "metadata": None
    }
    
    event = IngestionEvent.from_avro_dict(avro_dict)
    
    assert event.tenant_id == "550e8400-e29b-41d4-a716-446655440000"
    assert event.source_type == SourceType.UPLOAD
    assert event.file_hash == "a" * 64


def test_compute_file_hash():
    """Test SHA-256 hash computation."""
    content = b"test file content"
    file_hash = compute_file_hash(content)
    
    assert len(file_hash) == 64
    assert all(c in "0123456789abcdef" for c in file_hash)


def test_schema_validation_valid_message():
    """Test schema validation with valid message."""
    schema = IngestionEventSchema()
    timestamp_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
    
    message = {
        "tenant_id": "550e8400-e29b-41d4-a716-446655440000",
        "source_type": "UPLOAD",
        "file_hash": "a" * 64,
        "s3_uri": "s3://bucket/key",
        "original_filename": "test.pdf",
        "mime_type": "application/pdf",
        "timestamp": timestamp_ms
    }
    
    assert schema.validate(message) is True


def test_schema_validation_missing_required_field():
    """Test schema validation rejects messages with missing required fields."""
    schema = IngestionEventSchema()
    
    message = {
        "tenant_id": "550e8400-e29b-41d4-a716-446655440000",
        # Missing source_type
        "file_hash": "a" * 64,
        "s3_uri": "s3://bucket/key",
        "original_filename": "test.pdf",
        "mime_type": "application/pdf",
        "timestamp": int(datetime.now(timezone.utc).timestamp() * 1000)
    }
    
    assert schema.validate(message) is False


def test_schema_validation_invalid_file_hash():
    """Test schema validation rejects invalid file_hash."""
    schema = IngestionEventSchema()
    timestamp_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
    
    message = {
        "tenant_id": "550e8400-e29b-41d4-a716-446655440000",
        "source_type": "UPLOAD",
        "file_hash": "short",  # Invalid length
        "s3_uri": "s3://bucket/key",
        "original_filename": "test.pdf",
        "mime_type": "application/pdf",
        "timestamp": timestamp_ms
    }
    
    assert schema.validate(message) is False


def test_schema_registry_client_reject_non_compliant():
    """Test that schema registry client rejects non-compliant messages."""
    client = SchemaRegistryClient()
    timestamp_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
    
    # Valid message
    valid_message = {
        "tenant_id": "550e8400-e29b-41d4-a716-446655440000",
        "source_type": "UPLOAD",
        "file_hash": "a" * 64,
        "s3_uri": "s3://bucket/key",
        "original_filename": "test.pdf",
        "mime_type": "application/pdf",
        "timestamp": timestamp_ms
    }
    client.reject_non_compliant(valid_message)  # Should not raise
    
    # Invalid message (missing required field)
    invalid_message = {
        "tenant_id": "550e8400-e29b-41d4-a716-446655440000",
        # Missing source_type
        "file_hash": "a" * 64,
        "s3_uri": "s3://bucket/key",
        "original_filename": "test.pdf",
        "mime_type": "application/pdf",
        "timestamp": timestamp_ms
    }
    
    with pytest.raises(SchemaRegistryError, match="does not comply"):
        client.reject_non_compliant(invalid_message)
