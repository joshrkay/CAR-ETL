# Tenant Provisioning API Usage Guide

## Overview

The Tenant Provisioning API allows administrators to create new tenants with automatic setup of storage buckets and admin users.

## Prerequisites

1. **Admin Role**: You must have the `Admin` role in an existing tenant
2. **Authentication**: Valid JWT token with Admin role
3. **Environment Variables**: Configured Supabase credentials

## API Endpoint

**POST** `/api/v1/admin/tenants`

### Request Headers

```
Authorization: Bearer <your_jwt_token>
Content-Type: application/json
```

### Request Body

```json
{
  "name": "Acme Corporation",
  "slug": "acme-corp",
  "admin_email": "admin@acme.com",
  "environment": "prod"
}
```

### Field Descriptions

- **name** (required): Tenant name, 2-100 characters
- **slug** (required): URL-safe identifier, lowercase alphanumeric with hyphens
  - Pattern: `^[a-z0-9][a-z0-9-]*[a-z0-9]$`
  - Must be unique
- **admin_email** (required): Email address for the tenant admin user
  - Must be valid email format
  - User will be created if doesn't exist
- **environment** (optional): Environment type
  - Options: `prod`, `staging`, `dev`
  - Default: `prod`

### Response (201 Created)

```json
{
  "tenant_id": "550e8400-e29b-41d4-a716-446655440000",
  "name": "Acme Corporation",
  "slug": "acme-corp",
  "status": "active",
  "storage_bucket": "documents-550e8400-e29b-41d4-a716-446655440000",
  "admin_invite_sent": true,
  "created_at": "2026-01-08T12:00:00Z"
}
```

## Usage Examples

### Python (FastAPI TestClient)

```python
from fastapi.testclient import TestClient
from src.main import app
import jwt
from datetime import datetime, timedelta

# Create admin JWT token
config = get_auth_config()
payload = {
    "sub": "admin-user-id",
    "email": "admin@example.com",
    "app_metadata": {
        "tenant_id": "your-tenant-id",
        "roles": ["Admin"],
        "tenant_slug": "your-tenant-slug",
    },
    "exp": datetime.utcnow() + timedelta(hours=1),
}
token = jwt.encode(payload, config.supabase_jwt_secret, algorithm="HS256")

# Make request
client = TestClient(app)
response = client.post(
    "/api/v1/admin/tenants",
    json={
        "name": "Acme Corporation",
        "slug": "acme-corp",
        "admin_email": "admin@acme.com",
        "environment": "prod",
    },
    headers={"Authorization": f"Bearer {token}"},
)

if response.status_code == 201:
    tenant = response.json()
    print(f"Created tenant: {tenant['tenant_id']}")
```

### cURL

```bash
curl -X POST http://localhost:8000/api/v1/admin/tenants \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Acme Corporation",
    "slug": "acme-corp",
    "admin_email": "admin@acme.com",
    "environment": "prod"
  }'
```

### JavaScript/TypeScript (Fetch API)

```javascript
const response = await fetch('http://localhost:8000/api/v1/admin/tenants', {
  method: 'POST',
  headers: {
    'Authorization': `Bearer ${jwtToken}`,
    'Content-Type': 'application/json',
  },
  body: JSON.stringify({
    name: 'Acme Corporation',
    slug: 'acme-corp',
    admin_email: 'admin@acme.com',
    environment: 'prod',
  }),
});

if (response.ok) {
  const tenant = await response.json();
  console.log('Created tenant:', tenant.tenant_id);
}
```

## Error Responses

### 400 Bad Request - Duplicate Slug

```json
{
  "detail": {
    "code": "PROVISIONING_ERROR",
    "message": "Tenant with slug 'acme-corp' already exists"
  }
}
```

### 400 Bad Request - User Already Exists

```json
{
  "detail": {
    "code": "PROVISIONING_ERROR",
    "message": "User admin@acme.com already exists. Use invite_user API or provide user_id for existing users."
  }
}
```

### 400 Bad Request - Storage Bucket Creation Failed

```json
{
  "detail": {
    "code": "PROVISIONING_ERROR",
    "message": "Failed to create storage bucket: {error details}"
  }
}
```

### 401 Unauthorized

```json
{
  "detail": {
    "code": "NOT_AUTHENTICATED",
    "message": "User is not authenticated"
  }
}
```

### 403 Forbidden

```json
{
  "detail": {
    "code": "INSUFFICIENT_PERMISSIONS",
    "message": "Role 'Admin' is required"
  }
}
```

## What Gets Created

When you provision a tenant, the following resources are automatically created:

1. **Tenant Record**: Row in `public.tenants` table
2. **Storage Bucket**: `documents-{tenant_id}` bucket in Supabase Storage
3. **Admin User**: User account in Supabase Auth (if doesn't exist)
4. **Tenant-User Link**: Row in `public.tenant_users` linking admin to tenant

## Rollback Behavior

If any step fails during provisioning, the system automatically rolls back:

- Deletes tenant_users row (if created)
- Deletes storage bucket (if created)
- Deletes tenant row (if created)

This ensures no orphaned resources are left behind.

## Storage Bucket Access

After provisioning, tenants can access their storage bucket using:

```python
from supabase import create_client

supabase = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)
bucket_name = f"documents-{tenant_id}"

# Upload file
supabase.storage.from_(bucket_name).upload("file.pdf", file_data)

# List files
files = supabase.storage.from_(bucket_name).list()

# Download file
file_data = supabase.storage.from_(bucket_name).download("file.pdf")
```

The RLS policies ensure tenants can only access their own bucket.

## Testing

Run the test script:

```bash
# PowerShell
.\scripts\run_provisioning_test.ps1

# Python
python scripts/test_tenant_provisioning.py
```

## Best Practices

1. **Slug Naming**: Use descriptive, URL-safe slugs (e.g., `acme-corp`, `acme-staging`)
2. **Email Validation**: Ensure admin email is valid and accessible
3. **Environment**: Use appropriate environment (`prod`, `staging`, `dev`)
4. **Error Handling**: Always check response status and handle errors appropriately
5. **Cleanup**: Consider cleanup of test tenants after testing

## Security Notes

- Only users with `Admin` role can provision tenants
- Service role is used internally for tenant creation (bypasses RLS)
- Storage buckets are private by default
- RLS policies enforce tenant isolation at the database level
