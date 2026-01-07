# How to Enable Auth0 Management API

The Management API needs to be enabled in your Auth0 tenant. Follow these steps:

## Step 1: Check Your Auth0 Plan

1. Go to https://manage.auth0.com
2. Navigate to **Settings** > **Subscription**
3. Check your current plan

**Note:** Management API is available on:
- ✅ Developer Pro plan and above
- ✅ Enterprise plans
- ❌ Free/Developer plans may have limited access

If you're on a free plan, you may need to upgrade to access the Management API.

## Step 2: Enable Management API (If Available)

1. Go to https://manage.auth0.com
2. Navigate to **Applications** > **Applications**
3. Find your Machine-to-Machine application (Client ID: `eTcYVJTcXQiLf5eAdpPzRDH6mKT9pXF0`)
4. Click on the application to open it
5. Go to the **APIs** tab
6. Look for **"Auth0 Management API"** in the dropdown list

### If "Auth0 Management API" appears in the list:

1. Select **"Auth0 Management API"** from the dropdown
2. Toggle the **"Authorize"** switch to ON
3. You'll see a list of permissions
4. Grant the following permissions:
   - ✅ `read:users`
   - ✅ `create:users`
   - ✅ `update:users`
   - ✅ `delete:users`
   - ✅ `read:connections`
   - ✅ `update:connections`
   - ✅ `read:resource_servers`
   - ✅ `create:resource_servers`
   - ✅ `update:resource_servers`
   - ✅ `read:clients`
   - ✅ `update:clients`
5. Click **"Update"** or **"Authorize"** to save

### If "Auth0 Management API" does NOT appear:

This means the Management API is not available for your tenant. You have two options:

**Option A: Upgrade Your Plan**
- Contact Auth0 support or upgrade through the Dashboard
- Management API is typically available on paid plans

**Option B: Use Manual Setup**
- Create API resources manually through the Dashboard
- Configure settings through the UI
- Use the verification scripts to check configuration

## Step 3: Verify Management API is Enabled

After enabling, run the test script:

```powershell
python scripts/test_auth0_connection.py
```

You should see:
```
[SUCCESS] Token acquired successfully
[SUCCESS] Connected to Auth0 Management API
```

## Step 4: Run Setup Script

Once Management API is enabled and working:

```powershell
python scripts/setup_auth0.py
```

This will automatically:
- Create the "CAR API" resource
- Configure scopes
- Set JWT signing to RS256
- Configure password policy

## Troubleshooting

### Error: "Service not enabled within domain"

This means Management API is not enabled. Follow Step 2 above.

### Error: "access_denied"

This usually means:
1. The client is not authorized (toggle "Authorize" in the APIs tab)
2. Required permissions are not granted
3. The client secret might be incorrect

### Management API Not Available

If Management API is not available for your tenant:
- Check your subscription plan
- Contact Auth0 support
- Use manual setup through the Dashboard (see `docs/AUTH0_SETUP.md`)

## Alternative: Manual Setup

If you cannot enable Management API, you can set up everything manually:

1. See `docs/AUTH0_SETUP.md` for step-by-step manual instructions
2. Create API resources through the Dashboard
3. Configure settings through the UI
4. Use verification scripts to test your configuration
