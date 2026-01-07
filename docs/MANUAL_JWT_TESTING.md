# Manual JWT Testing Guide

This guide shows how to manually test JWT generation and validation for the CAR API.

## Prerequisites

1. **CAR API Resource** must exist in Auth0
   - Name: "CAR API"
   - Identifier: `https://api.car-platform.com`
   - Signing Algorithm: RS256

2. **Machine-to-Machine Application** configured for CAR API
   - Client ID and Secret
   - Authorized for "CAR API" (not Management API)
   - Granted scopes: `read:documents`, `write:documents`, `admin`

## Step 1: Get a JWT Token

### Using curl

```bash
curl -X POST https://dev-khx88c3lu7wz2dxx.us.auth0.com/oauth/token \
  -H 'Content-Type: application/json' \
  -d '{
    "client_id": "YOUR_API_CLIENT_ID",
    "client_secret": "YOUR_API_CLIENT_SECRET",
    "audience": "https://api.car-platform.com",
    "grant_type": "client_credentials"
  }'
```

### Using PowerShell

```powershell
$body = @{
    client_id = "YOUR_API_CLIENT_ID"
    client_secret = "YOUR_API_CLIENT_SECRET"
    audience = "https://api.car-platform.com"
    grant_type = "client_credentials"
} | ConvertTo-Json

Invoke-RestMethod -Uri "https://dev-khx88c3lu7wz2dxx.us.auth0.com/oauth/token" `
  -Method Post `
  -ContentType "application/json" `
  -Body $body
```

### Expected Response

```json
{
  "access_token": "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "Bearer",
  "expires_in": 86400
}
```

## Step 2: Inspect the Token

### Using jwt.io

1. Go to https://jwt.io
2. Paste your `access_token` in the "Encoded" section
3. The token will be automatically decoded
4. Verify:
   - **Algorithm**: RS256
   - **Audience (aud)**: `https://api.car-platform.com`
   - **Issuer (iss)**: `https://dev-khx88c3lu7wz2dxx.us.auth0.com/`
   - **Scopes**: Should include `read:documents`, `write:documents`, `admin`

### Using Python

```python
import json
from jose.utils import base64url_decode

token = "YOUR_TOKEN_HERE"
parts = token.split(".")

# Decode header
header = json.loads(base64url_decode(parts[0]).decode("utf-8"))
print("Header:", json.dumps(header, indent=2))

# Decode payload
payload = json.loads(base64url_decode(parts[1]).decode("utf-8"))
print("Payload:", json.dumps(payload, indent=2))
```

## Step 3: Verify JWKS Endpoint

### Using curl

```bash
curl https://dev-khx88c3lu7wz2dxx.us.auth0.com/.well-known/jwks.json
```

### Expected Response

```json
{
  "keys": [
    {
      "kty": "RSA",
      "use": "sig",
      "kid": "...",
      "n": "...",
      "e": "AQAB",
      "alg": "RS256"
    }
  ]
}
```

### Verify Key Properties

- `kty`: Should be "RSA"
- `alg`: Should be "RS256"
- `use`: Should be "sig" (signature)
- `kid`: Key ID (used to match token's key)

## Step 4: Verify Token Signature

### Using Python

```python
from jose import jwt, jwk
import httpx

# Get token (from Step 1)
token = "YOUR_TOKEN_HERE"

# Get JWKS
jwks_uri = "https://dev-khx88c3lu7wz2dxx.us.auth0.com/.well-known/jwks.json"
jwks = httpx.get(jwks_uri).json()

# Get key ID from token header
header = jwt.get_unverified_header(token)
kid = header["kid"]

# Find the key
key = next(k for k in jwks["keys"] if k["kid"] == kid)

# Construct public key
public_key = jwk.construct(key)

# Verify token
payload = jwt.decode(
    token,
    public_key,
    algorithms=["RS256"],
    audience="https://api.car-platform.com"
)

print("Token verified!")
print("Claims:", payload)
```

### Using the Test Script

If you have API client credentials set:

```powershell
$env:AUTH0_API_CLIENT_ID="your-api-client-id"
$env:AUTH0_API_CLIENT_SECRET="your-api-client-secret"
python scripts/test_jwt_api_resource.py
```

## Step 5: Test Token in API Request

Once you have a verified token, test it in an API request:

```bash
curl -X GET https://your-api-endpoint/api/documents \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

## Common Issues

### Error: "invalid_client"

- **Cause**: Client ID or Secret is incorrect
- **Fix**: Verify credentials in Auth0 Dashboard

### Error: "access_denied"

- **Cause**: Client is not authorized for the API resource
- **Fix**: 
  1. Go to Applications > Your Application
  2. APIs tab
  3. Select "CAR API"
  4. Toggle "Authorize" ON
  5. Grant required scopes

### Error: "invalid_audience"

- **Cause**: API resource doesn't exist or identifier is wrong
- **Fix**: Verify API resource exists with identifier `https://api.car-platform.com`

### Token Verification Fails

- **Cause**: Token signature doesn't match JWKS
- **Fix**: 
  - Verify JWKS endpoint is accessible
  - Check that token's `kid` matches a key in JWKS
  - Ensure RS256 algorithm is used

## Quick Test Checklist

- [ ] CAR API resource exists in Auth0
- [ ] Machine-to-Machine application created
- [ ] Application authorized for CAR API
- [ ] Scopes granted: read:documents, write:documents, admin
- [ ] Token obtained successfully
- [ ] Token decodes correctly (jwt.io)
- [ ] JWKS endpoint accessible
- [ ] Token signature verifies with JWKS
- [ ] Token audience matches API identifier
- [ ] Token scopes are correct

## Next Steps

After manual testing:
1. Integrate JWT validation into your FastAPI application
2. Use the health check endpoint to verify connectivity
3. Implement protected routes with JWT validation
