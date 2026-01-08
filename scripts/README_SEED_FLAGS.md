# Seed Feature Flags via Admin API

This script seeds feature flags using the admin API endpoints, testing the full API flow.

## Prerequisites

1. Ensure your `.env` file has all required variables:
   ```
   SUPABASE_URL=...
   SUPABASE_ANON_KEY=...
   SUPABASE_SERVICE_KEY=...
   SUPABASE_JWT_SECRET=...
   ```

2. Run the database migration first:
   ```bash
   supabase db push
   ```

## Usage

### Via Admin API (Recommended)

```bash
python scripts/seed_flags_via_api.py
```

This script:
- ✅ Uses the actual admin API endpoints
- ✅ Tests authentication and authorization
- ✅ Creates flags via `POST /api/v1/admin/flags`
- ✅ Verifies admin-only access control
- ✅ Lists all created flags

### Direct Database Access (Alternative)

```bash
python scripts/seed_feature_flags.py
```

This script:
- ✅ Directly accesses Supabase database
- ✅ Faster (no API overhead)
- ✅ Useful for bulk seeding

## Flags Created

The script creates 6 example feature flags:

1. **experimental_search** (Default: Disabled)
   - New experimental search algorithm with improved relevance

2. **advanced_analytics** (Default: Enabled)
   - Advanced analytics dashboard with real-time metrics

3. **ai_summarization** (Default: Disabled)
   - AI-powered document summarization feature

4. **bulk_export** (Default: Enabled)
   - Bulk export functionality for large datasets

5. **dark_mode** (Default: Disabled)
   - Dark mode UI theme

6. **api_v2** (Default: Disabled)
   - New API v2 endpoints with improved performance

## Testing

After seeding, test the flags:

```python
from src.dependencies import get_feature_flags
from src.features.service import FeatureFlagService

@app.get("/test-feature")
async def test_feature(flags: FeatureFlagService = Depends(get_feature_flags)):
    if await flags.is_enabled("experimental_search"):
        return {"message": "Feature enabled!"}
    return {"message": "Feature disabled"}
```

## Setting Tenant Overrides

Use the admin API to enable flags for specific tenants:

```bash
PUT /api/v1/admin/flags/experimental_search/tenants/{tenant_id}
{
  "enabled": true
}
```
