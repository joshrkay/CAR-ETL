"""
Error Sanitizer - Security Service

Sanitizes error messages to remove PII before logging or persistence.
CRITICAL: Must be called before any error logging or database storage.
"""

import re
from typing import Optional


# PII patterns to redact from error messages
PII_PATTERNS = [
    # Email addresses
    (r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', '[EMAIL]'),
    # Phone numbers (various formats)
    (r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b', '[PHONE]'),
    (r'\b\(\d{3}\)\s*\d{3}[-.]?\d{4}\b', '[PHONE]'),
    # SSN
    (r'\b\d{3}-\d{2}-\d{4}\b', '[SSN]'),
    # Credit card (simple pattern)
    (r'\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b', '[CARD]'),
    # IPv4 addresses
    (r'\b(?:\d{1,3}\.){3}\d{1,3}\b', '[IP]'),
    # UUIDs (may contain document/user IDs)
    (r'\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b', '[UUID]'),
    # URLs with potential query params containing PII
    (r'https?://[^\s]+\?[^\s]+', '[URL]'),
    # File paths that may contain usernames
    (r'/(?:home|Users)/[^/\s]+', '/[USER]'),
    # Common PII field patterns in error messages
    (r'(?i)(?:name|address|city|street|zip)[\s:=]+[\'"]?([^\'"}\s,]+)', r'\1=[REDACTED]'),
]


def sanitize_error_message(error_message: str) -> str:
    """
    Remove PII from error message using pattern matching.

    This is a defense-in-depth measure. It does NOT replace proper
    redaction (Presidio) for document content, but provides safety
    for error messages that might leak PII.

    Args:
        error_message: Raw error message that may contain PII

    Returns:
        Sanitized error message with PII patterns replaced

    Examples:
        >>> sanitize_error_message("Failed to parse file for john@example.com")
        'Failed to parse file for [EMAIL]'

        >>> sanitize_error_message("User 555-123-4567 not found")
        'User [PHONE] not found'
    """
    if not error_message:
        return error_message

    sanitized = error_message

    # Apply each pattern
    for pattern, replacement in PII_PATTERNS:
        sanitized = re.sub(pattern, replacement, sanitized)

    return sanitized


def sanitize_exception(exception: Exception) -> str:
    """
    Sanitize exception message for safe logging.

    Args:
        exception: Exception instance

    Returns:
        Sanitized error message string

    Examples:
        >>> ex = ValueError("Invalid email: test@example.com")
        >>> sanitize_exception(ex)
        'Invalid email: [EMAIL]'
    """
    error_message = str(exception)
    return sanitize_error_message(error_message)


def get_safe_error_context(exception: Exception) -> dict:
    """
    Extract safe logging context from exception.

    Returns metadata about the exception without PII.

    Args:
        exception: Exception instance

    Returns:
        Dictionary with safe error context for logging

    Example:
        >>> ex = ValueError("Invalid data")
        >>> get_safe_error_context(ex)
        {'error_type': 'ValueError', 'error_class': 'builtins'}
    """
    return {
        "error_type": type(exception).__name__,
        "error_class": type(exception).__module__,
        "has_cause": exception.__cause__ is not None,
        "has_context": exception.__context__ is not None,
    }


def truncate_error_message(message: str, max_length: int = 500) -> str:
    """
    Truncate error message to prevent log bloat.

    Args:
        message: Error message
        max_length: Maximum length (default: 500)

    Returns:
        Truncated message with ellipsis if needed

    Examples:
        >>> truncate_error_message("x" * 600, 100)
        'xxxx...xxx (truncated, 600 chars total)'
    """
    if len(message) <= max_length:
        return message

    # Show first and last parts
    prefix_len = max_length // 2
    suffix_len = max_length // 2 - 20  # Reserve space for truncation notice

    return (
        f"{message[:prefix_len]}...{message[-suffix_len:]} "
        f"(truncated, {len(message)} chars total)"
    )


def get_loggable_error(
    exception: Exception,
    max_length: int = 500,
    include_context: bool = True,
) -> dict:
    """
    Get complete loggable error information.

    Combines sanitization, truncation, and context extraction.

    Args:
        exception: Exception instance
        max_length: Maximum message length (default: 500)
        include_context: Whether to include error context (default: True)

    Returns:
        Dictionary ready for structured logging

    Example:
        >>> ex = ValueError("Invalid email: test@example.com")
        >>> result = get_loggable_error(ex)
        >>> result['sanitized_message']
        'Invalid email: [EMAIL]'
        >>> result['error_type']
        'ValueError'
    """
    sanitized = sanitize_exception(exception)
    truncated = truncate_error_message(sanitized, max_length)

    result = {
        "sanitized_message": truncated,
        "message_length": len(str(exception)),
    }

    if include_context:
        result.update(get_safe_error_context(exception))

    return result
