# Complete Environment Setup Guide

This guide covers all required environment variables for both Supabase and SharePoint connector setup.

## 📋 Complete `.env` File Template

Create a `.env` file in the project root with all these variables:

```bash
# ============================================
# CAR Platform Environment Variables
# NEVER commit this file to version control
# ============================================

# ============================================
# SUPABASE CONFIGURATION (Required)
# ============================================

# Your Supabase project URL
# Format: https://<project-ref>.supabase.co
# Get from: Supabase Dashboard → Settings → API → Project URL
SUPABASE_URL=https://your-project-ref.supabase.co

# Anonymous key (public, safe for client-side)
# Get from: Supabase Dashboard → Settings → API → Project API keys → anon public
SUPABASE_ANON_KEY=your-anon-key-here

# Service role key (CRITICAL - keep secret!)
# Get from: Supabase Dashboard → Settings → API → Project API keys → service_role secret
# WARNING: This key bypasses RLS - never expose it!
SUPABASE_SERVICE_KEY=mXq3Mkh3yziih/VSZRW8fdsqw8m3v9+4BVi3zPtxRxNE3UkypqS4YUZW+LVYFH00Qs/TgdayPYc/KoZb+3X1vg==


# JWT secret for token validation (CRITICAL - keep secret!)
# Get from: Supabase Dashboard → Settings → API → JWT Secret
# Used to verify JWT tokens issued by Supabase Auth
SUPABASE_JWT_SECRET=mXq3Mkh3yziih/VSZRW8fdsqw8m3v9+4BVi3zPtxRxNE3UkypqS4YUZW+LVYFH00Qs/TgdayPYc/KoZb+3X1vg==

# ============================================
# SHAREPOINT CONNECTOR (Required for SharePoint)
# ============================================

# Azure AD Application Client ID
# Get from: Azure Portal → App registrations → Your app → Overview → Application (client) ID
SHAREPOINT_CLIENT_ID=c2d0b1df-92ab-44d9-8d47-9722a97a6eb4

# Azure AD Application Client Secret
# Get from: Azure Portal → App registrations → Your app → Certificates & secrets → Client secrets
# Create a new secret if needed (valid for 6/12/24 months)
SHAREPOINT_CLIENT_SECRET=624ff5b6-6ce9-4556-adbc-9c01580f07b8

# ============================================
# GOOGLE DRIVE CONNECTOR (Required for Google Drive)
# ============================================

# Google OAuth Application Client ID
# Get from: Google Cloud Console → APIs & Services → Credentials → OAuth 2.0 Client ID
GOOGLE_CLIENT_ID=1863675278-ap57vk3lv7hlnvpvvcfdjokj5jmfu262.apps.googleusercontent.com

# Google OAuth Application Client Secret
# Get from: Google Cloud Console → APIs & Services → Credentials → OAuth 2.0 Client ID → Client secret
GOOGLE_CLIENT_SECRET=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

# OAuth Redirect URI (must match Google Cloud Console configuration)
# For dev: http://localhost:8000/oauth/google/callback
# For production: https://yourdomain.com/oauth/google/callback
GOOGLE_REDIRECT_URI=http://localhost:8000/oauth/google/callback

# OAuth Redirect URI (must match Azure AD configuration exactly)
# For local development:
SHAREPOINT_REDIRECT_URI=http://localhost:8000/oauth/microsoft/callback
# For production, use your production URL:
# SHAREPOINT_REDIRECT_URI=https://your-domain.com/oauth/microsoft/callback

# ============================================
# ENCRYPTION (Required for OAuth token storage)
# ============================================

# Encryption key for OAuth tokens (Fernet-compatible, base64-encoded)
# Generate with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
# Or use the JWT secret as fallback (less secure)
ENCRYPTION_KEY=your-encryption-key-here

# ============================================
# OPTIONAL: Application Configuration
# ============================================

# Application environment (dev, staging, production)
APP_ENV=development

# Log level (DEBUG, INFO, WARNING, ERROR)
LOG_LEVEL=INFO

# ============================================
# OPTIONAL: Other Services (if used)
# ============================================

# OpenAI API Key (if using AI features)
# OPENAI_API_KEY=sk-...

# Resend API Key (if using email features)
# RESEND_API_KEY=re_...

# Resend Webhook Secret (if using email webhooks)
# RESEND_WEBHOOK_SECRET=whsec_...
```

## 🔧 How to Get Supabase Credentials

### Step 1: Access Supabase Dashboard
1. Go to https://supabase.com/dashboard
2. Select your project (or create a new one)

### Step 2: Get Project URL
1. Navigate to **Settings** → **API**
2. Copy the **Project URL** (e.g., `https://abc123.supabase.co`)
3. This is your `SUPABASE_URL`

### Step 3: Get API Keys
1. In the same **Settings** → **API** page:
   - **anon public** key → `SUPABASE_ANON_KEY`
   - **service_role secret** key → `SUPABASE_SERVICE_KEY` ⚠️ **KEEP SECRET!**

