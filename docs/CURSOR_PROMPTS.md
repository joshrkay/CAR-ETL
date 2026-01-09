# Cursor IDE Prompts for CAR Platform Development

This document provides guidance on using Cursor IDE effectively with the CAR Platform codebase.

## Overview

Cursor IDE is an AI-powered code editor that can help accelerate development on the CAR Platform. This guide provides prompt templates and best practices for common development tasks.

## Prompt Templates

### Document Upload & Storage

```
Fix the document upload endpoint to upload files to Supabase Storage.

Requirements:
- Upload file content to Supabase Storage after validation
- Use bucket name: f"documents-{tenant_id}"
- Use storage path: f"uploads/{document_id}/{filename}"
- Calculate actual SHA-256 hash of file content
- Set proper content-type in file_options
- Handle upload errors with proper logging
```

### Email Ingestion

```
Fix the email ingestion service to upload email bodies and attachments to Supabase Storage.

Requirements:
- Upload email body text to Supabase Storage
- Upload attachment content to Supabase Storage
- Use bucket name: f"documents-{tenant_id}"
- Keep existing storage path format: f"emails/{tenant_id}/{document_id}/filename"
- Handle upload errors gracefully (log and continue for attachments)
```

### Bulk Upload

```
Fix the bulk upload service to upload files to Supabase Storage.

Requirements:
- After file validation succeeds, upload each file to Supabase Storage
- Use bucket name: f"documents-{tenant_id}"
- Use storage path: f"bulk/{batch_id}/{filename}"
- Upload before calling store_document_metadata
- On upload failure: mark file as failed in results
```

## Best Practices

### 1. Always Reference .cursorrules

When asking Cursor to make changes, always reference the `.cursorrules` file to ensure compliance with CAR Platform standards:

```
@.cursorrules

[Your request here]
```

### 2. Be Specific About Requirements

Include specific requirements in your prompts:
- Storage paths
- Bucket names
- Error handling expectations
- Function signatures

### 3. Request Compliance Verification

After making changes, ask Cursor to verify compliance:

```
@.cursorrules

Verify that all changes comply with CAR Platform standards.
```

### 4. Security & Privacy

Always emphasize security requirements in prompts:

```
SECURITY: Ensure PII redaction before storage (defense in depth)
- Call presidio_redact_bytes() before any storage operation
- Never log raw payload bodies
- Only log IDs and metadata
```

### 5. Architectural Boundaries

When requesting changes, specify the architectural layer:

```
This is in the Ingestion Plane - only capture and buffer data.
Do not add extraction logic.
```

## Common Patterns

### Adding a New Endpoint

```
Create a new API endpoint for [feature].

Requirements:
- Follow CAR Platform architectural boundaries
- Include proper authentication/authorization
- Add PII redaction before storage
- Include comprehensive error handling
- Add logging with tenant_id and user_id context
- Follow naming conventions (camelCase variables, verbNoun functions)
```

### Fixing Storage Issues

```
Fix [component] to upload files to Supabase Storage.

Requirements:
- Use FileStorageService for uploads
- Calculate SHA-256 hash before storage
- Set proper content-type
- Use correct storage path format
- Handle StorageUploadError appropriately
- Log successful uploads with storage_path
```

### Refactoring for Complexity

```
Refactor [function] to reduce cyclomatic complexity.

Requirements:
- Break into helper functions (max complexity 10)
- Each function should do ONE thing
- Maintain existing functionality
- Add proper type hints
- Update tests if needed
```

## Tips for Effective Prompts

1. **Include Context**: Reference specific files, line numbers, or functions
2. **Specify Standards**: Mention which CAR Platform standards apply
3. **Request Verification**: Ask Cursor to verify compliance after changes
4. **Be Iterative**: Break large changes into smaller, focused prompts
5. **Test Requirements**: Specify testing requirements (unit, integration, property-based)

## Example Workflow

1. **Identify Issue**: "The document upload endpoint doesn't upload files to storage"
2. **Reference Standards**: "@.cursorrules"
3. **Provide Specific Requirements**: List exact requirements (bucket names, paths, etc.)
4. **Request Implementation**: Ask Cursor to fix the issue
5. **Verify Compliance**: "@.cursorrules - Verify compliance"
6. **Review Changes**: Check that all requirements are met

## Notes

- Always test changes after Cursor makes modifications
- Review generated code for compliance with .cursorrules
- Don't assume Cursor will remember previous context - be explicit
- Use file references (@filename) to provide context
- Break complex tasks into smaller, focused prompts
