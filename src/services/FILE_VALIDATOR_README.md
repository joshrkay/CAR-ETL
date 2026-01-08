# File Validator Service

## Overview

The File Validator Service provides secure file validation for the CAR Platform's Ingestion Plane. It implements defense-in-depth security by validating file content against claimed MIME types using magic byte verification and structural validation.

## Architecture Layer

**Ingestion Plane** - Security boundary component that validates uploaded files before they enter the system.

## Key Features

### 1. Magic Byte Validation

Verifies file content matches the claimed MIME type by checking file signatures:

```python
from src.services.file_validator import FileValidator

validator = FileValidator()
result = validator.validate_file(content, "application/pdf")

if result.valid:
    print(f"Valid {result.mime_type} file, size: {result.file_size} bytes")
else:
    print(f"Validation failed: {result.errors}")
```

### 2. Supported File Types

| MIME Type | Magic Bytes | Additional Validation |
|-----------|-------------|----------------------|
| `application/pdf` | `%PDF` | None |
| `application/vnd.openxmlformats-officedocument.wordprocessingml.document` | `PK\x03\x04` | Office Open XML structure |
| `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet` | `PK\x03\x04` | Office Open XML structure |
| `image/png` | `\x89PNG` | None |
| `image/jpeg` | `\xff\xd8\xff` | None |
| `text/plain` | None | No magic byte validation |
| `text/csv` | None | No magic byte validation |

### 3. Office Document Validation

For DOCX and XLSX files, the validator performs additional structural checks:

- Verifies the file is a valid ZIP archive
- Checks for presence of `[Content_Types].xml`
- Validates the content type matches the claimed MIME type

This prevents:
- Corrupted ZIP files disguised as Office documents
- HTML/script files renamed with .docx/.xlsx extensions
- Cross-type confusion (XLSX claimed as DOCX)

### 4. Size Limit Enforcement

```python
# Default 100MB limit
validator = FileValidator()

# Custom limit (10MB)
validator = FileValidator(max_file_size=10 * 1024 * 1024)

# Tenant-specific limit
from src.services.file_validator import validate_file_with_tenant_config

result = validate_file_with_tenant_config(
    content=file_bytes,
    claimed_mime="application/pdf",
    tenant_max_size=tenant.settings.max_file_size
)
```

## Security Guarantees

### Defense in Depth

1. **Never Trust File Extensions**: Only magic bytes are used for validation
2. **Never Trust Client MIME Types**: Content is verified against claimed type
3. **Structural Validation**: Office documents are verified to be legitimate
4. **Size Limits**: Prevents resource exhaustion attacks

### What This Service DOES NOT Do

- **Content Inspection**: Does not scan for malicious content within valid files
- **PII Redaction**: Redaction happens in the Understanding Plane
- **Virus Scanning**: Antivirus should be a separate layer
- **Deep Format Validation**: Only validates file headers and basic structure

## Usage Examples

### Basic Validation

```python
from src.services.file_validator import FileValidator

validator = FileValidator()

# Validate a PDF
with open("document.pdf", "rb") as f:
    content = f.read()
    result = validator.validate_file(content, "application/pdf")
    
if not result.valid:
    raise ValueError(f"Invalid file: {', '.join(result.errors)}")
```

### Tenant-Specific Validation

```python
from src.services.file_validator import validate_file_with_tenant_config

# Get tenant configuration
tenant = get_tenant_by_id(tenant_id)
max_size = tenant.settings.get("max_file_size", None)

# Validate with tenant limits
result = validate_file_with_tenant_config(
    content=uploaded_file_bytes,
    claimed_mime=uploaded_mime_type,
    tenant_max_size=max_size
)

if not result.valid:
    return {"error": "File validation failed", "details": result.errors}
```

### Integration with Upload Handler

```python
from fastapi import UploadFile, HTTPException
from src.services.file_validator import FileValidator

async def handle_file_upload(file: UploadFile, tenant_id: str):
    # Read file content
    content = await file.read()
    
    # Get tenant config
    tenant = await get_tenant(tenant_id)
    max_size = tenant.settings.get("max_file_size", 100 * 1024 * 1024)
    
    # Validate
    validator = FileValidator(max_file_size=max_size)
    result = validator.validate_file(content, file.content_type)
    
    if not result.valid:
        raise HTTPException(
            status_code=400,
            detail={
                "message": "File validation failed",
                "errors": result.errors
            }
        )
    
    # Proceed with ingestion
    return await ingest_file(content, result.mime_type, tenant_id)
```

