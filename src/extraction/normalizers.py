"""
Value Normalizers - Understanding Plane

Normalizes extracted field values to standard formats.
Handles dates, currency, enums, and other data types.
"""

import re
import logging
from typing import Any, Optional, List
from datetime import datetime

logger = logging.getLogger(__name__)


def normalize_date(value: Any) -> Optional[str]:
    """
    Normalize date value to YYYY-MM-DD format.
    
    Args:
        value: Date value (string, datetime, or None)
        
    Returns:
        Normalized date string (YYYY-MM-DD) or None if invalid
    """
    if value is None:
        return None
    
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d")
    
    if not isinstance(value, str):
        value = str(value)
    
    value = value.strip()
    if not value or value.lower() in ["null", "none", "n/a", ""]:
        return None
    
    # Try common date formats
    date_patterns = [
        (r"(\d{4})-(\d{2})-(\d{2})", "%Y-%m-%d"),  # YYYY-MM-DD
        (r"(\d{2})/(\d{2})/(\d{4})", "%m/%d/%Y"),  # MM/DD/YYYY
        (r"(\d{2})-(\d{2})-(\d{4})", "%m-%d-%Y"),  # MM-DD-YYYY
        (r"(\d{1,2})/(\d{1,2})/(\d{4})", "%m/%d/%Y"),  # M/D/YYYY
        (r"(\d{4})/(\d{2})/(\d{2})", "%Y/%m/%d"),  # YYYY/MM/DD
    ]
    
    for pattern, fmt in date_patterns:
        match = re.match(pattern, value)
        if match:
            try:
                # Reconstruct date string for parsing
                if fmt == "%Y-%m-%d":
                    date_str = value
                elif fmt == "%m/%d/%Y":
                    parts = match.groups()
                    date_str = f"{parts[2]}-{parts[0]}-{parts[1]}"
                elif fmt == "%m-%d-%Y":
                    parts = match.groups()
                    date_str = f"{parts[2]}-{parts[0]}-{parts[1]}"
                elif fmt == "%Y/%m/%d":
                    parts = match.groups()
                    date_str = f"{parts[0]}-{parts[1]}-{parts[2]}"
                else:
                    continue
                
                parsed = datetime.strptime(date_str, "%Y-%m-%d")
                return parsed.strftime("%Y-%m-%d")
            except (ValueError, IndexError):
                continue
    
    logger.warning(
        "Failed to normalize date",
        extra={"value": value[:50] if isinstance(value, str) else str(value)}
    )
    return None


def normalize_currency(value: Any) -> Optional[float]:
    """
    Normalize currency value to float.
    
    Removes $, commas, and other formatting.
    
    Args:
        value: Currency value (string, number, or None)
        
    Returns:
        Normalized float value or None if invalid
    """
    if value is None:
        return None
    
    if isinstance(value, (int, float)):
        return float(value)
    
    if not isinstance(value, str):
        value = str(value)
    
    value = value.strip()
    if not value or value.lower() in ["null", "none", "n/a", ""]:
        return None
    
    # Remove currency symbols, commas, spaces
    cleaned = re.sub(r"[$,\s]", "", value)
    
    # Handle negative values in parentheses
    if cleaned.startswith("(") and cleaned.endswith(")"):
        cleaned = "-" + cleaned[1:-1]
    
    try:
        return float(cleaned)
    except ValueError:
        logger.warning(
            "Failed to normalize currency",
            extra={"value": value[:50]}
        )
        return None


def normalize_integer(value: Any) -> Optional[int]:
    """
    Normalize integer value.
    
    Args:
        value: Integer value (string, number, or None)
        
    Returns:
        Normalized integer or None if invalid
    """
    if value is None:
        return None
    
    if isinstance(value, int):
        return value
    
    if isinstance(value, float):
        if value.is_integer():
            return int(value)
        return None
    
    if not isinstance(value, str):
        value = str(value)
    
    value = value.strip()
    if not value or value.lower() in ["null", "none", "n/a", ""]:
        return None
    
    # Remove commas and spaces
    cleaned = re.sub(r"[,\s]", "", value)
    
    try:
        return int(float(cleaned))
    except ValueError:
        logger.warning(
            "Failed to normalize integer",
            extra={"value": value[:50]}
        )
        return None


