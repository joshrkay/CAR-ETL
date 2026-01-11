"""
PII Redactor - Understanding Plane

Redacts PII with multiple modes: mask, hash, or none.
Includes audit logging for compliance.
"""

import hashlib
import logging
from enum import Enum

from presidio_analyzer import RecognizerResult
from presidio_anonymizer import AnonymizerEngine
from presidio_anonymizer.entities import OperatorConfig

from src.extraction.pii_detector import detect_pii

logger = logging.getLogger(__name__)


class RedactionMode(str, Enum):
    """Redaction mode options."""

    MASK = "mask"  # Replace with [REDACTED]
    HASH = "hash"  # Replace with hash (reversible with key)
    NONE = "none"  # No redaction (internal use only)


class RedactedEntity:
    """Information about a redacted entity."""

    def __init__(
        self,
        entity_type: str,
        original_text: str,
        redacted_text: str,
        start: int,
        end: int,
        mode: RedactionMode,
    ):
        self.entity_type = entity_type
        self.original_text = original_text
        self.redacted_text = redacted_text
        self.start = start
        self.end = end
        self.mode = mode

    def to_dict(self) -> dict[str, int | str]:
        """Convert to dictionary for logging."""
        return {
            "entity_type": self.entity_type,
            "original_length": len(self.original_text),
            "redacted_length": len(self.redacted_text),
            "start": self.start,
            "end": self.end,
            "mode": self.mode.value,
        }


def _get_anonymizer_operators(mode: RedactionMode) -> dict[str, OperatorConfig]:
    """
    Get anonymizer operator configuration for redaction mode.

    Args:
        mode: Redaction mode

    Returns:
        Dictionary of operator configurations
    """
    if mode == RedactionMode.MASK:
        return {
            "DEFAULT": OperatorConfig(operator_name="replace", params={"new_value": "[REDACTED]"}),
        }
    elif mode == RedactionMode.HASH:
        # Use hash operator from Presidio
        return {
            "DEFAULT": OperatorConfig(operator_name="hash"),
        }
    elif mode == RedactionMode.NONE:
        # Return empty - no redaction
        return {}
    else:
        raise ValueError(f"Unknown redaction mode: {mode}")


def _hash_text(text: str, salt: str | None = None) -> str:
    """
    Hash text with optional salt.

    Args:
        text: Text to hash
        salt: Optional salt (for reversibility with key)

    Returns:
        Hashed text (first 16 chars of hex digest)
    """
    if salt:
        text_to_hash = f"{salt}:{text}"
    else:
        text_to_hash = text

    hash_obj = hashlib.sha256(text_to_hash.encode("utf-8"))
    return hash_obj.hexdigest()[:16]


def redact_pii(
    text: str,
    mode: RedactionMode = RedactionMode.MASK,
    language: str = "en",
    entities: list[str] | None = None,
) -> tuple[str, list[RedactedEntity]]:
    """
    Detect and redact PII from text.

    Args:
        text: Text to redact
        mode: Redaction mode (mask, hash, none)
        language: Language code (default: 'en')
        entities: Specific entity types to detect (None = all)

    Returns:
        Tuple of (redacted_text, list of RedactedEntity objects)

    Raises:
        ValueError: If mode is invalid
    """
    if not text or not text.strip():
        return text, []

    if mode == RedactionMode.NONE:
        # No redaction - return original
        logger.debug("Redaction mode is 'none' - skipping redaction")
        return text, []

    # Detect PII (with CRE exceptions)
    results = detect_pii(text, language=language, entities=entities)

    if not results:
        return text, []

    # Apply redaction based on mode
    redacted_entities: list[RedactedEntity] = []
    redacted_text: str

    if mode == RedactionMode.MASK:
        redacted_text = _apply_mask_redaction(text, results, redacted_entities, mode)
    elif mode == RedactionMode.HASH:
        redacted_text = _apply_hash_redaction(text, results, redacted_entities, mode)
    else:
        raise ValueError(f"Unsupported redaction mode: {mode}")

    # Audit logging
    _log_redaction_audit(text, redacted_text, redacted_entities, mode)

    return redacted_text, redacted_entities


def _apply_mask_redaction(
    text: str,
    results: list[RecognizerResult],
    redacted_entities: list[RedactedEntity],
    mode: RedactionMode,
) -> str:
    """
    Apply mask redaction to text.

    Args:
        text: Original text
        results: PII detection results
        redacted_entities: List to populate with redacted entities
        mode: Redaction mode

    Returns:
        Redacted text
    """
    anonymizer = AnonymizerEngine()
    operators = _get_anonymizer_operators(mode)
    anonymized = anonymizer.anonymize(
        text=text,
        analyzer_results=results,
        operators=operators,
    )

    # Build RedactedEntity list
    for result in results:
        entity_text = text[result.start : result.end]
        redacted_entities.append(
            RedactedEntity(
                entity_type=result.entity_type,
                original_text=entity_text,
                redacted_text="[REDACTED]",
                start=result.start,
                end=result.end,
                mode=mode,
            )
        )

    return anonymized.text


def _apply_hash_redaction(
    text: str,
    results: list[RecognizerResult],
    redacted_entities: list[RedactedEntity],
    mode: RedactionMode,
) -> str:
    """
    Apply hash redaction to text.

    Args:
        text: Original text
        results: PII detection results
        redacted_entities: List to populate with redacted entities
        mode: Redaction mode

    Returns:
        Redacted text
    """
    anonymizer = AnonymizerEngine()
    operators = _get_anonymizer_operators(mode)
    anonymized = anonymizer.anonymize(
        text=text,
        analyzer_results=results,
        operators=operators,
    )

    # Build RedactedEntity list
    for result in results:
        entity_text = text[result.start : result.end]
        hashed = _hash_text(entity_text)
        redacted_entities.append(
            RedactedEntity(
                entity_type=result.entity_type,
                original_text=entity_text,
                redacted_text=hashed,
                start=result.start,
                end=result.end,
                mode=mode,
            )
        )

    return anonymized.text


def _log_redaction_audit(
    original_text: str,
    redacted_text: str,
    entities: list[RedactedEntity],
    mode: RedactionMode,
) -> None:
    """
    Log redaction activity for audit compliance.

    Args:
        original_text: Original text
        redacted_text: Redacted text
        entities: List of redacted entities
        mode: Redaction mode used
    """
    if not entities:
        return

    # Count entities by type
    entity_counts: dict[str, int] = {}
    for entity in entities:
        entity_counts[entity.entity_type] = (
            entity_counts.get(entity.entity_type, 0) + 1
        )

    logger.info(
        "PII redaction performed",
        extra={
            "original_length": len(original_text),
            "redacted_length": len(redacted_text),
            "entities_redacted": len(entities),
            "entity_types": list(entity_counts.keys()),
            "entity_counts": entity_counts,
            "redaction_mode": mode.value,
            # SECURITY: Do not log actual PII content
        },
    )
