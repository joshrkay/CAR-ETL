# PII Detection and Redaction Usage Guide

## Overview

The CAR Platform provides CRE-aware PII detection and redaction with multiple redaction modes and audit logging.

## Key Features

1. **CRE-Specific Exceptions**: Property addresses, company names, and business contacts are NOT redacted
2. **Multiple Redaction Modes**: mask, hash, or none
3. **Audit Logging**: All redactions are logged for compliance
4. **PII Types Detected**: SSN, Phone, Email, Bank Account, Credit Card

## Usage

### Basic Redaction (Mask Mode)

```python
from src.extraction.redactor import redact_pii, RedactionMode

text = "Contact John Doe at john.doe@example.com or call (555) 123-4567."
redacted, entities = redact_pii(text, mode=RedactionMode.MASK)

print(redacted)
# "Contact John Doe at [REDACTED] or call [REDACTED]."

print(f"Redacted {len(entities)} entities")
# "Redacted 2 entities"
```

### Hash Mode (Reversible)

```python
from src.extraction.redactor import redact_pii, RedactionMode

text = "SSN: 123-45-6789"
redacted, entities = redact_pii(text, mode=RedactionMode.HASH)

print(redacted)
# "SSN: a1b2c3d4e5f6g7h8"

# Entity information available for audit
for entity in entities:
    print(f"{entity.entity_type}: {entity.original_text} -> {entity.redacted_text}")
```

### No Redaction (Internal Use)

```python
from src.extraction.redactor import redact_pii, RedactionMode

text = "Contact john.doe@example.com"
redacted, entities = redact_pii(text, mode=RedactionMode.NONE)

assert text == redacted  # No redaction performed
assert len(entities) == 0
```

### PII Detection Only

```python
from src.extraction.pii_detector import detect_pii

text = "Contact john.doe@example.com or call (555) 123-4567."
results = detect_pii(text)

for result in results:
    print(f"{result.entity_type}: {text[result.start:result.end]}")
    # "EMAIL_ADDRESS: john.doe@example.com"
    # "PHONE_NUMBER: (555) 123-4567"
```

## CRE-Specific Exceptions

The system automatically excludes from redaction:

1. **Property Addresses**: Detected when near terms like "property address", "premises address", etc.
2. **Company Names**: Detected when near terms like "tenant name", "landlord name", or contains business suffixes (LLC, Corp, Inc)
3. **Business Contacts**: Emails/phones from known CRE business domains (CBRE, JLL, etc.) or near business context

### Example: Property Address Exception

```python
text = "Property address: 123 Main Street, New York, NY 10001"
redacted, entities = redact_pii(text, mode=RedactionMode.MASK)

# Property address is NOT redacted (CRE exception)
assert "123 Main Street" in redacted
assert len(entities) == 0  # No PII detected
```

### Example: Company Name Exception

```python
text = "Tenant name: ABC Corporation LLC"
redacted, entities = redact_pii(text, mode=RedactionMode.MASK)

# Company name is NOT redacted (CRE exception)
assert "ABC Corporation LLC" in redacted
```

## Configuration

Edit `config/pii_patterns.yaml` to customize:

- PII entity types to detect
- CRE exception patterns
- Business email domains
- Redaction mode defaults

## Audit Logging

All redactions are automatically logged with:

- Original text length
- Redacted text length
- Number of entities redacted
- Entity types and counts
- Redaction mode used

**Security**: Actual PII content is NOT logged (only metadata).

## Integration with Extraction

The redaction system integrates with the extraction pipeline:

```python
from src.extraction.redactor import redact_pii, RedactionMode
from src.extraction.extractor import FieldExtractor

# Redact before extraction
document_text = "..."
redacted_text, _ = redact_pii(document_text, mode=RedactionMode.MASK)

# Extract from redacted text
extractor = FieldExtractor()
result = await extractor.extract_fields(redacted_text, industry="cre", document_type="lease")
```

## Testing

Run tests:

```bash
pytest tests/test_pii.py -v
```

Property-based tests verify no PII leakage across thousands of random inputs.

## Security Notes

1. **Strict Mode**: By default, redaction failures raise exceptions (fail closed)
2. **No PII in Logs**: Actual PII content is never logged
3. **Audit Trail**: All redactions are logged for compliance
4. **CRE Context**: Business information is preserved for CRE workflows
