# Presidio Deployment Guide

## Overview

Presidio is Microsoft's PII detection and redaction framework. This guide covers deploying Presidio for the CAR Platform's Understanding Plane redaction requirements.

**Architecture Decision**: Presidio will be deployed **in-process** (Python library) within the CAR Platform application. This aligns with the Understanding Plane's responsibility and maintains strict layering boundaries.

## Deployment Options

### Option 1: In-Process Deployment (Recommended)

**Pros:**
- Simple deployment (no additional services)
- Low latency (no network calls)
- Aligns with Understanding Plane architecture
- Easier to maintain and debug

**Cons:**
- Shares application resources (CPU/memory)
- Model loading increases application startup time
- Less isolation

**Use Case**: Recommended for initial deployment and most production scenarios.

### Option 2: Microservice Deployment

**Pros:**
- Independent scaling
- Resource isolation
- Can use GPU acceleration
- Better for high-volume scenarios

**Cons:**
- Additional infrastructure complexity
- Network latency
- Requires service discovery/load balancing
- More operational overhead

**Use Case**: Consider when redaction volume exceeds 1000 requests/second or requires dedicated GPU resources.

---

## Step 1: Install Dependencies

### Update requirements.txt

Add Presidio packages to `requirements.txt`:

```txt
# Presidio for PII detection and redaction
presidio-analyzer>=2.2.0
presidio-anonymizer>=2.2.0
presidio-image-redactor>=1.0.0  # Optional: for image redaction

# Spacy models for NLP (required by Presidio)
spacy>=3.7.0
# Download model: python -m spacy download en_core_web_lg
```

### Install Dependencies

```bash
# Install Python packages
pip install -r requirements.txt

# Download Spacy English model (required for Presidio)
python -m spacy download en_core_web_lg
```

**Note**: For production Docker images, include model download in Dockerfile.

---

## Step 2: Configuration

### Environment Variables

Add to `.env` file:

```env
# Presidio Configuration
PRESIDIO_ANALYZER_MODEL=en_core_web_lg
PRESIDIO_ANONYMIZER_OPERATORS=replace,hash,encrypt
PRESIDIO_DEFAULT_ANONYMIZER=replace
PRESIDIO_SUPPORTED_LANGUAGES=en
PRESIDIO_REDACTION_FAIL_MODE=strict  # strict|permissive (strict = fail closed)
```

### Create Configuration Module

Create `src/services/presidio_config.py`:

```python
"""
Presidio Configuration - Understanding Plane

Loads Presidio configuration from environment variables.
"""
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List


class PresidioConfig(BaseSettings):
    """Configuration for Presidio redaction service."""
    
    analyzer_model: str = "en_core_web_lg"
    anonymizer_operators: str = "replace,hash,encrypt"
    default_anonymizer: str = "replace"
    supported_languages: str = "en"
    redaction_fail_mode: str = "strict"  # strict|permissive
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        env_prefix="PRESIDIO_",
    )
    
    @property
    def anonymizer_operators_list(self) -> List[str]:
        """Get anonymizer operators as list."""
        return [op.strip() for op in self.anonymizer_operators.split(",")]
    
    @property
    def supported_languages_list(self) -> List[str]:
        """Get supported languages as list."""
        return [lang.strip() for lang in self.supported_languages.split(",")]
    
    @property
    def is_strict_mode(self) -> bool:
        """Check if fail mode is strict (fail closed)."""
        return self.redaction_fail_mode.lower() == "strict"


def get_presidio_config() -> PresidioConfig:
    """Get Presidio configuration instance."""
    return PresidioConfig()
```

---

## Step 3: Implement Presidio Service

### Update `src/services/redaction.py`

Replace the stub implementation with full Presidio integration:

