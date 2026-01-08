# Feature Flags System

Per-tenant feature flag system with caching and admin-only management.

## Architecture

### Database Schema
- `feature_flags`: Flag definitions with default enabled status
- `tenant_feature_flags`: Per-tenant overrides

### Caching
- **5-minute TTL**: Flags are cached for 5 minutes to avoid database queries
- **Cache-first**: All flag checks check cache before querying database
- **Automatic refresh**: Cache refreshes when expired

### Security
- **Admin-only modifications**: All create/update/delete operations require Admin role
- **Read access**: Users can check their own tenant's flags
- **Fail closed**: Errors return `False` (feature disabled)

## Usage

### In Endpoints

```python
from src.dependencies import get_feature_flags
from src.features.service import FeatureFlagService

@app.get("/experimental-feature")
async def experimental(
    flags: FeatureFlagService = Depends(get_feature_flags)
):
    if not await flags.is_enabled("experimental_search"):
        raise HTTPException(404, "Feature not available")
    return {"data": "experimental results"}
```

### Admin Management

```python
# Create a flag
POST /api/v1/admin/flags
{
  "name": "experimental_search",
  "description": "New search algorithm",
  "enabled_default": false
}

# Enable for specific tenant
PUT /api/v1/admin/flags/experimental_search/tenants/{tenant_id}
{
  "enabled": true
}
```

## Implementation Guarantees

✅ **No database queries on every check**: Cache is checked first, database only queried on cache miss/expiry

✅ **Admin-only modifications**: All modification endpoints require `require_role("Admin")`

✅ **No hardcoded values**: All flag values come from database (defaults or tenant overrides)