## Validation Result Model

```python
class ValidationResult(BaseModel):
    valid: bool              # Overall validation status
    mime_type: str          # Claimed MIME type
    file_size: int          # File size in bytes
    errors: list[str] = []  # List of validation errors
```

## Error Messages

| Error | Cause | Resolution |
|-------|-------|-----------|
| `File size X exceeds maximum Y bytes` | File too large | Reduce file size or request limit increase |
| `Unsupported MIME type: X` | MIME type not in allowlist | Use supported file type |
| `Magic bytes do not match claimed MIME type` | File content doesn't match extension | Verify file is correct type |
| `Missing [Content_Types].xml` | Invalid Office document | Use valid DOCX/XLSX file |
| `Content types do not match claimed MIME type` | Wrong Office document type | Verify file extension matches content |
| `Corrupted ZIP structure` | Damaged Office document | Re-export from Office application |

## Testing

The service includes comprehensive test coverage:

- **Magic Byte Validation**: 8 tests
- **Office Document Validation**: 5 tests
- **Size Limit Validation**: 6 tests
- **Malicious File Detection**: 5 tests
- **Unsupported MIME Types**: 2 tests
- **Edge Cases**: 5 tests
- **Property-Based Tests**: 4 tests
- **Model Tests**: 2 tests

Run tests:

```bash
python -m pytest tests/test_file_validator.py -v
```

## Security Considerations

### Known Limitations

1. **Text Files**: CSV and plain text files have no magic byte validation
   - Malicious scripts can be uploaded as CSV
   - Content filtering must happen at a different layer

2. **Polyglot Files**: Files valid in multiple formats may pass validation
   - Example: A file that's both valid PDF and valid ZIP
   - Mitigation: Strict MIME type enforcement at API layer

3. **Embedded Content**: No validation of embedded objects
   - PDFs with embedded JavaScript
   - Office documents with macros
   - Mitigation: Use separate content scanning layer

### Recommended Additional Layers

1. **Antivirus Scanning**: ClamAV or similar for malware detection
2. **Content Inspection**: Deep format validation for critical file types
3. **Sandboxing**: Execute/render files in isolated environment
4. **PII Redaction**: Presidio pipeline in Understanding Plane

## Configuration

### Environment Variables

None required - configuration is code-based.

### Tenant Settings

Tenants can configure:

```json
{
  "settings": {
    "max_file_size": 52428800  // 50MB in bytes
  }
}
```

### Adding New File Types

To add support for a new file type:

1. Add MIME type and magic bytes to `MAGIC_BYTES` dict
2. Implement additional validation if needed (see `_validate_office_document`)
3. Add tests for the new file type
4. Update this README

Example:

```python
MAGIC_BYTES = {
    # ... existing types ...
    "application/zip": [b"PK\x03\x04"],
}
```

## Compliance

### Standards Adherence

- **YAGNI**: Only validates what's explicitly required
- **Single Responsibility**: Only handles file validation
- **Cyclomatic Complexity**: All functions < 10
- **Strict Typing**: No `any` or `unknown` types
- **Error Handling**: All errors logged with context

### Architectural Boundaries

- **Ingestion Plane**: ✅ Validates incoming files
- **Does NOT**: Process, extract, or redact content (Understanding Plane)
- **Does NOT**: Store or manage files (Data Plane)
- **Does NOT**: Handle authentication (Control Plane)

## Performance

### Benchmarks

- Magic byte check: O(1) - checks first few bytes only
- Office validation: O(n) where n = ZIP directory size (not full file)
- Memory: Loads full file into memory (consider streaming for very large files)

### Optimization Notes

For files > 100MB, consider:
- Streaming validation (read first N bytes only)
- Async validation for multiple files
- Caching validation results by content hash

## Changelog

### v1.0.0 (2026-01-07)

- Initial implementation
- Magic byte validation for 7 file types
- Office Open XML structural validation
- Configurable size limits
- Comprehensive test suite with 37 tests
