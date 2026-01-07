"""Example routes demonstrating audit logging integration."""
from fastapi import APIRouter, Request, Depends
from typing import Optional

from src.audit.service import audit_log
from src.dependencies import get_tenant_id
from src.auth.dependencies import get_current_user_claims
from src.auth.jwt_validator import JWTClaims

router = APIRouter(prefix="/api/v1/audit-examples", tags=["audit-examples"])


@router.post("/document-upload")
async def example_document_upload(
    request: Request,
    document_id: str,
    tenant_id: str = Depends(get_tenant_id),
    claims: JWTClaims = Depends(get_current_user_claims)
):
    """Example: Document upload with audit logging.
    
    This demonstrates how to log audit events in your routes.
    The audit log is written asynchronously and won't block the request.
    """
    
    # Your business logic here
    # ... upload document ...
    
    # Log the audit event
    await audit_log(
        user_id=claims.user_id,
        tenant_id=tenant_id,
        action_type="document.upload",
        resource_id=document_id,
        request=request,
        additional_metadata={
            "document_size": request.headers.get("content-length"),
            "content_type": request.headers.get("content-type")
        }
    )
    
    return {
        "status": "success",
        "document_id": document_id,
        "message": "Document uploaded and audit logged"
    }


@router.delete("/document/{document_id}")
async def example_document_delete(
    document_id: str,
    request: Request,
    tenant_id: str = Depends(get_tenant_id),
    claims: JWTClaims = Depends(get_current_user_claims)
):
    """Example: Document deletion with audit logging."""
    
    # Your business logic here
    # ... delete document ...
    
    # Log the audit event
    await audit_log(
        user_id=claims.user_id,
        tenant_id=tenant_id,
        action_type="document.delete",
        resource_id=document_id,
        request=request
    )
    
    return {
        "status": "success",
        "document_id": document_id,
        "message": "Document deleted and audit logged"
    }


@router.get("/user-action")
async def example_user_action(
    action: str,
    request: Request,
    tenant_id: str = Depends(get_tenant_id),
    claims: JWTClaims = Depends(get_current_user_claims)
):
    """Example: Generic user action with audit logging."""
    
    # Log the audit event
    await audit_log(
        user_id=claims.user_id,
        tenant_id=tenant_id,
        action_type=f"user.action.{action}",
        request=request,
        additional_metadata={
            "action": action,
            "query_params": dict(request.query_params)
        }
    )
    
    return {
        "status": "success",
        "action": action,
        "message": "Action logged"
    }
