# Migrating Audit Logs from S3 to Supabase

## Overview

The audit logging system now supports both AWS S3 and Supabase PostgreSQL as storage backends. Supabase is the default backend and provides WORM (Write Once Read Many) storage through database-level constraints.

## Key Changes

### 1. Storage Backend Selection

The system now uses `AUDIT_STORAGE_BACKEND` environment variable to choose between:
- `supabase` (default) - Uses Supabase PostgreSQL with database triggers
- `s3` - Uses AWS S3 with Object Lock

### 2. Database Schema

A new `audit_logs` table is created in the `control_plane` schema with:
- Immutability enforced by database triggers
- Row Level Security (RLS) policies
- Automatic tampering attempt logging

### 3. Implementation Files

**New Files:**
- `src/audit/supabase_logger.py` - Supabase-based audit logger
- `src/audit/logger_factory.py` - Factory to select backend
- `alembic/versions/003_audit_logs_table.py` - Database migration

**Modified Files:**
- `src/config/audit_config.py` - Added backend selection
- `src/audit/__init__.py` - Updated exports
- `src/audit/service.py` - Uses factory function

## Migration Steps

### Step 1: Run Database Migration

```bash
alembic upgrade head
```

This will create the `audit_logs` table with:
- Immutability triggers (prevents updates/deletes)
- RLS policies (insert-only, read-only)
- Indexes for query performance

### Step 2: Set Environment Variable

```bash
# Use Supabase (default)
AUDIT_STORAGE_BACKEND=supabase

# Or explicitly set (optional, since supabase is default)
# AUDIT_STORAGE_BACKEND=s3  # Only if you want to use S3
```

### Step 3: Verify Configuration

Ensure Supabase is configured:
```bash
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SERVICE_ROLE_KEY=your-service-role-key
```

### Step 4: Restart Application

The audit logger will automatically use Supabase backend.

## WORM Storage Implementation

### Database Triggers

The migration creates triggers that:
1. **Prevent Updates**: Any UPDATE operation raises an exception
2. **Prevent Deletes**: Any DELETE operation raises an exception
3. **Log Tampering**: Attempts to modify logs are themselves logged

### Row Level Security (RLS)

RLS policies enforce:
- ✅ **INSERT**: Allowed (for writing audit logs)
- ✅ **SELECT**: Allowed (for reading audit logs)
- ❌ **UPDATE**: Denied (immutability)
- ❌ **DELETE**: Denied (immutability)

### Example Trigger Behavior

```sql
-- This will fail:
UPDATE control_plane.audit_logs 
SET action_type = 'modified' 
WHERE id = 'some-id';

-- Error: Audit logs are immutable. Updates and deletes are not allowed.
```

## Benefits of Supabase Backend

1. **No AWS Dependencies**: No need for AWS credentials or S3 setup
2. **Integrated**: Uses existing Supabase infrastructure
3. **Queryable**: Can query audit logs using SQL
4. **Transactional**: Benefits from PostgreSQL ACID guarantees
5. **Same Security**: Database-level immutability (equivalent to S3 Object Lock)

## Backward Compatibility

The S3 backend is still supported. To use S3:

```bash
AUDIT_STORAGE_BACKEND=s3
AUDIT_S3_BUCKET=your-bucket-name
```

## Testing

Run the migration and verify:

```sql
-- Verify table exists
SELECT * FROM control_plane.audit_logs LIMIT 1;

-- Try to update (should fail)
UPDATE control_plane.audit_logs SET action_type = 'test' WHERE id = (SELECT id FROM control_plane.audit_logs LIMIT 1);

-- Try to delete (should fail)
DELETE FROM control_plane.audit_logs WHERE id = (SELECT id FROM control_plane.audit_logs LIMIT 1);
```

## Acceptance Criteria Verification

✅ **1. Immutable Storage**: Database triggers prevent modifications  
✅ **2. All Required Fields**: Same AuditLogEntry model  
✅ **3. Async Writes**: Same async queue-based implementation  
✅ **4. Retention Period**: Tenant-specific retention supported  
✅ **5. Tampering Detection**: Database triggers log attempts automatically  

## Troubleshooting

### Migration Fails

If migration fails, check:
- Supabase connection string is correct
- You have permissions to create tables/triggers
- No existing `audit_logs` table conflicts

### RLS Policies Not Working

Ensure:
- Service role key is used (bypasses RLS for writes)
- RLS is enabled on the table
- Policies are created correctly

### Triggers Not Preventing Modifications

Verify triggers exist:
```sql
SELECT * FROM pg_trigger WHERE tgname LIKE '%audit_log%';
```
