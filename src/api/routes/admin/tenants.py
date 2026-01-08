"""Admin endpoints for tenant provisioning."""
from fastapi import APIRouter, Depends, HTTPException, status
from typing import Annotated
from uuid import UUID
from supabase import Client

from src.auth.models import AuthContext
from src.dependencies import get_current_user, require_role, get_supabase_client
from src.services.tenant_provisioning import TenantProvisioningService, ProvisioningError
from pydantic import BaseModel, Field, EmailStr
from typing import Literal
from datetime import datetime

router = APIRouter(prefix="/api/v1/admin/tenants", tags=["admin", "tenants"])


class TenantCreate(BaseModel):
    """Request model for creating a tenant."""
    
    name: str = Field(..., min_length=2, max_length=100)
    slug: str = Field(
        ...,
        pattern=r'^[a-z0-9][a-z0-9-]*[a-z0-9]$',
        max_length=50,
        description="URL-safe slug (lowercase alphanumeric with hyphens)"
    )
    admin_email: EmailStr
    environment: Literal['prod', 'staging', 'dev'] = 'prod'


class TenantResponse(BaseModel):
    """Response model for tenant creation."""
    
    tenant_id: UUID
    name: str
    slug: str
    status: str
    storage_bucket: str
    admin_invite_sent: bool
    created_at: datetime


@router.post("", response_model=TenantResponse, status_code=status.HTTP_201_CREATED)
async def create_tenant(
    tenant_data: TenantCreate,
    supabase: Annotated[Client, Depends(get_supabase_client)],
    auth: Annotated[AuthContext, Depends(require_role("Admin"))],
):
    """
    Provision a new tenant with storage bucket and admin user.
    
    Requires Admin role. Uses service_role to create tenant.
    
    Steps:
    1. Validate slug uniqueness
    2. Create tenant row
    3. Create storage bucket
    4. Setup bucket policies
    5. Invite admin user
    6. Link admin to tenant
    7. Return tenant details
    
    On failure, automatically rolls back all created resources.
    """
    try:
        provisioning_service = TenantProvisioningService(supabase)
        
        result = provisioning_service.provision_tenant(
            name=tenant_data.name,
            slug=tenant_data.slug,
            admin_email=tenant_data.admin_email,
            environment=tenant_data.environment,
        )
        
        return TenantResponse(**result)
        
    except ProvisioningError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "PROVISIONING_ERROR",
                "message": str(e),
            },
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "code": "INTERNAL_ERROR",
                "message": f"Failed to provision tenant: {str(e)}",
            },
        )
