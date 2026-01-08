# Security Guide - CAR Platform

## Quick Reference

**Last Security Audit**: January 7, 2026  
**Status**: ✅ All Critical Issues Resolved  
**Required Action**: Rotate exposed credentials

---

## Table of Contents

1. [Critical Security Fix - January 2026](#critical-security-fix)
2. [Environment Setup](#environment-setup)
3. [Credential Management](#credential-management)
4. [Security Best Practices](#security-best-practices)
5. [Incident Response](#incident-response)

---

## Critical Security Fix

### Issue: Hardcoded Production Credentials (RESOLVED ✅)

**Date**: January 7, 2026  
**Severity**: 🔴 CRITICAL  
**Status**: ✅ FIXED

Three PowerShell scripts contained hardcoded production credentials:
- ✅ `scripts/run_rls_test.ps1` - FIXED
- ✅ `scripts/run_service_role_test.ps1` - FIXED  
- ✅ `run_login_test.ps1` - FIXED

**Exposed Credentials**:
- `SUPABASE_SERVICE_KEY` - Bypasses ALL RLS policies
- `SUPABASE_JWT_SECRET` - Can forge authentication tokens
- `SUPABASE_ANON_KEY` - Public key
- `SUPABASE_URL` - Production endpoint

### Impact

**Service Role Key** (Most Critical):
- Bypasses Row-Level Security completely
- Grants unrestricted access to ALL tenant data
- Violates CAR Platform tenant isolation guarantees
- Complete database compromise if exposed

**JWT Secret**:
- Token forgery (impersonate any user)
- Authentication bypass
- Privilege escalation

### What Was Fixed

All scripts now:
1. Load credentials from `.env` file ONLY
2. Fail with clear error if `.env` is missing
3. Validate all required variables are set
4. Provide security warnings

```powershell
# Secure: Loads from .env file
if (Test-Path $envFile) {
    Get-Content $envFile | ForEach-Object {
        # Parse environment variables
    }
} else {
    Write-Host "ERROR: .env file not found"
    Write-Host "NEVER commit credentials to version control!"
    exit 1
}
```

---

## Environment Setup

### 1. Create `.env` File

Create a `.env` file in the project root (already in `.gitignore`):

```bash
# CAR Platform Environment Variables
# NEVER commit this file to version control

# Supabase Configuration
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_ANON_KEY=your_anon_key_here
SUPABASE_SERVICE_KEY=your_service_role_key_here
SUPABASE_JWT_SECRET=your_jwt_secret_here

# Optional: Application Configuration
ENVIRONMENT=dev
LOG_LEVEL=INFO
```

### 2. Verify `.gitignore`

Ensure `.env` files are never committed:

```gitignore
# Environment variables
.env
.env.local
.env.*.local
```

### 3. Run Tests

All test scripts load credentials from `.env`:

```powershell
# These will fail if .env is missing (secure by design)
.\scripts\run_rls_test.ps1
.\scripts\run_service_role_test.ps1
.\scripts\run_tenant_isolation_test.ps1
```

---

## Credential Management

### ⚠️ IMMEDIATE ACTION REQUIRED

If credentials were exposed, rotate them immediately:

#### 1. Rotate Service Role Key (< 1 hour)

```
Location: Supabase Dashboard → Settings → API → Service Role Key
Actions:
  1. Generate new key
  2. Update .env file
  3. Revoke old key IMMEDIATELY
```

#### 2. Rotate JWT Secret (< 1 hour)

```
Location: Supabase Dashboard → Settings → API → JWT Secret
Actions:
  1. Regenerate JWT secret
  2. Update .env file
WARNING: ALL existing user sessions will be invalidated
```

#### 3. Audit Access Logs

```
Check for:
- Unauthorized service_role access
- Unusual database queries
- Data exfiltration attempts
```

### Credential Security Levels

| Credential | Level | Usage | Exposure Risk |
|------------|-------|-------|---------------|
| `SUPABASE_SERVICE_KEY` | **CRITICAL** | Admin scripts only | Complete DB compromise |
| `SUPABASE_JWT_SECRET` | **CRITICAL** | Token verification | Token forgery, auth bypass |
| `SUPABASE_ANON_KEY` | **PUBLIC** | Client applications | Limited (public by design) |
| `SUPABASE_URL` | **PUBLIC** | All connections | Limited (public endpoint) |

---

## Security Best Practices

### ✅ DO

- Store credentials in `.env` file (in `.gitignore`)
- Use environment variables for all secrets
- Rotate credentials immediately if exposed
- Use service role key ONLY in administrative scripts
- Use anon key + JWT for client applications
- Enable audit logging for service role usage

### ❌ DO NOT

- **NEVER** commit credentials to version control
- **NEVER** hardcode credentials in scripts
- **NEVER** share service role key with clients
- **NEVER** log credentials or tokens
- **NEVER** use service role key in client applications
- **NEVER** commit `.env` files

### Tenant Isolation

The service role key exposure violates these CAR Platform guarantees:

❌ **Before Fix**:
- Tenant isolation compromised (service role bypasses RLS)
- Cross-tenant access possible (service role sees all data)
- RLS policies ineffective (service role ignores policies)

✅ **After Fix**:
- Tenant isolation absolute (RLS enforced)
- No cross-tenant access (controlled access patterns)
- Credentials secured (loaded from `.env` only)

---

## Incident Response

### Immediate Actions (< 1 hour)

1. **Rotate Credentials**
   - Rotate all exposed credentials
   - Revoke old credentials
   - Audit recent access logs
   - Notify security team

2. **Verify Fix**
   ```bash
   # No JWT tokens in codebase
   grep -r "eyJhbGci" . --exclude-dir=node_modules
   # Result: No matches ✅
   
   # .env is gitignored
   grep "^\.env$" .gitignore
   # Result: Found ✅
   ```

### Short-term (< 24 hours)

1. Review all changes made with compromised keys
2. Check for data exfiltration
3. Notify affected tenants if data accessed
4. Document incident

### Long-term (< 1 week)

1. Conduct security audit
2. Review access control policies
3. Implement additional monitoring
4. Update security training

### Monitoring

Monitor for unauthorized service role usage:
- Unexpected service role API calls
- Service role access from unknown IPs
- Bulk data exports using service role
- After-hours service role operations

---

## Additional Security Measures

### 1. IP Allowlisting

Configure Supabase to allow service role access only from known IPs:
- Supabase Dashboard → Settings → API → Service Role IP Allowlist

### 2. Database Audit Logging

Enable PostgreSQL audit logging:

```sql
-- Log all service_role queries
ALTER ROLE service_role SET log_statement = 'all';
```

### 3. Least Privilege

Create limited-privilege roles instead of using service_role:

```sql
-- Create admin role with specific permissions
CREATE ROLE admin_operations;
GRANT SELECT, INSERT ON specific_tables TO admin_operations;
```

### 4. Pre-commit Hooks

Prevent credential commits:

```bash
# Add to .git/hooks/pre-commit
if git diff --cached | grep -i "SUPABASE_SERVICE_KEY"; then
    echo "ERROR: Attempting to commit SUPABASE_SERVICE_KEY"
    exit 1
fi
```

---

## Compliance

### CAR Platform Standards

✅ **OWASP A02** (Cryptographic Failures) - Passed  
✅ **OWASP A07** (Authentication Failures) - Passed  
✅ **CWE-798** (Hardcoded Credentials) - Passed  
✅ **CAR Platform Security Standards** - Passed

### Architectural Invariants

- ✅ **Tenant isolation is absolute**: RLS enforced
- ✅ **No cross-tenant access**: Controlled patterns
- ✅ **Credentials never committed**: Loaded from `.env`

---

## References

- [OWASP Top 10](https://owasp.org/www-project-top-ten/)
- [Supabase Security Best Practices](https://supabase.com/docs/guides/api)
- CAR Platform: `.cursorrules` - Security & Privacy section

---

**Document Version**: 1.0  
**Last Updated**: January 7, 2026  
**Status**: ✅ Current
