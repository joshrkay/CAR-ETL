"""
Redaction Service - Understanding Plane

Provides PII redaction using Presidio before persisting data.
This service must be called before any data persistence or transmission.
"""

import logging
from typing import Optional
from presidio_analyzer import AnalyzerEngine
from presidio_anonymizer import AnonymizerEngine

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
        RuntimeError: If redaction fails and fail_mode is strict
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
        RuntimeError: If redaction fails
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
