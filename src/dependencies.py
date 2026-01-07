"""FastAPI dependencies for tenant context."""
import logging
from typing import Optional
from fastapi import Request, HTTPException, status
from sqlalchemy.engine import Engine

from src.middleware.auth import get_tenant_id_from_request

logger = logging.getLogger(__name__)


def get_tenant_db(request: Request) -> Engine:
    """FastAPI dependency to get tenant database connection from request state.
    
    This dependency should be used in routes that need tenant database access.
    The middleware must have already resolved the tenant context.
    
    Args:
        request: FastAPI request object.
    
    Returns:
        SQLAlchemy engine for tenant database.
    
    Raises:
        HTTPException: If tenant context not found in request state.
    """
    db = getattr(request.state, "db", None)
    
    if not db:
        logger.warning(
            f"Tenant database not found in request state: path={request.url.path}"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Tenant context not available"
        )
    
    return db


def get_tenant_id(request: Request) -> str:
    """FastAPI dependency to get tenant ID from request state.
    
    Args:
        request: FastAPI request object.
    
    Returns:
        Tenant ID string.
    
    Raises:
        HTTPException: If tenant ID not found in request state.
    """
    tenant_id = getattr(request.state, "tenant_id", None)
    
    if not tenant_id:
        logger.warning(
            f"Tenant ID not found in request state: path={request.url.path}"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Tenant context not available"
        )
    
    return tenant_id