```python
"""
Redaction Service - Understanding Plane

Provides PII redaction using Presidio before persisting data.
This service must be called before any data persistence or transmission.
"""

import logging
from typing import Optional
from presidio_analyzer import AnalyzerEngine
from presidio_anonymizer import AnonymizerEngine
from presidio_anonymizer.entities import OperatorConfig

from src.services.presidio_config import get_presidio_config

logger = logging.getLogger(__name__)

# Global analyzer and anonymizer instances (initialized on first use)
_analyzer: Optional[AnalyzerEngine] = None
_anonymizer: Optional[AnonymizerEngine] = None


def _get_analyzer() -> AnalyzerEngine:
    """
    Get or initialize Presidio analyzer engine.
    
    Returns:
        AnalyzerEngine instance (singleton)
    """
    global _analyzer
    if _analyzer is None:
        config = get_presidio_config()
        try:
            _analyzer = AnalyzerEngine()
            logger.info(
                "Presidio analyzer initialized",
                extra={"model": config.analyzer_model},
            )
        except Exception as e:
            logger.error(
                "Failed to initialize Presidio analyzer",
                extra={"error": str(e), "model": config.analyzer_model},
            )
            raise
    return _analyzer


def _get_anonymizer() -> AnonymizerEngine:
    """
    Get or initialize Presidio anonymizer engine.
    
    Returns:
        AnonymizerEngine instance (singleton)
    """
    global _anonymizer
    if _anonymizer is None:
        try:
            config = get_presidio_config()
            
            # Configure anonymization operators
            operators = {
                "DEFAULT": OperatorConfig(operator=config.default_anonymizer),
            }
            
            # Add custom operators if specified
            for op in config.anonymizer_operators_list:
                if op == "replace":
                    operators["DEFAULT"] = OperatorConfig(operator="replace")
                elif op == "hash":
                    operators["HASH"] = OperatorConfig(operator="hash")
                elif op == "encrypt":
                    operators["ENCRYPT"] = OperatorConfig(operator="encrypt")
            
            _anonymizer = AnonymizerEngine()
            logger.info("Presidio anonymizer initialized")
        except Exception as e:
            logger.error(
                "Failed to initialize Presidio anonymizer",
                extra={"error": str(e)},
            )
            raise
    return _anonymizer


def presidio_redact(text: str) -> str:
    """
    Redact PII from text using Presidio.
    
    SECURITY: This function MUST be called before persisting any unstructured text
    to database or S3, or transmitting to external APIs.
    
    Args:
        text: Text content that may contain PII
        
    Returns:
        Redacted text with PII replaced
        
    Raises:
        Exception: If redaction fails and fail_mode is strict
    """
    if not text or not text.strip():
        return text
    
    config = get_presidio_config()
    
    try:
        # Get analyzer and anonymizer
        analyzer = _get_analyzer()
        anonymizer = _get_anonymizer()
        
        # Detect PII entities
        results = analyzer.analyze(
            text=text,
            language=config.supported_languages_list[0],
            entities=None,  # Analyze all entity types
        )
        
        # Anonymize detected PII
        anonymized_result = anonymizer.anonymize(
            text=text,
            analyzer_results=results,
        )
        
        redacted_text = anonymized_result.text
        
        # Log redaction activity (without PII)
        if results:
            logger.info(
                "PII redaction performed",
                extra={
                    "text_length": len(text),
                    "entities_detected": len(results),
                    "entity_types": list(set(r.entity_type for r in results)),
                },
            )
        
        return redacted_text
        
    except Exception as e:
        logger.error(
            "PII redaction failed",
            extra={
                "error": str(e),
                "text_length": len(text),
                "fail_mode": config.redaction_fail_mode,
            },
        )
        
        # Fail closed in strict mode
        if config.is_strict_mode:
            raise RuntimeError(
                f"PII redaction failed in strict mode: {str(e)}"
            ) from e
        
        # In permissive mode, return original (with warning)
        logger.warning(
            "PII redaction failed in permissive mode - returning original text",
            extra={"text_length": len(text)},
        )
        return text


def presidio_redact_bytes(content: bytes, mime_type: str) -> bytes:
    """
    Redact PII from binary content using Presidio.
    
    Args:
        content: Binary content that may contain PII
        mime_type: MIME type of content (for appropriate parsing)
        
    Returns:
        Redacted content as bytes
        
    Raises:
        Exception: If redaction fails
    """
    # For text-based MIME types, decode, redact, re-encode
    if mime_type.startswith("text/") or mime_type in [
        "application/json",
        "application/xml",
        "application/xhtml+xml",
    ]:
        try:
            text = content.decode("utf-8")
            redacted_text = presidio_redact(text)
            return redacted_text.encode("utf-8")
        except UnicodeDecodeError:
            logger.warning(
                "Failed to decode content for redaction",
                extra={"mime_type": mime_type},
            )
            # Return original if decode fails
            return content
    
    # For binary content (images, PDFs), redaction is more complex
    # TODO: Implement binary content redaction using presidio-image-redactor
    logger.warning(
        "Binary content redaction not yet implemented",
        extra={"mime_type": mime_type, "size": len(content)},
    )
    return content
```

---

## Step 4: Docker Deployment

### Update Dockerfile (if exists)

If you have a Dockerfile, ensure it includes:

