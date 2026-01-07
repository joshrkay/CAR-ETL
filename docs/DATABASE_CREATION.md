# Creating the Control Plane Database

This guide shows multiple ways to create the `control_plane` database.

## Method 1: Using Python Script (Recommended)

### Prerequisites
- PostgreSQL is running
- Connection credentials available

### Step 1: Set Connection Details

**Option A: Using DATABASE_URL**
```powershell
$env:DATABASE_URL="postgresql://postgres:password@localhost:5432/postgres"
```

**Option B: Using Individual Variables**
```powershell
$env:PGHOST="localhost"
$env:PGPORT="5432"
$env:PGUSER="postgres"
$env:PGPASSWORD="your_password"
```

### Step 2: Run the Setup Script
```powershell
python scripts/setup_database.py
```

This will:
- Connect to PostgreSQL
- Check if `control_plane` database exists
- Create it if it doesn't exist
- Verify the creation

## Method 2: Using psql Command Line

### Connect to PostgreSQL
```powershell
psql -U postgres -h localhost
```

### Create Database
```sql
CREATE DATABASE control_plane;
```

### Verify
```sql
\l control_plane
```

### Exit
```sql
\q
```

## Method 3: Using SQL Script

### Run SQL Script
```powershell
psql -U postgres -h localhost -f scripts/create_database.sql
```

Or manually:
```powershell
psql -U postgres -h localhost -c "CREATE DATABASE control_plane;"
```

## Method 4: Using pgAdmin

1. Open pgAdmin
2. Connect to your PostgreSQL server
3. Right-click on "Databases"
4. Select "Create" > "Database"
5. Enter name: `control_plane`
6. Click "Save"

## Verification

After creating the database, verify it:

```powershell
python scripts/setup_database.py --verify
```

Or using psql:
```powershell
psql -U postgres -h localhost -c "\l control_plane"
```

## Next Steps

After creating the database:

1. **Set DATABASE_URL for the control_plane database:**
   ```powershell
   $env:DATABASE_URL="postgresql://postgres:password@localhost:5432/control_plane"
   ```

2. **Run migrations:**
   ```powershell
   alembic upgrade head
   ```

This will create:
- `control_plane` schema
- All tables (tenants, tenant_databases, system_config)
- Indexes
- Seed data (system_admin tenant)

## Troubleshooting

### Error: "password authentication failed"

**Fix:** Verify your PostgreSQL password:
```powershell
$env:PGPASSWORD="your_password"
```

Or use DATABASE_URL with password:
```powershell
$env:DATABASE_URL="postgresql://postgres:your_password@localhost:5432/postgres"
```

### Error: "could not connect to server"

**Fix:** 
1. Verify PostgreSQL is running
2. Check host and port
3. Check firewall settings

### Error: "permission denied to create database"

**Fix:** Use a user with CREATEDB privilege:
```sql
-- As superuser
ALTER USER your_user CREATEDB;
```

Or use the `postgres` superuser.

## Database Connection String Format

```
postgresql://[user[:password]@][host][:port][/database]
```

Examples:
- `postgresql://postgres:password@localhost:5432/control_plane`
- `postgresql://user@localhost/control_plane` (no password)
- `postgresql://user:pass@remote-host:5432/control_plane`
