"""Test Avro schema loading with installed packages."""
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

def main():
    print("Testing Avro schema loading...")
    print()
    
    try:
        from src.ingestion.schema import IngestionEventSchema
        
        schema = IngestionEventSchema()
        print("[OK] Schema loaded successfully")
        
        # Check if Avro is available
        if hasattr(schema.schema, 'name'):
            print(f"[OK] Avro schema parsed: {schema.schema.name}")
            print(f"[OK] Schema namespace: {schema.schema.namespace}")
            print(f"[OK] Schema type: {schema.schema.type}")
        else:
            print("[INFO] Using JSON schema (Avro not fully available)")
        
        # Test validation
        from src.ingestion.models import IngestionEvent, SourceType, compute_file_hash
        from datetime import datetime, timezone
        
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
        is_valid = schema.validate(avro_dict)
        
        if is_valid:
            print("[OK] Event validation passed")
        else:
            print("[ERROR] Event validation failed")
            return 1
        
        print()
        print("All tests passed!")
        return 0
        
    except Exception as e:
        print(f"[ERROR] {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main())
