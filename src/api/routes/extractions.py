"""Extraction routes for field overrides."""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from supabase import Client

from src.auth.decorators import require_permission
from src.auth.models import AuthContext
from src.dependencies import get_supabase_client
from src.services.field_override import FieldOverrideService, FieldOverrideNotFoundError

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/v1/extractions",
    tags=["extractions"],
)


class FieldOverrideRequest(BaseModel):
    """Request payload for overriding an extraction field."""

    value: str = Field(..., description="Corrected field value")
    notes: Optional[str] = Field(None, description="Notes about the correction")


class FieldOverrideResponse(BaseModel):
    """Response payload for an extraction field override."""

    field_id: str
    old_value: Optional[Any]
    new_value: Optional[Any]
    is_override: bool
    overridden_by: str
    overridden_at: datetime


@router.patch(
    "/{extraction_id}/fields/{field_id}",
    response_model=FieldOverrideResponse,
    summary="Override an extraction field value",
    status_code=status.HTTP_200_OK,
)
def override_extraction_field(
    extraction_id: UUID,
    field_id: UUID,
    payload: FieldOverrideRequest,
    request: Request,
    auth: AuthContext = Depends(require_permission("extractions:override")),
    supabase: Client = Depends(get_supabase_client),
) -> FieldOverrideResponse:
    """
    Override an extraction field value and emit a learning event.
    """
    request_id = getattr(request.state, "request_id", "unknown")
    service = FieldOverrideService(supabase)

    logger.info(
        "Field override requested",
        extra={
            "request_id": request_id,
            "extraction_id": str(extraction_id),
            "field_id": str(field_id),
            "user_id": str(auth.user_id),
        },
    )

    try:
        result = service.override_field(
            extraction_id=extraction_id,
            field_id=field_id,
            new_value=payload.value,
            user_id=auth.user_id,
            notes=payload.notes,
        )
    except FieldOverrideNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "FIELD_NOT_FOUND",
                "message": "Extraction field not found for override",
            },
        ) from exc

    return FieldOverrideResponse(
        field_id=result.field_id,
        old_value=result.old_value,
        new_value=result.new_value,
        is_override=result.is_override,
        overridden_by=result.overridden_by,
        overridden_at=datetime.fromisoformat(result.overridden_at),
    )
