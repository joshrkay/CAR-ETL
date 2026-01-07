# Supabase Connection Troubleshooting

## Current Issue

**Error:** `could not translate host name "db.qifioafprrtkoiyylsqa.supabase.co" to address: Name or service not known`

This indicates a DNS resolution problem.

## Possible Causes

1. **Project Not Fully Provisioned**
   - New Supabase projects can take a few minutes to fully provision
   - Check project status in Supabase dashboard

2. **Network/DNS Issues**
   - Firewall blocking connections
   - DNS server issues
   - Network connectivity problems

3. **Project Paused**
   - Free tier projects may pause after inactivity
   - Check project status in dashboard

4. **Incorrect Hostname Format**
   - Connection string format may vary
   - Always use the exact string from Supabase dashboard

## Solutions

### Solution 1: Verify Project Status

1. Go to https://app.supabase.com/project/qifioafprrtkoiyylsqa
2. Check if project shows as "Active"
3. If paused, click "Resume" or "Restore"

### Solution 2: Get Exact Connection String

1. Go to: Settings > Database > Connection string
2. Click "URI" tab
3. Select "Session mode"
4. **Copy the EXACT connection string** (don't construct it)
5. It should look like one of these formats:
   ```
   postgresql://postgres:[PASSWORD]@db.[PROJECT-REF].supabase.co:5432/postgres
   postgresql://postgres.[PROJECT-REF]:[PASSWORD]@aws-0-[REGION].pooler.supabase.com:5432/postgres
   ```

### Solution 3: Try Pooler Connection

The pooler connection resolved DNS earlier. Try:

```powershell
$env:DATABASE_URL="postgresql://postgres.qifioafprrtkoiyylsqa:4VNTmrNhb3NyoI2r@aws-0-us-east-1.pooler.supabase.com:5432/postgres?sslmode=require"
```

Or try different regions:
- `aws-0-us-east-1.pooler.supabase.com`
- `aws-0-us-west-1.pooler.supabase.com`  
- `aws-0-eu-west-1.pooler.supabase.com`

### Solution 4: Network Troubleshooting

1. **Check Internet Connection**
   ```powershell
   ping db.qifioafprrtkoiyylsqa.supabase.co
   ```

2. **Try Different DNS**
   - Use Google DNS: 8.8.8.8
   - Use Cloudflare DNS: 1.1.1.1

3. **Check Firewall**
   - Ensure port 5432 is not blocked
   - Check corporate firewall settings

### Solution 5: Use Supabase SQL Editor

As a workaround, you can run SQL directly in Supabase:

1. Go to: SQL Editor in Supabase dashboard
2. Run the migration SQL manually
3. Copy SQL from migration files and execute

## Your Current Configuration

- **Project URL:** https://qifioafprrtkoiyylsqa.supabase.co
- **Project Reference:** qifioafprrtkoiyylsqa
- **Password:** 4VNTmrNhb3NyoI2r
- **Connection String Format:** `postgresql://postgres:[PASSWORD]@db.[PROJECT-REF].supabase.co:5432/postgres`

## Next Steps

1. **Verify project is active** in Supabase dashboard
2. **Get exact connection string** from Settings > Database
3. **Try pooler connection** if direct connection fails
4. **Check network/DNS** if issues persist
5. **Contact Supabase support** if project appears active but connection fails

## Alternative: Manual SQL Execution

If connection issues persist, you can:

1. Go to Supabase SQL Editor
2. Copy SQL from migration files
3. Execute manually in the SQL Editor

The migration SQL is in:
- `alembic/versions/001_control_plane.py`
- `alembic/versions/002_seed_data.py`