def _parse_numeric_string(value: str) -> Optional[float]:
    """
    Parse a numeric string that may contain percent signs or commas.
    """
    cleaned = value.strip()
    if not cleaned:
        return None
    cleaned = cleaned.replace(",", "")
    cleaned = cleaned.replace("%", "")
    try:
        return float(cleaned)
    except ValueError:
        return None


def normalize_percent(value: Any) -> Optional[float]:
    """
    Normalize percent to float in 0-1 range.
    Accepts values like "7%", "0.07", 7, 0.07.
    """
    if value is None:
        return None

    if isinstance(value, (int, float)):
        numeric = float(value)
    else:
        if not isinstance(value, str):
            value = str(value)
        parsed = _parse_numeric_string(value)
        if parsed is None:
            logger.warning(
                "Failed to normalize percent",
                extra={"value": str(value)[:50]}
            )
            return None
        numeric = parsed

    # If expressed as whole number (e.g., 7), convert to 0.07
    if numeric > 1:
        numeric = numeric / 100.0
    # Clamp negative or overly large values
    if numeric < 0 or numeric > 5:  # 500% is definitely invalid here
        logger.warning(
            "Percent value out of expected range",
            extra={"value": numeric}
        )
        return None
    return numeric


def normalize_list_of_strings(value: Any) -> Optional[List[str]]:
    """
    Normalize list of strings from various formats (list, newline, comma-separated).
    """
    if value is None:
        return None

    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]

    if not isinstance(value, str):
        value = str(value)

    items = [item.strip("-• ").strip() for item in re.split(r"[\n;]", value) if item.strip()]
    return [item for item in items if item]


def normalize_enum(value: Any, allowed_values: List[str]) -> Optional[str]:
    """
    Normalize enum value to match allowed values.
    
    Args:
        value: Enum value (string or None)
        allowed_values: List of allowed enum values
        
    Returns:
        Normalized enum value or None if invalid
    """
    if value is None:
        return None
    
    if not isinstance(value, str):
        value = str(value)
    
    value = value.strip().lower()
    if not value:
        return None
    
    # Exact match (case-insensitive)
    for allowed in allowed_values:
        if value == allowed.lower():
            return allowed
    
    # Partial match (e.g., "monthly" matches "monthly")
    for allowed in allowed_values:
        if allowed.lower() in value or value in allowed.lower():
            return allowed
    
    logger.warning(
        "Enum value not in allowed values",
        extra={
            "value": value,
            "allowed_values": allowed_values
        }
    )
    return None


def normalize_boolean(value: Any) -> Optional[bool]:
    """
    Normalize boolean value.
    
    Args:
        value: Boolean value (string, bool, or None)
        
    Returns:
        Normalized boolean or None if invalid
    """
    if value is None:
        return None
    
    if isinstance(value, bool):
        return value
    
    if isinstance(value, (int, float)):
        return bool(value)
    
    if not isinstance(value, str):
        value = str(value)
    
    value = value.strip().lower()
    if not value:
        return None
    
    # Common boolean representations
    true_values = ["true", "yes", "y", "1", "on", "enabled", "required"]
    false_values = ["false", "no", "n", "0", "off", "disabled", "not required"]
    
    if value in true_values:
        return True
    elif value in false_values:
        return False
    
    logger.warning(
        "Failed to normalize boolean",
        extra={"value": value[:50]}
    )
    return None


def normalize_field_value(
    value: Any,
    field_type: str,
    enum_values: Optional[List[str]] = None
) -> Any:
    """
    Normalize field value based on type.
    
    Args:
        value: Raw field value
        field_type: Field type (string, date, currency, integer, enum, float, boolean)
        enum_values: Allowed values for enum type
        
    Returns:
        Normalized value
    """
    if value is None:
        return None
    
    if field_type == "date":
        return normalize_date(value)
    elif field_type == "currency":
        return normalize_currency(value)
    elif field_type == "integer":
        return normalize_integer(value)
    elif field_type == "enum":
        if enum_values:
            return normalize_enum(value, enum_values)
        return str(value).strip() if value else None
    elif field_type == "float":
        try:
            return float(value)
        except (ValueError, TypeError):
            return None
    elif field_type == "percent":
        return normalize_percent(value)
    elif field_type in ("list[string]", "list_string", "list"):
        return normalize_list_of_strings(value)
    elif field_type == "boolean":
        return normalize_boolean(value)
    else:  # string or unknown
        if isinstance(value, str):
            return value.strip()
        return str(value) if value else None
