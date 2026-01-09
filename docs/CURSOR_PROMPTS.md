# Cursor AI Prompts for CAR-ETL Fixes

This document contains ready-to-use prompts for Cursor AI to fix critical issues in the CAR-ETL codebase.

---

## 🔴 CRITICAL: Implement Supabase Storage File Upload

### Prompt 1A: Fix Document Upload Endpoint

```
Fix the document upload endpoint to actually upload files to Supabase Storage.

Current issue:
- File content is validated but never uploaded to storage
- Line 329 in src/api/routes/documents.py uses placeholder hash
- Files are discarded after validation

Requirements:
1. After validation succeeds, upload file content to Supabase Storage
2. Use bucket name: f"documents-{tenant_id}"
3. Use storage path: f"uploads/{document_id}/{filename}"
4. Calculate actual SHA-256 hash of file content (replace placeholder)
5. Pass the real hash to store_document_metadata()
6. Set proper content-type in file_options
7. Handle upload errors with proper logging
8. Update store_document_metadata signature to remove placeholder hash generation

Files to modify:
- src/api/routes/documents.py (upload_document function, lines 81-245)
- src/api/routes/documents.py (store_document_metadata function, lines 290-348)

Code should:
- Use supabase.storage.from_(bucket_name).upload(path, content, file_options)
- Import hashlib for hash calculation
- Log successful upload with storage_path
- Raise HTTPException on upload failure
```

### Prompt 1B: Fix Email Ingestion Storage

```
Fix the email ingestion service to upload email bodies and attachments to Supabase Storage.

Current issue:
- Line 172 in src/services/email_ingestion.py has comment "placeholder - in production, upload to S3"
- Email content and attachments are not uploaded to storage
- Storage paths are generated but never used

Requirements:
1. In _create_body_document (line 139): Upload email body text to Supabase Storage
2. In _create_attachment_document (line 203): Upload attachment content to Supabase Storage
3. Use bucket name: f"documents-{tenant_id}"
4. Keep existing storage path format: f"emails/{tenant_id}/{document_id}/filename"
5. Set proper content-type in file_options
6. Handle upload errors gracefully (log and continue for attachments)
7. File hashes are already calculated correctly - keep that logic

Files to modify:
- src/services/email_ingestion.py (_create_body_document, lines 139-201)
- src/services/email_ingestion.py (_create_attachment_document, lines 203-272)

Code should:
- Use self.client.storage.from_(bucket_name).upload()
- Upload before creating document record
- On upload failure for body: raise exception
- On upload failure for attachment: return None (already handled)
```

### Prompt 1C: Fix Bulk Upload Storage

```
Fix the bulk upload service to upload files to Supabase Storage.

Current issue:
- Files in ZIP are extracted and validated but never uploaded to storage
- Line 227-239 in src/api/routes/upload.py stores metadata but not file content

Requirements:
1. After file validation succeeds, upload each file to Supabase Storage
2. Use bucket name: f"documents-{tenant_id}"
3. Use storage path: f"bulk/{batch_id}/{filename}"
4. Hash is already calculated correctly (line 227) - keep that
5. Upload before calling store_document_metadata
6. On upload failure: mark file as failed in results

Files to modify:
- src/api/routes/upload.py (upload_bulk_documents function, lines 216-240)
- src/api/routes/upload.py (store_document_metadata function, signature)

Code should:
- Use supabase.storage.from_(bucket_name).upload()
- Add try/except around upload
- Pass actual storage_path to store_document_metadata
- Update store_document_metadata to accept storage_path parameter
```

---

## 🔴 CRITICAL: Fix Rate Limiter Fail-Open Behavior

### Prompt 2: Rate Limiter Should Fail Closed

```
Fix the email rate limiter to fail closed (reject requests) when rate limit checks fail.

Current issue:
- Lines 92-106 in src/services/email_rate_limiter.py catches all exceptions and allows request
- This is a security vulnerability - DoS protection is bypassed if rate limiter fails
- Comment says "In production, you might want to fail closed"

Requirements:
1. Remove the broad try/except that swallows errors
2. Let exceptions propagate to caller
3. Only catch specific, expected exceptions (e.g., database timeout)
4. For database errors: fail closed (raise RateLimitError with appropriate message)
5. Keep the same logic for when rate limit is actually exceeded

Files to modify:
- src/services/email_rate_limiter.py (check_rate_limit method, lines 49-106)

Code should:
- Remove or narrow the exception handler at line 92
- Add specific exception handling only for transient errors
- Default behavior: raise exception on any rate limit check failure
- This ensures production safety
```

