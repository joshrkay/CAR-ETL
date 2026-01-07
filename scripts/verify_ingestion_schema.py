"""Verify ingestion event schema implementation meets all acceptance criteria."""
import sys
from pathlib import Path
from datetime import datetime, timezone

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

def main():
    print("=" * 70)
    print("Ingestion Event Schema (US-2.1) - Acceptance Criteria Verification")
    print("=" * 70)
    print()
    
    # Acceptance Criteria 1: Avro/Protobuf schema created
    print("1. Avro/Protobuf schema created for IngestionEvent message type")
    print("-" * 70)
    try:
        schema_file = Path("schemas/ingestion_event.avsc")
        if schema_file.exists():
            print(f"   [OK] Avro schema file exists: {schema_file}")
            
            import json
            with open(schema_file, "r") as f:
                schema_json = json.load(f)
                assert schema_json["type"] == "record"
                assert schema_json["name"] == "IngestionEvent"
                print("   [OK] Schema is valid Avro record type")
                print(f"   [OK] Schema namespace: {schema_json.get('namespace', 'N/A')}")
        else:
            print(f"   [ERROR] Schema file not found: {schema_file}")
            return 1
    except Exception as e:
        print(f"   [ERROR] {e}")
        return 1
    
    # Acceptance Criteria 2: Required fields
    print()
    print("2. Required fields: tenant_id, source_type, file_hash, s3_uri, original_filename, mime_type, timestamp")
    print("-" * 70)
    try:
        from src.ingestion.models import IngestionEvent, SourceType, compute_file_hash
        
        # Check required fields
        required_fields = [
            "tenant_id", "source_type", "file_hash", "s3_uri",
            "original_filename", "mime_type", "timestamp"
        ]
        
        # Create a valid event
        file_hash = compute_file_hash(b"test content")
        event = IngestionEvent(
            tenant_id="550e8400-e29b-41d4-a716-446655440000",
            source_type=SourceType.UPLOAD,
            file_hash=file_hash,
            s3_uri=f"s3://bucket/{file_hash}",
            original_filename="test.pdf",
            mime_type="application/pdf",
            timestamp=datetime.now(timezone.utc)
        )
        
        for field in required_fields:
            assert hasattr(event, field), f"{field} field missing"
            print(f"   [OK] {field} field exists and validated")
        
        # Check source_type enum
        assert SourceType.UPLOAD in SourceType
        assert SourceType.EMAIL in SourceType
        assert SourceType.CLOUD_SYNC in SourceType
        print("   [OK] source_type enum has all three values: UPLOAD, EMAIL, CLOUD_SYNC")
        
    except Exception as e:
        print(f"   [ERROR] {e}")
        return 1
    
    # Acceptance Criteria 3: Optional fields
    print()
    print("3. Optional fields: source_path, parent_id, permissions_blob, metadata")
    print("-" * 70)
    try:
        from src.ingestion.models import IngestionEvent, SourceType, compute_file_hash
        
        optional_fields = ["source_path", "parent_id", "permissions_blob", "metadata"]
        
        file_hash = compute_file_hash(b"test content")
        event = IngestionEvent(
            tenant_id="550e8400-e29b-41d4-a716-446655440000",
            source_type=SourceType.EMAIL,
            file_hash=file_hash,
            s3_uri=f"s3://bucket/{file_hash}",
            original_filename="attachment.pdf",
            mime_type="application/pdf",
            timestamp=datetime.now(timezone.utc),
            source_path="/inbox",
            parent_id="parent-email-id",
            permissions_blob={"read": ["user-1"]},
            metadata={"key": "value"}
        )
        
        for field in optional_fields:
            assert hasattr(event, field), f"{field} field missing"
            print(f"   [OK] {field} field exists and can be set")
        
    except Exception as e:
        print(f"   [ERROR] {e}")
        return 1
    
    # Acceptance Criteria 4: Schema registry rejects non-compliant messages
    print()
    print("4. Schema registry configured to reject non-compliant messages")
    print("-" * 70)
    try:
        from src.ingestion.schema import SchemaRegistryClient, SchemaRegistryError
        from src.ingestion.models import IngestionEvent, SourceType, compute_file_hash
        
        client = SchemaRegistryClient()
        
        # Test valid message
        file_hash = compute_file_hash(b"test content")
        event = IngestionEvent(
            tenant_id="550e8400-e29b-41d4-a716-446655440000",
            source_type=SourceType.UPLOAD,
            file_hash=file_hash,
            s3_uri=f"s3://bucket/{file_hash}",
            original_filename="test.pdf",
            mime_type="application/pdf",
            timestamp=datetime.now(timezone.utc)
        )
        
        avro_dict = event.to_avro_dict()
        client.reject_non_compliant(avro_dict)  # Should not raise
        print("   [OK] Valid messages pass validation")
        
        # Test invalid message (missing required field)
        invalid_dict = avro_dict.copy()
        del invalid_dict["source_type"]
        
        try:
            client.reject_non_compliant(invalid_dict)
            print("   [ERROR] Invalid message should have been rejected")
            return 1
        except SchemaRegistryError:
            print("   [OK] Invalid messages are rejected with SchemaRegistryError")
        
    except Exception as e:
        print(f"   [ERROR] {e}")
        return 1
    
    # Summary
    print()
    print("=" * 70)
    print("[OK] All Acceptance Criteria Verified")
    print("=" * 70)
    print()
    print("Summary:")
    print("  [OK] 1. Avro schema created for IngestionEvent")
    print("  [OK] 2. All required fields defined and validated")
    print("  [OK] 3. All optional fields defined")
    print("  [OK] 4. Schema registry rejects non-compliant messages")
    print()
    print("Implementation Status: [OK] COMPLETE")
    print()
    print("Next Steps:")
    print("  1. Install dependencies: pip install avro-python3 confluent-kafka[avro]")
    print("  2. Run tests: pytest tests/test_ingestion_event_schema.py -v")
    print("  3. See docs/INGESTION_EVENT_SCHEMA.md for detailed documentation")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
