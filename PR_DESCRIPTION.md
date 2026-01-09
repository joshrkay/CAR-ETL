# Security Fixes and Critical Bug Fixes

## Summary
This PR addresses 5 critical security vulnerabilities and bugs discovered in the SharePoint connector and related services. All fixes follow `.cursorrules` standards for security, error handling, and defense in depth principles.

## Security Fixes

### 1. Remove Exposed Credentials from Setup Guide
**Issue**: `SHAREPOINT_SETUP.md` contained real Azure AD credentials (`SHAREPOINT_CLIENT_ID`, `SHAREPOINT_CLIENT_SECRET`) and a valid Fernet encryption key (`ENCRYPTION_KEY`). These credentials are now permanently exposed in version control history.

**Fix**: Replaced all real credentials with placeholders (`your-client-id-here`, `your-client-secret-here`, `your-encryption-key-here`) matching the pattern used in `ENV_SETUP_GUIDE.md`.

**Impact**: Prevents credential exposure in version control. Note: Credentials may still exist in git history and should be rotated.

### 2. Remove PII from Logs
**Issue**: `presidio_redact()` function logged `text_preview` containing the first 50 characters of potentially PII-containing text, violating the "No PII in Logs" rule.

**Fix**: Removed `text_preview` from logging, keeping only metadata like `text_length`.

**Impact**: Prevents sensitive data leakage in application logs, ensuring compliance with security standards.

## Bug Fixes

### 3. Fix Token Expiration Timestamp
**Issue**: OAuth token `expires_at` field stored `expires_in` (relative seconds) instead of absolute timestamp. This would cause any future logic checking token expiration by comparing timestamps to fail incorrectly.

**Fix**: Calculate absolute expiration time: `datetime.now(timezone.utc) + timedelta(seconds=expires_in)`.

**Impact**: Prevents OAuth token expiration checks from failing. Tokens will now correctly expire at the calculated absolute time.

### 4. Fix Encryption Key Return Type
**Issue**: `get_encryption_key()` returned inconsistent data types:
- When `ENCRYPTION_KEY` is set: returned 32 raw bytes (decoded from base64)
- When using JWT fallback: returned base64-encoded bytes (44 chars)

Since `Fernet` expects base64-encoded bytes, the `ENCRYPTION_KEY` path would fail.

**Fix**: Return base64-encoded bytes consistently. `ENCRYPTION_KEY` is now returned as-is (already base64-encoded string, converted to bytes).

**Impact**: Prevents encryption/decryption failures when `ENCRYPTION_KEY` environment variable is set. Users following the setup guide to generate a key via `Fernet.generate_key().decode()` will now have working encryption.

### 5. Add File Storage to SharePoint Sync
**Issue**: `_sync_file_item` method downloaded file content from SharePoint, redacted it, and computed its hash, but the `redacted_content` was never actually stored. Only metadata records were saved, meaning synced files had no actual content available for processing.

**Fix**: Added Supabase Storage upload before saving metadata. Redacted content is now uploaded to tenant's storage bucket (`documents-{tenant_id}`) at the calculated `storage_path`.

**Impact**: Prevents data loss. Synced SharePoint files now have actual content stored and available for processing.

## Testing
- [x] Verified all fixes compile without errors
- [x] Linter checks pass
- [x] No breaking changes to existing APIs
- [ ] Manual testing of OAuth flow (requires Azure AD setup)
- [ ] Manual testing of SharePoint sync (requires OAuth tokens)

## Breaking Changes
None. All changes are backward-compatible bug fixes and security improvements.

## Files Changed
- `SHAREPOINT_SETUP.md` - Replaced real credentials with placeholders
- `src/api/routes/connectors.py` - Fixed `expires_at` timestamp calculation
- `src/services/redaction.py` - Removed PII from logs
- `src/utils/encryption.py` - Fixed encryption key return type
- `src/connectors/sharepoint/sync.py` - Added file storage upload

## Related Issues
N/A - Proactive security audit and bug fixes