---

## 🟡 HIGH PRIORITY: Environment Variable Validation

### Prompt 3: Add Startup Environment Validation

```
Add environment variable validation on application startup.

Current issue:
- No .env file validation when app starts
- Missing credentials cause runtime failures
- Poor developer experience

Requirements:
1. Create a startup event handler in src/main.py
2. Validate all required environment variables are set:
   - SUPABASE_URL
   - SUPABASE_ANON_KEY
   - SUPABASE_SERVICE_KEY
   - SUPABASE_JWT_SECRET
3. Check that values are not empty or default placeholders
4. If validation fails: log clear error message and exit with code 1
5. If validation succeeds: log success message with environment info (don't log secrets)
6. Add helpful error messages pointing to .env.example or SECURITY.md

Files to modify:
- src/main.py (add startup event handler)
- src/auth/config.py (add validation method to AuthConfig)

Code should:
- Use @app.on_event("startup") decorator
- Call validation before accepting any requests
- Provide actionable error messages
- Never log secret values
```

---

## 🟡 HIGH PRIORITY: Fix Timezone Handling

### Prompt 4: Replace Deprecated datetime.utcnow()

```
Replace all usages of deprecated datetime.utcnow() with datetime.now(timezone.utc).

Current issue:
- datetime.utcnow() is deprecated and will be removed in future Python versions
- Used in src/auth/middleware.py line 108
- Used in src/auth/rate_limit.py line 30
- Inconsistent timezone handling throughout codebase

Requirements:
1. Find all usages of datetime.utcnow() in src/ directory
2. Replace with datetime.now(timezone.utc)
3. Add 'from datetime import timezone' import where needed
4. Ensure all datetime comparisons use timezone-aware datetimes
5. Run tests to verify no breakage

Files to check:
- src/auth/middleware.py
- src/auth/rate_limit.py
- Any other files with utcnow()

Code should:
- Import: from datetime import datetime, timezone
- Replace: datetime.utcnow() → datetime.now(timezone.utc)
- Be consistent across entire codebase
```

---

## 🟡 HIGH PRIORITY: Security Fixes Bundle

### Prompt 5A: Always Verify JWT Signatures

```
Remove JWT signature bypass in non-production environments.

Current issue:
- Lines 90-94 in src/auth/middleware.py disable signature verification in non-production
- This prevents testing auth security before production
- Creates dangerous production/staging behavioral gap

Requirements:
1. Always verify JWT signatures regardless of environment
2. Remove the if not self.config.is_production check
3. Keep proper HS256 verification
4. For ES256 tokens (Supabase access tokens), fetch public key from JWKS endpoint
5. Update comments explaining proper token verification
6. Tests should use properly signed test tokens

Files to modify:
- src/auth/middleware.py (_validate_token method, lines 77-100)

Code should:
- Always use verify_signature=True
- Always use verify_exp=True (unless specifically testing expired tokens)
- Handle ES256 tokens properly with public key verification
- Remove environment-based security bypasses
```

### Prompt 5B: Fix Path Traversal in ZIP Extraction

```
Add path traversal protection to bulk upload ZIP extraction.

Current issue:
- src/services/bulk_upload.py doesn't validate ZIP entry filenames
- Malicious ZIP could contain paths like "../../../etc/passwd"
- Lines 156-169 extract files without path validation

Requirements:
1. Before extracting each file, validate the filename
2. Check that resolved path is within the intended directory
3. Reject filenames containing ".." or starting with "/"
4. Use os.path.normpath() and verify path prefix
5. Add validation to extract_and_validate_files method
6. Add validation errors to results list

Files to modify:
- src/services/bulk_upload.py (extract_and_validate_files method, lines 122-192)

Code should:
- Import os and pathlib
- Validate: normalized_path = os.path.normpath(filename)
- Reject if normalized_path.startswith('..') or os.path.isabs(normalized_path)
- Add error: "Invalid filename: path traversal detected"
```

### Prompt 5C: Add XML Bomb Protection

