# Getting a Supabase JWT Token for Testing

## Method 1: Using the Script

```bash
# Set your Supabase credentials
$env:SUPABASE_URL = "https://qifioafprrtkoiyylsqa.supabase.co"
$env:SUPABASE_ANON_KEY = "your-anon-key"

# Get token by signing in
python scripts/get_supabase_token.py your-email@example.com your-password
```

## Method 2: Using Supabase Client Library

```python
from supabase import create_client, Client

url = "https://qifioafprrtkoiyylsqa.supabase.co"
key = "your-anon-key"

supabase: Client = create_client(url, key)

# Sign in
response = supabase.auth.sign_in_with_password({
    "email": "your-email@example.com",
    "password": "your-password"
})

token = response.session.access_token
print(f"Token: {token}")
```

## Method 3: Using Supabase REST API Directly

```bash
curl -X POST "https://qifioafprrtkoiyylsqa.supabase.co/auth/v1/token?grant_type=password" \
  -H "apikey: your-anon-key" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "your-email@example.com",
    "password": "your-password"
  }'
```

## Method 4: Using Service Role Key (Admin Token)

For testing with admin privileges, you can create a service role token:

```python
import jwt
from datetime import datetime, timedelta

# Service role key from Supabase Dashboard > Settings > API
service_role_key = "your-service-role-key"

# Create a token with custom claims
payload = {
    "sub": "service-role",
    "email": "admin@example.com",
    "https://car.platform/tenant_id": "your-tenant-id",
    "https://car.platform/roles": ["admin"],
    "iat": datetime.utcnow(),
    "exp": datetime.utcnow() + timedelta(hours=24)
}

# Note: This requires the Supabase JWT secret, not the service role key
# For proper token creation, use Supabase's token generation
```

## Getting Your Supabase Keys

1. **Go to Supabase Dashboard**: https://supabase.com/dashboard
2. **Select your project**: `qifioafprrtkoiyylsqa`
3. **Navigate to**: Settings > API
4. **Copy the keys**:
   - **anon/public key**: For client-side authentication
   - **service_role key**: For server-side admin operations (keep secret!)

## Adding Custom Claims to Tokens

Supabase tokens need custom claims for the CAR Platform:

- `https://car.platform/tenant_id`: Tenant UUID
- `https://car.platform/roles`: Array of role strings (e.g., `["admin", "analyst"]`)

You can add these via:
1. **Supabase Database Functions**: Create a function that adds claims
2. **Supabase Auth Hooks**: Use Postgres functions to modify tokens
3. **Manual Token Creation**: Sign tokens with custom claims (requires JWT secret)

## Testing the Token

Once you have a token:

```bash
# Test validation
python scripts/test_supabase_jwt_validation.py <your-token>
```

Or test via API:

```bash
curl -X GET "http://localhost:8000/api/v1/service-accounts/tokens" \
  -H "Authorization: Bearer <your-token>"
```

## Troubleshooting

### "Invalid or expired token"
- Check token hasn't expired
- Verify token is from the correct Supabase project
- Ensure algorithm is set to ES256

### "Missing tenant_id in token claims"
- Token needs custom claim: `https://car.platform/tenant_id`
- Add via Supabase Auth hooks or database functions

### "Missing roles in token claims"
- Token needs custom claim: `https://car.platform/roles`
- Should be an array: `["admin"]` or `["analyst", "viewer"]`
