# Auth0 Certificate Information

## Extracted Domain

From the provided Auth0 certificate, the following domain was extracted:

**Domain:** `dev-khx88c3lu7wz2dxx.us.auth0.com`

## Certificate Details

- **Subject CN:** dev-khx88c3lu7wz2dxx.us.auth0.com
- **Issuer CN:** dev-khx88c3lu7wz2dxx.us.auth0.com
- **Valid From:** 2026-01-07T01:28:43+00:00
- **Valid Until:** 2039-09-16T01:28:43+00:00
- **Serial Number:** 923959909286190914906
- **Fingerprint:** 0942dc565041e25c574c75cbff70044cef21e65c46f1a949692471d58d97e3ed

## Environment Configuration

Use the following in your `.env` file:

```bash
AUTH0_DOMAIN=dev-khx88c3lu7wz2dxx.us.auth0.com
AUTH0_API_IDENTIFIER=https://api.car-platform.com
AUTH0_MANAGEMENT_CLIENT_ID=your-management-client-id
AUTH0_MANAGEMENT_CLIENT_SECRET=your-management-client-secret
AUTH0_DATABASE_CONNECTION_NAME=Username-Password-Authentication
```

## Auth0 Endpoints

Based on the extracted domain:

- **JWKS Endpoint:** `https://dev-khx88c3lu7wz2dxx.us.auth0.com/.well-known/jwks.json`
- **Token Endpoint:** `https://dev-khx88c3lu7wz2dxx.us.auth0.com/oauth/token`
- **Management API:** `https://dev-khx88c3lu7wz2dxx.us.auth0.com/api/v2`
- **Authorization Endpoint:** `https://dev-khx88c3lu7wz2dxx.us.auth0.com/authorize`

## Testing

You can test the certificate parsing with:

```bash
python scripts/test_certificate_standalone.py
```

You can test JWT generation and validation with:

```bash
python scripts/test_jwt_manual.py
```

Make sure to set the environment variables first!
