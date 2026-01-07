"""Example FastAPI routes demonstrating JWT claims usage."""
from fastapi import APIRouter, Depends, HTTPException, status
from typing import List

from src.auth.decorators import requires_role, requires_any_role, requires_permission
from src.auth.dependencies import get_current_user_claims
from src.auth.jwt_validator import JWTClaims

router = APIRouter(prefix="/api/v1/example", tags=["example"])


@router.get("/me")
@requires_permission("view_tenant_settings")
async def get_current_user(claims: JWTClaims = Depends(get_current_user_claims)):
    """Get current user information from JWT claims.
    
    This endpoint demonstrates basic JWT claim extraction.
    """
    return {
        "user_id": claims.user_id,
        "email": claims.email,
        "tenant_id": claims.tenant_id,
        "roles": claims.roles
    }


@router.get("/admin-only")
@requires_role("Admin")
async def admin_endpoint(claims: JWTClaims = Depends(get_current_user_claims)):
    """Admin-only endpoint.
    
    This endpoint requires the 'admin' role.
    """
    return {
        "message": "This is an admin-only endpoint",
        "user_id": claims.user_id,
        "tenant_id": claims.tenant_id
    }


@router.get("/tenant-data")
@requires_permission("view_document")
async def get_tenant_data(claims: JWTClaims = Depends(get_current_user_claims)):
    """Get tenant-specific data.
    
    This endpoint uses tenant_id from JWT claims to scope data access.
    """
    if not claims.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User missing tenant_id claim"
        )
    
    # In real implementation, use claims.tenant_id to query tenant-specific data
    return {
        "tenant_id": claims.tenant_id,
        "message": f"Data for tenant {claims.tenant_id}",
        "user_roles": claims.roles
    }


@router.get("/moderator-or-admin")
@requires_any_role(["Admin", "Analyst"])
async def moderator_endpoint(
    claims: JWTClaims = Depends(get_current_user_claims)
):
    """Endpoint accessible to admin or moderator roles.
    
    This endpoint requires either 'admin' or 'moderator' role.
    """
    return {
        "message": "This endpoint is accessible to admins and moderators",
        "user_id": claims.user_id,
        "roles": claims.roles
    }
