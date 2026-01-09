# SharePoint Connector Setup Guide

## Environment Variables

Add these to your `.env` file:

```bash
# SharePoint OAuth Configuration
SHAREPOINT_CLIENT_ID=your-client-id-here
SHAREPOINT_CLIENT_SECRET=your-client-secret-here
SHAREPOINT_REDIRECT_URI=http://localhost:8000/oauth/microsoft/callback

# Encryption Key (for OAuth token encryption)
# Generate a new key with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
ENCRYPTION_KEY=your-encryption-key-here
```

## Azure AD App Registration

1. **Redirect URI**: Must match exactly `http://localhost:8000/oauth/microsoft/callback`
2. **API Permissions**: 
   - `Files.Read.All` (Application or Delegated)
   - `Sites.Read.All` (Application or Delegated)
   - `offline_access` (for refresh tokens)

## Database Migration

Run the migration to create the connectors table:

```bash
# Apply migration 025_connectors.sql
# This creates:
# - connectors table (with RLS)
# - oauth_states table (for OAuth state validation)
```

## API Endpoints

### 1. Start OAuth Flow
```http
POST /api/v1/connectors/sharepoint/auth
Authorization: Bearer <your-jwt-token>
```

Response:
```json
{
  "authorization_url": "https://login.microsoftonline.com/...",
  "state": "<state-uuid>"
}
```

### 2. OAuth Callback (Public)
```http
GET /oauth/microsoft/callback?code=<auth-code>&state=<state>
```

This endpoint is public (no auth required) and validates the state parameter to retrieve tenant_id.

### 3. List SharePoint Sites
```http
POST /api/v1/connectors/sharepoint/sites
Authorization: Bearer <your-jwt-token>
```

### 4. List Document Libraries
```http
POST /api/v1/connectors/sharepoint/drives?site_id=<site-id>
Authorization: Bearer <your-jwt-token>
```

### 5. Configure Sync Target
```http
POST /api/v1/connectors/sharepoint/configure
Authorization: Bearer <your-jwt-token>
Content-Type: application/json

{
  "site_id": "<site-id>",
  "drive_id": "<drive-id>",
  "folder_path": "/"
}
```

### 6. Trigger Sync
```http
POST /api/v1/connectors/sharepoint/sync
Authorization: Bearer <your-jwt-token>
```

## Security Notes

- OAuth tokens are encrypted before storage using Fernet symmetric encryption
- State parameter is validated to prevent CSRF attacks
- Tenant isolation is enforced via RLS policies
- No PII is logged (only IDs and metadata)

## Testing

1. Start the server: `uvicorn src.main:app --reload`
2. Call `/api/v1/connectors/sharepoint/auth` to get authorization URL
3. Redirect user to authorization URL
4. User completes OAuth flow
5. Microsoft redirects to `/oauth/microsoft/callback`
6. Callback validates state and stores encrypted tokens
7. Use other endpoints to list sites/drives and configure sync
