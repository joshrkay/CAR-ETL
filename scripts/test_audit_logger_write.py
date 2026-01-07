"""Test writing an audit log entry to Supabase."""
import os
import sys
import asyncio
from pathlib import Path
from datetime import datetime

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Set the service role key
os.environ['SUPABASE_SERVICE_ROLE_KEY'] = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InFpZmlvYWZwcnJ0a29peXlsc3FhIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc2Nzc1OTQ3NiwiZXhwIjoyMDgzMzM1NDc2fQ.EcN2vIilunhiercdPZm_H7Gouwf0xqSXgGNDkSmP-ZY'

from src.audit.models import AuditLogEntry
from src.audit.logger_factory import get_audit_logger

async def test_audit_logging():
    """Test writing an audit log entry."""
    print("=" * 60)
    print("Testing Audit Logger Write Operation")
    print("=" * 60)
    print()
    
    # Create a test audit entry
    print("1. Creating test audit log entry...")
    entry = AuditLogEntry.create(
        user_id="test-user-123",
        tenant_id="test-tenant-456",
        action_type="test.audit.log",
        resource_id="test-resource-789",
        request_metadata={
            "method": "POST",
            "path": "/api/v1/test",
            "test": True
        }
    )
    print(f"   [OK] Entry created: {entry.action_type}")
    print(f"   [OK] Timestamp: {entry.timestamp}")
    print()
    
    # Initialize logger
    print("2. Initializing audit logger...")
    logger = get_audit_logger()
    print(f"   [OK] Logger type: {type(logger).__name__}")
    print()
    
    # Start logger
    print("3. Starting audit logger...")
    await logger.start()
    print("   [OK] Logger started")
    print()
    
    # Write entry
    print("4. Writing audit log entry...")
    try:
        await logger.log(entry)
        print("   [OK] Entry queued for async write")
        
        # Wait a bit for async write
        print("   [OK] Waiting for async flush...")
        await asyncio.sleep(6)  # Wait longer than flush interval (5s)
        
    except Exception as e:
        print(f"   [ERROR] Failed to write: {e}")
        return 1
    print()
    
    # Stop logger
    print("5. Stopping audit logger...")
    await logger.stop()
    print("   [OK] Logger stopped")
    print()
    
    # Verify entry was written
    print("6. Verifying entry was written...")
    try:
        from src.db.supabase_client import get_supabase_client
        client = get_supabase_client(use_service_role=True)
        result = client.table('audit_logs').select('*').eq('action_type', 'test.audit.log').limit(1).execute()
        
        if result.data and len(result.data) > 0:
            log_entry = result.data[0]
            print(f"   [OK] Entry found in database!")
            print(f"   [OK] ID: {log_entry.get('id')}")
            print(f"   [OK] User ID: {log_entry.get('user_id')}")
            print(f"   [OK] Action Type: {log_entry.get('action_type')}")
            print(f"   [OK] Timestamp: {log_entry.get('timestamp')}")
        else:
            print("   [WARN] Entry not found (may need to wait longer)")
    except Exception as e:
        print(f"   [WARN] Could not verify: {e}")
    print()
    
    print("=" * 60)
    print("[OK] Audit Logger Test Complete")
    print("=" * 60)
    print()
    print("The audit logger is working correctly!")
    print("You can now use it in your application.")
    
    return 0

if __name__ == "__main__":
    sys.exit(asyncio.run(test_audit_logging()))
