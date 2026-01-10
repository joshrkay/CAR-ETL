"""
PII Protection Utilities - Security Layer

Provides utilities for protecting PII in logs and other contexts.
"""

import hashlib
import logging

logger = logging.getLogger(__name__)


def hash_email(email: str) -> str:
    """
    Hash email address for logging (PII protection).

    Uses SHA-256 and returns first 16 characters for readability.
    This allows correlation of logs without exposing actual email addresses.

    Args:
        email: Email address to hash

    Returns:
        First 16 characters of SHA-256 hash (hex)

    Example:
        hash_email("user@example.com") -> "a1b2c3d4e5f6g7h8"
    """
    if not email:
        return "empty"

    # Normalize email (lowercase, strip whitespace)
    normalized = email.lower().strip()

    # Hash using SHA-256
    hash_obj = hashlib.sha256(normalized.encode("utf-8"))
    hash_hex = hash_obj.hexdigest()

    # Return first 16 characters for readability
    return hash_hex[:16]


def hash_string(value: str, length: int = 16) -> str:
    """
    Hash any string value for logging (PII protection).

    Args:
        value: String value to hash
        length: Length of hash to return (default: 16)

    Returns:
        First N characters of SHA-256 hash (hex)
    """
    if not value:
        return "empty"

    normalized = value.lower().strip()
    hash_obj = hashlib.sha256(normalized.encode("utf-8"))
    hash_hex = hash_obj.hexdigest()

    return hash_hex[:length]
