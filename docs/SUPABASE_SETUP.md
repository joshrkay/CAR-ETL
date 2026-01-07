# Supabase Database Setup for CAR Platform

This guide explains how to configure the control plane database using Supabase.

## Getting Your Supabase Connection String

### Step 1: Access Supabase Dashboard

1. Go to https://app.supabase.com
2. Sign in to your account
3. Select your project (or create a new one)

### Step 2: Get Database Connection Details

1. In your Supabase project, go to **Settings** > **Database**
2. Scroll down to **Connection string**
3. Select **URI** tab
4. Copy the connection string

The connection string format is:
```
postgresql://postgres.[PROJECT-REF]:[YOUR-PASSWORD]@aws-0-[REGION].pooler.supabase.com:6543/postgres
```

Or for direct connection:
```
postgresql://postgres:[YOUR-PASSWORD]@db.[PROJECT-REF].supabase.co:5432/postgres
```

### Step 3: Update Connection String for control_plane Database

Supabase uses a single PostgreSQL instance with multiple databases. You have two options:

**Option A: Use the default `postgres` database (Recommended)**
- Supabase uses the `postgres` database by default
- Create the `control_plane` schema within it
- Connection string: `postgresql://postgres:[PASSWORD]@db.[PROJECT-REF].supabase.co:5432/postgres`

**Option B: Create a separate database (if you have access)**
- Create a new database called `control_plane`
- Connection string: `postgresql://postgres:[PASSWORD]@db.[PROJECT-REF].supabase.co:5432/control_plane`

## Setting Up DATABASE_URL

### PowerShell

```powershell
$env:DATABASE_URL="postgresql://postgres:[YOUR-PASSWORD]@db.[PROJECT-REF].supabase.co:5432/postgres"
```

Replace:
- `[YOUR-PASSWORD]` with your Supabase database password
- `[PROJECT-REF]` with your Supabase project reference ID

### Example

```powershell
$env:DATABASE_URL="postgresql://postgres:MySecurePassword123@db.abcdefghijklmnop.supabase.co:5432/postgres"
```

## Supabase-Specific Considerations

### 1. Connection Pooling

Supabase offers two connection modes:

**Transaction Mode (Port 6543)** - Recommended for serverless/server applications:
```
postgresql://postgres.[PROJECT-REF]:[PASSWORD]@aws-0-[REGION].pooler.supabase.com:6543/postgres
```

**Session Mode (Port 5432)** - Direct connection:
```
postgresql://postgres:[PASSWORD]@db.[PROJECT-REF].supabase.co:5432/postgres
```

For migrations, use **Session Mode (Port 5432)**.

### 2. SSL Connection

Supabase requires SSL connections. The connection string should include SSL parameters:

```
postgresql://postgres:[PASSWORD]@db.[PROJECT-REF].supabase.co:5432/postgres?sslmode=require
```

### 3. Password Security

- Never commit your Supabase password to version control
- Use environment variables or Supabase secrets management
- Rotate passwords regularly

## Running Migrations on Supabase

### Step 1: Set DATABASE_URL

```powershell
$env:DATABASE_URL="postgresql://postgres:[PASSWORD]@db.[PROJECT-REF].supabase.co:5432/postgres?sslmode=require"
```

### Step 2: Verify Connection

```powershell
python scripts/verify_database_url.py
```

### Step 3: Run Migrations

```powershell
python -m alembic upgrade head
```

This will:
- Create the `control_plane` schema
- Create all tables (tenants, tenant_databases, system_config)
- Create indexes
- Seed the `system_admin` tenant

## Supabase Dashboard Verification

After running migrations, verify in Supabase Dashboard:

1. Go to **Table Editor** in your Supabase project
2. You should see the `control_plane` schema
3. Tables should appear:
   - `control_plane.tenants`
   - `control_plane.tenant_databases`
   - `control_plane.system_config`

## Troubleshooting

### Error: "SSL connection required"

**Fix:** Add `?sslmode=require` to your connection string:
```
postgresql://postgres:[PASSWORD]@db.[PROJECT-REF].supabase.co:5432/postgres?sslmode=require
```

### Error: "password authentication failed"

**Fix:** 
1. Verify your database password in Supabase Dashboard
2. Reset password if needed: Settings > Database > Reset database password

### Error: "connection timeout"

**Fix:**
- Check your network connection
- Verify Supabase project is active
- Try using the pooler connection (port 6543) for better reliability

### Error: "permission denied to create schema"

**Fix:** 
- Supabase projects have limited permissions
- The `control_plane` schema should be created by migrations
- If issues persist, check Supabase project settings

## Connection String Examples

### Transaction Mode (Pooler) - For Application Code
```
postgresql://postgres.abcdefghijklmnop:MyPassword@aws-0-us-east-1.pooler.supabase.com:6543/postgres?sslmode=require
```

### Session Mode (Direct) - For Migrations
```
postgresql://postgres:MyPassword@db.abcdefghijklmnop.supabase.co:5432/postgres?sslmode=require
```

## Next Steps

After setting up Supabase connection:

1. **Verify connection:**
   ```powershell
   python scripts/verify_database_url.py
   ```

2. **Run migrations:**
   ```powershell
   python -m alembic upgrade head
   ```

3. **Verify in Supabase Dashboard:**
   - Check Table Editor for `control_plane` schema
   - Verify tables are created
   - Check seed data (system_admin tenant)

## Security Best Practices

1. **Never commit connection strings** to version control
2. **Use environment variables** for all database credentials
3. **Enable Row Level Security (RLS)** in Supabase if needed
4. **Use connection pooling** for production applications
5. **Rotate passwords** regularly
6. **Monitor connection usage** in Supabase dashboard
