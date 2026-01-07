# Real Login Flow Test Instructions

## Current Status

✅ **Database migrations applied:**
- `custom_access_token_hook` function created
- `tenants` table created
- `tenant_users` table created
- RLS policies configured

⚠️ **PostgREST Schema Cache Issue:**
The tables exist in the database, but PostgREST's schema cache needs to be refreshed before the test can run.

## How to Fix and Run the Test

### Step 1: Refresh PostgREST Schema Cache

**Option A: Via Dashboard (Recommended)**
1. Go to: https://supabase.com/dashboard/project/ueqzwqejpjmsspfiypgb/settings/api
2. Look for "Reload Schema" or "Refresh Schema" button
3. Click it to refresh the PostgREST schema cache

**Option B: Wait**
- PostgREST automatically refreshes its cache every few minutes
- Wait 2-5 minutes and try again

**Option C: Restart Project**
- In Supabase Dashboard → Settings → General
- Restart the project (this will refresh all caches)

### Step 2: Verify Tables Exist

Run this SQL in the Supabase SQL Editor:
```sql
SELECT table_name 
FROM information_schema.tables 
WHERE table_schema = 'public' 
  AND table_name IN ('tenants', 'tenant_users');
```

You should see both tables listed.

### Step 3: Run the Test

```powershell
.\run_login_test.ps1
```

Or manually:
```powershell
$env:SUPABASE_URL = "https://ueqzwqejpjmsspfiypgb.supabase.co"
$env:SUPABASE_ANON_KEY = "your-anon-key"
$env:SUPABASE_SERVICE_KEY = "your-service-key"
$env:SUPABASE_JWT_SECRET = "your-jwt-secret"
python tests/test_real_login.py
```

## What the Test Does

1. ✅ Creates a test tenant in the `tenants` table
2. ✅ Creates a test user in Supabase Auth
3. ✅ Links the user to the tenant in `tenant_users` table
4. ✅ Signs in to get a JWT token
5. ✅ Verifies the JWT contains custom claims:
   - `app_metadata.tenant_id`
   - `app_metadata.roles`
   - `app_metadata.tenant_slug`
6. ✅ Tests FastAPI middleware extraction of auth context
7. ✅ Cleans up test data

## Expected Output

When successful, you should see:
```
============================================================
Testing Real Login Flow with Supabase
============================================================

1. Setting up test tenant...
   Created new tenant: <uuid>

2. Creating test user in Supabase Auth...
   Created user: <uuid>
   Email: test-xxxxx@example.com

3. Linking user to tenant...
   Linked user to tenant with roles: ['Admin', 'User']

4. Signing in to get JWT token...
   Got access token: eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...

5. Verifying JWT contains custom claims...
   User ID (sub): <uuid>
   Email: test-xxxxx@example.com
   Tenant ID in JWT: <uuid>
   Roles in JWT: ['Admin', 'User']
   Tenant Slug in JWT: test-tenant-xxxxx
   ✅ All custom claims verified!

6. Testing FastAPI middleware with real token...
   ✅ Middleware extracted auth context:
      User ID: <uuid>
      Email: test-xxxxx@example.com
      Tenant ID: <uuid>
      Roles: ['Admin', 'User']
      Tenant Slug: test-tenant-xxxxx

7. Cleaning up test data...
   Deleted tenant_user relationship
   Deleted tenant
   Deleted user

============================================================
✅ All tests passed! Login flow is working correctly.
============================================================
```

## Troubleshooting

### Error: "Could not find the table 'public.tenants'"
- **Solution**: Refresh PostgREST schema cache (see Step 1 above)

### Error: "Failed to create user"
- **Solution**: Check that you're using the `SUPABASE_SERVICE_KEY` (not anon key) for admin operations

### Error: "JWT missing custom claims"
- **Solution**: Verify the auth hook is configured in Supabase Dashboard:
  - Go to Authentication → Hooks
  - Ensure `custom_access_token_hook` is enabled for `access_token` type

### Error: "Permission denied"
- **Solution**: Check RLS policies and grants are correctly applied