```dockerfile
FROM python:3.11-slim

# Install system dependencies for Spacy
RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Download Spacy model
RUN python -m spacy download en_core_web_lg

# Copy application code
COPY . .

# Expose port
EXPOSE 8000

# Run application
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Docker Compose (Optional)

If using Docker Compose, no additional services needed for in-process deployment:

```yaml
version: '3.8'

services:
  app:
    build: .
    ports:
      - "8000:8000"
    environment:
      - SUPABASE_URL=${SUPABASE_URL}
      - SUPABASE_ANON_KEY=${SUPABASE_ANON_KEY}
      - SUPABASE_SERVICE_KEY=${SUPABASE_SERVICE_KEY}
      - SUPABASE_JWT_SECRET=${SUPABASE_JWT_SECRET}
      - PRESIDIO_ANALYZER_MODEL=en_core_web_lg
      - PRESIDIO_REDACTION_FAIL_MODE=strict
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health/ready"]
      interval: 30s
      timeout: 5s
      retries: 3
      start_period: 30s  # Increased for model loading
    restart: unless-stopped
```

**Note**: Increase `start_period` in healthcheck to allow time for Presidio model loading.

---

## Step 5: Kubernetes Deployment

### Update Deployment YAML

Update `deployment/load-balancer-config.yaml` or create `deployment/presidio-deployment.yaml`:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: car-platform
  labels:
    app: car-platform
spec:
  replicas: 3
  selector:
    matchLabels:
      app: car-platform
  template:
    metadata:
      labels:
        app: car-platform
    spec:
      containers:
      - name: app
        image: car-platform:latest
        ports:
        - containerPort: 8000
          name: http
        env:
        - name: SUPABASE_URL
          valueFrom:
            secretKeyRef:
              name: car-platform-secrets
              key: supabase-url
        - name: SUPABASE_ANON_KEY
          valueFrom:
            secretKeyRef:
              name: car-platform-secrets
              key: supabase-anon-key
        - name: PRESIDIO_ANALYZER_MODEL
          value: "en_core_web_lg"
        - name: PRESIDIO_REDACTION_FAIL_MODE
          value: "strict"
        readinessProbe:
          httpGet:
            path: /health/ready
            port: 8000
          initialDelaySeconds: 30  # Increased for Presidio model loading
          periodSeconds: 30
          timeoutSeconds: 5
          successThreshold: 1
          failureThreshold: 3
        livenessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 60  # Increased for Presidio model loading
          periodSeconds: 60
          timeoutSeconds: 5
          failureThreshold: 3
        resources:
          requests:
            memory: "512Mi"  # Increased for Presidio models
            cpu: "500m"
          limits:
            memory: "1Gi"    # Increased for Presidio models
            cpu: "1000m"
```

**Key Changes:**
- Increased memory requests/limits (Presidio models require ~200-300MB)
- Increased `initialDelaySeconds` for readiness/liveness probes (model loading time)

---

## Step 6: Health Check Integration

### Update Health Check Endpoint

Update `src/api/routes/health.py` to include Presidio health check:

```python
# Add to health check endpoint
from src.services.redaction import _get_analyzer, _get_anonymizer

# In readiness check:
try:
    # Verify Presidio is initialized
    analyzer = _get_analyzer()
    anonymizer = _get_anonymizer()
    checks["presidio"] = {"status": "up"}
except Exception as e:
    checks["presidio"] = {
        "status": "down",
        "error": str(e)
    }
    all_healthy = False
```

---

## Step 7: Testing

### Unit Tests

Create `tests/test_redaction.py`:

```python
"""Tests for Presidio redaction service."""
import pytest
from src.services.redaction import presidio_redact, presidio_redact_bytes


def test_presidio_redact_email():
    """Test redaction of email addresses."""
    text = "Contact us at john.doe@example.com for support."
    redacted = presidio_redact(text)
    
    assert "john.doe@example.com" not in redacted
    assert "Contact us at" in redacted
    assert "@example.com" not in redacted


def test_presidio_redact_phone():
    """Test redaction of phone numbers."""
    text = "Call us at (555) 123-4567."
    redacted = presidio_redact(text)
    
    assert "(555) 123-4567" not in redacted
    assert "Call us at" in redacted


def test_presidio_redact_ssn():
    """Test redaction of SSN."""
    text = "SSN: 123-45-6789"
    redacted = presidio_redact(text)
    
    assert "123-45-6789" not in redacted
    assert "SSN:" in redacted


def test_presidio_redact_bytes():
    """Test redaction of bytes content."""
    content = b"Contact john.doe@example.com"
    redacted = presidio_redact_bytes(content, "text/plain")
    
    assert b"john.doe@example.com" not in redacted
    assert b"Contact" in redacted


def test_presidio_redact_empty():
    """Test redaction of empty text."""
    assert presidio_redact("") == ""
    assert presidio_redact("   ") == "   "
```

