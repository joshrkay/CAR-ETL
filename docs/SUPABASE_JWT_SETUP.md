# Supabase JWT Configuration

## Overview

The CAR Platform supports both Auth0 (RS256) and Supabase (ES256) for JWT authentication. This document explains how to configure the platform to use Supabase for JWT validation.

## Supabase JWKS Endpoint

Supabase provides JWKS (JSON Web Key Set) at:
```
https://{project-ref}.supabase.co/auth/v1/.well-known/jwks.json
```

For your project: `https://qifioafprrtkoiyylsqa.supabase.co/auth/v1/.well-known/jwks.json`

## Key Differences

| Feature | Auth0 | Supabase |
|---------|-------|----------|
| Algorithm | RS256 (RSA) | ES256 (Elliptic Curve) |
| JWKS URI | `https://{domain}/.well-known/jwks.json` | `https://{project-ref}.supabase.co/auth/v1/.well-known/jwks.json` |
| Key Type | RSA Public Key | EC (Elliptic Curve) Public Key |

## Configuration

### Environment Variables

Set the following environment variables to use Supabase:

```bash
# Supabase Configuration
AUTH0_DOMAIN=qifioafprrtkoiyylsqa.supabase.co
AUTH0_ALGORITHM=ES256
AUTH0_JWKS_URI=https://qifioafprrtkoiyylsqa.supabase.co/auth/v1/.well-known/jwks.json
AUTH0_API_IDENTIFIER=your-api-identifier

# Optional: If using Supabase for management operations
AUTH0_MANAGEMENT_CLIENT_ID=your-supabase-service-role-key
AUTH0_MANAGEMENT_CLIENT_SECRET=your-supabase-service-role-key
AUTH0_DATABASE_CONNECTION_NAME=supabase
```

### Automatic Detection

The configuration automatically detects Supabase if:
- The domain contains `supabase.co`
- The JWKS URI is not explicitly set

It will automatically:
- Set algorithm to ES256 (if not specified)
- Generate the correct Supabase JWKS URI format

## JWT Claims

Supabase JWTs should include the following custom claims:

- `https://car.platform/tenant_id` - Tenant identifier (UUID)
- `https://car.platform/roles` - Array of role strings (e.g., `["admin", "analyst"]`)

## Testing

### Verify JWKS Endpoint

```bash
curl https://qifioafprrtkoiyylsqa.supabase.co/auth/v1/.well-known/jwks.json
```

Expected response:
```json
{
  "keys": [
    {
      "alg": "ES256",
      "crv": "P-256",
      "ext": true,
      "key_ops": ["verify"],
      "kid": "73d2ca18-b5ba-4472-abb8-4ee5cd92b249",
      "kty": "EC",
      "use": "sig",
      "x": "7f05eYqeFrEE2UaEBS8D7qGKksGJgdJNoYOaH4hJJx0",
      "y": "5DE4qV9SZSzDbSBH5H05t2Q5aFeEY64n1XKBlULHcnQ"
    }
  ]
}
```

### Test JWT Validation

```python
from src.auth.jwt_validator import JWTValidator, get_jwt_validator

# Get validator (will use Supabase config if environment is set)
validator = get_jwt_validator()

# Validate a Supabase JWT token
claims = validator.extract_claims("your-supabase-jwt-token")
print(f"Tenant ID: {claims.tenant_id}")
print(f"Roles: {claims.roles}")
```

## Migration from Auth0 to Supabase

1. **Update Environment Variables:**
   ```bash
   AUTH0_DOMAIN=qifioafprrtkoiyylsqa.supabase.co
   AUTH0_ALGORITHM=ES256
   AUTH0_JWKS_URI=https://qifioafprrtkoiyylsqa.supabase.co/auth/v1/.well-known/jwks.json
   ```

2. **Restart API Server:**
   ```bash
   # Server will automatically use new configuration
   python -m uvicorn src.api.main:app --reload
   ```

3. **Verify:**
   - Test JWT validation with a Supabase token
   - Check logs for successful JWKS fetch
   - Verify claims extraction works correctly

## Troubleshooting

### Error: "Algorithm must be one of: RS256, ES256"
- Ensure `AUTH0_ALGORITHM=ES256` is set

### Error: "JWKS fetch failed"
- Verify `AUTH0_JWKS_URI` is correct
- Check network connectivity to Supabase
- Verify the JWKS endpoint is accessible

### Error: "Key with kid '...' not found in JWKS"
- The token's key ID doesn't match any key in the JWKS
- Verify the token is from the correct Supabase project
- Check if Supabase has rotated keys

## References

- [Supabase Auth Documentation](https://supabase.com/docs/guides/auth)
- [JWT.io](https://jwt.io/) - For token inspection
- [Supabase JWKS Endpoint](https://qifioafprrtkoiyylsqa.supabase.co/auth/v1/.well-known/jwks.json)
