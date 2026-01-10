"""Learning event emission helpers for ML training workflows."""
from __future__ import annotations

import logging
from typing import Any, Dict

from supabase import Client

logger = logging.getLogger(__name__)


def emit_field_override_event(
    supabase: Client,
    event: Dict[str, Any],
) -> None:
    """
    Emit a field override event for ML training.

    Args:
        supabase: Supabase client with user JWT
        event: Event payload for learning pipeline
    """
    try:
        result = supabase.table("learning_events").insert(event).execute()
        if not result.data:
            raise ValueError("Learning event insert returned no data")
    except Exception as exc:
        logger.error(
            "Failed to emit learning event",
            extra={
                "event_type": event.get("event_type"),
                "field_name": event.get("field_name"),
                "error": str(exc),
            },
            exc_info=True,
        )