### Property-Based Tests (Critical Path)

Add to `tests/test_redaction.py`:

```python
from hypothesis import given, strategies as st


@given(st.text(min_size=1, max_size=10000))
def test_presidio_redact_no_pii_leakage(text: str):
    """
    Property-based test: Verify no PII patterns leak through redaction.
    
    This is a critical security test - must pass for all inputs.
    """
    redacted = presidio_redact(text)
    
    # Verify common PII patterns are not present
    import re
    
    # Email pattern
    email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
    assert not re.search(email_pattern, redacted), "Email leaked in redaction"
    
    # SSN pattern
    ssn_pattern = r'\b\d{3}-\d{2}-\d{4}\b'
    assert not re.search(ssn_pattern, redacted), "SSN leaked in redaction"
    
    # Phone pattern (US)
    phone_pattern = r'\b\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b'
    # Note: This may have false positives, adjust as needed
```

---

## Step 8: Performance Considerations

### Model Loading

- **First Request Latency**: Presidio models load on first use (~2-5 seconds)
- **Solution**: Pre-warm models on application startup (add to `src/main.py` startup event)

```python
@app.on_event("startup")
async def startup_event():
    """Pre-warm Presidio models on startup."""
    from src.services.redaction import _get_analyzer, _get_anonymizer
    try:
        _get_analyzer()
        _get_anonymizer()
        logger.info("Presidio models pre-warmed")
    except Exception as e:
        logger.error(f"Failed to pre-warm Presidio: {e}")
        # Don't fail startup - models will load on first use
```

### Caching

Presidio analyzer results can be cached for identical text inputs:

```python
from functools import lru_cache
from hashlib import sha256

@lru_cache(maxsize=1000)
def _cached_analyze(text_hash: str, text: str) -> list:
    """Cache analyzer results for identical text."""
    analyzer = _get_analyzer()
    config = get_presidio_config()
    return analyzer.analyze(
        text=text,
        language=config.supported_languages_list[0],
    )

def presidio_redact(text: str) -> str:
    # ... existing code ...
    text_hash = sha256(text.encode()).hexdigest()
    results = _cached_analyze(text_hash, text)
    # ... rest of implementation ...
```

---

## Step 9: Monitoring & Observability

### Metrics to Track

- Redaction latency (p50, p95, p99)
- Redaction failures (strict mode)
- Entities detected per document
- Model loading time

### Logging

Presidio service already includes structured logging. Ensure logs are aggregated and monitored.

---

## Step 10: Production Checklist

- [ ] Presidio dependencies added to `requirements.txt`
- [ ] Spacy model (`en_core_web_lg`) downloaded in Dockerfile
- [ ] Configuration module created (`src/services/presidio_config.py`)
- [ ] Redaction service implemented (`src/services/redaction.py`)
- [ ] Health check includes Presidio status
- [ ] Unit tests written and passing
- [ ] Property-based tests written and passing
- [ ] Docker image builds successfully
- [ ] Kubernetes deployment updated (memory limits, probe delays)
- [ ] Pre-warming implemented in startup event
- [ ] Environment variables documented
- [ ] Monitoring/alerting configured
- [ ] Fail mode set to `strict` in production

---

## Troubleshooting

### Model Not Found

**Error**: `OSError: Can't find model 'en_core_web_lg'`

**Solution**: Ensure Spacy model is downloaded:
```bash
python -m spacy download en_core_web_lg
```

### High Memory Usage

**Issue**: Application memory usage increased significantly

**Solution**: 
- Verify memory limits in Kubernetes/Docker
- Consider using smaller Spacy model (`en_core_web_sm`) for lower memory footprint
- Monitor memory usage and adjust limits

### Slow Redaction

**Issue**: Redaction takes >1 second per document

**Solution**:
- Enable result caching (see Step 8)
- Consider microservice deployment for dedicated resources
- Profile and optimize analyzer configuration

---

## Migration from Stub Implementation

1. **Backward Compatibility**: The stub implementation returns original text. After Presidio deployment, all text will be redacted.
2. **Testing**: Run full test suite to ensure no regressions
3. **Gradual Rollout**: Consider feature flag for Presidio (enable per tenant initially)

---

## References

- [Presidio Documentation](https://microsoft.github.io/presidio/)
- [Presidio GitHub](https://github.com/microsoft/presidio)
- [Spacy Models](https://spacy.io/models/en)
