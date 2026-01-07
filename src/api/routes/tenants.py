"""Tenant provisioning API routes."""
import logging
from typing import Dict, Any
from fastapi import APIRouter, HTTPException, Depends, status, Request
from pydantic import BaseModel, Field, field_validator
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from src.services.tenant_provisioning import get_tenant_provisioning_service, TenantProvisioningService
from src.auth.dependencies import require_role
from src.auth.jwt_validator import JWTClaims

logger = logging.getLogger(__name__)

# Rate limiter: 10 creations per minute
limiter = Limiter(key_func=get_remote_address)
router = APIRouter(prefix="/api/v1/tenants", tags=["tenants"])


class TenantCreateRequest(BaseModel):
    """Request model for tenant creation."""
    
    name: str = Field(..., min_length=1, max_length=255, description="Tenant name")
    environment: str = Field(..., description="Tenant environment")
    
    @field_validator("environment")
    @classmethod
    def validate_environment(cls, v: str) -> str:
        """Validate environment value."""
        allowed = ["development", "staging", "production"]
        if v not in allowed:
            raise ValueError(f"Environment must be one of: {', '.join(allowed)}")
        return v
    
    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        """Validate tenant name."""
        if not v or not v.strip():
            raise ValueError("Tenant name cannot be empty")
        # Sanitize name (alphanumeric, underscore, hyphen)
        sanitized = "".join(c for c in v if c.isalnum() or c in ["_", "-"])
        if sanitized != v:
            raise ValueError("Tenant name can only contain alphanumeric characters, underscores, and hyphens")
        return v.strip()


class TenantCreateResponse(BaseModel):
    """Response model for tenant creation."""
    
    tenant_id: str = Field(..., description="Unique tenant identifier")
    name: str = Field(..., description="Tenant name")
    status: str = Field(..., description="Tenant status")


@router.post("", status_code=status.HTTP_201_CREATED, response_model=TenantCreateResponse)
@limiter.limit("10/minute")
async def create_tenant(
    request: Request,
    tenant_request: TenantCreateRequest,
    claims: JWTClaims = Depends(require_role("admin")),
    provisioning_service: TenantProvisioningService = Depends(get_tenant_provisioning_service)
) -> TenantCreateResponse:
    """Create a new tenant with isolated database.
    
    This endpoint:
    - Creates a PostgreSQL database named car_{tenant_id}
    - Encrypts the connection string with AES-256-GCM
    - Verifies database connectivity
    - Creates tenant record in control plane
    - Returns 201 Created only after full provisioning
    
    If any step fails, all changes are rolled back atomically.
    
    Args:
        request: Tenant creation request with name and environment.
        provisioning_service: Tenant provisioning service instance.
    
    Returns:
        Tenant creation response with tenant_id, name, and status.
    
    Raises:
        HTTPException: If provisioning fails (400 for validation, 500 for server errors).
    """
    try:
        logger.info(f"Creating tenant: name={tenant_request.name}, environment={tenant_request.environment}")
        
        result = provisioning_service.provision_tenant(
            name=tenant_request.name,
            environment=tenant_request.environment
        )
        
        logger.info(f"Tenant created successfully: {result['tenant_id']}")
        
        # Return 201 Created only after database is fully provisioned and verified
        return TenantCreateResponse(
            tenant_id=result["tenant_id"],
            name=result["name"],
            status=result["status"]
        )
    
    except ValueError as e:
        logger.warning(f"Validation error creating tenant: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    
    except RuntimeError as e:
        logger.error(f"Provisioning error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Tenant provisioning failed: {str(e)}"
        )
    
    except Exception as e:
        logger.error(f"Unexpected error creating tenant: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred during tenant provisioning"
        )
