# Auth0 JWT Claims Setup Guide

This guide explains how to configure Auth0 to inject custom claims (`tenant_id` and `roles`) into JWT tokens.

## Overview

The CAR Platform requires JWT tokens to include:
- `https://car.platform/tenant_id`: Tenant identifier from user metadata
- `https://car.platform/roles`: Array of role strings from user metadata

## Prerequisites

- Auth0 account with Management API enabled
- Auth0 API resource "CAR API" configured
- RS256 algorithm configured (already set)
- Users with `app_metadata.tenant_id` and `app_metadata.roles` set

---

## Step 1: Create Auth0 Action

1. **Navigate to Auth0 Dashboard:**
   - Go to: https://manage.auth0.com
   - Select your tenant

2. **Open Actions Library:**
   - Click **Actions** → **Library** in the left sidebar
   - Click **+ Create Action**

3. **Configure Action:**
   - **Name:** `Add CAR Platform Claims`
   - **Trigger:** Select **Login / Post Login**
   - Click **Create**

4. **Add Action Code:**
   - Copy the code from `infrastructure/auth0/actions/add-car-claims.js`
   - Paste into the code editor
   - Click **Deploy**

---

## Step 2: Attach Action to Flow

1. **Navigate to Flows:**
   - Click **Actions** → **Flows** in the left sidebar
   - Select **Login** flow

2. **Add Action:**
   - Click **+** (Custom) on the right side
   - Select **Add CAR Platform Claims** action
   - Drag it between **Start** and **Complete**
   - Click **Apply**

3. **Save Flow:**
   - Click **Apply** to save the flow

---

## Step 3: Configure Token Expiration

1. **Navigate to API Settings:**
   - Click **Applications** → **APIs** in the left sidebar
   - Select **CAR API** (or your API resource)

2. **Set Token Expiration:**
   - Scroll to **Token Expiration (Seconds)**
   - Set to **3600** (1 hour)
   - Click **Save**

---

## Step 4: Configure Refresh Token

1. **Navigate to Application Settings:**
   - Click **Applications** → **Applications**
   - Select your application

2. **Enable Refresh Token:**
   - Scroll to **Advanced Settings** → **Grant Types**
   - Ensure **Refresh Token** is enabled
   - Click **Save**

3. **Set Refresh Token Rotation:**
   - In **Advanced Settings** → **Refresh Token**
   - Set **Refresh Token Rotation** to **Rotating** (recommended)
   - Set **Refresh Token Expiration** to **30 days** (or your preference)
   - Click **Save**

---

## Step 5: Set User Metadata

Users must have `app_metadata` set with `tenant_id` and `roles`:

### Using Management API:

```python
from src.auth.auth0_client import Auth0ManagementClient

client = Auth0ManagementClient()

# Update user with tenant_id and roles
client.update_user(
    user_id="auth0|...",
    updates={
        "app_metadata": {
            "tenant_id": "550e8400-e29b-41d4-a716-446655440000",
            "roles": ["admin", "user"]
        }
    }
)
```

### Using Auth0 Dashboard:

1. Navigate to **User Management** → **Users**
2. Select a user
3. Scroll to **Metadata** tab
4. Add to **App Metadata**:
   ```json
   {
     "tenant_id": "550e8400-e29b-41d4-a716-446655440000",
     "roles": ["admin", "user"]
   }
   ```
5. Click **Save**

---

## Step 6: Verify Configuration

### Test Token Generation:

```bash
python scripts/test_jwt_claims.py
```

### Expected Token Structure:

```json
{
  "sub": "auth0|...",
  "aud": "https://api.car-platform.com",
  "iat": 1234567890,
  "exp": 1234571490,
  "https://car.platform/tenant_id": "550e8400-e29b-41d4-a716-446655440000",
  "https://car.platform/roles": ["admin", "user"]
}
```

---

## Troubleshooting

### Missing Claims

**Issue:** Token doesn't include `tenant_id` or `roles`

**Solutions:**
1. Verify Action is attached to Login flow
2. Verify user has `app_metadata.tenant_id` set
3. Check Action logs in Auth0 Dashboard → **Actions** → **Logs**

### Invalid Roles Format

**Issue:** `roles` claim is not an array

**Solutions:**
1. Ensure `app_metadata.roles` is an array: `["admin"]` not `"admin"`
2. Action will default to empty array if invalid

### Token Expiration

**Issue:** Token expires too quickly

**Solutions:**
1. Verify API Token Expiration is set to 3600 seconds (1 hour)
2. Use refresh token to obtain new access token

### Refresh Token Not Working

**Issue:** Refresh token request fails

**Solutions:**
1. Verify Refresh Token grant type is enabled
2. Verify client credentials are correct
3. Check token endpoint: `https://{domain}/oauth/token`

---

## Security Considerations

1. **Custom Claim Namespace:**
   - Use `https://car.platform/` namespace to avoid conflicts
   - Follows JWT best practices for custom claims

2. **Tenant ID Validation:**
   - Action logs warning if `tenant_id` is missing
   - Consider denying authentication if required

3. **Roles Validation:**
   - Action validates roles is an array
   - Defaults to empty array if invalid

4. **Token Expiration:**
   - 1 hour expiration balances security and usability
   - Refresh tokens allow seamless re-authentication

---

## Acceptance Criteria Verification

✅ **1. Auth0 Action configured to inject tenant_id claim**
- Action code in `infrastructure/auth0/actions/add-car-claims.js`
- Claim name: `https://car.platform/tenant_id`
- Source: `user.app_metadata.tenant_id`

✅ **2. Auth0 Action configured to inject roles claim**
- Claim name: `https://car.platform/roles`
- Source: `user.app_metadata.roles`
- Format: Array of role strings

✅ **3. Tokens signed with RS256 algorithm**
- Already configured in Auth0 API settings
- Validated in `src/auth/config.py`

✅ **4. Token expiration set to 1 hour with refresh token support**
- Token expiration: 3600 seconds (1 hour)
- Refresh token enabled in application settings
- Refresh token rotation configured

---

## Next Steps

1. Deploy Action to Auth0
2. Attach Action to Login flow
3. Set user metadata for test users
4. Run verification script: `python scripts/test_jwt_claims.py`
5. Integrate JWT validation in API endpoints

---

**Status:** ✅ **READY FOR DEPLOYMENT**