### Step 4: Get JWT Secret
1. In **Settings** → **API**
2. Scroll to **JWT Settings**
3. Copy the **JWT Secret** → `SUPABASE_JWT_SECRET` ⚠️ **KEEP SECRET!**

## 🔧 How to Get SharePoint Credentials

### Step 1: Create Azure AD App Registration
1. Go to https://portal.azure.com
2. Navigate to **Azure Active Directory** → **App registrations**
3. Click **New registration**
4. Fill in:
   - **Name**: CAR Platform SharePoint Connector
   - **Supported account types**: Accounts in this organizational directory only
   - **Redirect URI**: 
     - Platform: Web
     - URI: `http://localhost:8000/oauth/microsoft/callback` (for dev)
5. Click **Register**

### Step 2: Get Client ID
1. In your app registration, go to **Overview**
2. Copy the **Application (client) ID** → `SHAREPOINT_CLIENT_ID`

### Step 3: Create Client Secret
1. Go to **Certificates & secrets**
2. Click **New client secret**
3. Fill in:
   - **Description**: CAR Platform SharePoint Connector
   - **Expires**: 12 months (or your preference)
4. Click **Add**
5. **IMPORTANT**: Copy the secret value immediately (you won't see it again!)
6. This is your `SHAREPOINT_CLIENT_SECRET`

### Step 4: Configure API Permissions
1. Go to **API permissions**
2. Click **Add a permission**
3. Select **Microsoft Graph** → **Delegated permissions**
4. Add these permissions:
   - `Files.Read.All` - Read all files
   - `Sites.Read.All` - Read all sites
   - `offline_access` - Maintain access to data (for refresh tokens)
5. Click **Add permissions**
6. Click **Grant admin consent** (if you have admin rights)

### Step 5: Configure Redirect URI
1. Go to **Authentication**
2. Under **Platform configurations**, click **Add a platform** → **Web**
3. Add redirect URI: `http://localhost:8000/oauth/microsoft/callback`
4. Click **Configure**

## 🔐 Generate Encryption Key

Run this command to generate a secure encryption key:

```bash
python -c "from cryptography.fernet import Fernet; print('ENCRYPTION_KEY=' + Fernet.generate_key().decode())"
```

Copy the output and add it to your `.env` file.

## ✅ Verification Checklist

Before running the application, verify:

- [ ] `SUPABASE_URL` is set and accessible
- [ ] `SUPABASE_ANON_KEY` is set (starts with `eyJ...`)
- [ ] `SUPABASE_SERVICE_KEY` is set (starts with `eyJ...`)
- [ ] `SUPABASE_JWT_SECRET` is set (at least 32 characters)
- [ ] `SHAREPOINT_CLIENT_ID` is set (UUID format)
- [ ] `SHAREPOINT_CLIENT_SECRET` is set
- [ ] `SHAREPOINT_REDIRECT_URI` matches Azure AD configuration exactly
- [ ] `ENCRYPTION_KEY` is set (base64-encoded, 44 characters)
- [ ] Database migration `025_connectors.sql` has been applied

## 🧪 Test Your Configuration

### Test Supabase Connection
```bash
python scripts/test_connection.py
```

### Test SharePoint Setup
```bash
python scripts/test_sharepoint_e2e.py
```

### Run Unit Tests
```bash
python -m pytest tests/test_sharepoint_connector.py -v
```

## 🚨 Security Warnings

1. **Never commit `.env` file** - It's already in `.gitignore`
2. **Service Role Key** - This bypasses RLS. Only use server-side, never expose to clients
3. **JWT Secret** - If exposed, attackers can forge authentication tokens
4. **Client Secret** - If exposed, attackers can impersonate your application
5. **Encryption Key** - If exposed, stored OAuth tokens can be decrypted

## 📝 Database Migration

Before using the SharePoint connector, apply the database migration:

```bash
# Option 1: Via Supabase Dashboard
# 1. Go to Supabase Dashboard → SQL Editor
# 2. Copy contents of supabase/migrations/025_connectors.sql
# 3. Paste and run

# Option 2: Via Supabase CLI (if installed)
supabase db push
```

This creates:
- `connectors` table (stores OAuth credentials and sync config)
- `oauth_states` table (temporary OAuth state storage)
- RLS policies (enforces tenant isolation)

## 🔄 Environment-Specific Configuration

### Development
```bash
SHAREPOINT_REDIRECT_URI=http://localhost:8000/oauth/microsoft/callback
APP_ENV=development
```

### Production
```bash
SHAREPOINT_REDIRECT_URI=https://your-domain.com/oauth/microsoft/callback
APP_ENV=production
LOG_LEVEL=WARNING
```

## 📚 Additional Resources

- [Supabase Documentation](https://supabase.com/docs)
- [Microsoft Graph API Documentation](https://docs.microsoft.com/en-us/graph/)
- [Azure AD App Registration Guide](https://docs.microsoft.com/en-us/azure/active-directory/develop/quickstart-register-app)
- [SharePoint Setup Guide](./SHAREPOINT_SETUP.md)
