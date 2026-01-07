# Quick Start - JWT Testing

## Step 1: Set Environment Variables

Based on your Auth0 certificate, your domain is: `dev-khx88c3lu7wz2dxx.us.auth0.com`

Set the following environment variables in PowerShell:

```powershell
$env:AUTH0_DOMAIN="dev-khx88c3lu7wz2dxx.us.auth0.com"
$env:AUTH0_API_IDENTIFIER="https://api.car-platform.com"
$env:AUTH0_MANAGEMENT_CLIENT_ID="your-management-client-id"
$env:AUTH0_MANAGEMENT_CLIENT_SECRET="your-management-client-secret"
$env:AUTH0_DATABASE_CONNECTION_NAME="Username-Password-Authentication"
```

Or create a `.env` file in the project root:

```bash
AUTH0_DOMAIN=dev-khx88c3lu7wz2dxx.us.auth0.com
AUTH0_API_IDENTIFIER=https://api.car-platform.com
AUTH0_MANAGEMENT_CLIENT_ID=your-management-client-id
AUTH0_MANAGEMENT_CLIENT_SECRET=your-management-client-secret
AUTH0_DATABASE_CONNECTION_NAME=Username-Password-Authentication
```

## Step 2: Get Management API Credentials

1. Go to Auth0 Dashboard: https://manage.auth0.com
2. Navigate to **Applications** > **Applications**
3. Find or create a **Machine-to-Machine** application
4. Authorize it for **Auth0 Management API**
5. Grant permissions: `read:users`, `create:users`, `update:users`, `delete:users`
6. Copy the **Client ID** and **Client Secret**

## Step 3: Run JWT Test

```powershell
python scripts/test_jwt_manual.py
```

## Expected Output

If successful, you should see:

```
============================================================
JWT Generation and Validation Test
============================================================

[SUCCESS] Configuration loaded:
   Domain: dev-khx88c3lu7wz2dxx.us.auth0.com
   API Identifier: https://api.car-platform.com
   JWKS URI: https://dev-khx88c3lu7wz2dxx.us.auth0.com/.well-known/jwks.json
   Algorithm: RS256

============================================================
Step 1: Requesting Test Token
============================================================
[INFO] Requesting token from: https://dev-khx88c3lu7wz2dxx.us.auth0.com/oauth/token
[SUCCESS] Token obtained: eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9...

[SUCCESS] Token verified successfully!
```

## Troubleshooting

- **"Field required" errors**: Make sure all environment variables are set
- **"Token request failed"**: Check that your Management API client credentials are correct
- **"Network error"**: Verify internet connectivity and Auth0 domain is correct
