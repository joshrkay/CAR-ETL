"""
PII Detector - Understanding Plane

Detects PII in CRE documents with context-aware exceptions.
Property addresses, company names, and business contacts are NOT redacted.
"""

import logging
from typing import List, Optional, cast
from pathlib import Path
import yaml
from presidio_analyzer import AnalyzerEngine, RecognizerResult

logger = logging.getLogger(__name__)

# Load CRE exceptions configuration
_CONFIG_PATH = Path(__file__).parent.parent.parent / "config" / "pii_patterns.yaml"
_cre_exceptions: Optional[dict[str, object]] = None


def _load_cre_exceptions() -> dict[str, object]:
    """Load CRE exception patterns from configuration."""
    global _cre_exceptions
    if _cre_exceptions is None:
        try:
            with open(_CONFIG_PATH, "r", encoding="utf-8") as f:
                config = cast(dict[str, object], yaml.safe_load(f) or {})
                _cre_exceptions = cast(dict[str, object], config.get("cre_exceptions", {}))
        except Exception as e:
            logger.warning(
                "Failed to load CRE exceptions config, using defaults",
                extra={"error": str(e)},
            )
            _cre_exceptions = {}
    return _cre_exceptions


def _is_property_address(text: str, entity_text: str, context_window: int = 100) -> bool:
    """
    Check if detected location is a property address (not PII).
    
    Args:
        text: Full document text
        entityText: Detected entity text
        contextWindow: Characters before/after to check for context
        
    Returns:
        True if this appears to be a property address
    """
    exceptions = _load_cre_exceptions()
    patterns = cast(List[str], exceptions.get("property_address_patterns", []))
    
    # Find entity position in text
    entity_pos = text.find(entity_text)
    if entity_pos == -1:
        return False
    
    # Extract context around entity
    start = max(0, entity_pos - context_window)
    end = min(len(text), entity_pos + len(entity_text) + context_window)
    context = text[start:end].lower()
    
    # Check if any property address indicator is nearby
    for pattern in patterns:
        if pattern.lower() in context:
            return True
    
    return False


def _is_company_name(text: str, entity_text: str, context_window: int = 100) -> bool:
    """
    Check if detected entity is a company name (not PII).
    
    Args:
        text: Full document text
        entityText: Detected entity text
        contextWindow: Characters before/after to check for context
        
    Returns:
        True if this appears to be a company name
    """
    exceptions = _load_cre_exceptions()
    patterns = cast(List[str], exceptions.get("company_name_patterns", []))
    
    # Find entity position in text
    entity_pos = text.find(entity_text)
    if entity_pos == -1:
        return False
    
    # Extract context around entity
    start = max(0, entity_pos - context_window)
    end = min(len(text), entity_pos + len(entity_text) + context_window)
    context = text[start:end].lower()
    
    # Check if any company name indicator is nearby
    for pattern in patterns:
        if pattern.lower() in context:
            return True
    
    # Check for business entity suffixes
    entity_lower = entity_text.lower()
    business_suffixes = ["llc", "inc", "corp", "ltd", "lp", "llp", "reit"]
    for suffix in business_suffixes:
        if suffix in entity_lower:
            return True
    
    return False


def _is_business_contact(
    text: str,
    entity_text: str,
    entity_type: str,
    context_window: int = 150,
) -> bool:
    """
    Check if detected contact info is business-related (not PII).
    
    Args:
        text: Full document text
        entityText: Detected entity text
        entityType: Type of entity (EMAIL_ADDRESS, PHONE_NUMBER)
        contextWindow: Characters before/after to check for context
        
    Returns:
        True if this appears to be a business contact
    """
    if entity_type not in ["EMAIL_ADDRESS", "PHONE_NUMBER"]:
        return False
    
    exceptions = _load_cre_exceptions()
    business_context = cast(
        dict[str, List[str]],
        exceptions.get("business_contact_context", {}),
    )
    indicators = business_context.get("business_indicators", [])
    business_domains = business_context.get("business_email_domains", [])
    
    # Check email domain for business domains
    if entity_type == "EMAIL_ADDRESS" and "@" in entity_text:
        domain = entity_text.split("@")[-1].lower()
        if domain in business_domains:
            return True
    
    # Find entity position in text
    entity_pos = text.find(entity_text)
    if entity_pos == -1:
        return False
    
    # Extract context around entity
    start = max(0, entity_pos - context_window)
    end = min(len(text), entity_pos + len(entity_text) + context_window)
    context = text[start:end].lower()
    
    # Check if any business indicator is nearby
    for indicator in indicators:
        if indicator.lower() in context:
            return True
    
    return False


def detect_pii(
    text: str,
    language: str = "en",
    entities: Optional[List[str]] = None,
) -> List[RecognizerResult]:
    """
    Detect PII in text with CRE-specific exceptions.
    
    Args:
        text: Text to analyze
        language: Language code (default: 'en')
        entities: Specific entity types to detect (None = all)
        
    Returns:
        List of RecognizerResult objects for detected PII (excluding CRE exceptions)
    """
    if not text or not text.strip():
        return []
    
    # Load PII entity types from config
    try:
        with open(_CONFIG_PATH, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
            default_entities = config.get("pii_entities", None)
    except Exception:
        default_entities = None
    
    # Use provided entities or config default
    entities_to_detect = entities or default_entities
    
    # Initialize analyzer
    analyzer = AnalyzerEngine()
    
    # Detect all PII
    results = analyzer.analyze(
        text=text,
        language=language,
        entities=entities_to_detect,
    )
    
    # Filter out CRE exceptions
    filtered_results = []
    for result in results:
        try:
            entity_text = text[result.start : result.end]
            entity_type = result.entity_type
            
            # Skip property addresses
            if entity_type == "LOCATION" and _is_property_address(text, entity_text):
                logger.debug(
                    "Skipping property address (CRE exception)",
                    extra={"entity_type": entity_type},
                )
                continue
            
            # Skip company names (for PERSON entities)
            if entity_type == "PERSON" and _is_company_name(text, entity_text):
                logger.debug(
                    "Skipping company name (CRE exception)",
                    extra={"entity_type": entity_type},
                )
                continue
            
            # Skip business contacts
            if _is_business_contact(text, entity_text, entity_type):
                logger.debug(
                    "Skipping business contact (CRE exception)",
                    extra={"entity_type": entity_type},
                )
                continue
            
            # Keep this PII detection
            filtered_results.append(result)
        except Exception as e:
            # Log error but continue processing other results
            logger.warning(
                "Error processing PII detection result",
                extra={"error": str(e), "entity_type": result.entity_type},
            )
            # Include result if we can't verify it's an exception
            filtered_results.append(result)
    
    return filtered_results
