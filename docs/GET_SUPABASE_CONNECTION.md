# How to Get Your Supabase Connection String

Follow these steps to get the exact connection string from your Supabase dashboard.

## Step-by-Step Instructions

### Step 1: Access Supabase Dashboard
1. Go to **https://app.supabase.com**
2. Sign in to your account
3. Select your project (or create a new one if needed)

### Step 2: Navigate to Database Settings
1. In your project dashboard, click on **Settings** (gear icon in the left sidebar)
2. Click on **Database** in the settings menu

### Step 3: Get Connection String
1. Scroll down to the **Connection string** section
2. You'll see different connection modes:
   - **URI** - Full connection string
   - **JDBC** - Java format
   - **Golang** - Go format
   - **Node.js** - JavaScript format
   - **Python** - Python format
   - **Pooler mode** - Connection pooling

3. **For Migrations (Alembic):**
   - Click on the **URI** tab
   - Select **Session mode** (not Transaction mode)
   - Copy the connection string

### Step 4: Connection String Format

The connection string should look like one of these:

**Session Mode (for migrations):**
```
postgresql://postgres.[PROJECT-REF]:[PASSWORD]@aws-0-[REGION].pooler.supabase.com:5432/postgres
```

**Or Direct Connection:**
```
postgresql://postgres:[PASSWORD]@db.[PROJECT-REF].supabase.co:5432/postgres
```

### Step 5: Add SSL Parameter

Supabase requires SSL. Add `?sslmode=require` to the end:

```
postgresql://postgres:[PASSWORD]@db.[PROJECT-REF].supabase.co:5432/postgres?sslmode=require
```

## Setting DATABASE_URL

Once you have the connection string from Supabase:

```powershell
$env:DATABASE_URL="[PASTE_CONNECTION_STRING_HERE]?sslmode=require"
```

**Important:** 
- If the connection string already has `?sslmode=require`, don't add it twice
- Replace `[PASSWORD]` with your actual database password
- Use Session mode (port 5432) for migrations

## Verify Connection

After setting DATABASE_URL:

```powershell
python scripts/verify_database_url.py
```

## Run Migrations

Once connection is verified:

```powershell
python -m alembic upgrade head
```

## Troubleshooting

### If connection fails:

1. **Verify project is active** in Supabase dashboard
2. **Check password** - Reset if needed in Settings > Database
3. **Use exact string** from Supabase dashboard (don't construct manually)
4. **Check network** - Ensure you can reach Supabase servers
5. **Try pooler mode** if direct connection fails:
   ```
   postgresql://postgres.[PROJECT-REF]:[PASSWORD]@aws-0-[REGION].pooler.supabase.com:6543/postgres?sslmode=require
   ```

## Your Current Credentials

- **Password:** `4VNTmrNhb3NyoI2r`
- **Project Reference:** `qifioafprrtkoiyylsqa`

**Note:** The hostname format might be different. Get the exact connection string from Supabase dashboard to ensure it's correct.
