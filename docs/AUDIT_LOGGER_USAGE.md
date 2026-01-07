# Audit Logger Usage Guide

## Quick Start

The audit logger is automatically initialized when your FastAPI application starts. You can use it in any route to log audit events.

## Basic Usage

```python
from src.audit.service import audit_log
from fastapi import Request, Depends
from src.dependencies import get_tenant_id
from src.auth.dependencies import get_current_user_claims
from src.auth.jwt_validator import JWTClaims

@router.post("/api/v1/documents")
async def upload_document(
    request: Request,
    document_id: str,
    tenant_id: str = Depends(get_tenant_id),
    claims: JWTClaims = Depends(get_current_user_claims)
):
    # Your business logic here
    # ... upload document ...
    
    # Log the audit event
    await audit_log(
        user_id=claims.user_id,
        tenant_id=tenant_id,
        action_type="document.upload",
        resource_id=document_id,
        request=request
    )
    
    return {"status": "success"}
```

## Parameters

### Required Parameters

- `user_id` (str): User ID who performed the action
- `tenant_id` (str): Tenant ID where action occurred
- `action_type` (str): Type of action (e.g., "document.upload", "user.delete")

### Optional Parameters

- `resource_id` (str, optional): ID of the resource affected
- `request` (Request, optional): FastAPI Request object (automatically extracts metadata)
- `additional_metadata` (dict, optional): Additional metadata to include

## Action Type Naming Convention

Use dot-separated hierarchical names:
- `document.upload`
- `document.delete`
- `user.create`
- `user.update`
- `tenant.settings.update`
- `audit.tampering.attempt` (for tampering detection)

## Examples

### Example 1: Document Upload

```python
await audit_log(
    user_id=claims.user_id,
    tenant_id=tenant_id,
    action_type="document.upload",
    resource_id=document_id,
    request=request,
    additional_metadata={
        "file_size": file_size,
        "file_type": file_type
    }
)
```

### Example 2: User Deletion

```python
await audit_log(
    user_id=claims.user_id,
    tenant_id=tenant_id,
    action_type="user.delete",
    resource_id=deleted_user_id,
    request=request
)
```

### Example 3: Settings Update

```python
await audit_log(
    user_id=claims.user_id,
    tenant_id=tenant_id,
    action_type="tenant.settings.update",
    request=request,
    additional_metadata={
        "settings_changed": ["retention_period", "notification_email"]
    }
)
```

## What Gets Logged

Each audit log entry includes:

- `user_id`: User who performed the action
- `tenant_id`: Tenant where action occurred
- `timestamp`: ISO 8601 timestamp (automatically set)
- `action_type`: Type of action
- `resource_id`: Optional resource identifier
- `request_metadata`: Automatically extracted from Request object:
  - `method`: HTTP method (GET, POST, etc.)
  - `path`: Request path
  - `query_params`: Query parameters
  - `client_host`: Client IP address
  - `user_agent`: User agent string
- `retention_until`: Retention expiration date (7 years default, configurable per tenant)

## Async Behavior

The audit logger writes asynchronously:
- **Non-blocking**: Your request completes immediately
- **Batched writes**: Entries are batched for efficiency
- **Automatic retry**: Failed writes are retried
- **No performance impact**: Main request path never waits

## Synchronous Logging (Critical Events)

For critical events that must be logged immediately (e.g., tampering attempts):

```python
from src.audit.service import audit_log_sync

audit_log_sync(
    user_id=claims.user_id,
    tenant_id=tenant_id,
    action_type="audit.tampering.attempt",
    resource_id=s3_key,
    additional_metadata={"error_code": "InvalidObjectState"}
)
```

**Note:** Use `audit_log_sync()` sparingly - it blocks until the log is written.

## Example Routes

See `src/api/routes/audit_example.py` for complete working examples:
- Document upload with audit logging
- Document deletion with audit logging
- Generic user actions with audit logging

## Testing

Test the audit logger:

```bash
python scripts/test_audit_logger_write.py
```

Verify immutability:

```bash
python scripts/test_audit_immutability.py
```

## Querying Audit Logs

Query audit logs directly from Supabase:

```python
from src.db.supabase_client import get_supabase_client

client = get_supabase_client(use_service_role=True)

# Get all logs for a tenant
result = client.table('audit_logs').select('*').eq('tenant_id', tenant_id).execute()

# Get logs by action type
result = client.table('audit_logs').select('*').eq('action_type', 'document.upload').execute()

# Get recent logs
result = client.table('audit_logs').select('*').order('timestamp', desc=True).limit(100).execute()
```

## Best Practices

1. **Log all important actions**: Document uploads, deletions, user changes, etc.
2. **Use descriptive action types**: `document.upload` not `upload`
3. **Include resource IDs**: Makes it easier to trace specific resources
4. **Add context in metadata**: Include relevant details in `additional_metadata`
5. **Don't log PII**: Only log IDs and metadata, not sensitive data
6. **Use async logging**: Use `audit_log()` for normal operations
7. **Use sync logging sparingly**: Only for critical security events

## Troubleshooting

### Audit logs not appearing

1. Check that the audit logger started:
   - Look for "Audit logger started" in application logs
2. Wait for async flush:
   - Logs are batched and flushed every 5 seconds (default)
3. Check Supabase connection:
   - Verify `SUPABASE_SERVICE_ROLE_KEY` is set correctly
4. Check table exists:
   - Verify `audit_logs` table exists in `public` schema

### Errors writing logs

- Check Supabase service role key is valid
- Verify table exists and is accessible
- Check RLS policies allow inserts
- Review application logs for detailed error messages

## Configuration

Environment variables:

```bash
# Storage backend (default: supabase)
AUDIT_STORAGE_BACKEND=supabase

# Retention period (default: 7 years)
AUDIT_RETENTION_YEARS=7

# Async configuration
AUDIT_QUEUE_SIZE=1000
AUDIT_BATCH_SIZE=10
AUDIT_FLUSH_INTERVAL_SECONDS=5

# Supabase configuration
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SERVICE_ROLE_KEY=your-service-role-key
```

## See Also

- `docs/AUDIT_LOG_IMPLEMENTATION.md` - Complete implementation details
- `docs/SUPABASE_AUDIT_LOG_MIGRATION.md` - Migration guide
- `src/api/routes/audit_example.py` - Working examples
