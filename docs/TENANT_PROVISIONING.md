# Tenant Provisioning API

## Overview

The tenant provisioning API creates isolated PostgreSQL databases for each tenant with full rollback support on any failure.

## Endpoint

### POST /api/v1/tenants

Creates a new tenant with an isolated database.

**Request:**
```json
{
  "name": "acme_corp",
  "environment": "production"
}
```

**Response (201 Created):**
```json
{
  "tenant_id": "550e8400-e29b-41d4-a716-446655440000",
  "name": "acme_corp",
  "status": "active"
}
```

**Rate Limit:** 10 requests per minute per IP address

## Provisioning Process

1. **Create PostgreSQL Database**
   - Database name: `car_{tenant_id}` (UUID with hyphens replaced by underscores)
   - Uses psycopg2 with admin privileges

2. **Test Database Connection**
   - Verifies connectivity before proceeding
   - Fails fast if database is unreachable

3. **Encrypt Connection String**
   - Uses AES-256-GCM encryption
   - Key from `ENCRYPTION_KEY` environment variable

4. **Create Tenant Record**
   - Inserts into `control_plane.tenants` table
   - Inserts into `control_plane.tenant_databases` table

5. **Return 201 Created**
   - Only returned after all steps complete successfully

## Rollback Scenarios

If any step fails, all changes are automatically rolled back:

- **Database creation fails:** No rollback needed (database not created)
- **Connection test fails:** Database is deleted
- **Encryption fails:** Database is deleted
- **Tenant insert fails:** Database is deleted, tenant record removed if created

## Environment Variables

### Required

- `DATABASE_URL` - PostgreSQL connection string with admin privileges
- `ENCRYPTION_KEY` - Base64-encoded 32-byte key for AES-256-GCM

### Generate Encryption Key

```bash
python scripts/generate_encryption_key.py
```

Or manually:
```python
import secrets
import base64
key = base64.urlsafe_b64encode(secrets.token_bytes(32)).decode('utf-8')
print(key)
```

## Database Permissions

The `DATABASE_URL` must have elevated permissions to:
- `CREATE DATABASE`
- `DROP DATABASE`
- Connect to `postgres` database for admin operations

## Usage Example

```python
import requests

response = requests.post(
    "http://localhost:8000/api/v1/tenants",
    json={
        "name": "acme_corp",
        "environment": "production"
    }
)

if response.status_code == 201:
    tenant = response.json()
    print(f"Tenant created: {tenant['tenant_id']}")
else:
    print(f"Error: {response.json()}")
```

## Error Responses

### 400 Bad Request
- Invalid environment value
- Empty or invalid tenant name
- Tenant name already exists

### 422 Unprocessable Entity
- Validation errors (Pydantic)

### 429 Too Many Requests
- Rate limit exceeded (10/minute)

### 500 Internal Server Error
- Database creation failed
- Connection test failed
- Encryption failed
- Database insert failed

## Security Considerations

1. **Encryption Key:** Store `ENCRYPTION_KEY` securely, never commit to version control
2. **Database Permissions:** Use least-privilege principle for database user
3. **Rate Limiting:** Prevents abuse and resource exhaustion
4. **Input Validation:** Tenant names are sanitized and validated
5. **Connection Strings:** Encrypted at rest in database

## Testing

Run integration tests:

```bash
pytest tests/test_tenant_provisioning.py -v
```

Tests cover:
- Successful provisioning
- Rollback on database creation failure
- Rollback on connection test failure
- Rollback on tenant insert failure
- Duplicate name validation
- Invalid input validation

## Files

- `src/api/routes/tenants.py` - API endpoint
- `src/services/tenant_provisioning.py` - Provisioning logic
- `src/services/encryption.py` - AES encryption
- `src/db/tenant_manager.py` - Database creation/deletion
- `tests/test_tenant_provisioning.py` - Integration tests
