# Service Account API Tokens

## Overview

Service account tokens allow tenant developers to generate long-lived API tokens for automating document ingestion via scripts. Tokens are scoped to specific tenants and include limited roles (typically 'Analyst' or 'Ingestion').

## Implementation Status

✅ **Completed:**
- Database migration for `service_account_tokens` table
- Token generation service
- API endpoints for token management (create, list, revoke)
- Token metadata tracking (name, created_at, last_used, created_by)
- Admin endpoints for viewing and revoking tokens
- Revoked token checking in JWT validation
- Last used timestamp tracking

⚠️ **Note on OAuth Client Credentials Flow:**
The current implementation generates secure random tokens that are stored and validated directly. Full OAuth Client Credentials flow integration with Auth0 can be added as an enhancement. The current approach:
- Generates secure tokens using `secrets.token_urlsafe(32)`
- Stores token hashes in database for revocation checking
- Validates tokens by checking database on each request
- Immediately fails authentication for revoked tokens

## Database Schema

### `service_account_tokens` Table

```sql
CREATE TABLE control_plane.service_account_tokens (
    token_id UUID PRIMARY KEY,
    tenant_id UUID NOT NULL REFERENCES control_plane.tenants(tenant_id) ON DELETE CASCADE,
    token_hash VARCHAR(255) NOT NULL UNIQUE,
    name VARCHAR(255) NOT NULL,
    role VARCHAR(50) NOT NULL,
    created_by VARCHAR(255) NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_used TIMESTAMP,
    revoked_at TIMESTAMP,
    is_revoked BOOLEAN NOT NULL DEFAULT FALSE
);
```

**Indexes:**
- `idx_service_account_tokens_tenant_id` - On `tenant_id`
- `idx_service_account_tokens_token_hash` - On `token_hash` (unique)
- `idx_service_account_tokens_is_revoked` - On `is_revoked`
- `idx_service_account_tokens_created_at` - On `created_at`

## API Endpoints

### Create Token

**POST** `/api/v1/service-accounts/tokens`

**Authentication:** Admin role required

**Request Body:**
```json
{
  "name": "Document Ingestion Script",
  "role": "analyst"
}
```

**Response (201 Created):**
```json
{
  "token_id": "550e8400-e29b-41d4-a716-446655440000",
  "token": "secure-random-token-here",
  "name": "Document Ingestion Script",
  "role": "analyst",
  "tenant_id": "tenant-uuid",
  "created_at": "2024-01-15T10:00:00Z"
}
```

**Note:** The plain text token is only shown once. Store it securely.

### List Tokens

**GET** `/api/v1/service-accounts/tokens`

**Authentication:** Admin role required

**Response (200 OK):**
```json
[
  {
    "token_id": "550e8400-e29b-41d4-a716-446655440000",
    "name": "Document Ingestion Script",
    "role": "analyst",
    "created_by": "user-id",
    "created_at": "2024-01-15T10:00:00Z",
    "last_used": "2024-01-15T12:30:00Z",
    "is_revoked": false,
    "revoked_at": null
  }
]
```

### Revoke Token

**DELETE** `/api/v1/service-accounts/tokens/{token_id}`

**Authentication:** Admin role required

**Response (204 No Content):** Token is immediately revoked.

## Token Validation

Service account tokens are validated during JWT validation:

1. Token is extracted from `Authorization: Bearer <token>` header
2. Token hash is computed and checked against database
3. If token is found and not revoked:
   - Token is valid
   - `last_used` timestamp is updated
4. If token is revoked:
   - Authentication fails immediately with 401 Unauthorized
5. If token is not found:
   - Treated as regular Auth0 JWT token (continues normal validation)

## Roles

Service account tokens can be assigned the following roles:

- **admin** - Full access (same as Admin role)
- **analyst** - Read/write documents, override AI decisions
- **viewer** - Read-only access
- **ingestion** - Document upload only (new role for service accounts)

## Security Considerations

1. **Token Storage:** Tokens are hashed (SHA-256) before storage. Plain text tokens are never stored.

2. **Revocation:** Revoked tokens immediately fail authentication. No grace period.

3. **Last Used Tracking:** `last_used` timestamp is updated on each successful authentication.

4. **Tenant Isolation:** Tokens are scoped to specific tenants. Cross-tenant access is prevented.

5. **Role Limitation:** Service account tokens are limited to specific roles (typically 'analyst' or 'ingestion').

## Usage Example

### Creating a Token

```bash
curl -X POST https://api.car-platform.com/api/v1/service-accounts/tokens \
  -H "Authorization: Bearer <admin-token>" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Document Ingestion Script",
    "role": "analyst"
  }'
```

### Using a Token

```bash
curl -X POST https://api.car-platform.com/api/v1/documents \
  -H "Authorization: Bearer <service-account-token>" \
  -H "Content-Type: application/json" \
  -d '{
    "document": "..."
  }'
```

### Revoking a Token

```bash
curl -X DELETE https://api.car-platform.com/api/v1/service-accounts/tokens/{token_id} \
  -H "Authorization: Bearer <admin-token>"
```

## Future Enhancements

1. **Full OAuth Client Credentials Integration:**
   - Create Auth0 Machine-to-Machine applications for each service account
   - Use Auth0 tokens with custom claims (tenant_id, role)
   - Store client_id mapping for revocation

2. **Token Expiration:**
   - Add expiration date to tokens
   - Automatic cleanup of expired tokens

3. **Token Rotation:**
   - Support for token rotation without service interruption
   - Grace period for old tokens during rotation

4. **Usage Analytics:**
   - Track token usage patterns
   - Alert on unusual activity

## Migration

Run the database migration:

```bash
alembic upgrade head
```

This will create the `service_account_tokens` table in the `control_plane` schema.
