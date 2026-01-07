# Auth0 Setup Guide for CAR Platform

This document provides step-by-step instructions for configuring Auth0 for the CAR AI document intelligence platform.

## Prerequisites

- Auth0 account (sign up at https://auth0.com)
- Auth0 CLI installed (`npm install -g @auth0/auth0-cli`)
- Python 3.11+ environment
- Environment variables configured

## Overview

The CAR Platform requires:
1. Auth0 tenant with RS256 JWT signing
2. Database connection with password policy (8+ chars, 1 number, 1 special)
3. API resource "CAR API" with scopes: `read:documents`, `write:documents`, `admin`
4. Management API client for user operations
5. Health check endpoint verification

## Step 1: Auth0 Tenant Configuration

### 1.1 Create Auth0 Tenant

1. Sign up or log in to [Auth0 Dashboard](https://manage.auth0.com)
2. Select or create a tenant (e.g., `car-platform-dev`)
3. Note your tenant domain: `{tenant-name}.auth0.com`

### 1.2 Configure JWT Signing Algorithm

1. Navigate to **APIs** > **APIs** in the Auth0 Dashboard
2. We'll create the API in the next step, but ensure default signing algorithm is RS256
3. Go to **Settings** > **Advanced** > **OAuth**
4. Verify **JsonWebToken Signature Algorithm** is set to `RS256`

## Step 2: Create API Resource

### 2.1 Create "CAR API" Resource

1. Navigate to **APIs** > **APIs** in Auth0 Dashboard
2. Click **+ Create API**
3. Configure:
   - **Name**: `CAR API`
   - **Identifier**: `https://api.car-platform.com`
   - **Signing Algorithm**: `RS256`
4. Click **Create**

### 2.2 Configure API Scopes

1. In the API you just created, go to **Scopes** tab
2. Add the following scopes:
   - `read:documents` - Read document data
   - `write:documents` - Create/update documents
   - `admin` - Administrative operations
3. Save changes

## Step 3: Database Connection Setup

### 3.1 Create Database Connection

1. Navigate to **Authentication** > **Database** > **Database Connections**
2. Click **+ Create Database Connection**
3. Select **Username-Password-Authentication** (or create custom)
4. Configure connection:
   - **Name**: `Username-Password-Authentication` (or custom name)
   - **Requires Username**: Optional (based on your needs)

### 3.2 Configure Password Policy

1. In your database connection, go to **Settings** tab
2. Scroll to **Password Policy**
3. Configure:
   - **Password Policy**: `Fair` or `Good`
   - **Minimum Length**: `8`
   - **Require Lowercase**: `true`
   - **Require Uppercase**: `false` (optional)
   - **Require Numbers**: `true`
   - **Require Symbols**: `true`
4. Save changes

**Password Policy Requirements:**
- Minimum 8 characters
- At least 1 number
- At least 1 special character

## Step 4: Management API Client Setup

### 4.1 Create Machine-to-Machine Application

1. Navigate to **Applications** > **Applications**
2. Click **+ Create Application**
3. Configure:
   - **Name**: `CAR Platform Management Client`
   - **Type**: `Machine to Machine Applications`
4. Click **Create**

### 4.2 Authorize Management API

1. In the application you just created, go to **APIs** tab
2. Find **Auth0 Management API** in the list
3. Toggle authorization to **Authorized**
4. Expand **Permissions** and grant:
   - `read:users`
   - `create:users`
   - `update:users`
   - `delete:users`
   - `read:connections`
   - `read:clients`
5. Save changes

### 4.3 Retrieve Client Credentials

1. In the application, go to **Settings** tab
2. Copy the following values:
   - **Client ID**
   - **Client Secret** (click "Show" to reveal)

**⚠️ Security Note:** Store these credentials securely. Never commit them to version control.

## Step 5: Environment Configuration

### 5.1 Create `.env` File

Create a `.env` file in your project root:

```bash
# Auth0 Domain
AUTH0_DOMAIN=your-tenant.auth0.com

# API Configuration
AUTH0_API_IDENTIFIER=https://api.car-platform.com
AUTH0_API_NAME=CAR API
AUTH0_ALGORITHM=RS256

# Management API Credentials
AUTH0_MANAGEMENT_CLIENT_ID=your-management-client-id
AUTH0_MANAGEMENT_CLIENT_SECRET=your-management-client-secret

# Database Connection
AUTH0_DATABASE_CONNECTION_NAME=Username-Password-Authentication

# Retry Configuration (optional)
AUTH0_MAX_RETRIES=3
AUTH0_BASE_DELAY=1.0
```

### 5.2 Export Environment Variables (Alternative)

```bash
export AUTH0_DOMAIN=your-tenant.auth0.com
export AUTH0_API_IDENTIFIER=https://api.car-platform.com
export AUTH0_MANAGEMENT_CLIENT_ID=your-management-client-id
export AUTH0_MANAGEMENT_CLIENT_SECRET=your-management-client-secret
export AUTH0_DATABASE_CONNECTION_NAME=Username-Password-Authentication
```

## Step 6: Automated Setup (Optional)

If you have Auth0 CLI configured, you can use the setup script:

```bash
# Install Auth0 CLI
npm install -g @auth0/auth0-cli

# Login to Auth0
auth0 login

# Run setup script
chmod +x infrastructure/auth0/setup.sh
./infrastructure/auth0/setup.sh
```

**Note:** The script requires manual creation of the Management API client via Dashboard.

## Step 7: Verify Configuration

### 7.1 Test Health Check Endpoint

Start your FastAPI application:

```bash
uvicorn main:app --reload
```

Test the health check:

```bash
# Basic health check
curl http://localhost:8000/health

# Detailed health check
curl http://localhost:8000/health/detailed
```

Expected response (healthy):
```json
{
  "status": "healthy",
  "auth0_connected": true,
  "auth0_domain": "your-tenant.auth0.com",
  "message": "Auth0 connectivity verified"
}
```

### 7.2 Test Management API Client

You can test the Management API client programmatically:

```python
from src.auth.auth0_client import Auth0ManagementClient

client = Auth0ManagementClient()
is_connected = client.verify_connectivity()
print(f"Auth0 connected: {is_connected}")
```

## Troubleshooting

### Common Issues

1. **Token Acquisition Fails**
   - Verify `AUTH0_MANAGEMENT_CLIENT_ID` and `AUTH0_MANAGEMENT_CLIENT_SECRET` are correct
   - Ensure Management API client is authorized for Auth0 Management API
   - Check that required permissions are granted

2. **Health Check Returns "degraded"**
   - Verify network connectivity to Auth0
   - Check Auth0 tenant status at https://status.auth0.com
   - Review application logs for detailed error messages

3. **JWT Validation Fails**
   - Ensure API resource uses RS256 algorithm
   - Verify `AUTH0_API_IDENTIFIER` matches the API identifier in Auth0
   - Check JWKS URI is accessible: `https://{domain}/.well-known/jwks.json`

4. **Password Policy Not Enforced**
   - Verify password policy settings in database connection
   - Check that connection is enabled for your application
   - Test password creation via Management API

### Debug Mode

Enable debug logging:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

## Security Best Practices

1. **Secrets Management**
   - Never commit `.env` files to version control
   - Use secret management services (AWS Secrets Manager, Azure Key Vault, etc.) in production
   - Rotate Management API credentials regularly

2. **Token Handling**
   - Tokens are automatically cached and refreshed by `Auth0ManagementClient`
   - Tokens expire after 24 hours (default)
   - Failed token refresh triggers retry logic

3. **Network Security**
   - Use HTTPS in production
   - Implement rate limiting on health check endpoints
   - Monitor Auth0 API usage for anomalies

## Next Steps

After completing Auth0 setup:

1. Integrate JWT validation in your FastAPI application
2. Implement role-based access control (RBAC) using scopes
3. Set up user registration and login flows
4. Configure additional Auth0 features as needed (MFA, social logins, etc.)

## References

- [Auth0 Documentation](https://auth0.com/docs)
- [Auth0 Management API](https://auth0.com/docs/api/management/v2)
- [FastAPI Security](https://fastapi.tiangolo.com/tutorial/security/)
- [python-jose Documentation](https://python-jose.readthedocs.io/)
