# Supabase API Keys Configuration

Your Supabase API keys have been configured. These keys are used for Supabase REST API and client library access.

## Configured Keys

- **Anon Key (Publishable):** `sb_publishable_PhKpWt7-UWeydaiqe99LDg_OSnuK7a0`
- **Service Role Key (Secret):** `sb_secret_SDH3fH1Nl69oxRGNBPy91g_MhFHDYpm`
- **Project URL:** `https://qifioafprrtkoiyylsqa.supabase.co`

## Environment Variables

These keys are set as environment variables:
- `SUPABASE_ANON_KEY` - Public/anonymous key (safe for client-side)
- `SUPABASE_SERVICE_ROLE_KEY` - Secret key (server-side only, has admin access)
- `SUPABASE_URL` - Your Supabase project URL

## Important Notes

### For Database Migrations (Alembic)

**These API keys are NOT used for database migrations.** Alembic requires a direct PostgreSQL connection string.

You still need to set `DATABASE_URL` with your PostgreSQL connection string:

```powershell
$env:DATABASE_URL="postgresql://postgres:[YOUR-PASSWORD]@db.qifioafprrtkoiyylsqa.supabase.co:5432/postgres?sslmode=require"
```

Get the exact connection string from:
- https://app.supabase.com/project/qifioafprrtkoiyylsqa/settings/database
- Click "URI" tab → "Session mode" (port 5432)
- Copy the connection string

### For Supabase REST API / Client Library

These keys ARE used for:
- Supabase REST API calls
- Supabase client library (Python, JavaScript, etc.)
- Authentication and authorization
- Row Level Security (RLS) policies

## Using the Keys

### Python (Supabase Client)

```python
from supabase import create_client, Client

url = os.getenv("SUPABASE_URL")
key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")  # or SUPABASE_ANON_KEY

supabase: Client = create_client(url, key)
```

### REST API

```bash
curl -X GET 'https://qifioafprrtkoiyylsqa.supabase.co/rest/v1/tenants' \
  -H "apikey: sb_publishable_PhKpWt7-UWeydaiqe99LDg_OSnuK7a0" \
  -H "Authorization: Bearer sb_publishable_PhKpWt7-UWeydaiqe99LDg_OSnuK7a0"
```

## Security

⚠️ **Never commit these keys to version control!**

- Add `.env` to `.gitignore`
- Use environment variables in production
- Rotate keys if exposed
- Service Role Key has admin access - keep it secret!

## Next Steps

1. **For Database Migrations:** Still need to set `DATABASE_URL` with PostgreSQL connection string
2. **For Supabase API:** Keys are ready to use with Supabase client library
3. **For Manual Migration:** Run `scripts/run_migrations_manually.sql` in Supabase SQL Editor
