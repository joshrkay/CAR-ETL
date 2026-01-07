# Supabase API Keys Setup

Your Supabase API keys have been configured:

- **Anon Key:** `sb_publishable_PhKpWt7-UWeydaiqe99LDg_OSnuK7a0`
- **Service Role Key:** `sb_secret_SDH3fH1Nl69oxRGNBPy91g_MhFHDYpm`
- **Project URL:** `https://qifioafprrtkoiyylsqa.supabase.co`

## Quick Setup

Run the PowerShell script to set environment variables:

```powershell
.\scripts\setup_env_vars.ps1
```

Or set them manually:

```powershell
$env:SUPABASE_URL="https://qifioafprrtkoiyylsqa.supabase.co"
$env:SUPABASE_ANON_KEY="sb_publishable_PhKpWt7-UWeydaiqe99LDg_OSnuK7a0"
$env:SUPABASE_SERVICE_ROLE_KEY="sb_secret_SDH3fH1Nl69oxRGNBPy91g_MhFHDYpm"
```

## Important: Database Connection Still Needed

**These API keys are for Supabase REST API, NOT for database migrations.**

For Alembic migrations, you still need the PostgreSQL connection string:

1. Go to: https://app.supabase.com/project/qifioafprrtkoiyylsqa/settings/database
2. Click "URI" tab → "Session mode" (port 5432)
3. Copy the connection string
4. Set it as `DATABASE_URL`:

```powershell
$env:DATABASE_URL="postgresql://postgres:[PASSWORD]@db.qifioafprrtkoiyylsqa.supabase.co:5432/postgres?sslmode=require"
```

## What These Keys Are For

- **Anon Key:** Public key for client-side Supabase operations
- **Service Role Key:** Admin key for server-side operations (keep secret!)
- **NOT for:** Direct PostgreSQL connections (use `DATABASE_URL` instead)

## Next Steps

1. Set `DATABASE_URL` with PostgreSQL connection string
2. Run migrations: `python -m alembic upgrade head`
3. Or run manually: Use `scripts/run_migrations_manually.sql` in Supabase SQL Editor
