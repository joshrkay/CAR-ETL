# Auth0 Setup Scripts

This document describes the available setup scripts for configuring Auth0.

## Available Scripts

### 1. Guided Setup (Recommended First Step)

**Script:** `scripts/setup_auth0_guided.py`

**Purpose:** Interactive guide that checks your environment and provides step-by-step instructions.

**Usage:**
```powershell
python scripts/setup_auth0_guided.py
```

**What it does:**
- Checks which environment variables are set
- Provides instructions for setting missing variables
- Shows how to create Management API client
- Provides manual setup alternatives

**When to use:** Run this first to understand what's needed and verify your setup.

### 2. Automated Setup (After Credentials Are Set)

**Script:** `scripts/setup_auth0.py`

**Purpose:** Automatically configures Auth0 using the Management API.

**Prerequisites:**
- `AUTH0_DOMAIN` environment variable set
- `AUTH0_MANAGEMENT_CLIENT_ID` environment variable set
- `AUTH0_MANAGEMENT_CLIENT_SECRET` environment variable set
- `AUTH0_DATABASE_CONNECTION_NAME` environment variable set (defaults to "Username-Password-Authentication")

**Usage:**
```powershell
python scripts/setup_auth0.py
```

**What it does:**
- Creates API resource "CAR API" with identifier `https://api.car-platform.com`
- Configures scopes: `read:documents`, `write:documents`, `admin`
- Sets JWT signing algorithm to RS256
- Configures database connection password policy (8+ chars, 1 number, 1 special)

**When to use:** After you have Management API credentials set up.

### 3. Original Bash Script (Linux/Mac/WSL)

**Script:** `infrastructure/auth0/setup.sh`

**Purpose:** Bash script for Unix-like systems using Auth0 CLI.

**Prerequisites:**
- Auth0 CLI installed: `npm install -g @auth0/auth0-cli`
- Bash shell (Linux, Mac, or WSL on Windows)
- Auth0 CLI logged in: `auth0 login`

**Usage:**
```bash
chmod +x infrastructure/auth0/setup.sh
./infrastructure/auth0/setup.sh
```

**When to use:** If you prefer using Auth0 CLI on Unix-like systems.

## Setup Workflow

### Step 1: Run Guided Setup
```powershell
python scripts/setup_auth0_guided.py
```

This will show you:
- What environment variables you need
- How to create the Management API client
- Manual setup alternatives

### Step 2: Set Environment Variables

Based on your certificate, your domain is: `dev-khx88c3lu7wz2dxx.us.auth0.com`

**PowerShell:**
```powershell
$env:AUTH0_DOMAIN="dev-khx88c3lu7wz2dxx.us.auth0.com"
$env:AUTH0_MANAGEMENT_CLIENT_ID="your-client-id"
$env:AUTH0_MANAGEMENT_CLIENT_SECRET="your-client-secret"
$env:AUTH0_DATABASE_CONNECTION_NAME="Username-Password-Authentication"
$env:AUTH0_API_IDENTIFIER="https://api.car-platform.com"
```

**Or create a `.env` file:**
```bash
AUTH0_DOMAIN=dev-khx88c3lu7wz2dxx.us.auth0.com
AUTH0_MANAGEMENT_CLIENT_ID=your-client-id
AUTH0_MANAGEMENT_CLIENT_SECRET=your-client-secret
AUTH0_DATABASE_CONNECTION_NAME=Username-Password-Authentication
AUTH0_API_IDENTIFIER=https://api.car-platform.com
```

### Step 3: Create Management API Client

Follow the instructions from the guided setup script, or:

1. Go to https://manage.auth0.com
2. Applications > Create Application
3. Type: Machine to Machine Applications
4. Authorize for "Auth0 Management API"
5. Grant required permissions
6. Copy Client ID and Secret

### Step 4: Run Automated Setup

```powershell
python scripts/setup_auth0.py
```

This will automatically:
- Create the API resource
- Configure scopes
- Set JWT signing to RS256
- Configure password policy

### Step 5: Verify Setup

Test JWT generation:
```powershell
python scripts/test_jwt_manual.py
```

## Manual Setup Alternative

If you prefer to set up everything manually via the Auth0 Dashboard, see `docs/AUTH0_SETUP.md` for detailed step-by-step instructions.

## Troubleshooting

### "Configuration error: Field required"
- Make sure all required environment variables are set
- Run `scripts/setup_auth0_guided.py` to check what's missing

### "Cannot connect to Auth0 Management API"
- Verify your Management API client credentials are correct
- Check that the client is authorized for Auth0 Management API
- Ensure required permissions are granted

### "API resource already exists"
- This is normal if you've run the script before
- The script will use the existing API resource

### "Connection not found"
- The default connection "Username-Password-Authentication" should exist
- If using a custom connection name, make sure it exists in Auth0

## Next Steps

After setup is complete:
1. Test JWT generation: `python scripts/test_jwt_manual.py`
2. Test health endpoint: `curl http://localhost:8000/health`
3. Integrate into your FastAPI application
