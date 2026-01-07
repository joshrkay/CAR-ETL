# Authentication Module

Supabase Auth integration with custom claims middleware for multi-tenant SaaS.

## Setup

### 1. Database Migration

Run the migration to create the auth hook function:

```bash
supabase db push
```

### 2. Configure Supabase Auth Hook

In your Supabase Dashboard:

1. Go to **Authentication** → **Hooks**
2. Add a new hook:
   - **Hook Type**: `access_token`
   - **Hook Function**: `custom_access_token_hook`
   - **Schema**: `public`

This will automatically inject `tenant_id`, `roles`, and `tenant_slug` into JWT tokens.

### 3. Environment Variables

Ensure these are set in your `.env` file:

```env
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_ANON_KEY=your-anon-key
SUPABASE_SERVICE_KEY=your-service-key
SUPABASE_JWT_SECRET=your-jwt-secret
```

### 4. Database Schema Requirements

The auth hook expects these tables:

```sql
-- tenants table
CREATE TABLE public.tenants (
  id uuid PRIMARY KEY,
  slug text UNIQUE NOT NULL,
  -- other tenant fields
);

-- tenant_users table (junction table)
CREATE TABLE public.tenant_users (
  user_id uuid REFERENCES auth.users(id),
  tenant_id uuid REFERENCES public.tenants(id),
  roles text[] DEFAULT '{}',
  PRIMARY KEY (user_id, tenant_id)
);
```

## Usage

### Basic FastAPI Setup

```python
from fastapi import FastAPI
from src.auth.middleware import AuthMiddleware

app = FastAPI()
app.add_middleware(AuthMiddleware)
```

### Protected Endpoints

```python
from fastapi import Depends
from typing import Annotated
from src.auth.models import AuthContext
from src.dependencies import get_current_user, require_role

@app.get("/me")
async def get_user(user: Annotated[AuthContext, Depends(get_current_user)]):
    return {
        "user_id": str(user.user_id),
        "tenant_id": str(user.tenant_id),
        "roles": user.roles,
    }

@app.get("/admin")
async def admin_only(user: Annotated[AuthContext, Depends(require_role("Admin"))]):
    return {"message": "Admin access"}
```

### Client-Side Usage

```python
import requests

headers = {
    "Authorization": f"Bearer {access_token}"
}

response = requests.get("https://api.example.com/me", headers=headers)
```

## Error Codes

- `MISSING_TOKEN`: No Authorization header provided
- `INVALID_TOKEN`: Token signature is invalid or malformed
- `EXPIRED_TOKEN`: Token has expired
- `MISSING_CLAIMS`: Required claims (tenant_id, roles) are missing
- `RATE_LIMIT_EXCEEDED`: Too many authentication attempts

## Rate Limiting

Authentication attempts are rate-limited to 10 per IP per minute. Failed attempts are tracked in the `auth_rate_limits` table.

## Security Notes

- JWT tokens are validated using `SUPABASE_JWT_SECRET`
- Tokens must include `tenant_id` and `roles` in `app_metadata`
- Rate limiting prevents brute force attacks
- All sensitive operations require valid authentication
