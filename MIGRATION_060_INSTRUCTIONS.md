# Migration 060: Review Queue - Application Instructions

## Overview

This migration implements the prioritized review queue system for extractions requiring human review.

## What This Migration Does

1. **Creates `review_queue` table** with tenant isolation (RLS policies)
2. **Implements priority calculation** based on confidence, critical fields, and age
3. **Adds auto-population trigger** for extractions meeting review criteria
4. **Enables stale claim release** (30-minute auto-timeout)
5. **Creates indexes** for optimal query performance

## Prerequisites

- Database connection string for etlai.xyz
- PostgreSQL client (`psql`) installed
- Service role access to Supabase

## Application Methods

### Method 1: Automated Script (Recommended)

```bash
# Export database connection string
export DATABASE_URL='postgresql://postgres:[PASSWORD]@db.[PROJECT].supabase.co:5432/postgres'

# Run migration script
./scripts/apply_review_queue_migration.sh
```

### Method 2: Manual Application via Supabase Dashboard

1. Go to Supabase Dashboard → SQL Editor
2. Click "New Query"
3. Copy the entire contents of `supabase/migrations/060_review_queue.sql`
4. Paste into SQL Editor
5. Click "Run"

### Method 3: Direct psql Command

```bash
export DATABASE_URL='postgresql://postgres:[PASSWORD]@db.[PROJECT].supabase.co:5432/postgres'
psql "$DATABASE_URL" -f supabase/migrations/060_review_queue.sql
```

## Verification

After applying the migration, verify it was successful:

```bash
# Check table exists
psql "$DATABASE_URL" -c "\\dt review_queue"

# Check functions exist
psql "$DATABASE_URL" -c "\\df calculate_extraction_priority"
psql "$DATABASE_URL" -c "\\df should_queue_for_review"
psql "$DATABASE_URL" -c "\\df populate_review_queue"
psql "$DATABASE_URL" -c "\\df release_stale_claims"

# Check trigger exists
psql "$DATABASE_URL" -c "SELECT tgname FROM pg_trigger WHERE tgname = 'trigger_populate_review_queue';"

# Test priority calculation
psql "$DATABASE_URL" -c "SELECT public.calculate_extraction_priority('[EXTRACTION_ID]'::uuid);"
```

## Rollback (If Needed)

If you need to rollback this migration:

```sql
-- Drop trigger
DROP TRIGGER IF EXISTS trigger_populate_review_queue ON public.extractions;

-- Drop functions
DROP FUNCTION IF EXISTS public.populate_review_queue();
DROP FUNCTION IF EXISTS public.release_stale_claims();
DROP FUNCTION IF EXISTS public.should_queue_for_review(UUID);
DROP FUNCTION IF EXISTS public.calculate_extraction_priority(UUID);

-- Drop table (this will cascade delete all queue items)
DROP TABLE IF EXISTS public.review_queue CASCADE;
```

## Testing the Queue

After migration, test the queue functionality:

1. **Create a test extraction** with low confidence:
   ```sql
   -- This will automatically populate the queue via trigger
   INSERT INTO public.extractions (
     tenant_id, document_id, status, overall_confidence, parser_used
   ) VALUES (
     '[TENANT_ID]'::uuid,
     '[DOCUMENT_ID]'::uuid,
     'completed',
     0.75,  -- Below 0.85 threshold
     'unstructured'
   );
   ```

2. **Check queue was populated**:
   ```sql
   SELECT * FROM public.review_queue
   WHERE extraction_id = '[EXTRACTION_ID]'::uuid;
   ```

3. **Test API endpoints** (via curl or Postman):
   ```bash
   # List queue
   curl -H "Authorization: Bearer [TOKEN]" \
     https://etlai.xyz/api/v1/review/queue

   # Claim item
   curl -X POST -H "Authorization: Bearer [TOKEN]" \
     https://etlai.xyz/api/v1/review/queue/[ITEM_ID]/claim

   # Complete item
   curl -X POST -H "Authorization: Bearer [TOKEN]" \
     https://etlai.xyz/api/v1/review/queue/[ITEM_ID]/complete
   ```

## Queue Population Rules

Extractions are automatically queued when they meet ANY of these criteria:

1. **Low confidence**: `overall_confidence < 0.85`
2. **Parser fallback**: `parser_used = 'tika'`
3. **Low field confidence**: Any field has `confidence < 0.70`
4. **Entity resolution pending**: (future enhancement)

## Priority Scoring

Priority is calculated as:
```
Priority = (1 - confidence) × 50
         + critical_field_issues × 10
         + min(age_hours, 20)
```

Where:
- **Confidence penalty**: 0-50 points (lower confidence = higher priority)
- **Critical field issues**: 10 points each (base_rent, lease_start_date, lease_end_date)
- **Age bonus**: 1-20 points (older extractions get higher priority)

## API Endpoints

After migration, these endpoints are available:

- `GET /api/v1/review/queue` - List queue items (sorted by priority)
- `POST /api/v1/review/queue/{id}/claim` - Claim item for review
- `POST /api/v1/review/queue/{id}/complete` - Mark item as completed
- `POST /api/v1/review/queue/{id}/skip` - Skip item

All endpoints enforce:
- Tenant isolation via RLS
- Permission checks (`documents:read`, `documents:write`)
- 30-minute claim timeout with auto-release

## Monitoring

Monitor the queue health:

```sql
-- Check queue counts by status
SELECT status, COUNT(*)
FROM public.review_queue
GROUP BY status;

-- Check stale claims (should be 0 if auto-release is working)
SELECT COUNT(*)
FROM public.review_queue
WHERE status = 'claimed'
  AND claimed_at < (now() - INTERVAL '30 minutes');

-- Check average priority scores
SELECT
  AVG(priority) as avg_priority,
  MIN(priority) as min_priority,
  MAX(priority) as max_priority
FROM public.review_queue
WHERE status = 'pending';
```

## Troubleshooting

### Issue: Extractions not appearing in queue

**Solution**: Check if extraction meets queue criteria:
```sql
SELECT
  id,
  overall_confidence,
  parser_used,
  public.should_queue_for_review(id) as should_be_queued
FROM public.extractions
WHERE id = '[EXTRACTION_ID]'::uuid;
```

### Issue: Claims not being released

**Solution**: Manually trigger stale claim release:
```sql
SELECT public.release_stale_claims();
```

### Issue: RLS blocking access

**Solution**: Verify user has correct tenant_id:
```sql
-- Check current tenant context
SELECT public.tenant_id();

-- Check queue item tenant
SELECT tenant_id FROM public.review_queue WHERE id = '[ITEM_ID]'::uuid;
```

## Support

For issues or questions:
- Check logs: Application logs will show queue operations
- Review RLS policies: Ensure user has correct permissions
- Verify tenant isolation: All operations are tenant-scoped

## Change Log

- **2025-01-10**: Initial migration created
  - Review queue table with RLS
  - Priority calculation functions
  - Auto-population trigger
  - Stale claim release mechanism
  - API endpoints for queue management
