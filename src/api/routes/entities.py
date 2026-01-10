"""Entity resolution routes."""
import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field

from src.audit.logger import AuditLogger
from src.auth.decorators import require_permission
from src.auth.models import AuthContext
from src.dependencies import get_audit_logger, get_supabase_client
from src.entities.resolution import merge_entities
from src.exceptions import NotFoundError
from supabase import Client

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/v1/entities",
    tags=["entities"],
)


class EntityMergeRequest(BaseModel):
    """Request payload for entity merge."""

    merge_into_id: UUID = Field(..., description="Entity ID to merge into")


class EntityMergeResponse(BaseModel):
    """Response payload for entity merge."""

    merged_entity_id: UUID
    documents_updated: int


@router.post(
    "/{entity_id}/merge",
    response_model=EntityMergeResponse,
    status_code=status.HTTP_200_OK,
    summary="Merge two entities",
)
async def merge_entity(
    entity_id: UUID,
    request: Request,
    payload: EntityMergeRequest,
    auth: AuthContext = Depends(require_permission("entities:merge")),
    supabase: Client = Depends(get_supabase_client),
    audit_logger: AuditLogger = Depends(get_audit_logger),
) -> EntityMergeResponse:
    """Merge an entity into another entity."""
    request_id = getattr(request.state, "request_id", "unknown")
    tenant_id = auth.tenant_id

    if entity_id == payload.merge_into_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "INVALID_MERGE",
                "message": "merge_into_id must be different from entity_id",
            },
        )

    try:
        result = await merge_entities(
            supabase=supabase,
            tenant_id=tenant_id,
            source_entity_id=entity_id,
            target_entity_id=payload.merge_into_id,
            reviewed_by=auth.user_id,
            audit_logger=audit_logger,
        )
    except NotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": exc.code,
                "message": exc.message,
            },
        ) from exc
    except Exception as exc:
        logger.error(
            "Entity merge failed",
            extra={
                "request_id": request_id,
                "tenant_id": str(tenant_id),
                "entity_id": str(entity_id),
                "merge_into_id": str(payload.merge_into_id),
                "error": str(exc),
                "error_type": type(exc).__name__,
            },
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "code": "MERGE_FAILED",
                "message": "Failed to merge entities",
            },
        ) from exc

    return EntityMergeResponse(
        merged_entity_id=result.merged_entity_id,
        documents_updated=result.documents_updated,
    )
