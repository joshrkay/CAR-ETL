"""Service for handling extraction field overrides."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional, Dict, cast
from uuid import UUID

from supabase import Client

from src.learning.events import emit_field_override_event

logger = logging.getLogger(__name__)


class FieldOverrideNotFoundError(Exception):
    """Raised when an extraction field is not found for an override request."""


@dataclass(frozen=True)
class FieldOverrideResult:
    field_id: str
    old_value: Any
    new_value: Any
    is_override: bool
    overridden_by: str
    overridden_at: str
    field_name: str
    document_type: Optional[str]
    extraction_source: Optional[str]
    original_confidence: Optional[float]


class FieldOverrideService:
    """Service layer for extraction field overrides."""

    def __init__(self, supabase_client: Client):
        self.client = supabase_client

    @staticmethod
    def _display_value(value: Any) -> Any:
        if isinstance(value, dict):
            return value.get("value", value)
        return value

    @staticmethod
    def _updated_field_value(existing_value: Any, new_value: str) -> Any:
        if isinstance(existing_value, dict):
            updated = dict(existing_value)
            updated["value"] = new_value
            return updated
        return new_value

    def override_field(
        self,
        extraction_id: UUID,
        field_id: UUID,
        new_value: str,
        user_id: UUID,
        notes: Optional[str] = None,
    ) -> FieldOverrideResult:
        """
        Override an extraction field value and emit learning event.

        Args:
            extraction_id: Extraction UUID
            field_id: Extraction field UUID
            new_value: Corrected field value
            user_id: User UUID performing override
            notes: Optional notes for override (not persisted)
        """
        field_result = (
            self.client.table("extraction_fields")
            .select("id, extraction_id, field_name, field_value, confidence, source")
            .eq("id", str(field_id))
            .eq("extraction_id", str(extraction_id))
            .maybe_single()
            .execute()
        )

        if not field_result.data:
            raise FieldOverrideNotFoundError("Extraction field not found")

        field_data = cast(Dict[str, Any], field_result.data)
        existing_value = field_data.get("field_value")
        old_display_value = self._display_value(existing_value)
        updated_field_value = self._updated_field_value(existing_value, new_value)

        overridden_at = datetime.now(timezone.utc).isoformat()

        update_payload = {
            "field_value": updated_field_value,
            "is_override": True,
            "overridden_by": str(user_id),
            "overridden_at": overridden_at,
        }

        update_result = (
            self.client.table("extraction_fields")
            .update(update_payload)
            .eq("id", str(field_id))
            .execute()
        )

        if not update_result.data:
            raise ValueError("Failed to update extraction field")

        extraction_result = (
            self.client.table("extractions")
            .select("document_type, parser_used")
            .eq("id", str(extraction_id))
            .maybe_single()
            .execute()
        )
        extraction_data = cast(Optional[Dict[str, Any]], extraction_result.data)

        event_payload = {
            "event_type": "field_override",
            "document_type": (extraction_data or {}).get("document_type") or "unknown",
            "field_name": field_data.get("field_name"),
            "original_value": old_display_value,
            "corrected_value": new_value,
            "extraction_source": (extraction_data or {}).get("parser_used") or field_data.get("source"),
            "original_confidence": field_data.get("confidence"),
            "notes": notes,
        }

        emit_field_override_event(self.client, event_payload)

        logger.info(
            "Extraction field overridden",
            extra={
                "extraction_id": str(extraction_id),
                "field_id": str(field_id),
                "user_id": str(user_id),
            },
        )

        return FieldOverrideResult(
            field_id=str(field_id),
            old_value=old_display_value,
            new_value=self._display_value(updated_field_value),
            is_override=True,
            overridden_by=str(user_id),
            overridden_at=overridden_at,
            field_name=field_data.get("field_name"),
            document_type=(extraction_data or {}).get("document_type"),
            extraction_source=(extraction_data or {}).get("parser_used") or field_data.get("source"),
            original_confidence=field_data.get("confidence"),
        )