```
Add XML bomb protection to Office document validation.

Current issue:
- src/services/file_validator.py parses XML from Office docs without size limits
- Vulnerable to XML entity expansion attacks (billion laughs)
- Lines 132-166 in _validate_office_document

Requirements:
1. Add entity expansion limits to XML parsing
2. Use defusedxml library OR configure ElementTree securely
3. Set max entity expansion limit (e.g., 100)
4. Add size check for [Content_Types].xml (e.g., max 1MB)
5. Catch and handle XML parsing attacks as validation errors
6. Add defusedxml to requirements.txt if used

Files to modify:
- src/services/file_validator.py (_validate_office_document method)
- requirements.txt (if adding defusedxml)

Code should:
- Option 1: from defusedxml import ElementTree as ET
- Option 2: Configure xml.etree.ElementTree with secure defaults
- Check XML size before parsing: if len(content) > 1_000_000: error
- Catch xml.etree.ElementTree.ParseError for entity attacks
```

---

## 🟡 MEDIUM PRIORITY: Graceful Shutdown

### Prompt 6: Add Graceful Shutdown for Audit Logs

```
Add graceful shutdown handler to flush audit log buffers before exit.

Current issue:
- src/audit/logger.py has buffered audit logs
- No shutdown handler to flush buffers on SIGTERM/SIGINT
- Unflushed audit events are lost if process crashes

Requirements:
1. Add signal handlers for SIGTERM and SIGINT
2. On shutdown: flush all audit log buffers
3. Wait for flush to complete (with timeout)
4. Add shutdown event handler to FastAPI app
5. Log shutdown process
6. Ensure audit logger is thread-safe during shutdown

Files to modify:
- src/audit/logger.py (add shutdown method, signal handlers)
- src/main.py (add shutdown event handler)

Code should:
- Use signal.signal(signal.SIGTERM, shutdown_handler)
- Call audit_logger.shutdown() in FastAPI @app.on_event("shutdown")
- Flush with timeout (e.g., 5 seconds)
- Log "Audit logs flushed successfully" or warning if timeout
```

---

## 📋 Usage Instructions

### How to Use These Prompts in Cursor:

1. **Select the prompt text** from any section above
2. **Open Cursor** and press `Cmd+K` (Mac) or `Ctrl+K` (Windows/Linux)
3. **Paste the prompt** into Cursor's AI chat
4. **Review the changes** Cursor suggests
5. **Test the changes** before committing
6. **Repeat** for each prompt

### Recommended Order:

1. **Start with Critical Issues (🔴)**:
   - Prompt 1A, 1B, 1C: File storage (required for basic functionality)
   - Prompt 2: Rate limiter (security)

2. **Then High Priority (🟡)**:
   - Prompt 3: Environment validation (developer experience)
   - Prompt 4: Timezone handling (future-proofing)
   - Prompts 5A, 5B, 5C: Security fixes

3. **Finally Medium Priority**:
   - Prompt 6: Graceful shutdown (operational robustness)

### Testing After Each Fix:

```bash
# After storage fixes (Prompts 1A-1C):
pytest tests/test_document_upload.py -v
pytest tests/test_bulk_upload.py -v
pytest tests/test_email_ingestion.py -v

# After rate limiter fix (Prompt 2):
pytest tests/test_email_ingestion.py -k rate_limit -v

# After environment validation (Prompt 3):
# Try running without .env file - should fail gracefully
python -m uvicorn src.main:app

# After timezone fix (Prompt 4):
pytest tests/test_auth.py -v
pytest tests/test_audit.py -v

# After security fixes (Prompts 5A-5C):
pytest tests/test_auth.py -v
pytest tests/test_bulk_upload.py -v
pytest tests/test_file_validator.py -v
```

---

## 📝 Notes

- Each prompt is self-contained and can be used independently
- Prompts include file paths and line numbers for easy reference
- Always review AI-generated code before committing
- Run tests after each fix to ensure nothing breaks
- Some prompts may require updating tests to match new behavior
- The prompts assume Cursor has context of the full codebase

---

## 🔗 Related Documentation

- See [SECURITY.md](../SECURITY.md) for security best practices
- See [README_DEPLOYMENT.md](../README_DEPLOYMENT.md) for deployment guidance
- See test files for examples of proper usage

---

**Created**: 2026-01-09
**Status**: Ready to use
**Priority Order**: 1A → 1B → 1C → 2 → 3 → 4 → 5A → 5B → 5C → 6
