"""Example routes demonstrating tenant context usage."""
from fastapi import APIRouter, Depends, Request
from sqlalchemy.engine import Engine
from sqlalchemy import text

from src.dependencies import get_tenant_db, get_tenant_id
from src.auth.decorators import requires_permission
from src.auth.dependencies import get_current_user_claims
from src.auth.jwt_validator import JWTClaims

router = APIRouter(prefix="/api/v1/example", tags=["example"])


@router.get("/tenant-info")
@requires_permission("view_tenant_settings")
async def get_tenant_info(
    tenant_id: str = Depends(get_tenant_id),
    db: Engine = Depends(get_tenant_db),
    claims: JWTClaims = Depends(get_current_user_claims)
):
    """Get tenant information using tenant context.
    
    This endpoint demonstrates:
    - Accessing tenant_id from request state
    - Using tenant database connection
    """
    # Example: Query tenant database
    with db.connect() as conn:
        result = conn.execute(text("SELECT current_database()"))
        database_name = result.scalar()
    
    return {
        "tenant_id": tenant_id,
        "database_name": database_name,
        "message": "Tenant context is working"
    }


@router.get("/tenant-data")
@requires_permission("view_document")
async def get_tenant_data(
    tenant_id: str = Depends(get_tenant_id),
    db: Engine = Depends(get_tenant_db),
    claims: JWTClaims = Depends(get_current_user_claims)
):
    """Get tenant-specific data.
    
    This endpoint uses the tenant database connection to query
    tenant-specific data. The middleware ensures the correct
    database is used based on the JWT tenant_id claim.
    """
    # Example: Query tenant-specific table
    with db.connect() as conn:
        # This would query tenant-specific tables
        # Example: SELECT * FROM tenant_data WHERE tenant_id = ...
        result = conn.execute(text("SELECT 1 as data"))
        data = result.scalar()
    
    return {
        "tenant_id": tenant_id,
        "data": data
    }
